#!/usr/bin/env python
"""Split each practice sample in half and score against ONE half - the way the target is scored.

Every practice number this harness has ever reported was measured against ground truth computed on
the FULL training sample. The target is scored against "Human 1", one half of the human sample, with
the other half as the replication ceiling (the frozen scoring table). So a practice score and a
target score do not mean the same thing, and `tools/forecast_target.py` prices that gap with a
Gaussian simulation.

This measures the same gap instead of simulating it, on real respondents: recompute each task's ATE
table on two random halves of its own sample, score the SAME predictions (already paid for, no model
call) against half 1, and score half 2 against half 1 for an empirical ceiling.

    /opt/kernel/venv/bin/python tools/split_half.py [--reps 20] [--run runs/<id>]

What it can and cannot say: the practice halves are the practice studies' own sizes, not the
target's, so the absolute numbers are not a target forecast. The RELATIONSHIPS are the point -
how much score is lost when the reference is halved, and whether a compressed prediction beats a
noisy replicate on RMSE, which is the claim in REPORT.md section 7c that a simulation should not be
the only evidence for.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402
from ssb import score as S  # noqa: E402

TASKS = ["voelkel2026", "goldwert2026", "vlasceanu2024", "bbprime2025", "voelkel2024"]


def metrics(pred, human):
    return (S.directional_agreement(pred, human), S.spearman_rho(pred, human),
            S.rmse_pp(pred, human))


def main(run, reps=20, seed=0):
    run = Path(run)
    rows = []
    for t in TASKS:
        pf = run / "tasks" / t / "prediction.csv"
        if not pf.exists():
            continue
        pred = pd.read_csv(pf)
        ad = ssb.task.load_adapter(t)
        df = ssb.task.load_dataset(ad)
        full = pd.read_csv(run / "tasks" / t / "sealed" / "truth.csv")
        f = full.merge(pred, on=["condition", "outcome"], suffixes=("_h", "_p"))
        full_m = metrics(f.ate_p, f.ate_h)

        rng = np.random.default_rng(seed)
        got, ceil, lost = [], [], []
        for _ in range(reps):
            half = rng.random(len(df)) < 0.5
            try:
                t1 = ssb.task.true_ates(df[half], ad)
                t2 = ssb.task.true_ates(df[~half], ad)
            except Exception:
                continue
            a = (t1.rename(columns={"ate": "h1"})[["condition", "outcome", "h1"]]
                 .merge(t2.rename(columns={"ate": "h2"})[["condition", "outcome", "h2"]],
                        on=["condition", "outcome"])
                 .merge(pred, on=["condition", "outcome"]).dropna())
            if len(a) < 10:
                continue
            got.append(metrics(a.ate, a.h1))
            ceil.append(metrics(a.h2, a.h1))
        if not got:
            continue
        g, c = np.array(got), np.array(ceil)
        rows.append({"task": t, "n_cells": len(f), "reps": len(got),
                     "full_dir": full_m[0], "full_rho": full_m[1], "full_rmse": full_m[2],
                     "half_dir": g[:, 0].mean(), "half_rho": g[:, 1].mean(),
                     "half_rmse": g[:, 2].mean(),
                     "ceil_dir": c[:, 0].mean(), "ceil_rho": c[:, 1].mean(),
                     "ceil_rmse": c[:, 2].mean()})
        r = rows[-1]
        print("  %-14s cells %3d  FULL %.3f/%+.3f/%5.2f   HALF %.3f/%+.3f/%5.2f   CEILING %.3f/%+.3f/%5.2f"
              % (t, r["n_cells"], r["full_dir"], r["full_rho"], r["full_rmse"],
                 r["half_dir"], r["half_rho"], r["half_rmse"],
                 r["ceil_dir"], r["ceil_rho"], r["ceil_rmse"]))
    d = pd.DataFrame(rows)
    if len(d):
        print("\n%-22s%9s%9s%9s" % ("", "dir", "rho", "rmse"))
        for lab, cols in (("scored on FULL truth", ("full_dir", "full_rho", "full_rmse")),
                          ("scored on ONE HALF", ("half_dir", "half_rho", "half_rmse")),
                          ("replication ceiling", ("ceil_dir", "ceil_rho", "ceil_rmse"))):
            print("%-22s%9.3f%9.3f%9.2f" % (lab, d[cols[0]].mean(), d[cols[1]].mean(),
                                            d[cols[2]].mean()))
        print("\nCOST OF HALVING THE REFERENCE: dir %+.3f, rho %+.3f, rmse %+.2f pp"
              % (d.half_dir.mean() - d.full_dir.mean(), d.half_rho.mean() - d.full_rho.mean(),
                 d.half_rmse.mean() - d.full_rmse.mean()))
        beat = (d.half_rmse < d.ceil_rmse).sum()
        print("BEATS THE CEILING ON RMSE on %d of %d tasks; on rho on %d of %d"
              % (beat, len(d), (d.half_rho > d.ceil_rho).sum(), len(d)))
        out = run / "stages" / "calibration" / "split_half.csv"
        d.to_csv(out, index=False)
        print("written ->", out)
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="runs/20260815-practice-01")
    ap.add_argument("--reps", type=int, default=20)
    a = ap.parse_args()
    main(a.run, a.reps)
