#!/usr/bin/env python
"""How much of the margin over the two scripted baselines is real, and how much is 1,101 cells?

Standing finding 18 was learned on a gate: a statistic computed from a sample and read off one draw
is not evidence, because the spread is what says whether the number means anything. The scoreboard
carries the same shape of mistake in a different place - every Section-1 metric is a point estimate
over cells, quoted against two baselines with no uncertainty at all. "Beats the no-effect floor and
the all-positive baseline" is the stopping rule in AGENTS.md, and until now nothing said whether the
margin was distinguishable from zero.

    /opt/kernel/venv/bin/python tools/margin_ci.py [--boot 2000]

The resampling unit is the CONDITION (the arm), not the cell. A message's effects across the 9-24
outcomes of a task are one message's effects: they share whatever the predictor got right or wrong
about that message, so cells are not independent and a cell bootstrap would report intervals that
are far too narrow. Clustering on the arm is the conservative and correct choice, and it is stated
here rather than chosen after seeing which one gave a nicer answer.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
from ssb import score as S  # noqa: E402

ALL_POSITIVE_PP = 1.0        # the organizers' magnitude is not published (OPEN item 4); explicit


def margins(d):
    """Our score minus each baseline's, on the same cells."""
    zero = np.zeros(len(d))
    allp = np.full(len(d), ALL_POSITIVE_PP)
    return {
        "dir_vs_floor": S.directional_agreement(d.pred, d.human)
                        - S.directional_agreement(zero, d.human),
        "dir_vs_allpos": S.directional_agreement(d.pred, d.human)
                         - S.directional_agreement(allp, d.human),
        "rmse_vs_floor": S.rmse_pp(zero, d.human) - S.rmse_pp(d.pred, d.human),
        "rmse_vs_allpos": S.rmse_pp(allp, d.human) - S.rmse_pp(d.pred, d.human),
        "spearman": S.spearman_rho(d.pred, d.human),
        "r_within": S.pearson_r_within_outcomes(d),
    }


def boot(d, n=2000, seed=0):
    """Cluster bootstrap on `condition`, within task."""
    rng = np.random.default_rng(seed)
    keys = d.condition.unique()
    groups = {k: g for k, g in d.groupby("condition")}
    out = []
    for _ in range(n):
        pick = rng.choice(keys, size=len(keys), replace=True)
        s = pd.concat([groups[k] for k in pick], ignore_index=True)
        if s.human.nunique() < 3 or s.pred.nunique() < 2:
            continue
        try:
            out.append(margins(s))
        except Exception:
            continue
    return pd.DataFrame(out)


def main(run, n=2000):
    p = pd.read_csv(Path(run) / "stages" / "calibration" / "pairs.csv")
    rows = []
    for label, d in [("POOLED", p)] + [(t, g) for t, g in p.groupby("task")]:
        b = boot(d, n)
        obs = margins(d)
        r = {"set": label, "n_cells": len(d), "n_arms": d.condition.nunique(), "boots": len(b)}
        for k, v in obs.items():
            lo, hi = np.percentile(b[k], [2.5, 97.5])
            r[k] = v
            r[k + "_lo"], r[k + "_hi"] = lo, hi
            r[k + "_sig"] = bool(lo > 0)
        rows.append(r)
    d = pd.DataFrame(rows)

    print("\nMARGIN OVER THE TWO SCRIPTED BASELINES, with a 95% cluster bootstrap on the ARM")
    print("(a margin whose interval includes 0 is not a demonstrated win - AGENTS.md's stopping rule)")
    for key, nice in (("dir_vs_floor", "directional vs no-effect floor"),
                      ("dir_vs_allpos", "directional vs all-positive"),
                      ("rmse_vs_floor", "RMSE gain vs no-effect floor (pp)"),
                      ("rmse_vs_allpos", "RMSE gain vs all-positive (pp)"),
                      ("spearman", "Spearman rho (no baseline has one)"),
                      ("r_within", "Pearson r within outcomes")):
        print("\n  %s" % nice)
        for r in d.itertuples():
            v, lo, hi = getattr(r, key), getattr(r, key + "_lo"), getattr(r, key + "_hi")
            mark = "  " if lo > 0 else " *"
            print("    %-15s %+7.3f  [%+7.3f, %+7.3f]%s" % (r.set, v, lo, hi, mark))
    print("\n  * interval includes zero: not a demonstrated win on that row")
    out = Path(run) / "stages" / "calibration" / "margin_ci.csv"
    d.to_csv(out, index=False)
    print("\nwritten ->", out)
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="runs/20260815-practice-01")
    ap.add_argument("--boot", type=int, default=2000)
    a = ap.parse_args()
    main(a.run, a.boot)
