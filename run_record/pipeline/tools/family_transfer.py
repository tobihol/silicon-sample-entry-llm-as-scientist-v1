#!/usr/bin/env python
"""How wrong is a magnitude slope fitted in one outcome family when applied to another?

The target's trust family - four of thirteen outcomes and the entire point of the megastudy - has
ZERO practice pairs (standing finding 33), so any multiplier applied to a predicted trust ATE is a
cross-family extrapolation with no in-family evidence. Session 6 argued about that from theory and
finding 5's randomised band. This measures the extrapolation ERROR itself, on the families the
practice loop does cover, and it costs nothing: every pair is already paid for.

    /opt/kernel/venv/bin/python tools/family_transfer.py

Three nested folds, weakest to strongest:

  LOFO   leave-one-FAMILY-out       fit lambda on the other families, apply to the held-out one
  LOTO   leave-one-TASK-out         the fold the harness already uses (finding 29)
  LOTFO  leave-one-task-AND-family  fit on cells that share NEITHER the task NOR the family, which
                                    is the only fold that resembles the trust situation, because
                                    family and task are confounded here (policy is mostly one study)

Reported per fold: the transferred slope against the held-out family's own (oracle) slope, and what
each costs in RMSE against doing nothing (lambda = 1). Intervals are a cluster bootstrap on the ARM
(standing finding 42): a message's cells share whatever the predictor got right about that message.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
from ssb import score as S  # noqa: E402

PAIRS = RUN / "runs/20260815-practice-01/stages/calibration/pairs_with_family.csv"
B = 2000
RNG = np.random.default_rng(20260816)


def slope(d):
    return S.shrinkage_factor(d.pred, d.human)


def rmse(d, lam):
    return float(np.sqrt(((d.pred * lam - d.human) ** 2).mean()))


def boot_stat(d, fn, arms):
    """Cluster bootstrap on the arm. `fn` takes a frame and returns a float."""
    out = []
    idx = {a: g.index.values for a, g in d.groupby(arms)}
    keys = list(idx)
    for _ in range(B):
        pick = RNG.choice(len(keys), len(keys), replace=True)
        rows = np.concatenate([idx[keys[i]] for i in pick])
        v = fn(d.loc[rows])
        if np.isfinite(v):
            out.append(v)
    return np.percentile(out, [2.5, 97.5]) if out else (np.nan, np.nan)


def main(in_slope_only=True):
    p = pd.read_csv(PAIRS).dropna(subset=["pred", "human"])
    p["arm"] = p.task + "|" + p.condition
    full = p.copy()
    if in_slope_only:
        p = p[p.in_slope.astype(bool)]
    p = p[p.target_family.notna()]
    print(f"{len(full):,} scored pairs -> {len(p):,} with a target family"
          f"{' and in_slope' if in_slope_only else ''}")
    print(p.groupby(["target_family", "task"]).size().unstack(fill_value=0).to_string())

    fams = sorted(p.target_family.unique())
    pooled = slope(p)
    print(f"\npooled slope on these pairs: {pooled:.4f}   (deposited pooled slope: 1.5212 on 498 "
          f"in-slope pairs, which includes the cells with no family)")

    print("\n=== LOFO: fit on the other families, apply to the held-out one ===")
    print(f"{'held-out':<12}{'n':>5}{'own lam':>10}{'transferred':>13}{'ratio':>8}"
          f"{'RMSE lam=1':>12}{'RMSE transf':>13}{'RMSE oracle':>13}{'transf-1':>10}")
    rows = []
    for f in fams:
        held, rest = p[p.target_family == f], p[p.target_family != f]
        lam_own, lam_tr = slope(held), slope(rest)
        r1, rt, ro = rmse(held, 1.0), rmse(held, lam_tr), rmse(held, lam_own)
        lo, hi = boot_stat(held, lambda d, lt=lam_tr: rmse(d, lt) - rmse(d, 1.0), "arm")
        rows.append({"fold": "LOFO", "held_out": f, "n": len(held), "lam_own": lam_own,
                     "lam_transferred": lam_tr, "ratio": lam_tr / lam_own,
                     "rmse_none": r1, "rmse_transferred": rt, "rmse_oracle": ro,
                     "delta_vs_none": rt - r1, "ci_lo": lo, "ci_hi": hi})
        print(f"{f:<12}{len(held):>5}{lam_own:>10.3f}{lam_tr:>13.3f}{lam_tr/lam_own:>8.2f}"
              f"{r1:>12.3f}{rt:>13.3f}{ro:>13.3f}{rt - r1:>+10.3f}  [{lo:+.3f}, {hi:+.3f}]")

    print("\n=== LOTO: leave one TASK out (the fold the harness already uses) ===")
    for t in sorted(p.task.unique()):
        held, rest = p[p.task == t], p[p.task != t]
        lam_tr = slope(rest)
        r1, rt, ro = rmse(held, 1.0), rmse(held, lam_tr), rmse(held, slope(held))
        lo, hi = boot_stat(held, lambda d, lt=lam_tr: rmse(d, lt) - rmse(d, 1.0), "arm")
        rows.append({"fold": "LOTO", "held_out": t, "n": len(held), "lam_own": slope(held),
                     "lam_transferred": lam_tr, "ratio": lam_tr / slope(held),
                     "rmse_none": r1, "rmse_transferred": rt, "rmse_oracle": ro,
                     "delta_vs_none": rt - r1, "ci_lo": lo, "ci_hi": hi})
        print(f"{t:<14}{len(held):>5}{slope(held):>10.3f}{lam_tr:>13.3f}"
              f"{r1:>12.3f}{rt:>13.3f}{rt - r1:>+10.3f}  [{lo:+.3f}, {hi:+.3f}]")

    print("\n=== LOTFO: neither the task nor the family (the fold that resembles trust) ===")
    print(f"{'task':<14}{'family':<11}{'n':>5}{'fit n':>7}{'lam transf':>12}{'lam own':>9}"
          f"{'RMSE lam=1':>12}{'RMSE transf':>13}{'delta':>9}")
    for t in sorted(p.task.unique()):
        for f in fams:
            held = p[(p.task == t) & (p.target_family == f)]
            rest = p[(p.task != t) & (p.target_family != f)]
            if len(held) < 15 or len(rest) < 30:
                continue
            lam_tr = slope(rest)
            r1, rt = rmse(held, 1.0), rmse(held, lam_tr)
            lo, hi = boot_stat(held, lambda d, lt=lam_tr: rmse(d, lt) - rmse(d, 1.0), "arm")
            rows.append({"fold": "LOTFO", "held_out": f"{t}|{f}", "n": len(held),
                         "lam_own": slope(held), "lam_transferred": lam_tr,
                         "ratio": lam_tr / slope(held), "rmse_none": r1, "rmse_transferred": rt,
                         "rmse_oracle": rmse(held, slope(held)), "delta_vs_none": rt - r1,
                         "ci_lo": lo, "ci_hi": hi})
            print(f"{t:<14}{f:<11}{len(held):>5}{len(rest):>7}{lam_tr:>12.3f}{slope(held):>9.3f}"
                  f"{r1:>12.3f}{rt:>13.3f}{rt - r1:>+9.3f}  [{lo:+.3f}, {hi:+.3f}]")

    out = pd.DataFrame(rows)
    dst = RUN / "runs/20260815-practice-01/stages/calibration/family_transfer.csv"
    out.to_csv(dst, index=False)

    print("\n=== what this says about the trust extrapolation ===")
    lofo = out[out.fold == "LOFO"]
    print(f"  family slopes span {lofo.lam_own.min():.3f} - {lofo.lam_own.max():.3f} "
          f"(ratio {lofo.lam_own.max() / lofo.lam_own.min():.2f}x); a slope transferred INTO a "
          f"family is off by {lofo.ratio.min():.2f}-{lofo.ratio.max():.2f}x")
    for fold in ("LOFO", "LOTO", "LOTFO"):
        s = out[out.fold == fold]
        wins = int((s.delta_vs_none < 0).sum())
        excl = int(((s.ci_lo > 0) | (s.ci_hi < 0)).sum())
        print(f"  {fold:<6} transferred slope beats lambda=1 on {wins}/{len(s)} folds; "
              f"mean delta {s.delta_vs_none.mean():+.3f} pp; {excl}/{len(s)} intervals exclude zero")
    print(f"\nwritten: {dst}")
    return 0


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--all-pairs", action="store_true",
                   help="ignore the in_slope exclusions (a diagnostic, never a depositable slope)")
    n = a.parse_args()
    sys.exit(main(in_slope_only=not n.all_pairs))
