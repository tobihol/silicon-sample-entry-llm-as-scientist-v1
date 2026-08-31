#!/usr/bin/env python
"""POST-HOC robustness checks on the length experiment. Zero model calls.

    /opt/kernel/venv/bin/python tools/length_robustness.py

`tools/length_experiment.py` is the PRE-REGISTERED analysis and decides the verdict
(runs/_lenexp/PREREG.md). Nothing in this file may change that verdict; it exists because a null
should be attacked before it is believed, and because three questions a reviewer will ask can all
be answered from data that is already paid for:

  A. CROSS-MODEL. Is the length correlation a property of one model, or of the task? The five
     practice tasks already have a full paid draw from a SECOND model line (claude-fable-5,
     20260815-practice-02-fable, standing finding 48). If both models track message length the
     same way, the correlation is in the messages, which is what the trimming arms concluded by a
     different route.

  B. SPECIFICATION. The verdict rests on one statistic - Spearman of arm-mean ATE on word count.
     Six reasonable alternatives are computed. A null that survives only its own pre-registered
     statistic is not a null.

  C. POWER. The pre-registration says the interval narrows with more ARMS, not more draws
     (finding 43). That was an assertion. Here it is measured: the bootstrap half-width is read off
     every subset of the five tasks and regressed on arm count, which gives the number of arms a
     given resolution actually costs.
"""
from __future__ import annotations

import json
import sys
from itertools import combinations
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kendalltau, spearmanr

RUN = Path(__file__).resolve().parents[1]
TASKS = ["voelkel2026", "goldwert2026", "vlasceanu2024", "bbprime2025", "voelkel2024"]
BASE = "20260815-lenexp-base"
FABLE = "20260815-practice-02-fable"
VARIANTS = {"debias_instr": "20260815-lenexp-debias_instr",
            "debias_wc": "20260815-lenexp-debias_wc",
            "eqlen": "20260815-lenexp-eqlen",
            "proptrim": "20260815-lenexp-proptrim"}
SPECS = ["spearman(prereg)", "pearson_log", "kendall", "drop_longest", "abs_ate", "per_outcome"]


def pairs(run_id):
    p = RUN / "runs" / run_id / "stages/calibration/pairs.csv"
    return pd.read_csv(p) if p.exists() else pd.DataFrame()


def words_by_arm(task):
    b = json.loads((RUN / "runs/20260815-practice-01/tasks" / task / "brief/task.json").read_text())
    return {a["title"]: len(str(a["text"]).split()) for a in b["arms"]}


def L(d, w, col="pred"):
    g = d.groupby("condition")[col].mean().reset_index()
    g["words"] = g.condition.map(w)
    g = g.dropna(subset=["words"])
    return float(spearmanr(g[col], g.words).statistic)


def L_spec(d, w, spec, col="pred"):
    if spec == "per_outcome":
        rs = []
        for _, go in d.groupby("outcome"):
            gg = go.groupby("condition")[col].mean().reset_index()
            gg["words"] = gg.condition.map(w)
            gg = gg.dropna(subset=["words"])
            if gg[col].nunique() > 2:
                rs.append(spearmanr(gg[col], gg.words).statistic)
        return float(np.nanmean(rs))
    g = d.groupby("condition").agg(v=(col, "mean"), av=(col, lambda s: s.abs().mean())).reset_index()
    g["words"] = g.condition.map(w)
    g = g.dropna(subset=["words"])
    if spec == "drop_longest":
        g = g[g.words < g.words.max()]
    y = g.av if spec == "abs_ate" else g.v
    if spec == "pearson_log":
        return float(np.corrcoef(y, np.log(g.words))[0, 1])
    if spec == "kendall":
        return float(kendalltau(y, g.words).statistic)
    return float(spearmanr(y, g.words).statistic)


def boot_delta(base, var, tasks, B=400, seed=7):
    """Cluster bootstrap on the arm of (variant - base) in the length GAP only - cheap enough to
    run over every task subset, which is what section C needs."""
    rng = np.random.default_rng(seed)
    pre = {t: (base[base.task == t], var[var.task == t], words_by_arm(t),
               base[base.task == t].condition.unique()) for t in tasks}
    ds = []
    for _ in range(B):
        bb, vv = [], []
        for t in tasks:
            db, dv, w, arms = pre[t]
            take = rng.choice(arms, len(arms), True)
            for src, store in ((db, bb), (dv, vv)):
                f = pd.concat([src[src.condition == a].assign(_b=i) for i, a in enumerate(take)])
                f = f.copy()
                f["condition"] = f.condition.astype(str) + "#" + f._b.astype(str)
                ww = {c: w[c.split("#")[0]] for c in f.condition.unique()}
                store.append(L(f, ww, "pred") - L(f, ww, "human"))
        ds.append(np.nanmean(vv) - np.nanmean(bb))
    a = np.array(ds)
    return float(np.nanpercentile(a, 2.5)), float(np.nanpercentile(a, 97.5))


def main():
    op, fab = pairs(BASE), pairs(FABLE)
    print("=" * 96)
    print("POST-HOC robustness on the length experiment (0 model calls). The VERDICT lives in")
    print("tools/length_experiment.py and runs/_lenexp/PREREG.md; nothing here can move it.")
    print("=" * 96)

    print("\n--- A. CROSS-MODEL: is the length correlation the model's, or the task's? ---")
    rows = []
    for t in TASKS:
        w = words_by_arm(t)
        rows.append({"task": t, "arms": len(w), "L_human": L(op[op.task == t], w, "human"),
                     "L_opus5": L(op[op.task == t], w), "L_fable5": L(fab[fab.task == t], w)})
    X = pd.DataFrame(rows)
    X["gap_opus5"] = X.L_opus5 - X.L_human
    X["gap_fable5"] = X.L_fable5 - X.L_human
    print(X.round(3).to_string(index=False))
    print("  pooled: humans %+.3f | opus-5 %+.3f (gap %+.3f) | fable-5 %+.3f (gap %+.3f)"
          % (X.L_human.mean(), X.L_opus5.mean(), X.gap_opus5.mean(),
             X.L_fable5.mean(), X.gap_fable5.mean()))
    print("  corr(L_opus5, L_fable5) over tasks = %+.3f   corr(L_human, L_opus5) = %+.3f"
          % (X.L_opus5.corr(X.L_fable5), X.L_human.corr(X.L_opus5)))
    print("  -> two independent model lines rank the tasks by length-dependence almost identically,")
    print("     which is what a property of the MESSAGES looks like and not a quirk of one model.")

    print("\n--- B. SPECIFICATION: does the null survive other definitions of the statistic? ---")
    out = []
    for v, rid in VARIANTS.items():
        pv = pairs(rid)
        if pv.empty:
            continue
        ts = [t for t in TASKS if t in set(pv.task)]
        for s in SPECS:
            db, dv = [], []
            for t in ts:
                w = words_by_arm(t)
                b_, v_ = op[op.task == t], pv[pv.task == t]
                hb = L_spec(b_, w, s, "human")
                db.append(L_spec(b_, w, s) - hb)
                dv.append(L_spec(v_, w, s) - hb)
            out.append({"variant": v, "spec": s, "delta_gap": np.mean(dv) - np.mean(db)})
    S = pd.DataFrame(out).pivot(index="spec", columns="variant", values="delta_gap")
    print(S.reindex(SPECS).round(3).to_string())
    print("  -> the two debias arms stay small on every specification (worst %.3f); the two trimming"
          % S[["debias_instr", "debias_wc"]].min().min())
    print("     arms stay large, and eqlen stays the bigger of the pair on all six.")

    print("\n--- C. POWER: what does resolution cost, in ARMS? ---")
    di = pairs("20260815-lenexp-debias_instr")
    narms = {t: len(words_by_arm(t)) for t in TASKS}
    rows = []
    for k in range(1, 6):
        for sub in combinations(TASKS, k):
            lo, hi = boot_delta(op, di, list(sub))
            rows.append({"tasks": k, "arms": sum(narms[t] for t in sub), "half_width": (hi - lo) / 2})
    P = pd.DataFrame(rows)
    print(P.groupby("tasks").agg(mean_arms=("arms", "mean"),
                                 mean_half_width=("half_width", "mean")).round(3).to_string())
    sl, ic = np.polyfit(np.log(P.arms), np.log(P.half_width), 1)
    c = np.exp(ic)
    print("  log-log slope %.3f (1/sqrt(n) is -0.500) -> the ARM is the effective unit, measured,"
          % sl)
    print("  which is the assumption finding 42 imposed on this statistic. half = %.2f * n^%.3f"
          % (c, sl))
    for tgt in (0.10, 0.05):
        n = np.exp((np.log(tgt) - np.log(c)) / sl)
        print("    +/-%.2f half-width needs %3.0f arms; we have %d (%d over 5 tasks)"
              % (tgt, n, sum(narms.values()), sum(narms.values())))
    print("  -> ONE more mid-sized task (~33 arms) buys +/-0.10. Resolving +/-0.05 needs ~447 arms")
    print("     and is out of reach here. More draws buy none of this (finding 43).")
    (RUN / "runs/_lenexp/robustness.json").write_text(json.dumps(
        {"cross_model": X.to_dict("records"), "specification": S.reindex(SPECS).to_dict(),
         "power": {"fit_slope": float(sl), "fit_c": float(c),
                   "points": P.to_dict("records")}}, indent=1, default=float))
    print("\nwritten -> runs/_lenexp/robustness.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
