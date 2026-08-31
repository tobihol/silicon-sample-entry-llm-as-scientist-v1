#!/usr/bin/env python
"""The pre-registered verdicts for trust practice task #3 (altenmueller2024 Study 4b).

    /opt/kernel/venv/bin/python tools/altenmueller_verdicts.py

Rules fixed in `runs/_trusttask3/PREREG.md` BEFORE any call. 0 tokens: every prediction it reads is
on disk and already paid for. What this prints, in the prereg's own order:

  P1  the dissociation - does the predictor put MORALITY-based trust above EXPERTISE-based trust
      for a sociological institute?  (human: +7.54 vs +0.37 pp)   PASS/FAIL, all three model lines
  P2  the ordering of the five preregistered cells, with its covariance-aware ceiling beside it
  P3  trust-family magnitude, against the two trust benchmarks already on the board
  S1  the Section-1 rows on both tables, with `pearson_r_within_outcomes` marked NOT INTERPRETED
      because the within-outcome ceiling of this task is 0.000 and was known to be before the batch
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(RUN / "tools"))
from ssb import score as S                                              # noqa: E402
from task_power import power                                            # noqa: E402

LINES = {"claude-opus-5 (3 draws, PRIMARY)": "20260820-practice-alt",
         "claude-sonnet-5 (1 draw)": "20260820-practice-alt-sonnet-5",
         "claude-fable-5 (1 draw)": "20260820-practice-alt-fable-5"}
TASK = "altenmueller2024"
PRIMARY_ARM = "Sociological institute"
TRUST = ["trust_expertise", "trust_morality"]
BENCH = {"gligoric2025 (published null, conservatives only)": 0.42,
         "koetke2024 Study 5 (general population vignette)": 2.16}


def frames():
    truth = pd.read_csv(RUN / "runs" / LINES["claude-opus-5 (3 draws, PRIMARY)"] / "tasks" / TASK /
                        "sealed" / "truth.csv")
    out = {}
    for lab, rid in LINES.items():
        p = pd.read_csv(RUN / "runs" / rid / "tasks" / TASK / "prediction.csv")
        out[lab] = truth.merge(p.rename(columns={"ate": "pred"}), on=["condition", "outcome"])
    return truth, out


def main():
    truth, F = frames()
    p10 = power(truth.ate, truth.se, truth.n_treat, truth.n_control, truth.outcome)
    t5 = truth[truth.condition == PRIMARY_ARM]
    p5 = power(t5.ate, t5.se, t5.n_treat, t5.n_control, t5.outcome)
    print("\nCEILINGS (covariance-aware, finding 79; computed before the batch, prereg section 1)")
    print("   10-cell marginal %.3f | 5-cell primary marginal %.3f | WITHIN-OUTCOME %.3f"
          % (p10["max_attainable_r"], p5["max_attainable_r"], p10["within_ceiling_r"]))

    print("\nP1 - the dissociation: predicted morality-trust > expertise-trust for a sociological")
    print("     institute (human +7.54 vs +0.37 pp)")
    for lab, m in F.items():
        s = m[m.condition == PRIMARY_ARM].set_index("outcome")
        mo, ex = float(s.loc["trust_morality", "pred"]), float(s.loc["trust_expertise", "pred"])
        print("   %-32s morality %+5.1f  expertise %+5.1f   %s"
              % (lab, mo, ex, "PASS" if mo > ex else "FAIL"))

    print("\nP2 - ordering of the five preregistered cells (ceiling %.3f; no threshold, prereg "
          "section 3)" % p5["max_attainable_r"])
    for lab, m in F.items():
        s = m[m.condition == PRIMARY_ARM]
        print("   %-32s Spearman %+.3f   Pearson %+.3f   dir %.3f   RMSE %5.2f pp"
              % (lab, S.spearman_rho(s.pred, s.ate), S.pearson_r(s.pred, s.ate),
                 S.directional_agreement(s.pred, s.ate), S.rmse_pp(s.pred, s.ate)))

    print("\nP3 - trust-family magnitude (median |ATE| over the 4 trust cells)")
    hm = truth[truth.outcome.isin(TRUST)].ate.abs().median()
    print("   human %.2f pp" % hm)
    for lab, m in F.items():
        print("   %-32s predicted %.2f pp" % (lab, m[m.outcome.isin(TRUST)].pred.abs().median()))
    for k, v in BENCH.items():
        print("   for reference, %-50s %.2f pp" % (k, v))

    print("\nS1 - Section-1 rows, 10-cell table (the board's rows)")
    print("   %-32s%8s%9s%9s%12s%8s" % ("", "dir", "rho", "r", "r_within", "RMSE"))
    for lab, m in F.items():
        print("   %-32s%8.3f%+9.3f%+9.3f%12s%8.2f"
              % (lab, S.directional_agreement(m.pred, m.ate), S.spearman_rho(m.pred, m.ate),
                 S.pearson_r(m.pred, m.ate),
                 "%+.3f*" % S.pearson_r_within_outcomes(
                     m.rename(columns={"ate": "human"}), pred="pred", human="human"),
                 S.rmse_pp(m.pred, m.ate)))
    print("   * NOT INTERPRETED. The within-outcome ceiling of this task is 0.000 (prereg section")
    print("     1): two identity labels at n~245 cannot be told apart inside an outcome, so this")
    print("     row is at chance whatever it reads - the same situation as gligoric2025's r_adj.")

    print("\n   BASELINES. All 10 human ATEs are POSITIVE, so the all-positive baseline scores")
    print("   1.000 directional here and cannot be beaten on that row by anything that predicts a")
    print("   single negative cell. The honest comparison on this task is RMSE:")
    for lab, m in F.items():
        b = S.baselines(m.rename(columns={"ate": "human"})[["condition", "outcome", "human"]])
        ap = b[b.baseline == "all_positive"].iloc[0]
        nf = b[b.baseline == "no_effect_floor"].iloc[0]
        print("   %-32s RMSE %5.2f | all-positive %5.2f dir %.3f (margins %+5.2f pp / %+.3f) | "
              "no-effect %5.2f dir %.3f (margins %+5.2f pp / %+.3f)"
              % (lab, S.rmse_pp(m.pred, m.ate), ap.rmse_pp, ap.directional_agreement,
                 ap.rmse_pp - S.rmse_pp(m.pred, m.ate),
                 S.directional_agreement(m.pred, m.ate) - ap.directional_agreement,
                 nf.rmse_pp, nf.directional_agreement,
                 nf.rmse_pp - S.rmse_pp(m.pred, m.ate),
                 S.directional_agreement(m.pred, m.ate) - nf.directional_agreement))

    print("\nS2 - the slope, declared inadmissible before it was computed (adapter "
          "`exclude_from_slope`)")
    for lab, m in F.items():
        c = S.calibration(m.pred, m.ate)
        print("   %-32s alpha %+.3f  beta %+.3f" % (lab, c["alpha"], c["beta"]))
    return F


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    main()
