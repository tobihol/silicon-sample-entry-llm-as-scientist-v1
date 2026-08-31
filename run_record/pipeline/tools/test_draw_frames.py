#!/usr/bin/env python
"""Does the reconstruction of a paid draw agree with what the run itself wrote?

    /opt/kernel/venv/bin/python tools/test_draw_frames.py

Every offline analysis tool here (`draws_value`, `draw_scaling`, `prompt_experiment`,
`length_robustness`, `model_selection`) re-parses the transcripts on disk rather than trusting a
stored aggregate, which is right - it is what lets a single draw be scored the way the panel was.
But it had NO test against the artefact the run wrote at call time, and it was wrong: the old
`draw_frames` re-ran `plan_prompts` and assumed today's arm->part split is the split that was paid
for. On `voelkel2024` it is not, and 135 of 234 cells reconstructed as NaN.

This compares, for every run that has transcripts, the median over its draws against that run's own
`prediction.csv` - the file written by `tools/practice.py` when the calls were made, with the plan
that made them. It also asserts the RED path: the old part-wise reconstruction must disagree on
`voelkel2024`, so the defect stays detectable if anyone reintroduces it.
"""
import json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(RUN / "tools"))
import ssb  # noqa: E402
from draws_value import draw_frames  # noqa: E402

RUNS = {"runs/20260815-practice-01": 3, "runs/20260815-practice-02-fable": 1,
        "runs/20260817-practice-t67": 3, "runs/20260817-practice-fable-t67": 1,
        "runs/20260818-recheck-t67": 3, "runs/20260818-practice-sonnet": 1}

# HISTORY, kept because the exemption it granted is the reason the reparse exists. One stored
# artefact did NOT reproduce: session 10 hardened `ssb.predict.parse` (the `message_01` numeric
# fold, finding 70) AFTER 20260817-practice-t67 had written its prediction.csv, so 23 of that
# task's 292 cells were parsed by the older parser. Session 12 re-derived the whole board through
# one parser (`tools/reparse_audit.py --write`), which rewrote that prediction.csv (backup:
# prediction.csv.pre-reparse) and its scoreboard row, so the exemption is now EMPTY and a
# reappearance of the mismatch is a failure again rather than a known condition.
KNOWN_DRIFT = {}


def old_draw_frames(run, t, draws=3):
    """The reconstruction this test exists to refuse: part i parsed against today's part i."""
    b = json.loads((run / "tasks" / t / "brief" / "task.json").read_text())
    plan = ssb.predict.plan_prompts(b, budget_tokens=24000, per_arm_char_cap=12000)
    out = []
    for dr in range(draws):
        got = []
        for i, pb in enumerate(plan["briefs"]):
            f = run / "tasks" / t / ("transcript_draw%d_part%d.txt" % (dr, i + 1))
            if not f.exists():
                return []
            conds = [a["title"] for a in pb["arms"]]
            outs = ([o["name"] for o in pb["outcomes"]] if isinstance(pb["outcomes"], list)
                    else list(pb["outcomes"]))
            got.append(ssb.predict.parse(f.read_text(), conds, outs))
        out.append(pd.concat(got).drop_duplicates(["condition", "outcome"], keep="first"))
    return out


def main():
    bad = 0
    print(f"{'run':>38}{'task':>16}{'cells':>7}{'nan':>5}{'max|diff|':>11}{'  verdict'}")
    for run, draws in RUNS.items():
        d = RUN / run
        if not d.exists():
            continue
        for tdir in sorted((d / "tasks").glob("*")):
            t = tdir.name
            if not (tdir / "prediction.csv").exists():
                continue
            fs = draw_frames(d, t, draws)
            if not fs:
                continue
            agg = ssb.predict.aggregate(fs)
            got = pd.read_csv(tdir / "prediction.csv")
            m = got.merge(agg[["condition", "outcome", "ate"]], on=["condition", "outcome"],
                          how="left", suffixes=("_run", "_rebuilt"))
            diff = (m.ate_run - m.ate_rebuilt).abs()
            nan = int(m.ate_rebuilt.isna().sum() - m.ate_run.isna().sum())
            worst = float(np.nanmax(diff.values)) if len(diff) else 0.0
            ok = (worst <= 1e-9) and nan <= 0 and len(m) == len(got)
            drift = (run, t) in KNOWN_DRIFT
            bad += (not ok and not drift)
            verdict = "  ok" if ok else ("  DRIFT (known: %s)" % KNOWN_DRIFT[(run, t)]
                                         if drift else "  MISMATCH")
            print(f"{run:>38}{t:>16}{len(m):>7}{nan:>5}{worst:>11.2e}{verdict}")

    # red path: the defect must remain visible
    d = RUN / "runs/20260815-practice-01"
    old = old_draw_frames(d, "voelkel2024", 3)
    new = draw_frames(d, "voelkel2024", 3)
    n_old = int(ssb.predict.aggregate(old).ate.isna().sum())
    n_new = int(ssb.predict.aggregate(new).ate.isna().sum())
    print(f"\nred path  voelkel2024: old reconstruction NaN cells {n_old}, fixed {n_new}")
    if not (n_old > 0 and n_new == 0):
        print("RED PATH FAILED: the old defect no longer shows, so this test proves nothing")
        bad += 1

    print("\n%s" % ("ALL RECONSTRUCTIONS MATCH THE RUN'S OWN prediction.csv" if not bad
                    else "%d MISMATCH(ES)" % bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
