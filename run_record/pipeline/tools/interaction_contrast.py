#!/usr/bin/env python
"""What the finalized prereg's moderator ruling does to this deposit (TASK_08 item 1).

The ruling: Tier-1 subgroup metrics are recomputed from the individual rows via
`run_moderator_model()` on human reference and submission alike, and a subgroup effect is scored
as an **interaction contrast against a reference level** - the group's treatment effect minus the
reference group's - not as a raw subgroup ATE.

The harness never predicted moderation (`responsiveness.factor = 1` everywhere, standing finding
53), so the two readings should both come out at "no differential effect". "Should" is not a
measurement, so this recomputes both from the deposited artefacts:

    /opt/kernel/venv/bin/python tools/interaction_contrast.py runs/20260815-target-01

Reading A (raw subgroup ATE)     ATE[m,l,i,o] = mean(l, i) - mean(l, control)
Reading B (interaction contrast) A minus the same quantity at the reference level of m

for both the deposited Tier-1 rows (what a scorer recomputes) and the Tier-2 moderator cells
(what a scorer reads straight off the file). The two are DIFFERENT under the ruling and that is
the point of running it: Tier 2 submits exact zeros, Tier 1 submits synthesis noise around zero.
"""
import argparse, glob, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
SCALE_TO_PP = {"donation_ams": 10.0, "newsletter_signup": 100.0}
MODERATORS = ("gender", "age_band", "race", "education", "income", "party")


def pp(df, col, outcome_col="outcome"):
    return df[col] * df[outcome_col].map(SCALE_TO_PP).fillna(1.0)


def subgroup_ates_from_rows(t1, outcomes, mods):
    rows = []
    for m in mods:
        for l, g in t1.groupby(m):
            ctrl = g[g.condition == "control"]
            for c in sorted(set(g.condition) - {"control"}):
                gc = g[g.condition == c]
                for o in outcomes:
                    rows.append({"moderator": m, "level": l, "condition": c, "outcome": o,
                                 "ate": gc[o].mean() - ctrl[o].mean(), "n": len(gc)})
    return pd.DataFrame(rows)


def contrasts(ates, ref_of):
    ref = ates[ates.apply(lambda r: r.level == ref_of[r.moderator], axis=1)]
    key = ["moderator", "condition", "outcome"]
    j = ates.merge(ref[key + ["ate"]].rename(columns={"ate": "ate_ref"}), on=key)
    j["contrast"] = j.ate - j.ate_ref
    return j[j.level != j.moderator.map(ref_of)]


def main(run):
    d = RUN / run
    t1 = pd.read_csv(d / "stages/tier1.csv")
    card = pd.read_csv(d / "card/ate.csv")
    outcomes = sorted(card.outcome.unique())
    mods = [m for m in MODERATORS if m in t1.columns]
    print(f"{run}: {len(t1):,} Tier-1 rows, {len(mods)} moderators {mods}")

    marg = card.set_index(["condition", "outcome"]).ate
    a = subgroup_ates_from_rows(t1, outcomes, mods)
    a["ate_pp"] = pp(a, "ate")
    a["marg_pp"] = pp(a.assign(m=[marg[(c, o)] for c, o in zip(a.condition, a.outcome)]), "m")
    ref_of = {m: sorted(t1[m].unique())[0] for m in mods}
    print("  reference level per moderator:",
          ", ".join(f"{m}={ref_of[m]}" for m in mods))

    print("\n=== Reading A: raw subgroup ATEs, recomputed from the deposited rows ===")
    dev = (a.ate_pp - a.marg_pp)
    print(f"  {len(a):,} subgroup cells; |subgroup ATE - marginal ATE| "
          f"mean {dev.abs().mean():.3f} pp, max {dev.abs().max():.3f} pp")
    print(f"  (the card INTENDS these to be equal - responsiveness 1.0 - so every departure is "
          f"thin-cell synthesis noise)")
    thin = a.groupby(["moderator", "level"]).n.min()
    print(f"  smallest cell: {thin.min():,} rows ({thin.idxmin()})")

    print("\n=== Reading B: interaction contrasts against the reference level ===")
    cB = contrasts(a, ref_of)
    cB["contrast_pp"] = pp(cB, "contrast")
    print(f"  {len(cB):,} contrast cells (levels minus reference)")
    print(f"  intended value: EXACTLY 0.0 - the card predicts no moderation")
    print(f"  recomputed from rows: mean {cB.contrast_pp.mean():+.4f} pp, "
          f"SD {cB.contrast_pp.std():.3f} pp, max |.| {cB.contrast_pp.abs().max():.3f} pp")
    frac_pos = (cB.contrast_pp > 0).mean()
    print(f"  share strictly positive {frac_pos:.4f} (a coin flip is 0.5; an exact zero would be "
          f"scored 0.5 by the frozen table)")

    print("\n=== the same two readings on the Tier-2 moderator FILE (submitted, not recomputed) ===")
    modp = next(iter(glob.glob(str(d / "submission_T2/predictions/*cells_moderator*.csv"))), None)
    if modp:
        t2 = pd.read_csv(modp)
        print(f"  {Path(modp).name}: {len(t2):,} cells, {int(t2.isna().sum().sum())} NA "
              f"(the prereg forbids NA; 'no moderation' = repeat the condition mean)")
        ctrl = t2[t2.condition == "control"].set_index(["moderator", "moderator_level", "outcome"])["mean"]
        iv = t2[t2.condition != "control"].copy()
        iv["ate"] = iv["mean"] - [ctrl[(m, l, o)] for m, l, o in
                                  zip(iv.moderator, iv.moderator_level, iv.outcome)]
        iv["ate_pp"] = pp(iv, "ate")
        base = iv.rename(columns={"moderator_level": "level"})
        cB2 = contrasts(base[["moderator", "level", "condition", "outcome", "ate"]], ref_of)
        cB2["contrast_pp"] = pp(cB2, "contrast")
        print(f"  Reading A: |subgroup ATE - marginal ATE| max "
              f"{(base.ate_pp - pp(base.assign(m=[marg[(c, o)] for c, o in zip(base.condition, base.outcome)]), 'm')).abs().max():.10f} pp")
        print(f"  Reading B: max |interaction contrast| {cB2.contrast_pp.abs().max():.10f} pp "
              f"over {len(cB2):,} cells")
    else:
        print("  no Tier-2 moderator file found")

    print("\n=== the delta the ruling makes to THIS deposit ===")
    print("  Reading A would have scored our subgroup cells as the marginal ATE repeated in every")
    print("  group, which inherits the main-effect ranking; Reading B scores the level-vs-reference")
    print("  DIFFERENCE, which we predict as exactly zero. No prediction changes, no re-run is")
    print("  needed - but the two readings are not scored alike:")
    print(f"    Tier 2 (cells submitted directly)  contrast = {cB2.contrast_pp.abs().max():.2e} pp "
          f"-> an exact zero, scored 0.5 directional by the frozen table")
    print(f"    Tier 1 (recomputed from rows)      contrast = 0 +/- {cB.contrast_pp.std():.3f} pp "
          f"-> a coin flip per cell, same 0.5 in expectation with variance added")
    out = {"run": run, "n_subgroup_cells": len(a), "n_contrast_cells": len(cB),
           "tier1_contrast_sd_pp": float(cB.contrast_pp.std()),
           "tier1_contrast_max_pp": float(cB.contrast_pp.abs().max()),
           "tier1_share_positive": float(frac_pos),
           "tier2_contrast_max_pp": float(cB2.contrast_pp.abs().max()) if modp else None,
           "tier2_na_cells": int(t2.isna().sum().sum()) if modp else None,
           "reference_levels": ref_of, "min_cell_rows": int(thin.min())}
    (d / "stages" / "interaction_contrast.json").write_text(json.dumps(out, indent=1))
    print(f"\nwritten: {d / 'stages' / 'interaction_contrast.json'}")
    return 0


if __name__ == "__main__":
    a_ = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    a_.add_argument("run", nargs="?", default="runs/20260815-target-01")
    sys.exit(main(a_.parse_args().run))
