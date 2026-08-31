#!/usr/bin/env python
"""What did paying for three draws actually buy, in SCORE terms?

Standing finding 29 measured that independent draws disagree by only 0.077-0.151 pp per cell against
an RMSE of 2.6 pp, and concluded that more draws are not worth buying. That is an argument about a
dispersion. This is the direct measurement the cached transcripts allow: score every SINGLE draw the
way the scoreboard scores the panel, and compare.

    /opt/kernel/venv/bin/python tools/draws_value.py

It re-parses each draw through the same plan_prompts split policy the run used, so a split task's
parts are reassembled exactly as they were, and it costs nothing - every transcript is already on
disk and already paid for.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402
from ssb import score as S  # noqa: E402

TASKS = ["voelkel2026", "goldwert2026", "vlasceanu2024", "bbprime2025", "voelkel2024"]


def draw_frames(run, t, draws=3):
    """Rebuild each draw's prediction from the transcripts on disk.

    It used to re-run `plan_prompts` and parse part i's transcript against part i's arm list, on the
    assumption that today's split is the split that was paid for. It is not: on `voelkel2024` the
    arm->part assignment has changed since the batch was bought, so 7 of 13 arms in each part were
    looked for in the wrong transcript and 135 of 234 cells came back NaN - silently, because a
    dropna downstream just made the task smaller. Every part transcript is therefore parsed against
    the WHOLE brief's arms and outcomes and the parts are unioned; a cell answered in any part is
    found, and a cell answered in none stays NaN. Verified against each run's own `prediction.csv`
    (written at call time, with the correct split) by `tools/test_draw_frames.py`.
    """
    b = json.loads((run / "tasks" / t / "brief" / "task.json").read_text())
    plan = ssb.predict.plan_prompts(b, budget_tokens=24000, per_arm_char_cap=12000)
    n_parts = len(plan["briefs"])
    conds = [a["title"] for a in b["arms"]]
    outs = ([o["name"] for o in b["outcomes"]] if isinstance(b["outcomes"], list)
            else list(b["outcomes"]))
    out = []
    for dr in range(draws):
        got = []
        for i in range(n_parts):
            f = run / "tasks" / t / ("transcript_draw%d_part%d.txt" % (dr, i + 1))
            if not f.exists():
                return []
            got.append(ssb.predict.parse(f.read_text(), conds, outs))
        g = pd.concat(got)
        # first NON-NULL answer per cell, not merely the first row (the parts each return a full
        # grid, so "first" alone would keep part 1's NaN over part 2's real number)
        # kind="stable" is load-bearing: the parts are in call order, and where two parts both
        # answered a shared anchor arm the run kept the EARLIER part's number. A default
        # (quicksort) sort silently reorders the ties and picks the other one - which is exactly
        # the 3-cell disagreement this test caught on voelkel2024.
        g = g.sort_values("ate", kind="stable", key=lambda s: s.isna()) \
             .drop_duplicates(["condition", "outcome"], keep="first")
        out.append(g.sort_values(["condition", "outcome"]).reset_index(drop=True))
    return out


def score(truth, fr):
    m = (truth.merge(fr[["condition", "outcome", "ate"]].rename(columns={"ate": "pred"}),
                     on=["condition", "outcome"]).rename(columns={"ate": "human"})
         .dropna(subset=["pred"]))
    return (S.directional_agreement(m.pred, m.human), S.spearman_rho(m.pred, m.human),
            S.rmse_pp(m.pred, m.human), len(m))


def main(run, draws=3):
    run = Path(run)
    rows = []
    print("\n%-15s%6s   %-22s%-24s%s" % ("task", "cells", "ONE draw (mean of 3)",
                                          "%d-draw median" % draws, "one-draw RMSE range"))
    for t in TASKS:
        fs = draw_frames(run, t, draws)
        if not fs:
            continue
        truth = pd.read_csv(run / "tasks" / t / "sealed" / "truth.csv")
        singles = [score(truth, f) for f in fs]
        med = score(truth, ssb.predict.aggregate(fs))
        r = {"task": t, "n_cells": med[3],
             "dir_1": np.mean([s[0] for s in singles]), "dir_med": med[0],
             "rho_1": np.mean([s[1] for s in singles]), "rho_med": med[1],
             "rmse_1": np.mean([s[2] for s in singles]), "rmse_med": med[2],
             "rmse_1_best": min(s[2] for s in singles), "rmse_1_worst": max(s[2] for s in singles)}
        rows.append(r)
        print("%-15s%6d   %.3f/%+.3f/%5.2f     %.3f/%+.3f/%5.2f        %.2f-%.2f"
              % (t, r["n_cells"], r["dir_1"], r["rho_1"], r["rmse_1"],
                 r["dir_med"], r["rho_med"], r["rmse_med"], r["rmse_1_best"], r["rmse_1_worst"]))
    d = pd.DataFrame(rows)
    if not len(d):
        return d
    print("\nMEAN  one draw     dir %.4f  rho %+.4f  rmse %.4f" % (d.dir_1.mean(), d.rho_1.mean(),
                                                                   d.rmse_1.mean()))
    print("MEAN  %d-draw median dir %.4f  rho %+.4f  rmse %.4f" % (draws, d.dir_med.mean(),
                                                                   d.rho_med.mean(), d.rmse_med.mean()))
    print("\nWHAT THE PANEL BOUGHT: dir %+.4f, rho %+.4f, rmse %+.4f pp"
          % (d.dir_med.mean() - d.dir_1.mean(), d.rho_med.mean() - d.rho_1.mean(),
             d.rmse_1.mean() - d.rmse_med.mean()))
    out = run / "stages" / "calibration" / "draws_value.csv"
    d.to_csv(out, index=False)
    print("written ->", out)
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="runs/20260815-practice-01")
    ap.add_argument("--draws", type=int, default=3)
    a = ap.parse_args()
    main(a.run, a.draws)
