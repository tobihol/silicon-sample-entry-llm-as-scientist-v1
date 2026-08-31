#!/usr/bin/env python
"""TASK_15 direction 2: does the predictor distort ONE DIMENSION of a trust battery?

0 model calls - every prediction it reads was paid for in sessions 13 and 14.

    /opt/kernel/venv/bin/python tools/subscale_bias.py

The question, and why it is about the card's primary outcome. The target's PRIMARY outcome
`trust_multidimensional` is the mean of FOUR subscales - competence, integrity, benevolence,
openness (`/workspace/benchmark/codebook.csv` rows 55-59) - and the harness predicts the composite
directly, never the subscales. If this predictor systematically moves the COMPETENCE dimension
differently from the moral dimensions, a four-dimension mean inherits a quarter of that distortion
and nothing in the practice loop would ever show it: no practice task before session 13 had a trust
battery at all (standing finding 33).

Two carved tasks DO carry the subscales, and they are the only two on the mounted data:
  * koetke2024 Study 5 - METI expertise (6 items) / integrity (4) / benevolence (4) + the composite.
    Three arms in which a scientist admits the limits of her methods, the limits of her results, or
    her own personal fallibility - exactly the stimulus family that could cost perceived competence.
  * altenmueller2024 Study 4b - the same battery split expertise (6) vs morality (8), two arms.

## The estimand (fixed before the arithmetic below was run)

The composite inherits a DIMENSION-SPECIFIC distortion, not the overall magnitude error - standing
findings 78/84/88 already measure the latter, and a common shift moves every subscale together and
so cannot bend one dimension against another. So per model line m and arm a, with e = predicted -
human on each subscale:

    b_competence(m, a) = e_competence - mean(e over the MORAL subscales)

and the bias it implies in an equal-weight four-dimension mean is `b_competence / 4` (or `2/4` if
`openness`, which no carved task measures, carries the same distortion as competence, since both are
non-moral dimensions - reported as a bracket, not as a point).

## The recommendation rule (fixed before the arithmetic, and deliberately hard to pass)

A correction to the card's trust cells is RECOMMENDED (to the operator - never applied here; RUNBOOK
2a) only if all three hold:
  1. the sign of `b_competence` agrees across BOTH tasks and ALL THREE model lines;
  2. |b_competence / 4| exceeds the target's own SE(ATE) on `trust_multidimensional`, which is
     sigma sqrt(2/n) = 20.6 sqrt(2/529) = 1.27 pp - a correction below the study's own resolution
     cannot be scored as an improvement;
  3. the target's arms plausibly belong to the same stimulus family (a scientist conceding
     limitations), which is a reading of the 16 stimuli, reported here and not voted on.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
KOETKE = {"opus-5": "20260819-practice-koetke", "fable-5": "20260819-practice-koetke-fable-5",
          "sonnet-5": "20260819-practice-koetke-sonnet-5"}
ALT = {"opus-5": "20260820-practice-alt", "fable-5": "20260820-practice-alt-fable-5",
       "sonnet-5": "20260820-practice-alt-sonnet-5"}
TARGET_SE = 20.6 * np.sqrt(2 / (18000 / 17 / 2))          # trust_multidimensional, Human 1


def frames(runs, task):
    truth = pd.read_csv(RUN / "runs" / list(runs.values())[0] / "tasks" / task / "sealed"
                        / "truth.csv").pivot(index="condition", columns="outcome", values="ate")
    pred = {m: pd.read_csv(RUN / "runs" / r / "tasks" / task / "prediction.csv")
            .pivot(index="condition", columns="outcome", values="ate") for m, r in runs.items()}
    return truth, pred


def leg(name, runs, task, comp, moral, composite=None):
    truth, pred = frames(runs, task)
    print("\n" + "=" * 96)
    print("%s - competence dimension `%s` against the moral dimensions %s" % (name, comp, moral))
    print("\n  HUMAN ATEs (pp of scale range)")
    cols = [comp] + moral + ([composite] if composite else [])
    print(truth[cols].round(2).to_string().replace("\n", "\n  "))
    rows = []
    for m, p in pred.items():
        print("\n  PREDICTED - %s" % m)
        print(p[cols].round(2).to_string().replace("\n", "\n  "))
        for a in truth.index:
            e_c = p.loc[a, comp] - truth.loc[a, comp]
            e_m = float(np.mean([p.loc[a, o] - truth.loc[a, o] for o in moral]))
            rows.append({"task": task, "model": m, "arm": a, "e_comp": e_c, "e_moral": e_m,
                         "b_comp": e_c - e_m,
                         "gap_h": float(np.mean([truth.loc[a, o] for o in moral])) - truth.loc[a, comp],
                         "gap_p": float(np.mean([p.loc[a, o] for o in moral])) - p.loc[a, comp]})
    d = pd.DataFrame(rows)
    print("\n  PER-ARM ERRORS  (e = predicted - human;  b = e_competence - mean e_moral)")
    print("  %-10s%-26s%10s%10s%10s%12s%12s" %
          ("model", "arm", "e_comp", "e_moral", "b_comp", "gap human", "gap pred"))
    for r in d.itertuples():
        print("  %-10s%-26s%10.2f%10.2f%10.2f%12.2f%12.2f"
              % (r.model, r.arm[:25], r.e_comp, r.e_moral, r.b_comp, r.gap_h, r.gap_p))
    print("\n  by model:  " + " | ".join("%s b = %+.2f" % (m, g.b_comp.mean())
                                         for m, g in d.groupby("model")))
    print("  pooled  b_competence = %+.2f pp  (arm-mean range %+.2f to %+.2f)"
          % (d.b_comp.mean(), d.groupby("arm").b_comp.mean().min(),
             d.groupby("arm").b_comp.mean().max()))
    print("  the DISSOCIATION GAP (moral minus competence, in the effects themselves):"
          " human %+.2f, predicted %+.2f -> the predictor %s the dissociation"
          % (d.gap_h.mean(), d.gap_p.mean(),
             "understates" if d.gap_p.mean() < d.gap_h.mean() else "overstates"))
    return d


def main():
    print(__doc__)
    k = leg("koetke2024 Study 5", KOETKE, "koetke2024", "trust_expertise",
            ["trust_integrity", "trust_benevolence"], "trust_meti")
    a = leg("altenmueller2024 Study 4b", ALT, "altenmueller2024", "trust_expertise",
            ["trust_morality"])
    both = pd.concat([k, a])

    print("\n" + "=" * 96)
    print("VERDICT")
    per_task = both.groupby("task").b_comp.mean()
    per_model = both.groupby("model").b_comp.mean()
    print("  b_competence by task : %s" % ", ".join("%s %+.2f" % (t, v) for t, v in per_task.items()))
    print("  b_competence by model: %s" % ", ".join("%s %+.2f" % (m, v) for m, v in per_model.items()))
    signs = set(np.sign(list(per_task.values) + list(per_model.values)))
    agree = len(signs) == 1
    b = float(both.b_comp.mean())
    print("\n  1. sign agrees across both tasks and all three lines: %s" % ("YES" if agree else "NO"))
    print("  2. implied bias in an equal-weight FOUR-dimension mean: %+.2f pp"
          " (bracket %+.2f pp if `openness` carries it too)" % (b / 4, b / 2))
    print("     target resolution SE(ATE) on trust_multidimensional = %.2f pp -> |bias| %s SE"
          % (TARGET_SE, "exceeds" if abs(b / 4) > TARGET_SE else "is BELOW"))
    rec = agree and abs(b / 4) > TARGET_SE
    print("\n  RECOMMENDATION: %s" % ("PENDING-OPERATOR - a correction of %+.2f pp on the card's 16"
                                      " trust_multidimensional cells" % (b / 4) if rec else
                                      "NO CORRECTION. Rule 2 fails: the dimension-specific"
                                      " distortion is smaller than the study's own resolution, so"
                                      " applying it could not be scored as an improvement and would"
                                      " be choosing an output from a diagnostic (RUNBOOK 2a)."))

    # what the card itself does across its two trust readings - a free consistency check
    ate = pd.read_csv(RUN / "runs/20260815-target-01/card/ate.csv")
    w = ate.pivot(index="condition", columns="outcome", values="ate")
    print("\n  FREE CHECK on the card: `trust_multidimensional` against the single-item"
          " `trust_post` over its 16 arms")
    print("     mean %.2f vs %.2f pp, difference %+.2f pp, Pearson r %+.3f, Spearman %+.3f"
          % (w.trust_multidimensional.mean(), w.trust_post.mean(),
             (w.trust_multidimensional - w.trust_post).mean(),
             w.trust_multidimensional.corr(w.trust_post),
             w.trust_multidimensional.corr(w.trust_post, method="spearman")))
    print("     a composite that were a pure halo of the single item would read r = 1.000;"
          " it does not, so the card does distinguish them.")
    out = {"b_competence_pooled": b, "composite_bias_quarter": b / 4,
           "composite_bias_half": b / 2, "target_se": float(TARGET_SE),
           "sign_agrees": bool(agree), "recommend_correction": bool(rec),
           "by_task": per_task.to_dict(), "by_model": per_model.to_dict()}
    (RUN / "runs/_subscale").mkdir(exist_ok=True)
    (RUN / "runs/_subscale/subscale_bias.json").write_text(json.dumps(out, indent=1))
    both.to_csv(RUN / "runs/_subscale/errors.csv", index=False)
    print("\nwrote runs/_subscale/{subscale_bias.json,errors.csv}")


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    main()
