#!/usr/bin/env python
"""Does the synthetic data exaggerate demographic group differences? A Tier-1 Section-4 row, measured.

The frozen table's "Demographic predictability" row asks exactly this: "R^2 of outcomes on
moderators: does the synthetic data exaggerate group differences relative to humans?" Nothing had
ever computed it. `inputs/baselines/` anchors 351 of 351 subgroup cells on real data (finding 11),
which makes the offsets defensible one at a time and says nothing about their JOINT strength.

    /opt/kernel/venv/bin/python tools/demographic_predictability.py runs/20260815-target-01

Regresses each outcome on the six moderators in the deposited control rows and compares to the same
regression on the control arms of the five training datasets.

Two confounds it controls, because the uncontrolled version reads 3.2x and is meaningless:
  - R^2 rises mechanically with the number of dummies, and the datasets carry 2-5 moderators against
    the deposit's 6, so every comparison is run on a MATCHED moderator set and on ADJUSTED R^2;
  - predictability is a property of the CONSTRUCT, not of the synthesis. Climate attitudes are
    party-polarised and democracy/emotion outcomes are not, so pooling the five datasets compares
    the deposit against constructs the target does not measure. The per-moderator table is the
    readable one.
"""
import argparse, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
from ssb import task as T  # noqa: E402

TASKS = ["voelkel2026", "goldwert2026", "vlasceanu2024", "bbprime2025", "voelkel2024"]
CLIMATE_REF = "voelkel2026"   # the only climate-attitude dataset with a party cut
MODS = ["gender", "age_band", "race", "education", "income", "party"]


def adj_r2(df, outcols, modcols):
    cols = [m for m in modcols if m in df.columns]
    if not cols:
        return {}
    X = pd.get_dummies(df[cols].astype(str), drop_first=True).astype(float).values
    X = np.column_stack([np.ones(len(X)), X])
    p = X.shape[1] - 1
    out = {}
    for o in outcols:
        if o not in df.columns:
            continue
        y = df[o].astype(float).values
        ok = np.isfinite(y)
        if ok.sum() < 50 or p >= ok.sum() - 1:
            continue
        b, _, _, _ = np.linalg.lstsq(X[ok], y[ok], rcond=None)
        ss = ((y[ok] - y[ok].mean()) ** 2).sum()
        if ss <= 0:
            continue
        r2 = 1 - (((y[ok] - X[ok] @ b) ** 2).sum() / ss)
        out[o] = 1 - (1 - r2) * (ok.sum() - 1) / (ok.sum() - p - 1)
    return out


def main(run):
    d = RUN / run
    t1 = pd.read_csv(d / "stages/tier1.csv")
    ctrl = t1[t1.condition == "control"]
    outs = [c for c in pd.read_csv(d / "card/ate.csv").outcome.unique() if c in t1.columns]
    print(f"\n{run}: {len(ctrl):,} control rows, {len(outs)} outcomes, {len(MODS)} moderators")

    print("\n=== per moderator, adjusted R^2 (the readable comparison) ===")
    rows = {}
    for n in TASKS:
        ad = T.load_adapter(n)
        df = T.load_dataset(ad)
        oc = list(ad.get("outcomes", {})) if isinstance(ad.get("outcomes"), dict) \
            else list(ad.get("outcomes", []))
        have = [o for o in oc if o in df.columns]
        r = {}
        for m in MODS:
            if m in ad.get("moderators", {}):
                v = adj_r2(df, have, [m])
                if v:
                    r[m] = np.mean(list(v.values()))
        rows[n] = r
    syn = {}
    for m in MODS:
        v = adj_r2(ctrl, outs, [m])
        if v:
            syn[m] = np.mean(list(v.values()))
    tab = pd.DataFrame(rows).T
    tab.loc["** DEPOSITED **"] = pd.Series(syn)
    print(tab.round(4).to_string())

    print(f"\n=== deposit against the CLIMATE reference ({CLIMATE_REF}) and against all others ===")
    ref = pd.Series(rows[CLIMATE_REF])
    other = pd.DataFrame({k: v for k, v in rows.items() if k != CLIMATE_REF}).T.max()
    cmp = pd.DataFrame({"deposited": pd.Series(syn), "climate_ref": ref, "best_other": other})
    cmp["vs_climate"] = cmp.deposited / cmp.climate_ref
    cmp["vs_best_other"] = cmp.deposited / cmp.best_other
    print(cmp.round(4).to_string())

    flagged = cmp[(cmp.climate_ref.isna()) & (cmp.vs_best_other > 2.0)]
    print("\nVERDICT:")
    ok = cmp.dropna(subset=["vs_climate"])
    print(f"  moderators WITH a climate reference: {', '.join(ok.index)} at "
          f"{ok.vs_climate.min():.2f}-{ok.vs_climate.max():.2f}x - the deposit sits at the climate")
    print("  level, which is the target's construct. Party carries it (climate is party-polarised).")
    if len(flagged):
        print(f"  NO climate reference and >2x every human value: {', '.join(flagged.index)}")
        print("  These are anchored on real cuts (finding 11) but their JOINT strength is unchecked,")
        print("  and every dataset that could check them measures a non-climate construct.")
        print("  Unresolved risk, not a proven error - the same shape as finding 33. See OPEN item 21.")
    return 0


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("run", nargs="?", default="runs/20260815-target-01")
    sys.exit(main(a.parse_args().run))
