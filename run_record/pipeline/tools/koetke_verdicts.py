#!/usr/bin/env python
"""The pre-registered verdicts for trust practice task #2 (koetke2024 Study 5).

    /opt/kernel/venv/bin/python tools/koetke_verdicts.py

Everything here is fixed in runs/_trusttask2/PREREG.md, written before the first model call:
P1/P2/P3 (the trust-vs-belief dissociation), S1 (Section-1 rows on the 27-cell and the 24-cell
tables, each beside its attainable-r ceiling), S2 (the trust-family magnitude), S3 (the slope that
may not be used), and the bootstrap intervals with BOTH clusterings, because with three arms an
arm-clustered interval is indicative only and saying so is part of the pre-registration.

Reruns in a second, spends nothing: it reads each run's own prediction.csv and sealed truth.
"""
import json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(RUN / "tools"))
import ssb  # noqa: E402
import build_koetke as BK  # noqa: E402

LINES = {"claude-opus-5 (3 draws, PRIMARY)": "20260819-practice-koetke",
         "claude-fable-5 (1 draw, QUARANTINED)": "20260819-practice-koetke-fable-5",
         "claude-sonnet-5 (1 draw)": "20260819-practice-koetke-sonnet-5"}
ARMS = ["Limits of Methods", "Limits of Results", "Personal Humility"]
MANIP = "perceived_humility"
TRUST = ["trust_meti", "trust_expertise", "trust_integrity", "trust_benevolence"]


def load(run_id):
    d = RUN / "runs" / run_id / "tasks" / "koetke2024"
    t = pd.read_csv(d / "sealed" / "truth.csv").rename(columns={"ate": "human", "se": "se_human"})
    p = pd.read_csv(d / "prediction.csv").rename(columns={"ate": "pred"})
    return t.merge(p, on=["condition", "outcome"])


def dissociation(x, col):
    """P1, P2, P3 on any table with a `condition`/`outcome`/<col> shape."""
    v = x.pivot(index="outcome", columns="condition", values=col)
    lim = ["Limits of Methods", "Limits of Results"]
    signs = [v.loc["trust_meti", a] > 0 for a in lim] + [v.loc["belief_research", a] < 0 for a in lim]
    p1 = sum(signs)
    p2 = all(v.loc["belief_research", "Personal Humility"] > v.loc["belief_research", a] for a in lim)
    idx = {a: v.loc["trust_meti", a] - v.loc["belief_research", a] for a in ARMS}
    order = sorted(ARMS, key=lambda a: -idx[a])
    return {"P1_signs": int(p1),
            "P1": "PASS" if p1 == 4 else ("PARTIAL" if p1 == 3 else "FAIL"),
            "P2": "PASS" if p2 else "FAIL",
            "P3_order": order, "index": {a: round(idx[a], 2) for a in ARMS}}


def boot(d, stat, cluster, n=2000, seed=20260819):
    rng = np.random.default_rng(seed)
    keys = d[cluster].unique() if cluster else None
    out = []
    for _ in range(n):
        if cluster:
            pick = rng.choice(keys, len(keys), replace=True)
            s = pd.concat([d[d[cluster] == k] for k in pick])
        else:
            s = d.iloc[rng.integers(0, len(d), len(d))]
        try:
            out.append(stat(s))
        except Exception:
            pass
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def ceilings():
    df = pd.read_csv(BK.DATA)
    d = BK.derive(df)
    t = BK.ate_table(d)
    t24 = t[t.outcome != MANIP]
    tt = t[t.outcome.str.startswith("trust_")]
    return {"27_marginal": BK.signal(d, t), "27_within": BK.signal(d, t, within=True),
            "24_marginal": BK.signal(d, t24), "24_within": BK.signal(d, t24, within=True),
            "trust_marginal": BK.signal(d, tt), "trust_within": BK.signal(d, tt, within=True)}


ROWS = ["directional_agreement", "spearman_rho", "pearson_r", "pearson_r_within_outcomes",
        "rmse_pp", "r_adj", "rmse_adj", "cal_alpha", "cal_beta",
        "vs_no_effect_floor_directional", "vs_no_effect_floor_rmse",
        "vs_all_positive_directional", "vs_all_positive_rmse"]


def main():
    cl = ceilings()
    print("ATTAINABLE-r CEILINGS (covariance-aware; PREREG section 1)")
    for k, v in cl.items():
        print("  %-16s var_true %8.3f   ceiling %.3f" % (k, v["var_true"], v["ceiling_r"]))

    human = None
    for name, rid in LINES.items():
        d = load(rid)
        human = d
        print("\n=== %s  [%s]" % (name, rid))
        s27 = ssb.score.scorecard(d)
        s24 = ssb.score.scorecard(d[d.outcome != MANIP])
        print("  %-32s %10s %10s" % ("row", "27 cells", "24 cells (no manip check)"))
        for r in ROWS:
            print("  %-32s %10.4f %10.4f" % (r, s27[r], s24[r]))
        v = dissociation(d, "pred")
        print("  P1 signs %d/4 -> %s | P2 %s | P3 order %s -> %s"
              % (v["P1_signs"], v["P1"], v["P2"], " > ".join(v["P3_order"]),
                 "PASS" if v["P3_order"] == ["Limits of Results", "Limits of Methods",
                                             "Personal Humility"] else "FAIL"))
        print("     dissociation index (trust - belief): %s" % v["index"])
        tr = d[d.outcome.isin(TRUST)]
        print("  S2 trust magnitude: median |pred| %.2f pp (max %.2f) against human median %.2f pp"
              % (tr.pred.abs().median(), tr.pred.abs().max(), tr.human.abs().median()))
        beta = np.polyfit(d.pred, d.human, 1)[0]
        lo_a, hi_a = boot(d, lambda s: np.polyfit(s.pred, s.human, 1)[0], "condition")
        lo_c, hi_c = boot(d, lambda s: np.polyfit(s.pred, s.human, 1)[0], None)
        print("  S3 slope beta %.3f  [arm-clustered %.3f, %.3f | cell %.3f, %.3f] "
              "- EXCLUDED from any fitted calibration (PREREG section 2)"
              % (beta, lo_a, hi_a, lo_c, hi_c))
        for row in ["directional_agreement", "spearman_rho", "pearson_r_within_outcomes", "rmse_pp"]:
            f = (lambda s, r=row: ssb.score.scorecard(s)[r])
            la, ha = boot(d, f, "condition", n=500)
            lc, hc = boot(d, f, None, n=500)
            print("     %-28s %8.4f  arm[%.3f, %.3f] (indicative)  cell[%.3f, %.3f] (anticons.)"
                  % (row, s27[row], la, ha, lc, hc))

    print("\nHUMAN table, for the record")
    print(dissociation(human, "human"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
