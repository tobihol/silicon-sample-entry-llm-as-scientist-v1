#!/usr/bin/env python
"""Score the length-controlled prompt experiment against the rules fixed in runs/_lenexp/PREREG.md.

    /opt/kernel/venv/bin/python tools/length_experiment.py

Standing finding 59 measured that the predictor's ordering of the messages tracks how LONG each
message is (+0.726 on the deposited target card, against +0.294 on practice and +0.106 for the
humans). That is a diagnostic, not a diagnosis: longer messages carry more argument, and humans may
reward that too. This tool reads the five prompt variants that separate the two explanations.

Primary quantity, per task:

    L_pred  = Spearman(mean predicted ATE per arm, ORIGINAL word count)
    L_human = Spearman(mean human ATE per arm,     ORIGINAL word count)   [a property of the task]
    gap     = L_pred - L_human                                            [the over-weighting]

The word count is ALWAYS the original one, for every variant, because that is the stimulus length
the humans saw; a trimmed variant that still tracks original length is tracking content.

Intervals are a cluster bootstrap on the ARM within task (finding 42), paired: the same resampled
arms are scored under base and under the variant, so the contrast is a within-resample difference.
The noise floor is measured, not assumed - the three already-paid draws of the base prompt are
re-scored individually, giving the draw-to-draw spread of the same statistics under no treatment.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402

BASE_RUN = "20260815-lenexp-base"
PRACTICE = "20260815-practice-01"                 # where the three cached draws live
VARIANTS = {"debias_instr": "20260815-lenexp-debias_instr",
            "debias_wc": "20260815-lenexp-debias_wc",
            "eqlen": "20260815-lenexp-eqlen",
            "proptrim": "20260815-lenexp-proptrim"}
B = 2000
SEED = 20260815


def words_by_arm(task: str) -> dict:
    """Original word count per arm, from the carved brief - not from inputs/texts, so it is exactly
    the text the base prompt carried."""
    b = json.loads((RUN / "runs" / PRACTICE / "tasks" / task / "brief" / "task.json").read_text())
    return {a["title"]: len(str(a["text"]).split()) for a in b["arms"]}


def load_pairs(run_id: str) -> pd.DataFrame:
    p = RUN / "runs" / run_id / "stages" / "calibration" / "pairs.csv"
    if not p.exists():
        return pd.DataFrame()
    return pd.read_csv(p)


def _length_corr(d: pd.DataFrame, w: dict, col: str) -> float:
    g = d.groupby("condition")[col].mean().reset_index()
    g["words"] = g.condition.map(w)
    g = g.dropna(subset=["words"])
    if g.condition.nunique() < 4 or g[col].nunique() < 3:
        return np.nan
    return float(spearmanr(g[col], g.words).statistic)


def task_metrics(d: pd.DataFrame, w: dict) -> dict:
    """The frozen Section-1 rows plus the two length correlations, on one task's cells."""
    sc = ssb.score.scorecard(d[["condition", "outcome", "pred", "human", "se"]]
                             .rename(columns={"se": "se_human"}))
    return {"L_pred": _length_corr(d, w, "pred"), "L_human": _length_corr(d, w, "human"),
            "directional_agreement": sc["directional_agreement"],
            "spearman_rho": sc["spearman_rho"],
            "pearson_r_within_outcomes": sc["pearson_r_within_outcomes"],
            "rmse_pp": sc["rmse_pp"]}


def profile(pairs: pd.DataFrame, tasks: list) -> pd.DataFrame:
    rows = []
    for t in tasks:
        d = pairs[pairs.task == t]
        if not len(d):
            continue
        m = task_metrics(d, words_by_arm(t))
        rows.append({"task": t, **m, "gap": m["L_pred"] - m["L_human"]})
    return pd.DataFrame(rows)


def _resample(d: pd.DataFrame, rng) -> pd.DataFrame:
    arms = d.condition.unique()
    take = rng.choice(arms, size=len(arms), replace=True)
    return pd.concat([d[d.condition == a].assign(_b=i) for i, a in enumerate(take)])


def contrast(base: pd.DataFrame, var: pd.DataFrame, tasks: list, keys: list) -> dict:
    """Paired cluster bootstrap of (variant - base), pooled as the unweighted mean over tasks."""
    rng = np.random.default_rng(SEED)
    draws = {k: [] for k in keys}
    per_task = {t: (base[base.task == t], var[var.task == t], words_by_arm(t)) for t in tasks}
    for _ in range(B):
        vb, vv = {k: [] for k in keys}, {k: [] for k in keys}
        for t in tasks:
            db, dv, w = per_task[t]
            arms = db.condition.unique()
            take = rng.choice(arms, size=len(arms), replace=True)
            rb = pd.concat([db[db.condition == a].assign(_b=i) for i, a in enumerate(take)])
            rv = pd.concat([dv[dv.condition == a].assign(_b=i) for i, a in enumerate(take)])
            # a resampled arm appears more than once; the length correlation is over ARMS, so it
            # is computed on the resampled arm list, duplicates included - that is the cluster.
            for frame, store in ((rb, vb), (rv, vv)):
                f = frame.copy()
                f["condition"] = f.condition.astype(str) + "#" + f._b.astype(str)
                ww = {c: w[c.split("#")[0]] for c in f.condition.unique()}
                m = task_metrics(f, ww)
                m["gap"] = m["L_pred"] - m["L_human"]
                for k in keys:
                    store[k].append(m[k])
        for k in keys:
            draws[k].append(np.nanmean(vv[k]) - np.nanmean(vb[k]))
    out = {}
    for k in keys:
        a = np.array(draws[k], dtype=float)
        out[k] = {"delta": float(np.nanmean(a)),
                  "lo": float(np.nanpercentile(a, 2.5)), "hi": float(np.nanpercentile(a, 97.5)),
                  "p_worse": float(np.nanmean(a > 0))}
    return out


def base_draw_null(tasks: list) -> pd.DataFrame:
    """The noise floor: the three already-paid draws of the SAME base prompt, scored one at a time.
    Any variant effect smaller than this spread is a draw, not a treatment."""
    rows = []
    for t in tasks:
        td = RUN / "runs" / PRACTICE / "tasks" / t
        truth = pd.read_csv(td / "sealed" / "truth.csv").rename(columns={"ate": "human"})
        b = json.loads((td / "brief" / "task.json").read_text())
        conds = [a["title"] for a in b["arms"]]
        outs = ([o["name"] for o in b["outcomes"]] if isinstance(b["outcomes"], list)
                else list(b["outcomes"]))
        w = words_by_arm(t)
        for dr in range(3):
            fs = sorted(td.glob("transcript_draw%d_part*.txt" % dr))
            if not fs:
                continue
            f = pd.concat([ssb.predict.parse(x.read_text(), conds, outs) for x in fs])
            f = f.drop_duplicates(["condition", "outcome"], keep="first")
            d = truth.merge(f.rename(columns={"ate": "pred"}), on=["condition", "outcome"])
            m = task_metrics(d, w)
            rows.append({"task": t, "draw": dr, **m, "gap": m["L_pred"] - m["L_human"]})
    return pd.DataFrame(rows)


def main() -> int:
    base = load_pairs(BASE_RUN)
    if base.empty:
        raise SystemExit("no base run at runs/%s - run tools/practice.py --variant base first"
                         % BASE_RUN)
    all_tasks = list(base.task.unique())
    print("=" * 100)
    print("LENGTH-CONTROLLED PROMPT EXPERIMENT - scored against runs/_lenexp/PREREG.md")
    print("=" * 100)

    pb = profile(base, all_tasks)
    print("\n--- base (draw 0 of 20260815-practice-01, re-scored; 0 tokens) ---")
    print(pb.round(3).to_string(index=False))
    print("  pooled: L_pred %+.3f  L_human %+.3f  gap %+.3f | dir %.3f rho %+.3f rmse %.2f"
          % (pb.L_pred.mean(), pb.L_human.mean(), pb.gap.mean(),
             pb.directional_agreement.mean(), pb.spearman_rho.mean(), pb.rmse_pp.mean()))

    null = base_draw_null(all_tasks)
    print("\n--- the null band: the SAME prompt, three independent paid draws ---")
    piv = null.pivot_table(index="draw", values=["gap", "spearman_rho"], aggfunc="mean")
    print(piv.round(4).to_string())
    gap_sd = float(null.groupby("draw").gap.mean().std())
    rho_sd = float(null.groupby("draw").spearman_rho.mean().std())
    print("  pooled draw-to-draw SD:  gap %.4f   spearman_rho %.4f" % (gap_sd, rho_sd))
    print("  -> a variant effect smaller than this is a draw of the dice, not a treatment.")

    keys = ["gap", "L_pred", "spearman_rho", "directional_agreement",
            "pearson_r_within_outcomes", "rmse_pp"]
    results = {}
    for v, run_id in VARIANTS.items():
        pv = load_pairs(run_id)
        if pv.empty:
            print("\n--- %s: NOT RUN ---" % v)
            continue
        tasks = [t for t in all_tasks if t in set(pv.task.unique())]
        pvp, pbp = profile(pv, tasks), profile(base, tasks)
        print("\n" + "-" * 100)
        print("--- %s  (%d tasks: %s) ---" % (v, len(tasks), ", ".join(tasks)))
        j = pbp[["task", "L_pred", "gap", "spearman_rho", "rmse_pp"]].merge(
            pvp[["task", "L_pred", "gap", "spearman_rho", "rmse_pp"]], on="task",
            suffixes=("_base", "_var"))
        print(j.round(3).to_string(index=False))
        c = contrast(pbp_pairs := base[base.task.isin(tasks)], pv, tasks, keys)
        results[v] = {"tasks": tasks, "contrast": c,
                      "base_pooled": pbp.mean(numeric_only=True).to_dict(),
                      "variant_pooled": pvp.mean(numeric_only=True).to_dict()}
        print("  pooled base   : gap %+.3f  L_pred %+.3f  rho %+.3f  dir %.3f  rmse %.2f"
              % (pbp.gap.mean(), pbp.L_pred.mean(), pbp.spearman_rho.mean(),
                 pbp.directional_agreement.mean(), pbp.rmse_pp.mean()))
        print("  pooled variant: gap %+.3f  L_pred %+.3f  rho %+.3f  dir %.3f  rmse %.2f"
              % (pvp.gap.mean(), pvp.L_pred.mean(), pvp.spearman_rho.mean(),
                 pvp.directional_agreement.mean(), pvp.rmse_pp.mean()))
        # Both ends of the margin, always (standing finding 52). The POINT estimate is the pooled
        # difference of the two profiles; the bootstrap MEAN is the average over resamples and is
        # not identical to it - a correlation is a biased statistic under resampling, and here the
        # two differ by up to 0.01. Printing one and calling it the other is how finding 52 happened.
        print("  DELTA (variant - base): point estimate, then the 95% cluster bootstrap on the arm")
        print("    %-28s %8s  %8s  %s" % ("", "point", "boot mean", "95% CI"))
        for k in keys:
            d = c[k]
            point = float(pvp[k].mean() - pbp[k].mean())
            d["point"] = point
            print("    %-28s %+8.4f  %+8.4f  [%+.4f, %+.4f]"
                  % (k, point, d["delta"], d["lo"], d["hi"]))
        if v.startswith("debias"):
            g, r = c["gap"], c["spearman_rho"]
            # the rule is stated on the effect, so it is read on the POINT estimate, with the
            # bootstrap supplying the interval - both must clear their own bar.
            eff = g["hi"] < 0 and abs(g["point"]) > gap_sd
            noninf = r["lo"] >= -0.02
            print("  PREREG rule 1 (gap down, CI excludes 0, beats the %.4f null band): %s"
                  % (gap_sd, "PASS" if eff else "FAIL"))
            print("  PREREG rule 2 (rho non-inferior, CI low >= -0.02): %s"
                  % ("PASS" if noninf else "FAIL"))
            print("  VERDICT for %s: %s" % (v, "PASS - eligible for a target-03 card"
                                            if (eff and noninf) else
                                            "FAIL - the target is not touched"))
    # The mechanism reading declared in PREREG.md is a comparison of the two trimming arms with
    # each other, not of each with base: they share a trimming style and a total word budget and
    # differ only in whether the presented lengths are equal or proportional to the originals.
    pe, pp_ = load_pairs(VARIANTS["eqlen"]), load_pairs(VARIANTS["proptrim"])
    mech = {}
    if not pe.empty and not pp_.empty:
        tasks = [t for t in all_tasks if t in set(pe.task.unique()) & set(pp_.task.unique())]
        print("\n" + "-" * 100)
        print("--- MECHANISM: eqlen - proptrim (same trimming, same total words kept, "
              "length ordering destroyed vs preserved) ---")
        mech = contrast(pp_, pe, tasks, ["L_pred", "spearman_rho", "pearson_r_within_outcomes",
                                         "rmse_pp"])
        for k, d in mech.items():
            print("    %-28s %+.4f  [%+.4f, %+.4f]" % (k, d["delta"], d["lo"], d["hi"]))
        ep, pq = profile(pe, tasks), profile(pp_, tasks)
        print("    L_pred: base %+.3f -> proptrim %+.3f -> eqlen %+.3f"
              % (profile(base, tasks).L_pred.mean(), pq.L_pred.mean(), ep.L_pred.mean()))
        print("    accuracy cost of trimming is paid by BOTH arms: rho %+.3f (prop) vs %+.3f (eq)"
              % (pq.spearman_rho.mean(), ep.spearman_rho.mean()))

    (RUN / "runs/_lenexp/results.json").write_text(json.dumps(
        {"null_band": {"gap_sd": gap_sd, "rho_sd": rho_sd},
         "base_profile": pb.to_dict("records"),
         "null_draws": null.to_dict("records"),
         "variants": results, "mechanism_eqlen_minus_proptrim": mech}, indent=1, default=float))
    print("\nwritten -> runs/_lenexp/results.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())
