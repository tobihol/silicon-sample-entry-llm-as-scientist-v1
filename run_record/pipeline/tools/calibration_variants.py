#!/usr/bin/env python
"""Three magnitude corrections, compared leave-one-task-out. All three preserve rank exactly.

REPORT.md section 7b measured that the predicted ATE spread is 0.427 of the human spread - severe
under-dispersion, the failure mode the frozen scoring table calls its headline diagnostic - and then
ASSERTED that "fixing" it would lose RMSE. That assertion is testable on the pairs already paid for,
and an obvious-looking improvement that nobody has tested is exactly the kind of thing a later
session re-invents. So it is tested here, once, with the answer written down.

    /opt/kernel/venv/bin/python tools/calibration_variants.py

  raw           deposit the predictions as they are
  ols_beta      multiply by the fitted slope             (what --lambda-policy pooled does)
  sd_match      multiply by sd_human/sd_pred             - matches the SPREAD exactly
  quantile_map  put predictions on the human ATE distribution by rank - matches the whole SHAPE

Spearman and directional agreement are identical for all four, because every one of them is a
monotone transform. Only RMSE and the calibration slope can move, which is the point.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
from ssb import score as S  # noqa: E402


def ols_beta(pred_te, human_tr, pred_tr):
    return pred_te * S.shrinkage_factor(pred_tr, human_tr)


def sd_match(pred_te, human_tr, pred_tr):
    return pred_te * (np.std(human_tr) / np.std(pred_tr))


def quantile_map(pred_te, human_tr, pred_tr):
    q = (pd.Series(pred_te).rank(pct=True) - 0.5 / len(pred_te)).clip(1e-6, 1 - 1e-6)
    return np.quantile(human_tr, q)


VARIANTS = {"ols_beta": ols_beta, "sd_match": sd_match, "quantile_map": quantile_map}


def main(run):
    p = pd.read_csv(Path(run) / "stages" / "calibration" / "pairs.csv")
    rows = []
    print("\nLEAVE-ONE-TASK-OUT RMSE (pp), lower is better")
    print("%-15s%7s%9s%11s%11s%14s" % ("held out", "n", "raw", "ols_beta", "sd_match",
                                       "quantile_map"))
    for t in sorted(p.task.unique()):
        tr, te = p[p.task != t], p[p.task == t]
        r = {"task": t, "n": len(te), "raw": S.rmse_pp(te.pred, te.human)}
        for k, f in VARIANTS.items():
            r[k] = S.rmse_pp(f(te.pred.values, tr.human.values, tr.pred.values), te.human)
        rows.append(r)
        print("%-15s%7d%9.3f%11.3f%11.3f%14.3f" % (t, r["n"], r["raw"], r["ols_beta"],
                                                   r["sd_match"], r["quantile_map"]))
    d = pd.DataFrame(rows)
    print("\n%-15s%7s%9.3f%11.3f%11.3f%14.3f" % ("MEAN", "", d.raw.mean(), d.ols_beta.mean(),
                                                  d.sd_match.mean(), d.quantile_map.mean()))
    print("%-15s%7s%9s%11s%11s%14s" % ("wins over raw", "", "-",
                                       "%d/%d" % ((d.ols_beta < d.raw).sum(), len(d)),
                                       "%d/%d" % ((d.sd_match < d.raw).sum(), len(d)),
                                       "%d/%d" % ((d.quantile_map < d.raw).sum(), len(d))))
    print("\nREADING: matching the human spread (sd_match) or the whole human shape (quantile_map)")
    print("        makes RMSE WORSE. Under-dispersion is not a bug to be corrected here - it is the")
    print("        RMSE-optimal response to r < 1. Only the fitted slope helps, and only by ~0.01 pp.")
    out = Path(run) / "stages" / "calibration" / "calibration_variants.csv"
    d.to_csv(out, index=False)
    print("\nwritten ->", out)
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default="runs/20260815-practice-01")
    a = ap.parse_args()
    main(a.run)
