#!/usr/bin/env python
"""The gate machinery's own failure modes, tested. No model calls, no spend.

    /opt/kernel/venv/bin/python tools/test_gates.py

Every run so far has been green, so the code that is supposed to STOP a run had never run.
"A gate that passes on the seed is not a gate" (standing finding 18) has a sibling: a gate that
has never failed has not been shown to stop anything. This exercises the red paths.
"""
import json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402

RUN = Path(__file__).resolve().parents[1]
CASES = []


def case(name):
    def deco(f):
        CASES.append((name, f))
        return f
    return deco


@case("a red gate makes the run un-closeable")
def _():
    d = Path(tempfile.mkdtemp()) / "r"
    d.mkdir(parents=True)
    (d / "gates.json").write_text(json.dumps(
        {k: {"passed": True, "detail": "", "at": ""} for k in ssb.gates.GATES}))
    assert ssb.gates.verdict(d)["may_finish"] is True
    g = json.loads((d / "gates.json").read_text())
    g["G6_reconstruction"]["passed"] = False
    (d / "gates.json").write_text(json.dumps(g))
    v = ssb.gates.verdict(d)
    assert v["may_finish"] is False and v["failed"] == ["G6_reconstruction"], v
    return "verdict: may_finish False, failed=['G6_reconstruction']"


@case("a missing gate makes the run un-closeable")
def _():
    d = Path(tempfile.mkdtemp()) / "r"
    d.mkdir(parents=True)
    (d / "gates.json").write_text(json.dumps(
        {k: {"passed": True, "detail": "", "at": ""} for k in list(ssb.gates.GATES)[:-1]}))
    v = ssb.gates.verdict(d)
    assert v["may_finish"] is False and v["complete"] is False and len(v["missing"]) == 1, v
    return "verdict: complete False, missing=%s" % v["missing"]


@case("tools/target.py refuses to close on a red gate")
def _():
    src = (RUN / "tools" / "target.py").read_text()
    assert 'if not v["may_finish"]:' in src and "RUN NOT CLOSEABLE" in src, \
        "target.py no longer raises on a red gate"
    return "target.py raises SystemExit('RUN NOT CLOSEABLE') after writing every artefact"


@case("an unknown gate name is refused")
def _():
    d = Path(tempfile.mkdtemp()) / "r"
    d.mkdir(parents=True)
    try:
        ssb.gates.record(d, "G9_invented_by_me", True, "")
    except KeyError as e:
        return "KeyError: %s" % str(e)[:60]
    raise AssertionError("an invented gate name was accepted")


@case("a scoreboard row without an explicit stub flag is refused")
def _():
    try:
        ssb.gates.scoreboard_append({"run_id": "x", "task_id": "y", "n_cells": 1})
    except KeyError as e:
        return "KeyError: %s" % str(e)[:70]
    raise AssertionError("a row with no stub flag was appended - a scripted number could be "
                         "read as a practice score")


@case("the frozen file's hash is what G1 compares against")
def _():
    h = ssb.gates.frozen_hash()
    assert isinstance(h, str) and len(h) == 64, h
    return "frozen sha256 %s..." % h[:16]


@case("a deposit filename must be primary or secondary-k (run against make check)")
def _():
    """Measured, not read off the source: the RUNBOOK claims anything but primary|secondary-k
    fails the filename check, and that claim had never been executed."""
    import hashlib, shutil
    src = next((RUN / "runs").glob("*/submission_T1"), None)
    if src is None:
        return "SKIPPED - no submission_T1 on disk to mutate"
    out = []
    for entry, want in (("secondary-2", "PASS"), ("tertiary", "FAIL"), ("primary2", "FAIL")):
        base = Path(tempfile.mkdtemp())
        d = base / "s"
        shutil.copytree(src, d)
        for f in (d / "predictions").glob("*.csv"):
            f.rename(d / "predictions" / ("sodalab_T1_%s_v1.csv" % entry))
        f = d / "predictions" / ("sodalab_T1_%s_v1.csv" % entry)
        m = json.loads((d / "metadata.json").read_text())
        m["entry"] = entry
        m["prediction_files"] = [{"file": "predictions/" + f.name,
                                  "sha256": hashlib.sha256(f.read_bytes()).hexdigest()}]
        (d / "metadata.json").write_text(json.dumps(m, indent=2))
        rc = subprocess.run(["make", "check"], cwd=d, capture_output=True, text=True).returncode
        got = "FAIL" if rc else "PASS"
        assert got == want, "entry=%s expected %s got %s" % (entry, want, got)
        out.append("%s->%s" % (entry, got))
        shutil.rmtree(base, ignore_errors=True)
    return "make check: " + ", ".join(out)


@case("verify_deposit --strict rejects a deposit that is not team_31")
def _():
    """TASK_08 fixed the team id at `team_31`. `check.R` only rejects the template's own example
    id, so `sodalab` - a placeholder this harness invented - passed the validator green for eight
    runs. The check is only a check if the wrong id fails it, so the red path is forced here on a
    COPY of a real run (the deposit itself is never mutated)."""
    import shutil
    src = next((m.parents[1] for m in sorted((RUN / "runs").glob("*/submission_T1/metadata.json"))
                if json.loads(m.read_text()).get("team_id") == "team_31"), None)
    if src is None:
        return "SKIPPED - no team_31 deposit on disk"
    base = Path(tempfile.mkdtemp(dir=str(RUN / "runs")))
    d = base / "r"
    shutil.copytree(src, d, ignore=shutil.ignore_patterns("raw_model_logs"))
    tool = str(RUN / "tools" / "verify_deposit.py")
    rel = str(d.relative_to(RUN))
    try:
        green = subprocess.run([sys.executable, tool, rel], capture_output=True, text=True)
        assert "[PASS] team_id is team_31" in green.stdout, green.stdout[-400:]
        for tier in (1, 2, 3):
            md = d / f"submission_T{tier}" / "metadata.json"
            m = json.loads(md.read_text())
            m["team_id"] = "sodalab"
            md.write_text(json.dumps(m, indent=2))
        red = subprocess.run([sys.executable, tool, rel, "--strict"], capture_output=True, text=True)
        assert red.returncode != 0, "wrong team id still exited 0"
        assert "[FAIL] team_id is team_31" in red.stdout, red.stdout[-400:]
        # and the filename stamp is a second, independent hold
        assert "[FAIL] prediction filenames stamped" not in green.stdout
    finally:
        shutil.rmtree(base, ignore_errors=True)
    return "team_31 PASS / sodalab FAIL (exit %d)" % red.returncode


@case("a deposit built outside the Aug 28-31 window is marked NOT-FOR-PUBLICATION")
def _():
    import datetime as dt
    sys.path.insert(0, str(RUN / "tools"))
    import verify_deposit as VD
    assert (VD.WINDOW_OPEN, VD.WINDOW_CLOSE) == (dt.date(2026, 8, 28), dt.date(2026, 8, 31))
    src = next((m for m in sorted((RUN / "runs").glob("*/submission_T1/metadata.json"))
                if json.loads(m.read_text()).get("team_id") == "team_31"), None)
    if src is None:
        return "SKIPPED - no team_31 deposit on disk"
    md = json.loads(src.read_text())
    today = dt.date.today()
    inw = VD.WINDOW_OPEN <= today <= VD.WINDOW_CLOSE
    assert md.get("not_for_publication_before") == VD.WINDOW_OPEN.isoformat(), md.get(
        "not_for_publication_before")
    assert ("NOT-FOR-PUBLICATION" in md.get("publication_status", "")) == (not inw), md.get(
        "publication_status")
    return "today %s -> %s" % (today, md["publication_status"][:48])


@case("the budget ceiling refuses a call it cannot cover")
def _():
    """Finding 27 applies to the budget guard too: a guard that has never fired has not been shown
    to stop anything. Two properties. (a) It reserves headroom - an earlier version checked only
    whether the ceiling was ALREADY crossed and so overshot by a whole call, measured at 74,574
    against a 60,000 ceiling on tools/fake/claude. (b) A cache hit is already-paid money and counts
    against the ceiling, so the ceiling governs the BATCH and not the session."""
    sys.path.insert(0, str(RUN / "tools"))
    import practice as P
    saved = dict(P.LEDGER)
    try:
        P.LEDGER.update({"ceiling_tokens": 100_000, "billed_tokens": 60_000,
                         "prior_billed_tokens": 0, "paid_calls": 3, "path": None, "stopped": None})
        P._ledger_guard("a small call", 10_000)                    # 70k <= 100k: must be allowed
        crossed = False
        try:
            P._ledger_guard("a big call", 50_000)                  # 110k > 100k: must refuse
        except SystemExit:
            crossed = True
        assert crossed, "the guard allowed a call that would cross the ceiling"
        P.LEDGER.update({"billed_tokens": 10_000, "prior_billed_tokens": 50_000, "stopped": None})
        crossed = False
        try:
            P._ledger_guard("a big call", 50_000)
        except SystemExit:
            crossed = True
        assert crossed, "cache hits did not count against the ceiling"
        return "refuses a call it cannot cover; cache hits count as already paid"
    finally:
        P.LEDGER.clear()
        P.LEDGER.update(saved)


@case("the billed estimator is the one that was right")
def _():
    """tiktoken alone was 2.44x low on the only batch ever paid for; the billed estimator was 0.3%
    high on the same batch. If either measured factor is edited away, this fails."""
    sys.path.insert(0, str(RUN / "tools"))
    import practice as P
    actual, tiktoken_est, billed_est = 941_504, 386_564, 944_474   # run 20260815-practice-01
    assert abs(billed_est / actual - 1) < 0.02, "billed estimator drifted from the measured batch"
    assert P.BILLED_INPUT_FACTOR > 2.5, "the CLI overhead factor went missing"
    assert P.OUT_TOKENS_PER_CELL == 19, "output tokens per cell is not the measured value"
    return ("billed est/actual %.3f vs tiktoken est/actual %.3f"
            % (billed_est / actual, tiktoken_est / actual))


@case("a target blinding event stops stage 5 before it predicts")
def _():
    """The frozen file: "You never seek, ingest, or infer from human outcome data of the target
    study - including its pilots, preprints about it, or anything derived from them. If you
    encounter any, stop, record where, and tell the operator." Stage 5a asks the predictor directly.
    This proves the YES branch aborts BEFORE any prediction call, rather than recording a worry and
    carrying on - the failure mode that would put a contaminated prediction in a deposit."""
    sys.path.insert(0, str(RUN / "tools"))
    import practice as P
    import target as T

    calls = []
    real = P.call

    def fake_call(user, system, model, execute, **sampling):
        calls.append(sampling)
        if sampling.get("stage") == "target_probe":
            return ("STUDY: the climate-trust megastudy\nAUTHORS: known\n"
                    "CONFIDENCE: 91\nRESULTS_KNOWN: YES\n"), "k" * 64, False
        return "condition,outcome,ate\n", "k" * 64, False

    P.call = fake_call
    try:
        d = Path(tempfile.mkdtemp()) / "blind"
        try:
            T.main(str(RUN / "runs/20260815-practice-01"), "claude-opus-5", draws=3,
                   execute=True, approved=True, run_id="ZZ-blinding-redpath-test")
            return "FAIL: no abort"
        except SystemExit as e:
            assert "BLINDING EVENT" in str(e), "wrong abort: %s" % e
            stages = [c.get("stage") for c in calls]
            assert stages == ["target_probe"], \
                "a prediction call was made after the blinding event: %s" % stages
            shutil.rmtree(RUN / "runs" / "ZZ-blinding-redpath-test", ignore_errors=True)
            return "SystemExit('BLINDING EVENT...') after 1 probe call and 0 prediction calls"
    finally:
        P.call = real


@case("a truncated TARGET arm aborts stage 5")
def _():
    """Finding 17 capped arms at 12,000 chars so a practice prompt stays in the target's size band,
    and asserted the target is "provably never truncated". Measured: the longest target arm is
    11,134 chars, 92.8% of the cap - 866 chars of headroom, not the comfortable margin the wording
    implies. A re-extraction that adds whitespace would cross it, and the only symptom would be a
    slightly better score on a stimulus no respondent saw. So the abort is tested, with the cap
    lowered to force the condition the real cap is one edit away from."""
    sys.path.insert(0, str(RUN / "tools"))
    import target as T
    import ssb as _ssb

    b = _ssb.predict.target_brief()
    longest = max(len(a.get("text", "")) for a in b["arms"])
    assert longest < 12000, "the real cap ALREADY bites: longest arm %d" % longest
    headroom = 12000 - longest

    real = _ssb.predict.plan_prompts
    _ssb.predict.plan_prompts = (lambda brief, budget_tokens=24000, per_arm_char_cap=12000:
                                 real(brief, budget_tokens=budget_tokens,
                                      per_arm_char_cap=longest - 100))
    try:
        T.main(str(RUN / "runs/20260815-practice-01"), "claude-opus-5", draws=3,
               run_id="ZZ-truncation-redpath-test")
        return "FAIL: no abort"
    except SystemExit as e:
        assert "TARGET ARM TRUNCATED" in str(e), "wrong abort: %s" % e
        return "SystemExit('TARGET ARM TRUNCATED...'); real headroom is %d chars (%.1f%% of cap)" % (
            headroom, 100 * longest / 12000)
    finally:
        _ssb.predict.plan_prompts = real
        shutil.rmtree(RUN / "runs" / "ZZ-truncation-redpath-test", ignore_errors=True)


@case("a scoreboard row parsed by a stale parser is flagged")
def _():
    """Finding 72: a stored prediction is a parser version as much as a model answer, and the board
    carried rows from two versions with nothing recording it. A pairs.csv check cannot see this -
    the row and its pairs move together - so the alarm has to be the recorded version itself."""
    sys.path.insert(0, str(RUN / "tools"))
    import pandas as pd
    import verify_scoreboard as V
    import reparse_audit as R

    today = ssb.predict.parser_version()
    assert R.main.__module__ and today == V.ssb.predict.parser_version()
    sb = pd.DataFrame([
        {"run_id": "A", "task_id": "t", "stub": False, "parser_version": today},
        {"run_id": "B", "task_id": "t", "stub": False, "parser_version": "deadbeef0000"},
        {"run_id": "C", "task_id": "t", "stub": True, "parser_version": "deadbeef0000"},
        {"run_id": "D", "task_id": "t", "stub": False, "parser_version": "unverified"}])
    n = V.parser_report(sb)
    assert n == 1, "expected exactly the stale PAID row to be flagged, got %d" % n
    clean = V.parser_report(sb[sb.parser_version != "deadbeef0000"])
    assert clean == 0, "a board with no stale paid row must not raise the alarm"
    # and a row appended today must carry today's version, not a blank
    assert "parser_version" in ssb.gates.SCOREBOARD.read_text().splitlines()[0]
    return "stale PAID row flagged (1), stub and unverified rows not, board header carries the column"


@case("every declared dependency imports in the run interpreter")
def _():
    """Standing finding 97, made cheap and made recurrent. `openpyxl` was installed in session 16
    and was ABSENT AGAIN at the start of session 17, so the fix does not survive the session
    boundary and the lesson has to be a CHECK, not an installation. Two of the five original
    practice tasks cannot be carved without these: vlasceanu2024 (.xlsx) and voelkel2024 (.sav)."""
    import tomllib
    deps = tomllib.loads((RUN.parent / "pyproject.toml").read_text())["project"]["dependencies"]
    mod = {"openpyxl": "openpyxl", "pyreadstat": "pyreadstat", "pandas": "pandas",
           "numpy": "numpy", "scipy": "scipy"}
    missing = []
    for d in deps:
        name = d.split(">")[0].split("=")[0].split("<")[0].strip()
        m = mod.get(name, name.replace("-", "_"))
        r = subprocess.run([sys.executable, "-c", "import %s" % m], capture_output=True, text=True)
        if r.returncode != 0:
            missing.append(name)
    assert not missing, ("declared but not importable: %s. Two of the five original practice "
                         "tasks cannot be carved without them." % missing)
    return "%d declared dependencies, all importable" % len(deps)


@case("a brief that gives one arm two names is refused before the batch")
def _():
    """MEASURED on a paid batch this session. kim2024's adapter renamed the raw condition codes
    to readable titles and left the raw codes in the sample description's arm-size sentence;
    `claude-opus-5` answered with the raw code and the parser - correctly (finding 70) - refused a
    name it was not given, losing all 22 cells after the calls were paid for. Neither a model
    error nor a parse error: the brief was ambiguous."""
    sys.path.insert(0, str(RUN / "tools"))
    import practice
    pre_fix = {"arms": {"control": "Control (unrelated text)", "consensus": "Scientific consensus",
                        "causal": "Causal evidence"}}
    bad = [{"sample": "3,007 U.S. adults (control n = 1,008, consensus n = 994, causal n = 1,005)",
            "arms": [{"title": "Scientific consensus", "text": "..."}], "outcomes": {},
            "instruction": ""}]
    good = [{"sample": "3,007 U.S. adults recruited on Amazon Mechanical Turk.",
             "arms": [{"title": "Scientific consensus", "text": "..."}], "outcomes": {},
             "instruction": ""}]
    # a raw code inside a STIMULUS must not fire: redacting a stimulus changes the task (f.22)
    in_stim = [{"sample": "clean", "arms": [{"title": "Scientific consensus",
                                             "text": "[block: consensus] the message"}],
                "outcomes": {}, "instruction": ""}]
    try:
        practice.assert_one_name_per_arm("kim2024", pre_fix, bad)
        raise AssertionError("the ambiguous brief was accepted")
    except SystemExit as e:
        assert "two names" in str(e), e
    practice.assert_one_name_per_arm("kim2024", pre_fix, good)     # must NOT raise
    practice.assert_one_name_per_arm("kim2024", pre_fix, in_stim)  # must NOT raise
    # and the STRUCTURAL fix: every shipped adapter of a NEW task maps each arm to itself
    for name in ("kim2024", "dablander2025"):
        a = ssb.task.load_adapter(name)
        assert all(str(k) == str(v) for k, v in a["arms"].items()), (name, a["arms"])
    return "ambiguous brief refused; clean brief and in-stimulus code accepted; new adapters identity-mapped"


@case("a condition name containing a CSV delimiter is refused before the batch")
def _():
    """MEASURED on a paid batch this session, one defect after the last. dablander2025's arms were
    titled `Civil disobedience, no scientist`; `claude-opus-5` quoted the field and parsed, while
    `claude-sonnet-5` dropped the comma so its row would still have three fields, and lost all 25
    cells. The harness chooses the names and the answer format is `condition,outcome,ate`."""
    sys.path.insert(0, str(RUN / "tools"))
    import practice
    bad = [{"arms": [{"title": "Civil disobedience, no scientist"}], "control_arms": ["Ctrl"],
            "outcomes": {"y": {}}}]
    try:
        practice.assert_csv_safe_names("t", bad)
        raise AssertionError("a comma in an arm title was accepted")
    except SystemExit as e:
        assert "delimiter" in str(e), e
    for ch in (";", "\t"):
        try:
            practice.assert_csv_safe_names("t", [{"arms": [{"title": "a%sb" % ch}],
                                                  "control_arms": [], "outcomes": {}}])
            raise AssertionError("%r accepted" % ch)
        except SystemExit:
            pass
    practice.assert_csv_safe_names("t", [{"arms": [{"title": "Civil disobedience - no scientist"}],
                                          "control_arms": ["Ctrl"], "outcomes": {"y": {}}}])
    # and every task on disk must now be clean
    import json as _j
    dirty = []
    for name in _j.loads((RUN / "inputs/recognition_keys.json").read_text())["tasks"]:
        ad = ssb.task.load_adapter(name)
        names = list(ad["arms"].values()) + list(ad["outcomes"])
        dirty += [(name, n) for n in names if any(c in str(n) for c in ",;\t")]
    assert not dirty, dirty
    return "comma/semicolon/tab arm titles refused, hyphen accepted, all 13 tasks clean"


# ------------------------------------------------------------------ parallel-arm safety
# The operator intends to run two concurrent sessions on separate arms against one runs/ mount.
# These four cases are the red paths for that: they run REAL concurrent processes against a
# throw-away SSB_RUNROOT, so they exercise the lock rather than assert that it is called.

_CHILD = r"""
import os, sys, time
sys.path.insert(0, %r)
os.environ["SSB_RUNROOT"] = sys.argv[1]
os.environ.setdefault("SSB_ARM", sys.argv[4] if len(sys.argv) > 4 else "")
import ssb
n, tag = int(sys.argv[2]), sys.argv[3]
for i in range(n):
    ssb.gates.scoreboard_append({"run_id": "%%s-%%d" %% (tag, i), "task_id": "t", "stub": True,
                                 "n_cells": 1, "note": "x" * int(sys.argv[5]),
                                 "parser_version": "test"})
"""


def _sandbox():
    root = Path(tempfile.mkdtemp())
    (root / "runs").mkdir()
    return root


def _spawn(root, n, tag, arm="", note=400):
    src = str(RUN / ".prime/agent/skills/ssb/src")
    p = Path(tempfile.mkdtemp()) / "child.py"
    p.write_text(_CHILD % src)
    return subprocess.Popen([sys.executable, str(p), str(root), str(n), tag, arm, str(note)],
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


@case("two concurrent scorers cannot corrupt the board")
def _():
    import pandas as pd
    root = _sandbox()
    # 300,000-char notes on purpose: a 400-char row fits in one write() and Linux does not tear
    # it, so a small-row test would pass against the UNLOCKED code too. Measured on the
    # pre-session-17 protocol at this size: 81 rows for 80 writes, TWO headers and one torn row
    # on 3 of 3 trials.
    ps = [_spawn(root, 20, "A", note=300_000), _spawn(root, 20, "B", note=300_000)]
    outs = [p.communicate() for p in ps]
    for (o, e), p in zip(outs, ps):
        assert p.returncode == 0, e[-800:]
    sb = pd.read_csv(root / "runs" / "scoreboard.csv")
    assert len(sb) == 40, "lost or duplicated rows: %d of 40" % len(sb)
    assert list(sb.columns) == ssb.gates.SCOREBOARD_COLS, sb.columns
    assert sb.run_id.nunique() == 40 and sb.note.map(len).eq(300_000).all(), "torn row"
    assert (root / "runs" / "scoreboard.csv").read_text().count("run_id,stage,stub") == 1, \
        "more than one header - two writers both thought the file was new"
    shutil.rmtree(root, ignore_errors=True)
    return "40/40 rows of 300k chars, one header, no torn row, columns intact"


@case("a duplicate (run_id, task_id) is refused under concurrency")
def _():
    import pandas as pd
    root = _sandbox()
    ps = [_spawn(root, 20, "SAME"), _spawn(root, 20, "SAME")]  # identical (run_id, task_id) stream
    outs = [p.communicate() for p in ps]
    rcs = [p.returncode for p in ps]
    assert sorted(rcs) == [0, 1] or rcs == [1, 1], "expected the loser to raise, got %s" % rcs
    err = "".join(e for _, e in outs)
    assert "scoreboard already has" in err, err[-600:]
    sb = pd.read_csv(root / "runs" / "scoreboard.csv")
    assert sb.duplicated(["run_id", "task_id"]).sum() == 0, "duplicate rows written concurrently"
    return "%d unique rows, no duplicate; the losing writer raised KeyError" % len(sb)


@case("a second arm cannot claim the first arm's run_id")
def _():
    root = _sandbox()
    env = dict(os.environ, SSB_RUNROOT=str(root), SSB_ARM="a")
    src = str(RUN / ".prime/agent/skills/ssb/src")
    code = ("import sys; sys.path.insert(0, %r); import ssb; "
            "print(ssb.gates.new_run('20260822-x'))" % src)
    r1 = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert r1.returncode == 0, r1.stderr
    assert r1.stdout.strip().endswith("20260822-x-a"), r1.stdout
    # same arm resumes the same directory
    r1b = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert r1b.returncode == 0 and r1b.stdout.strip().endswith("20260822-x-a"), r1b.stderr
    # the other arm gets its OWN id, and cannot take arm a's
    env2 = dict(env, SSB_ARM="b")
    r2 = subprocess.run([sys.executable, "-c", code], env=env2, capture_output=True, text=True)
    assert r2.returncode == 0 and r2.stdout.strip().endswith("20260822-x-b"), r2.stdout
    # arm b asking for arm a's id by name still cannot get it: the namespace suffix is applied
    # to whatever it asks for, so the two arms cannot address the same directory at all.
    steal = ("import sys; sys.path.insert(0, %r); import ssb; "
             "print(ssb.gates.new_run('20260822-x-a'))" % src)
    r3 = subprocess.run([sys.executable, "-c", steal], env=env2, capture_output=True, text=True)
    assert r3.returncode == 0 and r3.stdout.strip().endswith("20260822-x-a-b"), r3.stdout
    # the case namespacing CANNOT cover is an UNARMED process (the historical default) walking
    # into an armed run's id. That is what the claim registry is for.
    env0 = dict(os.environ, SSB_RUNROOT=str(root))
    env0.pop("SSB_ARM", None)
    r4 = subprocess.run([sys.executable, "-c", steal], env=env0, capture_output=True, text=True)
    assert r4.returncode != 0 and "is claimed by arm" in r4.stderr, r4.stdout + r4.stderr
    return ("arm a -> -x-a (resumable), arm b -> -x-b, arm b asking for -x-a gets -x-a-b; "
            "an UNARMED process asking for -x-a raises KeyError")


@case("the completions cache is content-keyed and written atomically")
def _():
    """(item 1b) Two writers can only ever target the same cache file when they are making the
    IDENTICAL call, because the filename is the sha256 of prompt+model+sampling. So the layout is
    collision-safe by construction and the only real hazard is a torn write."""
    a = ssb.predict.cache_key("u", "s", "m", draw=0)
    assert ssb.predict.cache_key("u", "s", "m", draw=0) == a, "cache key is not deterministic"
    for kw in [dict(user="u2"), dict(system="s2"), dict(model="m2"), dict(draw=1)]:
        args = dict(user="u", system="s", model="m", draw=0) | kw
        assert ssb.predict.cache_key(args["user"], args["system"], args["model"],
                                     draw=args["draw"]) != a, "key does not cover %s" % kw
    src = (RUN / "tools" / "practice.py").read_text()
    assert "ssb.gates._atomic_write(f, json.dumps(" in src, "cache write is not atomic"
    d = Path(tempfile.mkdtemp()) / "c.json"
    ssb.gates._atomic_write(d, '{"ok": 1}')
    assert json.loads(d.read_text())["ok"] == 1
    assert not list(d.parent.glob(".c.json.tmp*")), "temp file left behind"
    return "key covers prompt+model+sampling (4/4 perturbations change it); write is temp+os.replace"


@case("the deposited Tier-1 rows still reproduce from today's synthesis code")
def _():
    """Session 18 added three flags to `ssb.synth` (`rho` as a per-outcome dict,
    `spread_gamma`, `scale_on_control`) and each defaults to the deposited behaviour. A
    default that is *claimed* to be inert is not known to be inert: this re-synthesises
    `runs/20260815-target-01`'s 43,200 rows from that run's own card, at the deposited
    pool sizes and seed, and requires every one of the 33 columns to come back
    identical. It is the only check that stands between a synthesis edit and a deposit
    that silently stops reproducing from its card."""
    import numpy as np, pandas as pd
    d = RUN / "runs/20260815-target-01"
    if not (d / "stages/tier1.csv").exists():
        return "SKIP: no deposited tier1.csv on disk"
    want = pd.read_csv(d / "stages/tier1.csv")
    crd = ssb.card.Card.load(d / "card")
    got, _ = ssb.synth.synthesize(crd, pd.read_csv(RUN / "inputs/pool/joint.csv"),
                                  n_per_intervention=2400, n_control=4800, seed=0)
    assert list(got.columns) == list(want.columns), "column set changed"
    num = [c for c in want.columns if pd.api.types.is_numeric_dtype(want[c])]
    worst = max(float((want[c].astype(float) - got[c].astype(float)).abs().max()) for c in num)
    # 1e-12, not 0. `pandas.read_csv`'s float parser is not correctly rounded, so a
    # deposited CSV differs from the in-memory values that WROTE it by 1 ULP on ~13% of
    # the non-integer composite rows (1.42e-14 on a 0-100 scale). Measured, not assumed:
    # writing and re-reading 62.916666666666664 loses 7.1e-15. Every integer column here
    # reproduces at exactly 0.0. Standing finding 61 in a second place - byte equality is
    # the wrong test for "did the numbers change".
    assert worst < 1e-12, "deposited rows no longer reproduce: max |diff| = %g" % worst
    for c in want.columns:
        if c not in num:
            assert want[c].astype(str).equals(got[c].astype(str)), "column %s changed" % c
    return ("43,200 x 33 reproduce with all three flags at their defaults "
            "(max |diff| %.2g, the CSV reader's own 1 ULP)" % worst)


def main():
    print("%-52s%s" % ("case", "result"))
    fails = 0
    for name, f in CASES:
        try:
            r = f()
            print("%-52s%s" % (name, r))
        except Exception as e:
            fails += 1
            print("%-52sFAIL: %s" % (name, e))
    if fails:
        raise SystemExit("%d gate-machinery cases FAILED" % fails)
    print("\ngate machinery PASS: %d red-path cases" % len(CASES))


if __name__ == "__main__":
    main()
