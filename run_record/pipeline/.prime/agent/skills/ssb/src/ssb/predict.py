"""ssb.predict - the analysis-level predictor, and the calibration map fitted on practice.

THE PREDICTOR IS A PLAIN COMPLETION, NOT AN AGENT. It is handed a brief in one user
message and answers with a CSV. It has no tools, no retrieval and no filesystem, so
the blinding claim is structural: for a training task it *cannot* open the sealed
truth or the source dataset, and for the target study it cannot go looking for
anything. An agentic predictor would make blinding a promise instead of a property.
(rlm() children are used for harness work - reconnaissance, code, review - never to
produce a prediction.)

Nothing in this module makes a call. `command()` returns the exact argv from the
frozen definitions; the run stage executes it, caches on `cache_key`, and asks the
operator before any batch.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import spec

SYSTEM = """You are a research analyst predicting the results of a randomised message experiment.
You reason at the level of the analysis - average treatment effects per message per outcome -
never by imagining individual respondents.

Rules:
- Answer ONLY with CSV: a header line `condition,outcome,ate` then one row per cell. No prose.
- `ate` is in percentage points of that outcome's scale range (a 0-100 slider: 1 unit = 1 pp;
  a $0-10 item: $1 = 10 pp; a 0/1 item: 1 percentage point of the signup rate = 1 pp).
- Effects may be negative, and a message that plausibly backfires on an outcome should get a
  negative number. Reverse-valenced outcomes (e.g. a distrust item) move opposite to the
  construct the message pushes.
- Fill every cell. Do not omit rows, do not write NA.
- Give your honest ordering and relative magnitude. Do not inflate effects to look decisive:
  most message effects in large field-quality megastudies are small.
"""

TARGET_PREAMBLE = """You are predicting a preregistered megastudy on ~18,000 U.S. adults
(census-based quotas on age, gender and race/ethnicity), run online. Each respondent reads ONE
text and then answers the outcome battery. The control condition reads one of three neutral,
off-topic filler texts (the history of neckties, the rules of baseball, types of dance).
"""


def target_brief() -> dict:
    """The target study's brief, assembled from the read-only benchmark only."""
    s = spec.load()
    cb = {r["target_label"]: r for r in spec.codebook()}
    return {
        "preamble": TARGET_PREAMBLE,
        "arms": [{"title": t["title"], "tag": t["tag"], "text": t["text"]}
                 for t in spec.stimuli()["stimuli"] if t["title"] != "control"],
        "outcomes": [{"name": o, "lo": s["ranges"][o][0], "hi": s["ranges"][o][1],
                      "question": cb.get(o, {}).get("question_text", ""),
                      "response_options": cb.get(o, {}).get("response_options", "")}
                     for o in s["outcomes"]],
        "note": ("belief_post and trust_post are RE-ASKED post-treatment: the same two items were "
                 "already answered by the same respondent before the text (belief_pre, trust_pre). "
                 "newsletter_signup requires leaving the survey tab to subscribe. "
                 "donation_ams gives away part of a real $10 bonus."),
    }


def build_prompt(brief: dict) -> tuple[str, str]:
    """(system, user). The user message carries the full stimulus texts - a predictor
    that has not read the message cannot predict the message."""
    lines = [brief.get("preamble", ""), ""]
    if brief.get("sample"):
        lines += [f"Sample: {brief['sample']}", ""]
    lines.append("OUTCOMES (name | scale | question):")
    for o in brief["outcomes"] if isinstance(brief["outcomes"], list) else []:
        lines.append(f"- {o['name']} | {o['lo']}-{o['hi']} | {o.get('question','')}")
    if isinstance(brief["outcomes"], dict):
        lines = lines[:-1] + [f"- {k} | {v['lo']}-{v['hi']} | {v.get('question','')}"
                              for k, v in brief["outcomes"].items()]
    lines += ["", f"CONDITIONS ({len(brief['arms'])} interventions, each vs control):", ""]
    for a in brief["arms"]:
        lines += [f"### {a['title']}", a.get("text", "(text not available)"), ""]
    if brief.get("control_texts"):
        lines += ["CONTROL CONDITION (the comparison every effect is measured against):", ""]
        for a, t in brief["control_texts"].items():
            lines += [f"### {a} (control)", t, ""]
    if brief.get("note"):
        lines += ["NOTES: " + brief["note"], ""]
    names = [a["title"] for a in brief["arms"]]
    outs = ([o["name"] for o in brief["outcomes"]] if isinstance(brief["outcomes"], list)
            else list(brief["outcomes"]))
    lines += [f"Return exactly {len(names) * len(outs)} rows: every condition x every outcome.",
              "Header: condition,outcome,ate"]
    return SYSTEM, "\n".join(lines)


def command(user: str, system: str, model: str) -> list[str]:
    """The exact simulator/predictor call from the frozen definitions. Not executed here."""
    return ["env", "-u", "ANTHROPIC_API_KEY", "-u", "ANTHROPIC_AUTH_TOKEN",
            "MAX_THINKING_TOKENS=0", "claude", "-p", user, "--system-prompt", system,
            "--tools", "", "--settings", '{"claudeMdExcludes":["**"]}',
            "--no-session-persistence", "--output-format", "json", "--model", model]


def cache_key(user: str, system: str, model: str, **sampling) -> str:
    """Covers the prompt AND every sampling parameter, per the frozen budget rule."""
    blob = json.dumps({"u": user, "s": system, "m": model, **sampling}, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


# Typographic characters a model retypes in their ASCII form. MEASURED, not anticipated: an arm
# titled `Outpartisans’ Experiences of Harm` came back as `Outpartisans' Experiences of Harm`
# and lost all 9 of its cells in a paid batch (session 8). These pairs are the SAME character in
# two encodings, so folding them cannot merge two genuinely different arms - unlike touching any
# other internal character, which is why the rule below is a fixed table and not a fuzzy match.
_TYPO = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"',
                       "–": "-", "—": "-", " ": " ", "…": "..."})


def _norm(s: str) -> str:
    """Match a condition or outcome name written back sloppily: case, surrounding whitespace,
    quotes, markdown emphasis and trailing punctuation are all noise, and so is whether the model
    retyped a curly apostrophe as a straight one. No other internal character is touched, so two
    genuinely different arms can never collide."""
    return re.sub(r"\s+", " ", str(s).translate(_TYPO).strip().strip('"\'`*_ ').strip(" .:")).lower()


def _numfold(s: str) -> str:
    """`Message 01` -> `message 1` -> `message1`. Three differences a model reliably introduces when
    it retypes a label: it drops a leading zero, it writes the separator its own way
    (`message_01`, `Message-01`), and it drops the punctuation inside the name when it runs the
    words together (`Outpartisans' Willingness to Learn` -> `OutpartisansWillingnessToLearn`). All
    three are re-encodings of the same name, never a different arm, and the map below refuses any
    folded key that two real names share, so a collision cannot silently merge two arms. MEASURED
    twice, not anticipated: `claude-fable-5` answered a 73-arm task entirely in `message_01` form
    and lost all 292 cells, and `claude-sonnet-5` answered a 26-arm task in run-together CamelCase
    and lost the two arms whose titles carry an apostrophe - both after the calls were paid for.
    """
    return re.sub(r"(?<!\d)0+(\d)", r"\1",
                  re.sub(r"[\s_\-'.]+", "", _norm(s)))


def _numfold_map(names) -> dict:
    """Folded name -> real name, dropping any folded key two real names share."""
    out = {}
    for n in names:
        k = _numfold(n)
        if k in out and out[k] != n:
            out[k] = None
        else:
            out.setdefault(k, n)
    return {k: v for k, v in out.items() if v is not None}


def _digits(s: str) -> str:
    """The number inside a label, leading zeros dropped: `msg01` -> `1`, `Message 01` -> `1`."""
    d = "".join(ch for ch in _norm(s) if ch.isdigit())
    return d.lstrip("0") or ("0" if d else "")


def _digitfold_map(names) -> dict:
    """`msg01` -> `Message 01`, but ONLY where the number IS the identity.

    MEASURED on a paid batch (session 11): `claude-sonnet-5` answered task 7's 73 arms as
    `msg01..msg73` and lost all 292 cells. `_numfold` cannot help - `msg` is not a re-encoding of
    `message`, it is an abbreviation, and no general abbreviation rule is safe.

    What IS safe is the narrow case this map is restricted to: every arm name has a number, the
    numbers are unique, and the arms share ONE common non-numeric stem (`message NN`). Then the
    arm's name carries no information the number does not, and reading the number is not a guess
    about which arm was meant. If the names disagree on their stem, or two share a number, or one
    has no number at all, the map is empty and nothing is folded.

    Conditions only (see `parse`): a bare number in an OUTCOME position would let a value column
    masquerade as an outcome name.
    """
    names = list(names)
    if not names:
        return {}
    keys, stems = [], set()
    for n in names:
        k = _digits(n)
        if not k:
            return {}
        keys.append(k)
        stems.add(re.sub(r"[\s_\-'.]+", "", "".join(ch for ch in _norm(n) if not ch.isdigit())))
    if len(set(keys)) != len(keys) or len(stems) != 1:
        return {}
    return dict(zip(keys, names))


_DELIMS = (",", ";", "\t", "|")


def _fields(line: str):
    """The same line split every plausible way, most-fields first. A model that answers with a
    markdown table, semicolons or tabs has still answered; only the delimiter is wrong, and
    guessing it is not a judgement call about the prediction."""
    outs = []
    for d in _DELIMS:
        if d in line:
            parts = [p.strip().strip('"') for p in line.split(d)]
            parts = [p for p in parts if p != ""]
            outs.append(parts)
    return sorted(outs, key=len, reverse=True) or [[line.strip()]]


_NUM = re.compile(r"^([+-]?\d{1,3}(?:,\d{3})+(?:\.\d+)?|[+-]?\d*\.?\d+(?:[eE][+-]?\d+)?)"
                  r"\s*(pp|%|percentage points?|points?|pts?)?$", re.I)


def _number(s: str):
    """A value with a unit is a value. 'N/A' is not - it must stay NaN, because a zero there
    would be scored as a deliberate null prediction (0.5 directional credit)."""
    m = _NUM.match(str(s).strip().strip('"'))
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def parse(text: str, conditions: list[str], outcomes: list[str]) -> pd.DataFrame:
    """Parse a completion into a complete condition x outcome ATE table.

    Missing or unparseable cells come back as NaN rather than 0: a silently zeroed
    cell would score as a deliberate null prediction (0.5 directional credit) and
    hide a broken call.
    """
    body = re.sub(r"^```[a-z]*\n|```$", "", text.strip(), flags=re.M)
    cmap = {_norm(c): c for c in conditions}
    omap = {_norm(o): o for o in outcomes}
    # A numbered arm - `Message 01` - comes back as `Message 1` often enough that a task carved
    # with 73 numbered arms would lose cells to a leading zero. The fold is applied only when the
    # exact name misses AND the folded key is unambiguous, so it can never merge two real arms.
    cmap.update({k: v for k, v in _numfold_map(conditions).items() if k not in cmap})
    omap.update({k: v for k, v in _numfold_map(outcomes).items() if k not in omap})
    # Last resort, conditions only and only for a purely numbered arm list (see _digitfold_map).
    cmap.update({k: v for k, v in _digitfold_map(conditions).items() if k not in cmap})
    rows = []
    for line in body.splitlines():
        for parts in _fields(line):
            if len(parts) < 3:
                continue
            # find the OUTCOME as a whole field, then the condition before it and the first
            # number after it. Locating the outcome first is what makes a trailing comment
            # column, a markdown table and a swapped delimiter all parse the same way.
            def _look(m, p):        # exact name, then the re-encoding fold, then the number
                return m.get(_norm(p)) or m.get(_numfold(p)) or m.get(_digits(p))
            j = next((i for i, p in enumerate(parts) if _look(omap, p)), None)
            if j is None or j == 0:
                continue
            cond = (_look(cmap, ",".join(parts[:j]))
                    or next((_look(cmap, p) for p in parts[:j] if _look(cmap, p)), None))
            if cond is None:
                continue
            val = next((v for v in (_number(p) for p in parts[j + 1:]) if v is not None), None)
            if val is not None:
                rows.append({"condition": cond, "outcome": _look(omap, parts[j]), "ate": val})
            break
    grid = pd.DataFrame([{"condition": c, "outcome": o} for c in conditions for o in outcomes])
    d = pd.DataFrame(rows).drop_duplicates(["condition", "outcome"]) if rows else \
        pd.DataFrame(columns=["condition", "outcome", "ate"])
    return grid.merge(d, on=["condition", "outcome"], how="left")


def parser_version() -> str:
    """A hash of the PARSING CODE, so a stored prediction can say which parser made it.

    Standing finding 72: a stored prediction is a parser version as much as a model answer -
    `20260817-practice-t67`'s hackenburg2025 prediction disagreed with today's parser on 23 of 292
    cells because the parser was hardened after that file was written, and nothing recorded it.
    Every scoreboard row now carries this string (`ssb.gates.scoreboard_append`), and
    `tools/reparse_audit.py` re-derives the board through the parser that exists today.

    It hashes the functions a parsed cell passes through, not the module file: hashing predict.py
    would change on an edit to `to_native` or a docstring and make every row look re-parsed when
    nothing about parsing moved.
    """
    import hashlib as _h, inspect as _i
    names = ["_norm", "_numfold", "_numfold_map", "_digits", "_digitfold_map",
             "_fields", "_number", "parse", "aggregate"]
    blob = "".join(_i.getsource(globals()[n]) for n in names)
    blob += repr(sorted(_TYPO.items()))
    return _h.sha256(blob.encode()).hexdigest()[:12]


def aggregate(frames: list[pd.DataFrame]) -> pd.DataFrame:
    """Median across independent draws, with the spread kept as an honesty diagnostic.

    A panel of independent completions is cheaper than a bigger model and gives the
    only uncertainty estimate available before the human data exists.
    """
    d = pd.concat(frames)
    g = d.groupby(["condition", "outcome"])["ate"]
    return g.median().rename("ate").reset_index().merge(
        g.agg(["std", "count"]).reset_index().rename(
            columns={"std": "ate_sd_across_draws", "count": "n_draws"}),
        on=["condition", "outcome"])


# --------------------------------------------------------------------------
# calibration - what practice actually transfers
# --------------------------------------------------------------------------


def fit_calibration(pairs: pd.DataFrame, by: str | None = "family",
                    pred="pred", human="human", min_n: int = 20) -> dict:
    """Fit the shrinkage map on (predicted, human) pairs from scored training tasks.

    The practice loop exists to estimate this. The predictor supplies ordering and
    sign (Section-1 directional/Spearman rows, which no transform can fix); this map
    supplies absolute magnitude (the Calibration alpha/beta row and the RMSE row).
    Fitted through the origin so a predicted null stays a null.

    `by` groups the pairs (default: outcome family), falling back to the pooled slope
    wherever a group has fewer than `min_n` pairs.

    A pairs frame may carry a boolean `in_slope` column. Rows with `in_slope == False`
    are scored like any other (ordering, sign, RMSE) but are EXCLUDED from the fitted
    magnitude map. That is not a convenience: goldwert2026's ATEs are Lee-bounded ~10.6
    pp wide against a median |ATE| of 2.4 pp (OPEN item 11), so its magnitudes are not
    identified by its own data and cannot inform a slope, however many cells it has.
    """
    from . import score as S
    d = pairs.dropna(subset=[pred, human])
    if "in_slope" in d.columns:
        d = d[d["in_slope"].astype(bool)]
    pooled = S.shrinkage_factor(d[pred], d[human])
    out = {"_pooled": pooled, "_n": int(len(d))}
    if by and by in d.columns:
        for k, g in d.groupby(by):
            out[str(k)] = S.shrinkage_factor(g[pred], g[human]) if len(g) >= min_n else pooled
    return out


def apply_calibration(ate: pd.DataFrame, lam: dict, family_of=None) -> pd.DataFrame:
    """Multiply predicted ATEs by the fitted slope for their family."""
    d = ate.copy()
    fam = d.outcome.map(family_of) if family_of else pd.Series("_pooled", index=d.index)
    d["ate"] = d.ate * fam.map(lambda f: lam.get(str(f), lam["_pooled"])).astype(float)
    return d


FAMILY = {
    "trust_multidimensional": "trust", "trust_post": "trust", "distrust_post": "trust",
    "inst_trust_mean": "trust", "funding_perceptions": "policy", "policy_role_mean": "policy",
    "policy_general": "policy", "policy_specific_mean": "policy", "belief_post": "belief",
    "concern_mean": "belief", "behavior_mean": "behaviour",
    "donation_ams": "behaviour", "newsletter_signup": "behaviour",
}


# --------------------------------------------------------------------------
# the scripted stub - NOT a predictor
# --------------------------------------------------------------------------

STUB_MODEL = "stub-scripted-v1"


def stub_completion(user: str, system: str, seed: int = 0) -> str:
    """Return a CSV in the predictor's own output format, WITHOUT calling a model.

    This exists so the loop's plain-code stages (parse -> score -> calibrate -> card ->
    synthesise -> validate -> gates) can be exercised end to end when no simulator
    credential is provisioned. It is a scripted function of the cell's NAMES and a seed:
    it has read no message text and knows nothing. A number it produces is not a
    prediction and must never be recorded as a practice score - runs that use it carry
    stage="dryrun-stub" on the scoreboard and `stub: true` in the card meta.
    """
    import hashlib as _h
    conds, outs = _stub_grid(user)
    lines = ["condition,outcome,ate"]
    for c in conds:
        for o in outs:
            h = int(_h.sha256(f"{seed}|{c}|{o}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
            val = (h - 0.35) * 4.0                      # roughly -1.4 .. +2.6 pp
            if "distrust" in o:
                val = -val
            lines.append(f"{c},{o},{val:.2f}")
    return "\n".join(lines)


def _stub_grid(user: str) -> tuple[list[str], list[str]]:
    """Recover the condition and outcome names from the prompt the stub was handed."""
    outs = re.findall(r"^- ([A-Za-z0-9_]+) \| ", user, flags=re.M)
    conds = re.findall(r"^### (.+)$", user, flags=re.M)
    return conds, outs


def to_native(ate: pd.DataFrame, col: str = "ate") -> pd.DataFrame:
    """pp -> native units. The predictor answers in percentage points of each
    outcome's scale range (the frozen scoring unit); ssb.card stores native units,
    because Tier-1 rows and Tier-2 means are in native units. Forgetting this
    conversion is silent on the eleven 0-100 sliders (1 pp = 1 unit) and catastrophic
    on donation_ams ($1 = 10 pp) and newsletter_signup (1 pp = 0.01), where it asks
    the card for effects the scale cannot deliver - caught by card.clipping_report()
    in run 20260815-dryrun-01."""
    d = ate.copy()
    d[col] = [spec.from_pp(v, o) for v, o in zip(d[col], d.outcome)]
    return d


# --------------------------------------------------------------------------
# prompt budget: what actually fits in one context, and what to do when it does not
# --------------------------------------------------------------------------

def n_tokens(text: str) -> int:
    """Token count. `tiktoken`'s cl100k is a PROXY for the target model's tokenizer -
    measured against it on this harness's own briefs it runs within a few percent of
    chars/4, and the budget policy below is stated with enough headroom to absorb that.
    Falls back to chars/4 when tiktoken is not installed."""
    try:
        import tiktoken
        return len(tiktoken.get_encoding("cl100k_base").encode(text))
    except Exception:
        return int(len(text) / 4)


def _truncate(text: str, cap: int) -> str:
    """Cut at a paragraph boundary and SAY SO in the text the predictor reads.
    A silent truncation is a prompt the run report cannot describe."""
    if len(text) <= cap:
        return text
    cut = text.rfind("\n\n", 0, cap)
    cut = cut if cut > cap * 0.6 else cap
    return (text[:cut].rstrip() +
            f"\n\n[... stimulus truncated for prompt budget: {cut:,} of {len(text):,} "
            f"characters shown; the omitted remainder continues in the same style ...]")


def plan_prompts(brief: dict, budget_tokens: int = 60000, per_arm_char_cap: int = 8000,
                 n_anchor: int = 2) -> dict:
    """Split one brief into prompts that fit a context budget, deterministically.

    The order of preference is set by what each remedy costs:

      1. NOTHING - if the assembled prompt fits, send it whole. Every arm in one
         context is what lets the predictor rank arms against each other.
      2. TRUNCATE a single arm whose own text exceeds `per_arm_char_cap`, at a
         paragraph boundary, with a visible marker. Costs content within one arm.
      3. SPLIT the arms across parts, each part carrying the control text(s) and the
         same `n_anchor` anchor arms. Costs cross-arm calibration between parts -
         which is why the anchors are repeated: the spread of an anchor arm's
         predictions ACROSS parts measures that cost instead of assuming it away.

    Summarising is deliberately NOT an option: a second model rewriting the stimulus
    changes the thing being predicted, and the predictor would no longer have read the
    message it is predicting.
    """
    b = json.loads(json.dumps(brief))
    trunc = {}
    for a in b["arms"]:
        t = a.get("text") or ""
        if len(t) > per_arm_char_cap:
            a["text"] = _truncate(t, per_arm_char_cap)
            trunc[a["title"]] = {"chars_before": len(t), "chars_after": len(a["text"])}
    _, user = build_prompt(b)
    whole = n_tokens(user)
    plan = {"task_id": b.get("task_id"), "n_arms": len(b["arms"]),
            "tokens_whole": whole, "budget_tokens": budget_tokens,
            "truncated_arms": trunc, "policy": "whole", "parts": 1, "anchors": []}
    if whole <= budget_tokens:
        return {**plan, "briefs": [b]}

    titles = sorted(a["title"] for a in b["arms"])
    anchors = [titles[0], titles[-1]][:max(0, min(n_anchor, len(titles) - 1))]
    rest = [t for t in titles if t not in anchors]
    by_title = {a["title"]: a for a in b["arms"]}
    fixed_tokens = whole - sum(n_tokens(by_title[t].get("text") or "") for t in titles)
    anchor_tokens = sum(n_tokens(by_title[t].get("text") or "") for t in anchors)
    room = budget_tokens - fixed_tokens - anchor_tokens
    # Longest-processing-time packing: fix the number of parts first, then balance them.
    # Greedy left-to-right packing would leave a fat part and a thin one, i.e. two prompts in
    # two different context regimes - the exact thing the budget is meant to prevent.
    tok = {t: n_tokens(by_title[t].get("text") or "") for t in rest}
    k = max(1, int(np.ceil(sum(tok.values()) / max(room, 1))))
    buckets: list[list] = [[] for _ in range(k)]
    load = [0] * k
    for t in sorted(rest, key=lambda x: -tok[x]):
        i = int(np.argmin(load))
        buckets[i].append(t)
        load[i] += tok[t]
    parts = [sorted(b) for b in buckets if b]
    briefs = []
    for k, group in enumerate(parts):
        pb = json.loads(json.dumps(b))
        keep = sorted(set(group) | set(anchors))
        pb["arms"] = [by_title[t] for t in keep]
        pb["task_id"] = f"{b.get('task_id','task')}__part{k + 1}of{len(parts)}"
        pb["note"] = ((b.get("note", "") + " ") if b.get("note") else "") + (
            f"This is part {k + 1} of {len(parts)}: the arms below are a subset of the "
            f"study's {len(titles)} arms, all measured against the same control. "
            f"Predict them on the study's own scale, not relative to each other.")
        briefs.append(pb)
    return {**plan, "policy": "split", "parts": len(parts), "anchors": anchors,
            "tokens_per_part": [n_tokens(build_prompt(x)[1]) for x in briefs], "briefs": briefs}


def anchor_spread(frames: dict, anchors: list) -> pd.DataFrame:
    """How much did SPLITTING the prompt change the answer? One row per anchor cell:
    the spread of that cell's predicted ATE across the parts that all contained it.
    This is the cost of `plan_prompts`'s split policy, measured rather than assumed."""
    d = pd.concat([f.assign(_part=k) for k, f in frames.items()])
    d = d[d.condition.isin(anchors)]
    g = d.groupby(["condition", "outcome"])["ate"]
    return g.agg(["median", "std", "min", "max", "count"]).reset_index()
