#!/usr/bin/env python
"""Is the predicted ranking of messages driven by how LONG each message is?

Section 1 scores Spearman rho on the ordering of the 16 interventions, so what that ordering is
actually made of is worth knowing. Nothing had asked. On the deposited target card the answer is
uncomfortable: predicted mean effect correlates with stimulus word count at **Spearman +0.726**.

    /opt/kernel/venv/bin/python tools/length_bias.py runs/20260815-target-01

Prints the target correlation with a bootstrap interval over arms, then the same statistic on the
five practice tasks where the HUMAN ordering is known - which is the only way to tell a bias from a
real effect, because longer messages carry more arguments and humans may reward that too.

The honest reading is in the output: the predictor over-weights length relative to humans on
average, the target card sits at the top of its own range, and on one of five practice tasks humans
leaned on length MORE than the predictor did. A flag for a later session, not a defect to patch -
and certainly not a reason to edit a deposited prediction after the fact.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
TASKS = ["voelkel2026", "goldwert2026", "vlasceanu2024", "bbprime2025", "voelkel2024"]


def boot(x, y, B=5000, seed=0):
    rng = np.random.default_rng(seed)
    n, out = len(x), []
    for _ in range(B):
        i = rng.integers(0, n, n)
        xs, ys = pd.Series(x.iloc[i].values), pd.Series(y.iloc[i].values)
        if xs.nunique() > 2:
            out.append(xs.corr(ys, method="spearman"))
    return np.nanpercentile(out, [2.5, 97.5]) if out else (np.nan, np.nan)


def main(run):
    d = RUN / run
    st = json.loads((RUN / "inputs/stimuli.json").read_text())["stimuli"]
    arms = pd.DataFrame([{"condition": s["title"], "words": s["n_words"]}
                         for s in st if s["title"] != "control"])
    raw = pd.read_csv(d / "stages/target/ate_pp_raw.csv")
    am = raw.groupby("condition").ate.mean().rename("pred").reset_index()
    m = am.merge(arms, on="condition")
    rho = m.pred.corr(m.words, method="spearman")
    lo, hi = boot(m.pred, m.words)
    print(f"\n=== TARGET card ({run}), {len(m)} interventions ===")
    print(f"  Spearman(predicted mean ATE, words) = {rho:+.3f}   95% CI [{lo:+.3f}, {hi:+.3f}]")
    big = m.words.max()
    m2 = m[m.words < big]
    print(f"  excluding the {big:,}-word outlier (n={len(m2)}): "
          f"{m2.pred.corr(m2.words, method='spearman'):+.3f}")
    print(f"  Pearson on log(words): {m.pred.corr(np.log(m.words)):+.3f}")
    print("\n  ranking, longest-effect first:")
    for _, r in m.sort_values("pred", ascending=False).iterrows():
        print(f"    {r.condition:30s} {int(r.words):5d} words   {r.pred:+.2f} pp")

    print("\n=== the same statistic where the HUMAN ordering is known ===")
    p1 = pd.read_csv(RUN / "runs/20260815-practice-01/stages/calibration/pairs.csv")
    rows = []
    for t in TASKS:
        f = RUN / f"inputs/texts/{t}_arms.json"
        if not f.exists():
            continue
        ln = {k: len(str(v).split()) for k, v in json.loads(f.read_text()).items()}
        g = p1[p1.task == t].groupby("condition").agg(pred=("pred", "mean"),
                                                      human=("human", "mean")).reset_index()
        g["words"] = g.condition.map(ln)
        g = g.dropna(subset=["words"])
        if len(g) < 5:
            continue
        rows.append({"task": t, "arms": len(g),
                     "pred_vs_len": g.pred.corr(g.words, method="spearman"),
                     "human_vs_len": g.human.corr(g.words, method="spearman")})
    L = pd.DataFrame(rows)
    L["gap"] = L.pred_vs_len - L.human_vs_len
    print(L.round(3).to_string(index=False))
    print(f"\n  mean predictor {L.pred_vs_len.mean():+.3f} vs mean human {L.human_vs_len.mean():+.3f}"
          f"  ->  the predictor over-weights length by {L.gap.mean():+.3f} on average")
    over = int((L.gap > 0).sum())
    print(f"  predictor leans on length MORE than humans on {over} of {len(L)} tasks")

    print("\nVERDICT: the target card's ordering is substantially explained by message length "
          f"({rho:+.3f}),")
    print("  which is above the predictor's own practice average and above what humans typically")
    print("  reward - but the human length-correlation ON THE TARGET is sealed and unknown, and on")
    print(f"  {len(L) - over} of {len(L)} practice tasks humans leaned on length MORE than the "
          "predictor did.")
    print("  A flag and a concrete experiment for a later session (a length-controlled prompt),")
    print("  NOT grounds for editing a deposited prediction after seeing the diagnostic.")
    return 0


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("run", nargs="?", default="runs/20260815-target-01")
    sys.exit(main(a.parse_args().run))
