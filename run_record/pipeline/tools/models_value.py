#!/usr/bin/env python
"""What did a second MODEL buy? The same question `draws_value.py` asks of draws.

Standing finding 43 argued from a dispersion that a panel should aggregate over MODELS rather than
over draws of one model, and priced a second model as the cheaper option that attacks bias instead
of variance. Finding 48 is the measurement that corrected it. This tool is that measurement, so the
finding can be re-run in a second instead of trusted.

    /opt/kernel/venv/bin/python tools/models_value.py
    /opt/kernel/venv/bin/python tools/models_value.py --runs runs/20260815-practice-01 runs/20260815-practice-02-fable

It takes two or more practice runs that scored the SAME carved tasks with different models, joins
their pairs.csv on (task, condition, outcome), scores each model alone and the panel (mean and
median) with the frozen Section-1 metrics, and reports what the panel bought over the best single
model.

Two traps it refuses to fall into, both of which cost real reasoning the first time:

  - `corr(err_a, err_b)` is NOT the diagnostic. `e = pred - human` for both models, so both errors
    contain `-human`, whose variance dominates; the correlation is forced toward 1 by construction
    and read +0.970 on models whose panel bought nothing. It is printed with that warning attached,
    next to `corr(pred_a, pred_b)`, which is the honest number and read +0.889.
  - A margin is against a NAMED baseline, and "panel - first model" is not "panel - best model".
    Reading a bootstrap of the first contrast against the point estimate of the second produced an
    apparent 3x bias in the bootstrap and a paragraph of invented explanation about within-outcome
    demeaning. The bootstrap was fine. `--bootstrap` therefore reports BOTH contrasts, always
    labelled, because that is the mistake this tool exists to make impossible.
"""
import argparse, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
from ssb import score as S  # noqa: E402

KEY = ["task", "condition", "outcome"]
DEFAULT = ["runs/20260815-practice-01", "runs/20260815-practice-02-fable"]


def load(run: str) -> tuple[str, pd.DataFrame]:
    d = RUN / run
    p = pd.read_csv(d / "stages/calibration/pairs.csv")
    import json
    model = None
    for f in ("stages/practice/cost.json", "stages/target/cost.json", "run.json"):
        try:
            j = json.loads((d / f).read_text())
        except Exception:
            continue
        model = j.get("model") or j.get("params", {}).get("model")
        if model:
            break
    if not model:
        raise SystemExit(f"{run}: no model recorded in cost.json or run.json - cannot label a column")
    return model, p


def sc(df: pd.DataFrame, col: str) -> dict:
    g = pd.DataFrame({"condition": df.condition, "outcome": df.outcome,
                      "human": df.human, "se_human": df.se, "pred": df[col]})
    r = S.ate_recovery(g)
    cal = S.calibration(g.pred, g.human)
    return {"dir": r["directional_agreement"], "rho": r["spearman_rho"], "r": r["pearson_r"],
            "r_within": r["pearson_r_within_outcomes"], "rmse": r["rmse_pp"],
            "r_adj": r.get("r_adj", np.nan), "beta": cal["beta"]}


def main(runs, bootstrap=0, seed=0):
    frames, models = [], []
    for run in runs:
        model, p = load(run)
        models.append(model)
        frames.append(p[KEY + ["human", "se", "pred"]].rename(columns={"pred": f"pred__{model}"}))
    m = frames[0]
    for f in frames[1:]:
        m = m.merge(f.drop(columns=["human", "se"]), on=KEY, validate="1:1")
    cols = [f"pred__{x}" for x in models]
    m["panel_mean"] = m[cols].mean(axis=1)
    m["panel_median"] = m[cols].median(axis=1)
    print(f"\n{len(m)} cells shared by {len(models)} models: {', '.join(models)}")

    print("\n=== each model alone, and the panel (frozen Section-1 metrics) ===")
    rows = {**{f"{x} alone": sc(m, f"pred__{x}") for x in models},
            "panel (mean)": sc(m, "panel_mean"), "panel (median)": sc(m, "panel_median")}
    res = pd.DataFrame(rows).T
    print(res.round(4).to_string())

    singles = res.loc[[f"{x} alone" for x in models]]
    pan = res.loc["panel (mean)"]
    print("\n=== what the panel bought over the BEST single model ===")
    print("  directional %+.4f   rho %+.4f   r_within %+.4f   r_adj %+.4f   RMSE %+.4f pp"
          % (pan["dir"] - singles["dir"].max(), pan["rho"] - singles["rho"].max(),
             pan["r_within"] - singles["r_within"].max(), pan["r_adj"] - singles["r_adj"].max(),
             singles["rmse"].min() - pan["rmse"]))

    print("\n=== are the models making the SAME errors? ===")
    a, b = cols[0], cols[1]
    ea, eb = m[a] - m.human, m[b] - m.human
    print("  corr(pred, pred)  = %+.3f   <- the honest number" % m[a].corr(m[b]))
    print("  corr(err,  err)   = %+.3f   <- ARTEFACT, do not quote: both errors contain -human,"
          % ea.corr(eb))
    print("                                  whose variance dominates and forces this toward 1.")
    print("  by task:")
    for t, g in m.groupby("task"):
        print("    %-15s n=%3d  corr(pred)=%+.3f  corr(err)=%+.3f"
              % (t, len(g), g[a].corr(g[b]), (g[a] - g.human).corr(g[b] - g.human)))

    print("\n=== per task: does the panel beat the first model? ===")
    out = []
    for t, g in m.groupby("task"):
        d = {"task": t, "n": len(g)}
        for x in models:
            s = sc(g, f"pred__{x}")
            d[f"rw_{x[:12]}"] = s["r_within"]
            d[f"rmse_{x[:12]}"] = s["rmse"]
        p = sc(g, "panel_mean")
        d["rw_panel"], d["rmse_panel"] = p["r_within"], p["rmse"]
        out.append(d)
    pt = pd.DataFrame(out).set_index("task")
    print(pt.round(3).to_string())
    base = models[0][:12]
    print("\n  panel wins over %s alone:  r_within %d/%d   RMSE %d/%d"
          % (models[0], (pt.rw_panel > pt[f"rw_{base}"]).sum(), len(pt),
             (pt.rmse_panel < pt[f"rmse_{base}"]).sum(), len(pt)))

    if bootstrap:
        rng = np.random.default_rng(seed)
        m2 = m.copy()
        m2["arm"] = m2.task + "||" + m2.condition
        idx = {k: g for k, g in m2.groupby("arm")}
        arms = list(idx)
        first = cols[0]
        best_lab = singles["r_within"].idxmax()
        best_col = f"pred__{best_lab.replace(' alone', '')}"
        rec = []
        for _ in range(bootstrap):
            d = pd.concat([idx[k] for k in rng.choice(arms, len(arms), replace=True)],
                          ignore_index=True)
            p, q, r2 = sc(d, "panel_mean"), sc(d, first), sc(d, best_col)
            rec.append([p["dir"] - q["dir"], p["rho"] - q["rho"], p["r_within"] - q["r_within"],
                        q["rmse"] - p["rmse"], p["r_within"] - r2["r_within"]])
        bs = pd.DataFrame(rec, columns=["dir_vs_first", "rho_vs_first", "r_within_vs_first",
                                        "rmse_vs_first", "r_within_vs_BEST"])
        qs = sc(m, first)
        rs = sc(m, best_col)
        point = {"dir_vs_first": pan["dir"] - qs["dir"],
                 "rho_vs_first": pan["rho"] - qs["rho"],
                 "r_within_vs_first": pan["r_within"] - qs["r_within"],
                 "rmse_vs_first": qs["rmse"] - pan["rmse"],
                 "r_within_vs_BEST": pan["r_within"] - rs["r_within"]}
        print("\n=== cluster bootstrap on the ARM (%d resamples) ===" % bootstrap)
        print("    vs_first = vs %s (the incumbent);  vs_BEST = vs %s"
              % (models[0], best_lab.replace(" alone", "")))
        for c in bs.columns:
            lo, hi = np.percentile(bs[c], [2.5, 97.5])
            verd = "EXCLUDES ZERO" if lo > 0 or hi < 0 else "includes zero"
            bias = "" if abs(bs[c].mean() - point[c]) < 0.25 * bs[c].std() else "  BOOTSTRAP BIASED"
            print("  %-18s point %+.4f  boot %+.4f  [%+.4f, %+.4f]  %s%s"
                  % (c, point[c], bs[c].mean(), lo, hi, verd, bias))
        print("\n  Read the two r_within rows together. A panel that beats the INCUMBENT but not the")
        print("  BEST member has not shown that aggregation works - it has shown the other model is")
        print("  better on that row, and the cheaper action is to switch models, not to average them.")

    print("\nVERDICT: a panel is worth buying only if corr(pred, pred) is low enough that the")
    print("models disagree about the ORDERING. At +0.889 they do not, and the panel bought ~0.01")
    print("of one correlation row for 453,231 billed tokens (standing finding 48).")
    return 0


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--runs", nargs="+", default=DEFAULT)
    a.add_argument("--bootstrap", type=int, default=0)
    a.add_argument("--seed", type=int, default=0)
    n = a.parse_args()
    sys.exit(main(n.runs, n.bootstrap, n.seed))
