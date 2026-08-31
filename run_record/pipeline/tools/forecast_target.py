#!/usr/bin/env python
"""What should this harness expect to SCORE on the target, and what does the ceiling look like?

Every practice number is measured against practice ground truth computed on the FULL training
sample. The target is scored against "Human 1" - one half of the human sample - with the other half
as the replication ceiling (the frozen scoring table). A half sample carries more sampling noise
than the full samples the practice scores were measured against, so a practice score and a target
score do NOT mean the same thing, however identical the prompt shape is.

This prices that gap. Nothing here touches the target's human data - it is a noise calculation from
the frozen file's stated design (~18,000 U.S. adults, 16 interventions + control) and this harness's
own measured skill.

It is a SIMULATION. `tools/split_half.py` is its empirical companion and it should be read first:
it measures the same gap on real respondents and it corrected two claims this file's output was used
to make (standing finding 40) - halving the reference costs only dir -0.028 / rho -0.073 / RMSE
+0.32 pp, and beating the replication ceiling on RMSE is conditional on noise/signal rather than
general. Quote the two sources together or neither.

    /opt/kernel/venv/bin/python tools/forecast_target.py [--practice-run runs/<id>]

Inputs, all measured or stated, none chosen:
  outcome SD      implied by the practice cells' own SEs and arm sizes
  n per condition frozen file: ~18,000 over 17 conditions, halved for Human 1
  r_adj           the disattenuated practice correlation = our correlation with TRUE effects
  sd_ratio        our measured under-dispersion (standing finding 34)
  tau_sd          the ONLY free parameter: how big the target's true effects are. Scanned, because
                  standing finding 5 says trust effects are ~0-1 pp while the practice tasks'
                  deconvolved spread is 2.76 pp, and the answer differs by scenario.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
from ssb import score as S  # noqa: E402

N_TOTAL, N_COND, N_CELLS = 18000, 17, 208       # frozen file
TAU_SCAN = (0.5, 1.0, 2.0, None)                # None -> the practice-deconvolved value


def main(practice_run, draws=400, seed=7):
    p = pd.read_csv(Path(practice_run) / "stages" / "calibration" / "pairs.csv")
    sd_out = p.se.mean() / np.sqrt(1 / p.n_treat.median() + 1 / p.n_control.median())
    n_half = N_TOTAL / N_COND / 2
    se_t = sd_out * np.sqrt(2 / n_half)
    r_adj = float(np.sqrt(max(np.corrcoef(p.pred, p.human)[0, 1] ** 2 /
                              max(1 - (p.se ** 2).mean() / p.human.var(), 1e-9), 0)))
    r_adj = min(r_adj, 0.999)
    sd_ratio = float(p.pred.std() / p.human.std())
    tau_practice = float(np.sqrt(max(p.human.var() - (p.se ** 2).mean(), 0)))
    lam = float(S.calibration(p.pred, p.human)["beta"])

    hdr = {"implied_outcome_sd_pp": sd_out, "human1_n_per_condition": n_half,
           "se_of_a_human1_ate_pp": se_t, "our_r_with_true_effects": r_adj,
           "our_sd_ratio": sd_ratio, "practice_deconvolved_tau_sd_pp": tau_practice,
           "fitted_lambda": lam, "n_cells": N_CELLS, "draws": draws}
    print("\nFORECAST INPUTS (measured, not chosen)")
    for k, v in hdr.items():
        print("  %-32s %.3f" % (k, v))

    rng = np.random.default_rng(seed)
    rows = []
    print("\n%-8s%-22s%9s%9s%9s%9s%9s%9s" % ("tau_sd", "scenario", "dir", "rho", "rmse",
                                              "ceil_dir", "ceil_rho", "ceil_rmse"))
    for tau_sd in [t if t else tau_practice for t in TAU_SCAN]:
        for lab, mult in (("as predicted (raw)", 1.0), ("calibrated x%.2f" % lam, lam)):
            M, C = [], []
            for _ in range(draws):
                tau = rng.normal(0, tau_sd, N_CELLS)
                h1 = tau + rng.normal(0, se_t, N_CELLS)
                h2 = tau + rng.normal(0, se_t, N_CELLS)
                z = rng.normal(0, 1, N_CELLS)
                pr = r_adj * tau / max(tau_sd, 1e-9) + np.sqrt(1 - r_adj ** 2) * z
                pr = pr * sd_ratio * np.std(h1) * mult
                M.append((S.directional_agreement(pr, h1), S.spearman_rho(pr, h1),
                          S.rmse_pp(pr, h1)))
                C.append((S.directional_agreement(h2, h1), S.spearman_rho(h2, h1),
                          S.rmse_pp(h2, h1)))
            M, C = np.array(M), np.array(C)
            rows.append({"tau_sd": tau_sd, "scenario": lab, "dir": M[:, 0].mean(),
                         "rho": M[:, 1].mean(), "rmse": M[:, 2].mean(),
                         "dir_p10": np.percentile(M[:, 0], 10), "dir_p90": np.percentile(M[:, 0], 90),
                         "ceil_dir": C[:, 0].mean(), "ceil_rho": C[:, 1].mean(),
                         "ceil_rmse": C[:, 2].mean()})
            r = rows[-1]
            print("%-8.2f%-22s%9.3f%9.3f%9.2f%9.3f%9.3f%9.2f" % (
                tau_sd, lab, r["dir"], r["rho"], r["rmse"], r["ceil_dir"], r["ceil_rho"],
                r["ceil_rmse"]))
        print()
    out = Path(practice_run) / "stages" / "calibration" / "target_forecast.json"
    out.write_text(json.dumps({"inputs": hdr, "scan": rows}, indent=1))
    print("written ->", out)
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--practice-run", default="runs/20260815-practice-01")
    ap.add_argument("--draws", type=int, default=400)
    a = ap.parse_args()
    main(a.practice_run, a.draws)
