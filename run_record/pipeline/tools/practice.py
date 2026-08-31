#!/usr/bin/env python
"""Stage 3 of the AGENTS.md loop, end to end, with ONE command and no judgement calls.

    # 1. plan only - assembles EVERY payload (probes included), makes NO call, prints the bill
    /opt/kernel/venv/bin/python tools/practice.py --model <model-id>

    # 2. spend, after the operator has approved the number printed by step 1
    /opt/kernel/venv/bin/python tools/practice.py --model <model-id> --execute --approved

Stage 3 is one of only two stages that spend budget (AGENTS.md), so the default of this script
is to spend nothing: it carves the tasks, assembles the recognition probes and the prediction
prompts through the real `ssb.predict` path, writes every payload to disk, and prints the exact
token bill. `--execute` additionally runs `ssb.predict.command()` - the frozen argv, verbatim -
and requires `--approved` on the same line.

What one `--execute` run does, in order:

  0. carve every task (`ssb.task.carve`) -> brief/ + sealed/ ; sealed/ is never read by anything
     that touches a prompt
  3a. RECOGNITION PROBE (OPEN item 3), BEFORE any prediction: one call per task asking the
     predictor to name the study from the brief alone, graded by a regex list fixed in
     inputs/recognition_keys.json
  3b. PREDICTION: n independent draws per task through plan_prompts' whole/truncate/split policy,
      every call cached on ssb.predict.cache_key (prompt + model + every sampling parameter)
  3c. aggregate by median, score with ssb.task.score_task, leak_audit every transcript WITH its
      positive control, append one scoreboard row per task with stub=False
  3d. write stages/calibration/pairs.csv - the input stage 4 needs - and stages/practice/cost.json

Blinding is structural and unchanged: `--tools ""`, no filesystem, no session persistence, and
the argv comes from `ssb.predict.command()` which is the frozen line. This script never passes a
sealed path, a truth value or a dataset path into a prompt; the leak audit checks anyway.

Stages 4-9 are plain code and are driven by tools/dryrun.py's own sequence (or the RUNBOOK).
"""
import argparse, hashlib, json, os, re, shutil, subprocess, sys, time
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ssb  # noqa: E402
import length_variants  # noqa: E402
import prompt_variants  # noqa: E402  (the variant registry: length treatments + prompt/ablation)

RUN = Path(__file__).resolve().parents[1]
TASKS = ["voelkel2026", "goldwert2026", "vlasceanu2024", "bbprime2025", "voelkel2024"]
CACHE = RUN / "runs" / "_cache" / "completions"
REHEARSAL_CACHE = RUN / "runs" / "_cache" / "rehearsal"
KEYS = json.loads((RUN / "inputs" / "recognition_keys.json").read_text())

# An answer is ~19 tokens a row plus a header. This is the ONLY quantity in the bill that is an
# estimate rather than a measurement of an assembled payload; it is flagged as such in cost.json.
# Was 12 until run 20260815-practice-01 measured it: 204 cells -> 3915 output tokens (19.2/cell),
# 90 -> 1833 (20.4), 165 -> 2855 (17.3). 12 was a tiktoken-shaped guess of an Anthropic-tokenised
# answer, and it was low by the same ~1.6x as everything else here.
OUT_TOKENS_PER_CELL = 19
PROBE_OUT_TOKENS = 120

# --- what a call actually costs, measured, not assumed -------------------------------------------
# ssb.predict.n_tokens is tiktoken cl100k, which is a PROXY for Anthropic's tokenizer, and `claude -p`
# adds a per-call pass of its own over the same prompt. Both were invisible until 12 real calls were
# in runs/_cache/completions with their usage payloads (run 20260815-practice-01, model claude-opus-5):
#
#   tiktoken -> Anthropic context   1.574x  (n=12, range 1.513-1.598)
#   CLI's own haiku pass / context  0.732   (n=12, range 0.710-0.762)  -- billed, and real tokens
#
# so a payload of E tiktoken tokens is E * 1.574 * 1.732 = 2.73E tokens actually billed, before the
# answer. An estimate that ignores this is low by 2.6x, which is exactly the factor that tripped the
# budget guard mid-batch. These are ratios, so they stay valid if a payload changes size; re-measure
# them if the model or the CLI version changes (both are recorded in summary.json).
# SESSION 10 CORRECTION, measured by tools/billing_factors.py on the two tasks carved this
# session: this factor is not a constant, it is a CHARACTERS-PER-TOKEN ratio for the corpus in the
# prompt - `ssb.predict.n_tokens` has no tiktoken installed here and falls back to len/4. The
# climate briefs read 1.40-1.57 (2.5-2.9 chars/token); tappin2023 and hackenburg2025 read
# 1.206 (3.32), so their first batch came in at 0.77x its own estimate. The constant is left at
# the HIGHER value deliberately: an over-priced batch asks the operator for too much headroom, an
# under-priced one spends money nobody approved. Re-measure on the first batch of a new corpus.
TOKENIZER_FACTOR = 1.574          # len/4 (or tiktoken cl100k) -> Anthropic tokens
CLI_OVERHEAD_FACTOR = 0.732       # extra billed input per call, as a fraction of the context
BILLED_INPUT_FACTOR = TOKENIZER_FACTOR * (1.0 + CLI_OVERHEAD_FACTOR)
TOKENIZER_MEASURED_ON = {"run": "20260815-practice-01", "model": "claude-opus-5", "n_calls": 12,
                         "cli": "claude 2.1.220", "overhead_is": "a per-call haiku pass over the "
                         "same prompt, visible in payload.modelUsage"}


def billed_tokens(payload: dict) -> int:
    """Every token the provider charged for this ONE call, across every model the CLI used.
    This is a measurement of what came back, not an estimate of what was sent."""
    mu = (payload or {}).get("modelUsage") or {}
    n = 0
    for v in mu.values():
        n += (v.get("inputTokens", 0) + v.get("cacheReadInputTokens", 0)
              + v.get("cacheCreationInputTokens", 0) + v.get("outputTokens", 0))
    if n:
        return n
    u = (payload or {}).get("usage") or {}          # fallback: opus leg only
    return (u.get("input_tokens", 0) + u.get("cache_read_input_tokens", 0)
            + u.get("cache_creation_input_tokens", 0) + u.get("output_tokens", 0))

PROBE_SYSTEM = """You are answering a factual question about a research study. Answer ONLY in the
fixed format below, with no prose before or after it.

STUDY: <the published study's name, or UNKNOWN>
AUTHORS: <surnames, or UNKNOWN>
CONFIDENCE: <an integer 0-100>
RESULTS_KNOWN: <YES if you believe you already know this study's published results, otherwise NO>
"""

# OPEN 36 / standing finding 89: `CONFIDENCE` above has NO STATED REFERENT, so its values are not
# interpretable and this harness no longer quotes them (`tools/confidence_audit.py` measures what
# they are worth: they do not separate RECOGNISED from UNRECOGNISED). The field is LEFT IN the v1
# prompt on purpose - editing it changes `ssb.predict.cache_key` and turns every probe transcript on
# disk into a cache miss. V2 below is the defined replacement, adopted only by a session that is
# buying fresh probes anyway, via `--probe-version 2`, so the change is explicit and dated.
PROBE_SYSTEM_V2 = """You are answering a factual question about a research study. Answer ONLY in the
fixed format below, with no prose before or after it.

STUDY: <the published study's name, or UNKNOWN>
AUTHORS: <surnames, or UNKNOWN>
CONFIDENCE: <an integer 0-100: how confident you are that the STUDY line above is CORRECT. Answer 0
if the STUDY line is UNKNOWN.>
RESULTS_KNOWN: <YES if you believe you already know this study's published results, otherwise NO>
"""

PROBE_INSTRUCTION = """Below is the design of a randomised message experiment: its sample, its
outcome measures, and the full text of every arm.

Do you recognise it as a specific published study? Do not guess from the topic alone - answer
UNKNOWN unless you can name the study or its authors.

Answer in the fixed format. Do not predict any result.
"""


def probe_prompt(brief: dict, version: int = 1) -> tuple[str, str]:
    """The stage-3a payload, built from the SAME brief the predictor will see, so recognition is
    measured on the actual payload and not on a summary of it.

    `version=2` defines the CONFIDENCE field (OPEN 36). It is not the default: every probe result on
    disk was bought under v1, and switching the system prompt makes all of them cache misses."""
    _, user = ssb.predict.build_prompt(brief)
    body = user.rsplit("Return exactly", 1)[0].rstrip()      # drop the CSV instruction only
    return (PROBE_SYSTEM if version == 1 else PROBE_SYSTEM_V2), PROBE_INSTRUCTION + "\n" + body


def grade_probe(text: str, task: str, probe_version: int = 1) -> dict:
    """Deterministic grading: a regex list fixed BEFORE any call, plus the model's self-report.
    Both are recorded, so a disagreement between them is visible rather than resolved by taste.

    Only `identity_keys` are graded. `content_keys` are phrases the task's own content forces
    (voelkel2024's outcome battery IS its paper's title), so echoing one is not recall."""
    k = KEYS["tasks"][task]
    matched = [p for p in k["identity_keys"] if re.search(p, text, re.I)]
    content = [p for p in k.get("content_keys", []) if re.search(p, text, re.I)]
    m = re.search(r"RESULTS_KNOWN:\s*(YES|NO)", text, re.I)
    conf = re.search(r"CONFIDENCE:\s*(\d+)", text)
    study = re.search(r"STUDY:\s*(.+)", text)
    self_report = m.group(1).upper() if m else "UNPARSED"
    return {"task": task, "matched_identifiers": matched, "matched_content_keys": content,
            "self_report_results_known": self_report,
            "self_report_confidence": int(conf.group(1)) if conf else None,
            # OPEN 36: under v1 the field has no stated referent. It is recorded for provenance and
            # must not be quoted as a measurement; `tools/confidence_audit.py` shows it does not
            # separate the verdict and that one model line answered 90 and 4 to the same STUDY:
            # UNKNOWN. v2 states the referent.
            "confidence_referent": ("UNDEFINED - recorded, never interpreted (OPEN 36)"
                                    if probe_version == 1 else "confidence that STUDY is correct"),
            "probe_version": probe_version,
            "self_report_study": (study.group(1).strip()[:200] if study else None),
            "verdict": "RECOGNISED" if (matched or self_report == "YES") else "UNRECOGNISED"}


def assert_not_self_identifying(task: str, payloads: list, allow: bool) -> list:
    """A brief that names its own study cannot test recall. Assembling the payloads for the first
    time found two that did (OPEN item 3), so this is checked on every run, not once."""
    k = KEYS["tasks"][task]
    blob = "\n".join(payloads)
    bad = [p for p in k["identity_keys"] if re.search(p, blob, re.I)]
    if bad and not allow:
        raise SystemExit("%s: the assembled payload contains its own study's identity (%s). A brief "
                         "that names its study cannot measure recall. Redact the adapter's "
                         "sample_description (a proper noun, not a stimulus) or rerun with "
                         "--allow-identified and say so in the report." % (task, bad))
    return bad


def assert_one_name_per_arm(task: str, ad: dict, briefs: list) -> None:
    """A brief must give each arm exactly ONE name. MEASURED, on a paid batch: kim2024's adapter
    renamed the raw condition codes (`consensus`, `causal`) to readable titles (`Scientific
    consensus`, `Causal evidence`) and left the RAW codes in the sample description's arm-size
    sentence. `claude-opus-5` answered every row with the raw code, and the parser - correctly, per
    finding 70 - refused a name it had not been given, so all 22 cells were lost after the calls
    were paid for.

    This is neither a model error nor a parse error: the brief was ambiguous, and the fix belongs
    where the ambiguity was introduced. `_norm`/`_numfold` fold ENCODINGS of one name; two
    different names for one arm is a different failure and cannot be folded without the parser
    choosing which arm was meant. The structural fix is to write the TITLE into the derived file so
    that the adapter's arms map is the identity and no raw code exists anywhere.

    Scope, and why it is narrow. Only the HARNESS-WRITTEN parts of the brief are checked - the
    sample description, the outcome list, the instruction - and never the stimulus texts. A raw
    code can sit inside a message the study really showed (`voelkel2024`'s stimulus carries the
    Qualtrics block name `[CCT5 - Intro - Misperception_Competition]`), and redacting a stimulus
    changes the thing being predicted (finding 22). Codes that differ from their title only in
    case or punctuation are skipped: the parser already folds those (finding 65)."""
    renamed = {str(raw): str(title) for raw, title in ad.get("arms", {}).items()
               if ssb.predict._norm(raw) != ssb.predict._norm(title)}
    if not renamed:
        return
    fields = []
    for b in briefs:
        fields.append(str(b.get("sample", "")))
        fields.append(str(b.get("instruction", "")))
        outs = b.get("outcomes", {})
        fields += [json.dumps(outs, ensure_ascii=False)]
        fields += [a.get("title", "") for a in b.get("arms", [])]
    blob = "\n".join(fields)
    for title in sorted(set(map(str, ad.get("arms", {}).values())), key=len, reverse=True):
        blob = re.sub(re.escape(title), " ", blob, flags=re.I)   # inside a title IS the title
    bad = [f"{raw!r} (the raw code) alongside {title!r} (the title)"
           for raw, title in renamed.items()
           if re.search(r"(?<![A-Za-z0-9_])%s(?![A-Za-z0-9_])" % re.escape(raw), blob, re.I)]
    if bad:
        raise SystemExit(
            "%s: the brief's own prose gives an arm two names - %s. A model answers with whichever "
            "it saw last and the parser refuses a name it was not given, so every cell of that arm "
            "is lost AFTER the calls are paid for. The fix is at the source: write the TITLE into "
            "the derived file so the adapter's arms map is the identity and no raw code exists."
            % (task, "; ".join(bad)))


def assert_csv_safe_names(task: str, briefs: list) -> None:
    """A condition or outcome name that contains a COMMA cannot survive the answer format.

    MEASURED, on a paid batch this session, immediately after the two-names defect: dablander2025's
    arms were titled `Civil disobedience, no scientist`. `claude-opus-5` quoted the field and
    parsed; `claude-sonnet-5` wrote `Civil disobedience no scientist,policy_support,-1.5` - it
    dropped the comma so its row would still have three fields - and lost all 25 cells. A dropped
    character is not an encoding of a name (finding 73), so the parser must not and does not guess.

    The answer format is `condition,outcome,ate` and the harness chooses the names, so the fix is
    to not put a delimiter in one. Semicolons and tabs are refused for the same reason: they are
    delimiters `ssb.predict.parse` accepts."""
    bad = []
    for b in briefs:
        outs = b.get("outcomes", {})
        names = ([a.get("title", "") for a in b.get("arms", [])] + list(b.get("control_arms", []))
                 + (list(outs) if isinstance(outs, dict) else [o["name"] for o in outs]))
        bad += [n for n in names if any(c in str(n) for c in ",;\t")]
    if bad:
        raise SystemExit(
            "%s: %d condition/outcome name(s) contain a delimiter the answer format uses: %s. "
            "A model that writes an unquoted CSV row drops the character and the parser refuses "
            "the name it was not given, losing every cell of that arm AFTER the calls are paid "
            "for. Rename the arm in its builder." % (task, len(set(bad)), sorted(set(bad))[:4]))


def assert_run_id_free(run_id: str, tasks=None):
    """Refuse to start a run whose scoreboard rows already exist.

    scoreboard_append refuses the duplicate anyway, but it does so at the END, after every call and
    every artefact. Re-running into a used run_id is the defect behind finding 46 - it overwrites
    pairs.csv while the scoreboard keeps the old rows - so the cheapest place to stop it is before
    the work, not after it."""
    sb = RUN / "runs" / "scoreboard.csv"
    if not sb.exists():
        return
    try:
        d = pd.read_csv(sb)
    except Exception:
        return
    hit = d[d.run_id == run_id]
    if len(hit):
        raise SystemExit(
            "run_id %r already has %d scoreboard row(s) (tasks: %s).\n"
            "Re-running into it would overwrite this run's artefacts while those rows survive, "
            "leaving numbers nothing can reproduce (standing finding 46). Use a new --run-id - "
            "every completed call is cached, so a fresh id costs nothing to re-derive."
            % (run_id, len(hit), ", ".join(map(str, hit.task_id.unique()))))


def _inputs_digest() -> str | None:
    """sha256 over the whole inputs/ tree, recorded in run.json. Never fatal: a missing manifest
    tool must not stop a run that is otherwise fine."""
    try:
        sys.path.insert(0, str(RUN / "tools"))
        import inputs_manifest
        return inputs_manifest.current_digest()
    except Exception:
        return None


CACHE_DIR = CACHE                 # rebound to REHEARSAL_CACHE by main() when --rehearsal is set

# --- the live spend ledger --------------------------------------------------------------------
# The guard that stopped the last batch was a human reading a number after the fact. This one is
# the loop's own: every PAID call adds its measured billed tokens here, the running total goes to
# disk after each call, and crossing the ceiling raises before the next call is made. A cache hit
# adds nothing, because it costs nothing.
LEDGER = {"ceiling_tokens": None, "billed_tokens": 0, "billed_usd": 0.0, "paid_calls": 0,
          "cached_calls": 0, "prior_billed_tokens": 0, "calls": [], "path": None, "stopped": None}


def _ledger_flush():
    if LEDGER["path"]:
        Path(LEDGER["path"]).write_text(json.dumps(LEDGER, indent=1))


def _ledger_guard(next_label: str, est_next: int = 0):
    """Called BEFORE a paid call. Refuses to start one the ceiling cannot cover.

    `est_next` is what THIS call is expected to be billed, from the measured factors, so the guard
    reserves headroom instead of discovering the overshoot afterwards. Without it the ledger can
    exceed the ceiling by a whole call - proved on the red path against tools/fake/claude, where a
    60,000 ceiling ran to 74,574 before stopping."""
    c = LEDGER["ceiling_tokens"]
    spent = LEDGER["billed_tokens"] + LEDGER["prior_billed_tokens"]   # the BATCH, not the session
    if c and spent + est_next > c:
        LEDGER["stopped"] = ("ceiling %d cannot cover %s (batch so far %d = %d this session + %d "
                             "already paid and reused from cache, over %d paid calls; this call is "
                             "estimated at %d more)"
                             % (c, next_label, spent, LEDGER["billed_tokens"],
                                LEDGER["prior_billed_tokens"], LEDGER["paid_calls"], est_next))
        _ledger_flush()
        raise SystemExit("BUDGET CEILING: %s\nEvery completed call is cached, so raising "
                         "--max-billed-tokens and re-running resumes for free." % LEDGER["stopped"])


def call(user: str, system: str, model: str, execute: bool, **sampling) -> tuple[str, str, bool]:
    """(text, cache_key, from_cache). Cached on the prompt AND every sampling parameter, per the
    frozen budget rule. A cache hit costs nothing, so a rerun after a crash is free.

    A rehearsal writes to a SEPARATE cache: a scripted answer must never be able to satisfy a
    later real call and turn into a paid-for prediction that nobody paid for."""
    key = ssb.predict.cache_key(user, system, model, **sampling)
    f = CACHE_DIR / f"{key}.json"
    if f.exists():
        hit = json.loads(f.read_text())
        LEDGER["cached_calls"] += 1
        LEDGER["prior_billed_tokens"] += billed_tokens(hit.get("payload"))
        _ledger_flush()
        return hit["text"], key, True
    if not execute:
        return "", key, False
    label = json.dumps(sampling, sort_keys=True)
    est_next = round((ssb.predict.n_tokens(system) + ssb.predict.n_tokens(user))
                     * BILLED_INPUT_FACTOR)      # answer excluded: it is the only unmeasured part
    _ledger_guard(label, est_next)
    argv = ssb.predict.command(user, system, model)          # the frozen line, verbatim
    p = subprocess.run(argv, capture_output=True, text=True, timeout=1800)
    if p.returncode != 0:
        raise SystemExit("call failed (rc=%d) key=%s\n%s" % (p.returncode, key[:12], p.stderr[-2000:]))
    try:
        payload = json.loads(p.stdout)
        text = payload.get("result", payload.get("text", p.stdout))
    except json.JSONDecodeError:
        payload, text = {"raw": p.stdout}, p.stdout
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    # PARALLEL SAFETY (item 1b). The cache LAYOUT is already collision-safe under two writers:
    # the filename IS sha256(prompt + model + every sampling parameter), so two processes can
    # only ever target the same file when they are making the identical call, and then the two
    # payloads are interchangeable by construction. What was NOT safe is the WRITE: a plain
    # write_text is not atomic, so a concurrent reader could see a truncated JSON file and a
    # crash could leave one on disk forever. Write to a temp file in the same directory and
    # os.replace it, which is atomic within a filesystem; last writer wins, harmlessly.
    ssb.gates._atomic_write(f, json.dumps({"key": key, "model": model, "sampling": sampling,
                                           "text": text, "payload": payload}, indent=1))
    n = billed_tokens(payload)
    LEDGER["billed_tokens"] += n
    LEDGER["billed_usd"] += float(payload.get("total_cost_usd") or 0.0)
    LEDGER["paid_calls"] += 1
    LEDGER["calls"].append({"sampling": sampling, "key": key[:12], "billed_tokens": n,
                            "usd": round(float(payload.get("total_cost_usd") or 0.0), 4),
                            "running_total": LEDGER["billed_tokens"]})
    _ledger_flush()
    print("      paid %-42s %7d tok  running %8d / %s" % (
        label, n, LEDGER["billed_tokens"], LEDGER["ceiling_tokens"] or "no ceiling"), flush=True)
    return text, key, False


def bill(plans: dict, draws: int, probe: bool) -> dict:
    """The token bill, per task and total. Input tokens are the payload ssb.predict.command()
    would actually send, counted by ssb.predict.n_tokens (tiktoken cl100k as a proxy)."""
    rows, tot_in, tot_out, calls = [], 0, 0, 0
    for t, p in plans.items():
        per_draw_in = sum(p["tokens_per_part"])
        pred_in = per_draw_in * draws
        pred_out = p["n_cells"] * OUT_TOKENS_PER_CELL * draws
        pred_calls = p["parts"] * draws
        pr_in = p["probe_tokens"] if probe else 0
        pr_out = PROBE_OUT_TOKENS if probe else 0
        pr_calls = 1 if probe else 0
        rows.append({"task": t, "policy": p["policy"], "parts": p["parts"], "n_cells": p["n_cells"],
                     "calls": pred_calls + pr_calls, "probe_in": pr_in, "probe_out": pr_out,
                     "predict_in": pred_in, "predict_out": pred_out,
                     "total_tokens": pred_in + pred_out + pr_in + pr_out})
        tot_in += pred_in + pr_in
        tot_out += pred_out + pr_out
        calls += pred_calls + pr_calls
    for r in rows:                       # what the provider will actually bill, per Standing Finding
        r["billed_est"] = round((r["probe_in"] + r["predict_in"]) * BILLED_INPUT_FACTOR
                                + r["probe_out"] + r["predict_out"])
    billed = sum(r["billed_est"] for r in rows)
    return {"per_task": rows, "draws": draws, "probe": probe, "calls": calls,
            "input_tokens": tot_in, "output_tokens": tot_out, "total_tokens": tot_in + tot_out,
            "billed_tokens_est": billed,
            "billed_factors": {"tokenizer": TOKENIZER_FACTOR, "cli_overhead": CLI_OVERHEAD_FACTOR,
                               "billed_input_factor": round(BILLED_INPUT_FACTOR, 3),
                               "out_tokens_per_cell": OUT_TOKENS_PER_CELL,
                               "measured_on": TOKENIZER_MEASURED_ON},
            "note": "input_tokens is the assembled payload counted by tiktoken cl100k, measured; "
                    "billed_tokens_est is what the provider will charge - the same payload through "
                    "Anthropic's tokenizer (x%.3f) plus the CLI's own per-call pass over it "
                    "(+%.1f%%) - and is the number to compare against an approval ceiling. Output "
                    "is estimated at %d tokens/cell (+%d per probe) and is the only quantity here "
                    "that is not derived from a measurement."
                    % (TOKENIZER_FACTOR, 100 * CLI_OVERHEAD_FACTOR, OUT_TOKENS_PER_CELL,
                       PROBE_OUT_TOKENS)}


def main(model, run_id=None, draws=3, tasks=None, execute=False, approved=False, probe=True,
         allow_identified=False, rehearsal=False, max_billed_tokens=None, variant="base",
         allow_missing_cells=0.0, probe_version=1):
    global CACHE_DIR
    t0 = time.time()
    LEDGER["ceiling_tokens"] = max_billed_tokens
    tasks = tasks or TASKS
    # Which binary will actually answer? Recorded on every run, so a rehearsal can never be read
    # as a practice score and a real run carries the hash of what it called.
    which = shutil.which("claude")
    binary = {"resolved": which,
              "sha256": (hashlib.sha256(Path(which).read_bytes()).hexdigest()[:16] if which else None)}
    if rehearsal:
        CACHE_DIR = REHEARSAL_CACHE
        os.environ["SSB_REHEARSAL"] = "1"
        approved = True                       # a rehearsal spends nothing, so nothing to approve
    if execute and not approved:
        raise SystemExit("--execute requires --approved: stage 3 spends the operator's budget "
                         "(AGENTS.md: 'Ask the operator before either'). Run without --execute "
                         "first and show them the bill.")
    _pfx = "rehearsal-" if rehearsal else ""
    run_id = run_id or (time.strftime("%Y%m%d-") + _pfx + "practice-" + time.strftime("%H%M%S"))
    # What were these prompts built from? run.json records the frozen file and the spec and, until
    # now, nothing about inputs/ - the stimuli, adapters, texts, pool and baselines that determine
    # every prompt. A changed input changes the cache key, so the symptom was a silent extra CALL
    # rather than a warning, and two scoreboard rows built from different inputs compared as if
    # they were the same experiment.
    # PARALLEL SAFETY: the run DIRECTORY is namespaced by SSB_ARM, so the scoreboard's run_id
    # must be the namespaced one too, or the board points at a directory that does not exist and
    # nothing can re-derive the row. Resolve it BEFORE the duplicate check.
    run_id = ssb.gates.namespaced(run_id)
    assert_run_id_free(run_id)
    inputs_digest = _inputs_digest()
    d = ssb.gates.new_run(run_id, stub_predictor=rehearsal, inputs_sha256=inputs_digest,
                          note="%sstage 3 practice, model=%s, draws=%d, probe=%s, variant=%s, "
                               "claude=%s"
                               % ("REHEARSAL (scripted answers, no credential) - " if rehearsal else "",
                                  model, draws, probe, variant, binary["resolved"]))
    ssb.gates.record(d, "G1_frozen_intact",
                     ssb.gates.frozen_hash() == json.loads((d / "run.json").read_text())["frozen_sha256"],
                     "APPEND_SYSTEM.md sha256 matches the value recorded at run start")
    st = d / "stages" / "practice"
    st.mkdir(parents=True, exist_ok=True)
    LEDGER["path"] = str(st / "spend.json")
    _ledger_flush()
    (st / "probes").mkdir(parents=True, exist_ok=True)
    (st / "prompts").mkdir(parents=True, exist_ok=True)

    # ---- assemble everything first, so the bill is exact before anything is spent -------------
    plans, briefs, probes = {}, {}, {}
    for t in tasks:
        task_dir = d / "tasks" / t
        ssb.task.carve(t, task_dir)
        b = json.loads((task_dir / "brief" / "task.json").read_text())
        # The length experiment's only seam (runs/_lenexp/PREREG.md). `base` is the identity, so a
        # base run's cache keys are the original practice run's and cost nothing; every other
        # variant changes the prompt text and nothing else in this file.
        b, vmeta = prompt_variants.apply(b, variant)
        (task_dir / "brief" / ("task_%s.json" % variant)).write_text(json.dumps(b, indent=1))
        plan = ssb.predict.plan_prompts(b, budget_tokens=24000, per_arm_char_cap=12000)
        parts = plan.pop("briefs")
        briefs[t] = parts
        toks = []
        sub = st / "prompts" / t
        sub.mkdir(parents=True, exist_ok=True)
        for i, pb in enumerate(parts):
            system, user = ssb.predict.build_prompt(pb)
            system = vmeta.get("system", system)   # a variant may replace the SYSTEM prompt
            (sub / "system.txt").write_text(system)
            (sub / ("user_part%d.txt" % (i + 1) if len(parts) > 1 else "user.txt")).write_text(user)
            toks.append(ssb.predict.n_tokens(system) + ssb.predict.n_tokens(user))
        ps, pu = probe_prompt(parts[0], probe_version)
        (st / "probes" / t).mkdir(parents=True, exist_ok=True)
        (st / "probes" / t / "system.txt").write_text(ps)
        (st / "probes" / t / "user.txt").write_text(pu)
        probes[t] = (ps, pu)
        outs = ([o["name"] for o in b["outcomes"]] if isinstance(b["outcomes"], list) else list(b["outcomes"]))
        payloads = [(sub / f).read_text() for f in sorted(x.name for x in sub.iterdir())] + [pu]
        selfid = assert_not_self_identifying(t, payloads, allow_identified)
        assert_one_name_per_arm(t, ssb.task.load_adapter(t), parts)
        assert_csv_safe_names(t, parts)
        content = [p for p in KEYS["tasks"][t].get("content_keys", [])
                   if re.search(p, "\n".join(payloads), re.I)]
        plans[t] = {**plan, "variant": vmeta, "tokens_per_part": toks,
                    "n_cells": len(b["arms"]) * len(outs),
                    "probe_tokens": ssb.predict.n_tokens(ps) + ssb.predict.n_tokens(pu),
                    "self_identifying_keys_in_payload": selfid,
                    "content_keys_in_payload": content}
    cost = bill(plans, draws, probe)
    (st / "cost.json").write_text(json.dumps({"model": model, **cost, "plans": plans}, indent=1))
    print("\nSTAGE 3 BILL  model=%s  draws=%d  probe=%s" % (model, draws, probe))
    print("%-15s%-8s%6s%10s%12s%10s%10s" % ("task", "policy", "calls", "probe_in", "predict_in", "est_out", "total"))
    for r in cost["per_task"]:
        print("%-15s%-8s%6d%10d%12d%10d%10d" % (r["task"], r["policy"], r["calls"], r["probe_in"],
                                                r["predict_in"], r["probe_out"] + r["predict_out"],
                                                r["total_tokens"]))
    print("%-15s%-8s%6d%10s%12d%10d%10d" % ("TOTAL", "", cost["calls"], "", cost["input_tokens"],
                                            cost["output_tokens"], cost["total_tokens"]))
    print("\nBILLED ESTIMATE (what the provider charges, not what tiktoken counts): %d tokens"
          % cost["billed_tokens_est"])
    print("  = payload x %.3f (Anthropic tokenizer) x %.3f (the CLI's own per-call pass) + answers"
          % (TOKENIZER_FACTOR, 1 + CLI_OVERHEAD_FACTOR))
    print("  ceiling for this run: %s" % (max_billed_tokens or "none set"))
    print("\npayloads written under %s" % st)
    if not execute:
        print("\nNO CALL WAS MADE (plan-only). Re-run with --execute --approved to spend.\n")
        return {"run": str(d), "cost": cost, "executed": False}

    # ---- 3a. recognition probe, BEFORE any prediction -----------------------------------------
    probe_rows = []
    if probe:
        for t in tasks:
            ps, pu = probes[t]
            text, key, cached = call(pu, ps, model, execute, stage="probe", task=t)
            (st / "probes" / t / "completion.txt").write_text(text)
            g = grade_probe(text, t, probe_version)
            g.update({"cache_key": key, "from_cache": cached,
                      "recall_window_note": KEYS["tasks"][t]["recall_window_note"]})
            probe_rows.append(g)
            print("  probe %-15s %-13s self=%-8s matched=%s"
                  % (t, g["verdict"], g["self_report_results_known"], g["matched_identifiers"]))
        (st / "recognition_probe.json").write_text(json.dumps(probe_rows, indent=1))

    # ---- 3b/3c. predict, aggregate, score, audit ----------------------------------------------
    pairs, board, missing_cells = [], [], {}
    for t in tasks:
        task_dir = d / "tasks" / t
        frames, per_part, transcripts = [], {}, []
        for dr in range(draws):
            got = []
            vmeta = plans[t]["variant"]
            for i, pb in enumerate(briefs[t]):
                system, user = ssb.predict.build_prompt(pb)
                system = vmeta.get("system", system)   # a variant may replace the SYSTEM prompt
                text, key, cached = call(user, system, model, execute, draw=dr)
                tf = task_dir / ("transcript_draw%d_part%d.txt" % (dr, i + 1))
                tf.write_text(text)
                transcripts.append(tf)
                conds = [a["title"] for a in pb["arms"]]
                # A variant may declare aliases for its arm titles (an ablation that renames arms
                # `Message A` gets answered as `A`). They are added to the names the parser will
                # accept and mapped back below; nothing else downstream sees them.
                al = vmeta.get("title_aliases") or {}
                conds = conds + [x for c in conds for x in al.get(c, [])]
                outs = ([o["name"] for o in pb["outcomes"]] if isinstance(pb["outcomes"], list)
                        else list(pb["outcomes"]))
                f = ssb.predict.parse(text, conds, outs)
                # An ablation may have shown the model pseudonymous arm titles. The answer is
                # mapped back to the real titles HERE, before anything downstream sees it, so the
                # scorer, the sealed truth and the leak audit all work on real condition names.
                back = vmeta.get("rename_back")
                if back:
                    f["condition"] = f["condition"].map(lambda c: back.get(c, c))
                    # An alias and its full title both appear in the parsed grid and both map to
                    # the same real condition, so exactly one of the two carries the answer. Keep
                    # the filled one; keeping the first would keep the empty one half the time.
                    f = (f.assign(_na=f.ate.isna()).sort_values("_na")
                          .drop_duplicates(["condition", "outcome"], keep="first")
                          .drop(columns="_na").reset_index(drop=True))
                per_part.setdefault("part%d" % (i + 1), []).append(f)
                got.append(f)
            # A split task's parts share their anchor arms, so one cell can be answered twice.
            # Keeping the FIRST row lets an unparsed part-1 cell mask a perfectly good part-2
            # answer - measured in session 11, where `Alternative Control` came back as
            # `AltCon_Placebo` in part 1 and correctly in part 2, and the arm was scored as
            # missing. Keep the first NON-NULL; stable, so part order still breaks real ties.
            g = pd.concat(got)
            frames.append(g.assign(_na=g.ate.isna()).sort_values("_na", kind="stable")
                           .drop_duplicates(["condition", "outcome"], keep="first")
                           .drop(columns="_na").reset_index(drop=True))
        agg = ssb.predict.aggregate(frames)
        n_missing = int(agg.ate.isna().sum())
        # The default is still an abort: a silently missing cell scores as a deliberate null
        # prediction (0.5 directional credit), and every abort so far was a PARSE defect worth
        # fixing (session 8's alias and apostrophe; this session's `message_01`). But an answer
        # can also be genuinely incomplete - claude-fable-5 discussed arm `Message 68` in prose
        # and then omitted its four rows from a 292-cell table - and refusing the whole arm for
        # 1.4% of its cells throws away a paid batch to protect a completeness we do not have.
        # A tolerance is therefore allowed only when it is asked for on the command line, bounded,
        # and recorded: the missing cells stay NaN (never 0), are listed in summary.json, are
        # excluded from the pairs, and tools/prompt_experiment.py compares arms on the INTERSECTION
        # of their cells so a contrast is never computed over two different grids.
        if n_missing and n_missing > allow_missing_cells * len(agg):
            raise SystemExit("%s: %d of %d cells unparsed after %d draws - a silently missing cell "
                             "would score as a null prediction (0.5 directional credit). Fix the "
                             "parse, or pass --allow-missing-cells if the answer itself is "
                             "incomplete (max allowed here: %.1f%%)."
                             % (t, n_missing, len(agg), draws, 100 * allow_missing_cells))
        missing_cells[t] = agg[agg.ate.isna()][["condition", "outcome"]].to_dict("records")
        if n_missing:
            print("  %-15s %d of %d cells MISSING from the answer (%.1f%%), kept NaN and excluded"
                  % (t, n_missing, len(agg), 100 * n_missing / len(agg)))
        plan = plans[t]
        if plan["policy"] == "split" and plan["anchors"]:
            back = plan["variant"].get("rename_back") or {}
            anchors = [back.get(a, a) for a in plan["anchors"]]   # the frames are already renamed
            sp = ssb.predict.anchor_spread({k: ssb.predict.aggregate(v) for k, v in per_part.items()},
                                           anchors)
            sp.to_csv(task_dir / "anchor_spread.csv", index=False)
            plan["anchor_spread_pp"] = {"mean_sd": float(sp["std"].mean()),
                                        "max_range": float((sp["max"] - sp["min"]).max())}
        pred_csv = task_dir / "prediction.csv"
        agg[["condition", "outcome", "ate"]].to_csv(pred_csv, index=False)
        sc = ssb.task.score_task(task_dir, pred_csv)
        audit = ssb.task.leak_audit(task_dir, transcripts)
        pos = task_dir / "transcript_positive_control.txt"
        pos.write_text((task_dir / "sealed" / "truth.csv").read_text())
        audit_pos = ssb.task.leak_audit(task_dir, [pos])
        ad = ssb.task.load_adapter(t)
        pr = next((x for x in probe_rows if x["task"] == t), {})
        # OPEN item 11: magnitudes that the task's own data does not identify cannot inform a slope.
        # OPEN item 3, pre-registered before the first probe call: neither can magnitudes a
        # predictor may be RECALLING rather than predicting. Both are structural exclusions from
        # the fitted slope, not notes - the task is still scored on every other row.
        # A third structural exclusion, declared in the ADAPTER before the task is ever run:
        # `exclude_from_slope` is a string reason for a task whose MAGNITUDES are not on the
        # target's footing even though its ordering is. Task 6 is a 7-point Likert item where the
        # target is a slider (and the ten-issue check in notes/DATA_HACKENBURG.md finds no
        # constant bridge); task 7's stimuli are LLM-authored where the target's are human-written.
        # Both are still scored on every Section-1 row - only the fitted slope is protected.
        in_slope = ((not ad.get("attrition_bounds")) and pr.get("verdict") != "RECOGNISED"
                    and not ad.get("exclude_from_slope"))
        excluded_because = ([] + (["attrition_bounds"] if ad.get("attrition_bounds") else [])
                            + (["recognised"] if pr.get("verdict") == "RECOGNISED" else [])
                            + ([ad["exclude_from_slope"]] if ad.get("exclude_from_slope") else []))
        truth = pd.read_csv(task_dir / "sealed" / "truth.csv")
        p = truth.merge(agg[["condition", "outcome", "ate"]].rename(columns={"ate": "pred"}),
                        on=["condition", "outcome"]).rename(columns={"ate": "human"})
        p["task"], p["family"], p["in_slope"] = t, "practice_" + t, in_slope
        p["recognition"] = pr.get("verdict", "not_probed")
        p["out_of_slope_because"] = "|".join(excluded_because)
        pairs.append(p)
        board.append({"run_id": run_id, "stage": "rehearsal" if rehearsal else "practice",
                      "stub": bool(rehearsal), "task_id": t,
                      "n_cells": len(p), "leak_verdict": audit["verdict"],
                      "note": "%smodel=%s; draws=%d; variant=%s; %s, %d part(s); in_slope=%s; "
                              "positive_control=%s; recognition=%s"
                              % ("REHEARSAL scripted answers - NOT a prediction; "
                                 if rehearsal else "",
                                 model, draws, variant, plan["policy"], plan["parts"],
                                 in_slope, audit_pos["verdict"],
                                 pr.get("verdict", "not_probed")),
                      **{k: v for k, v in sc.items() if k in
                         {"directional_agreement", "spearman_rho", "pearson_r",
                          "pearson_r_within_outcomes", "rmse_pp", "r_adj", "rmse_adj",
                          "cal_alpha", "cal_beta", "shrinkage_factor",
                          "vs_no_effect_floor_directional", "vs_no_effect_floor_rmse",
                          "vs_all_positive_directional", "vs_all_positive_rmse"}}})
        print("  %-14s cells %4d  dir %.3f  rho %+.3f  rmse %5.2f  leak %s (pos %s)"
              % (t, len(p), sc["directional_agreement"], sc["spearman_rho"], sc["rmse_pp"],
                 audit["verdict"], audit_pos["verdict"]))

    pairs = pd.concat(pairs, ignore_index=True)
    (d / "stages" / "calibration").mkdir(parents=True, exist_ok=True)
    pairs.to_csv(d / "stages" / "calibration" / "pairs.csv", index=False)
    (d / "stages" / "prompt_plans.json").write_text(json.dumps(plans, indent=1))
    ok = (all(r["leak_verdict"] == "CLEAN" for r in board)
          and all("positive_control=LEAK" in r["note"] for r in board))
    ssb.gates.record(d, "G2_practice_scored", ok,
                     "%d cells over %d tasks, %d draws each, model=%s; every transcript audited "
                     "with its positive control" % (len(pairs), len(tasks), draws, model))
    for row in board:
        ssb.gates.scoreboard_append(row)
    spent = LEDGER["billed_tokens"] + LEDGER["prior_billed_tokens"]
    est = cost["billed_tokens_est"]
    out = {"run": str(d), "cost": cost, "executed": True, "G2": ok, "rehearsal": bool(rehearsal),
           "binary": binary, "cache_dir": str(CACHE_DIR),
           "spend": {**{k: v for k, v in LEDGER.items() if k != "calls"},
                     "batch_billed_tokens": spent,
                     "estimate_billed_tokens": est,
                     "estimate_tiktoken_tokens": cost["total_tokens"],
                     "actual_over_estimate": round(spent / est, 3) if est else None,
                     "actual_over_tiktoken": round(spent / cost["total_tokens"], 3)},
           "recognition": probe_rows, "board": board, "missing_cells": missing_cells,
           "allow_missing_cells": allow_missing_cells, "seconds": round(time.time() - t0, 1)}
    print("\nSPEND  batch %d billed tokens (%d this session, %d reused from cache, $%.2f new)"
          % (spent, LEDGER["billed_tokens"], LEDGER["prior_billed_tokens"], LEDGER["billed_usd"]))
    print("       estimate was %d billed / %d tiktoken -> actual/estimate %.2f, actual/tiktoken %.2f"
          % (est, cost["total_tokens"], spent / est if est else 0, spent / cost["total_tokens"]))
    (st / "summary.json").write_text(json.dumps(out, indent=1))
    print("\nstage 3 complete ->", d)
    print("NEXT: stage 4 - ssb.predict.fit_calibration on stages/calibration/pairs.csv (RUNBOOK step 1)")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, help="model id, passed straight to --model")
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--draws", type=int, default=3,
                    help="independent completions per prompt, median-aggregated (default 3)")
    ap.add_argument("--tasks", nargs="*", default=None)
    ap.add_argument("--execute", action="store_true", help="actually call the model")
    ap.add_argument("--approved", action="store_true", help="the operator approved the printed bill")
    ap.add_argument("--no-probe", dest="probe", action="store_false", help="skip stage 3a")
    ap.add_argument("--rehearsal", action="store_true",
                    help="run the FULL execute path against tools/fake/claude (scripted answers, no "
                         "credential, separate cache, scoreboard rows flagged stub=True). "
                         "Put tools/fake on PATH first.")
    ap.add_argument("--max-billed-tokens", type=int, default=None,
                    help="hard ceiling on tokens the provider actually bills for this BATCH "
                         "(cache hits count as already paid). The run stops before the call that "
                         "would cross it; every completed call is cached, so resuming is free.")
    ap.add_argument("--allow-identified", action="store_true",
                    help="proceed even though an assembled payload names its own study - the "
                         "recognition probe is then uninformative for that task and says so")
    ap.add_argument("--allow-missing-cells", type=float, default=0.0,
                    help="fraction of a task's cells the ANSWER may omit before the run aborts "
                         "(default 0.0). Missing cells stay NaN, are listed in summary.json and "
                         "are excluded from the pairs; use only when the completion is genuinely "
                         "incomplete rather than mis-parsed.")
    ap.add_argument("--variant", default="base", choices=prompt_variants.VARIANTS,
                    help="length treatment applied to the brief BEFORE plan_prompts "
                         "(runs/_lenexp/PREREG.md). 'base' is the identity and its calls are "
                         "already cached, so a base run spends nothing.")
    ap.add_argument("--probe-version", type=int, default=1, choices=(1, 2),
                    help="1 (default) is the probe every result on disk was bought under; 2 states "
                         "what CONFIDENCE means (OPEN 36) and makes every probe a cache miss, so "
                         "use it only in a session that is buying fresh probes anyway.")
    a = ap.parse_args()
    main(a.model, a.run_id, a.draws, a.tasks, a.execute or a.rehearsal, a.approved, a.probe,
         a.allow_identified, a.rehearsal, a.max_billed_tokens, a.variant, a.allow_missing_cells,
         a.probe_version)
