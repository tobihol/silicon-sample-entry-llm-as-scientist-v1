#!/usr/bin/env python
"""The two TASK_17 breadth tasks, graded against `runs/_trusttask5/PREREG.md`. 0 model calls.

    /opt/kernel/venv/bin/python tools/kimdab_verdicts.py

Every verdict, its threshold and its chance level were fixed in the pre-registration before any
call. Nothing here re-derives a threshold from a result.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(RUN / "tools"))
import ssb  # noqa: E402
from task_power import power  # noqa: E402

LINES = [("20260822-practice-kimdab-main", "claude-opus-5", 3),
         ("20260822-practice-kimdab-claude-sonnet-5-main", "claude-sonnet-5", 1),
         ("20260822-practice-kimdab-claude-fable-5-main", "claude-fable-5", 1)]
# the four trust tasks already on the board (findings 78, 84, 88, 94)
# the four trust tasks already on the board: (task, opus run_id, the trust outcome names)
SERIES = [("gligoric2025", "20260819-practice-gligoric", None),
          ("koetke2024", "20260819-practice-koetke", None),
          ("altenmueller2024", "20260820-practice-alt", None),
          ("orchinik2024", "20260821-practice-orchinik", None)]
TRUSTY = ("trust", "credib", "meti", "skill", "expert", "moral", "benevol", "integrity", "open")
CARD = RUN / "runs" / "20260815-target-01" / "card"


def frame(run_id, task):
    d = RUN / "runs" / run_id / "tasks" / task
    tr = pd.read_csv(d / "sealed" / "truth.csv")
    pr = pd.read_csv(d / "prediction.csv")
    return (tr.merge(pr, on=["condition", "outcome"], suffixes=("_h", "_p"))
              .rename(columns={"ate_h": "human", "ate_p": "pred"}))


def beta(m, n_boot=2000, seed=20260822):
    b = float(np.polyfit(m.pred, m.human, 1)[0])
    rng = np.random.default_rng(seed)
    arms = m.condition.unique()
    bs = []
    for _ in range(n_boot):
        pick = rng.choice(arms, len(arms), replace=True)
        s = pd.concat([m[m.condition == a] for a in pick])
        if s.pred.nunique() > 1:
            bs.append(np.polyfit(s.pred, s.human, 1)[0])
    return b, float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))


def main():
    print("VERDICTS against runs/_trusttask5/PREREG.md  (thresholds fixed before any call)\n")
    hk = frame(LINES[0][0], "kim2024")
    hd = frame(LINES[0][0], "dablander2025")

    print("HUMAN TABLES (identical for every line)")
    tk = hk[hk.outcome == "trust_climate_scientists"]
    print("  kim2024 trust cells: %s   median |ATE| %.2f pp"
          % (", ".join("%s %+.2f" % (r.condition, r.human) for r in tk.itertuples()),
             tk.human.abs().median()))
    sd = hd[hd.outcome == "science_credibility"]
    print("  dablander2025 science_credibility: %.2f to %.2f pp, median |ATE| %.2f pp (H9 null)"
          % (sd.human.min(), sd.human.max(), sd.human.abs().median()))

    rows = []
    for run_id, model, draws in LINES:
        k, d = frame(run_id, "kim2024"), frame(run_id, "dablander2025")
        # ---- P1: kim2024 trust magnitude in [0.3, 2.5] pp
        pk = k[k.outcome == "trust_climate_scientists"]
        med = float(pk.pred.abs().median())
        p1 = 0.3 <= med <= 2.5
        # ---- P2: two orderings
        def cell(df, cond, out, col="pred"):
            return float(df[(df.condition == cond) & (df.outcome == out)][col].iloc[0])
        a = cell(k, "Scientific consensus", "consensus_perceived") > \
            cell(k, "Causal evidence", "consensus_perceived")
        b_ = cell(k, "Causal evidence", "evidence_natural") < \
             cell(k, "Scientific consensus", "evidence_natural")
        p2 = a and b_
        # ---- P3: dablander science_credibility median |pred| <= 3.0 pp
        pd_ = d[d.outcome == "science_credibility"]
        med_sc = float(pd_.pred.abs().median())
        p3 = med_sc <= 3.0
        # ---- P4: all three CD radicalness cells above all three legal ones. The reference arm is
        # a legal march and its own cell is 0 by construction, so it counts as one of the three.
        rad = d[d.outcome == "perceived_radicalness"]
        cd = rad[rad.condition.str.startswith("Civil")].pred.to_numpy()
        lg = np.append(rad[rad.condition.str.startswith("Legal")].pred.to_numpy(), 0.0)
        p4 = bool(cd.min() > lg.max())
        bk, bklo, bkhi = beta(k)
        bd, bdlo, bdhi = beta(d)
        rows.append({"model": model, "draws": draws,
                     "P1 kim trust median |pred| pp": round(med, 2), "P1": "PASS" if p1 else "FAIL",
                     "P2": "PASS" if p2 else "FAIL",
                     "P3 dab sci-cred median |pred| pp": round(med_sc, 2),
                     "P3": "PASS" if p3 else "FAIL", "P4": "PASS" if p4 else "FAIL",
                     "beta_kim": "%.2f [%.2f, %.2f]" % (bk, bklo, bkhi),
                     "beta_dab": "%.2f [%.2f, %.2f]" % (bd, bdlo, bdhi)})
    R = pd.DataFrame(rows)
    print("\nPRE-REGISTERED VERDICTS")
    print(R.to_string(index=False))

    print("\nP1 IN CONTEXT - the trust magnitude series (findings 78, 84, 88, 94, now 5 tasks)")
    # The four earlier readings are quoted as PUBLISHED (findings 78, 84, 88, 94), not re-derived:
    # each used that task's own pre-registered stratum, and a regex over outcome names picks a
    # different set of cells. Re-deriving them here with a fifth rule would silently restate four
    # published numbers.
    PUB = [("gligoric2025", 0.42, 0.90, "finding 78"), ("koetke2024", 2.16, 1.20, "finding 84"),
           ("altenmueller2024", 4.33, 1.60, "finding 88"), ("orchinik2024", 1.14, 0.80, "finding 94")]
    print("  %-18s %10s %10s   %s" % ("task", "human", "opus pred", "source"))
    for t, h, p, src in PUB:
        print("  %-18s %10.2f %10.2f   %s (as published)" % (t, h, p, src))
    print("  %-18s %10.2f %10.2f %6d  <- NEW"
          % ("kim2024", tk.human.abs().median(),
             float(hk[hk.outcome == "trust_climate_scientists"].pred.abs().median()), len(tk)))
    print("  %-18s %10.2f %10.2f %6d  <- NEW"
          % ("dablander2025", sd.human.abs().median(),
             float(hd[hd.outcome == "science_credibility"].pred.abs().median()), len(sd)))

    print("\nTHE CARD'S OWN TRUST CELLS, for the comparison finding 84 makes")
    ate = pd.read_csv(CARD / "ate.csv")
    tr_out = [o for o in ate.outcome.unique() if "trust" in o or "distrust" in o]
    pp = []
    for o in tr_out:
        s = ate[ate.outcome == o]
        pp += list(s.ate.abs())
    print("  %d trust cells, median |ATE| %.2f pp (outcomes: %s)"
          % (len(pp), float(np.median(pp)), ", ".join(tr_out)))
    print("  kim2024's human trust ATEs are %+.2f and %+.2f pp on a 4-point item; the card's trust "
          "median is %.2f pp." % (tk.human.iloc[0], tk.human.iloc[1], float(np.median(pp))))

    (RUN / "runs" / "_trusttask5" / "verdicts.json").write_text(
        json.dumps({"lines": rows,
                    "human": {"kim2024_trust_median_pp": float(tk.human.abs().median()),
                              "dablander_scicred_median_pp": float(sd.human.abs().median())},
                    "card_trust_median_pp": float(np.median(pp))}, indent=1))
    print("\nwritten: runs/_trusttask5/verdicts.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
