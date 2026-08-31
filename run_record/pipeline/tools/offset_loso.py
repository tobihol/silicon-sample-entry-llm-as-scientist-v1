#!/usr/bin/env python
"""Is the card's subgroup surface wrong, or is the surface itself untransferable? LOSO across anchors.

    /opt/kernel/venv/bin/python tools/offset_loso.py        # 0 model tokens, reads runs/_offsets/

`tools/subgroup_audit.py` regresses held-out human offsets on the card's and reads the slope b.
A small b has two readings and they demand opposite actions:

  (i)  the card exaggerates a real group difference  -> shrink it (a multiplier helps);
  (ii) group differences do not transfer between samples at all -> no offset table could do
       better, and the shrinkage is toward zero because zero is the best available prediction.

The two are separated by measuring the SAME transfer between two HUMAN datasets. If human A's
offsets predict human B's with b ~ 1 and high r, the surface is real and (i) holds. If human-human
transfer is as weak as card-human transfer, (ii) holds and the honest response is shrinkage, not a
better anchor.

Then leave-one-dataset-out: fit a per-moderator multiplier k_m on the other held-out anchors,
predict the held-out one, and compare RMSE against the card as deposited (k = 1) and against an
all-zero subgroup table (k = 0, the prediction finding 11 replaced). Verdict rules are fixed in
runs/_offsets/PREREG.md V4 and are applied here, not chosen here.
"""
import argparse, itertools, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]


def load(out_dir):
    raw = json.load(open(out_dir / "audit_offsets.json"))
    rows = []
    for k, v in raw.items():
        ds, mod, fam = k.split("|")
        for l in set(v["oc"]) & set(v["oh"]):
            rows.append(dict(dataset=ds, moderator=mod, family=fam, level=l,
                             oc=v["oc"][l], oh=v["oh"][l], n=v["ns"].get(l, 0),
                             status=v["status"], scale=v["scale"]))
    return pd.DataFrame(rows)


def slope(c, h):
    c, h = np.asarray(c, float), np.asarray(h, float)
    den = float((c * c).sum())
    return float((c * h).sum() / den) if den > 1e-12 else np.nan


def main(out_dir, boot, seed):
    df = load(out_dir)
    held = df[df.status.str.startswith("heldout")].copy()
    rng = np.random.default_rng(seed)
    pd.set_option("display.width", 200)

    # ---- 1. human-human transfer: the noise floor the card is being judged against ----------
    print("=== 1. HUMAN-vs-HUMAN transfer (does the surface transfer between samples at all?) ===")
    hh = []
    for (mod, fam), g in held.groupby(["moderator", "family"]):
        for a, b in itertools.combinations(sorted(g.dataset.unique()), 2):
            ga, gb = g[g.dataset == a], g[g.dataset == b]
            m = ga.merge(gb, on="level", suffixes=("_a", "_b"))
            if len(m) < 3:
                continue
            hh.append(dict(moderator=mod, family=fam, a=a, b_ds=b, n_levels=len(m),
                           b=slope(m.oh_a, m.oh_b),
                           r=float(np.corrcoef(m.oh_a, m.oh_b)[0, 1]),
                           rmse=float(np.sqrt(((m.oh_a - m.oh_b) ** 2).mean()))))
    hh = pd.DataFrame(hh)
    if len(hh):
        print(hh.round(3).to_string(index=False))
        print("\n  per moderator, human-human vs card-human:")
        for mod, g in hh.groupby("moderator"):
            ch = held[held.moderator == mod]
            print(f"    {mod:10s} human-human r median {g.r.median():+.3f} (n={len(g)} pairs)   "
                  f"card-human r {float(np.corrcoef(ch.oc, ch.oh)[0, 1]):+.3f}   "
                  f"card-human b {slope(ch.oc, ch.oh):.3f}")
    else:
        print("  no (moderator, family) carries two held-out datasets")

    # ---- 2. leave-one-dataset-out multiplier ------------------------------------------------
    print("\n=== 2. LOSO: fit k_m on the other anchors, score the held-out one (RMSE, pp) ===")
    rows = []
    for mod, g in held.groupby("moderator"):
        ds = sorted(g.dataset.unique())
        if len(ds) < 2:
            continue
        for d in ds:
            tr, te = g[g.dataset != d], g[g.dataset == d]
            k = slope(tr.oc, tr.oh)
            rmse = lambda p: float(np.sqrt(((te.oh - p) ** 2).mean()))
            # empirical ceiling: predict the held-out anchor from the OTHER HUMAN anchors.
            # Same (family, level) where another anchor has it, else the same level pooled over
            # families. If no other anchor sees the level at all, the ceiling is undefined there
            # and the row is scored on the covered subset only.
            fam_mean = tr.groupby(["family", "level"]).oh.mean()
            lvl_mean = tr.groupby("level").oh.mean()
            pred, mask = [], []
            for _, x in te.iterrows():
                if (x.family, x.level) in fam_mean.index:
                    pred.append(float(fam_mean.loc[(x.family, x.level)])); mask.append(True)
                elif x.level in lvl_mean.index:
                    pred.append(float(lvl_mean.loc[x.level])); mask.append(True)
                else:
                    pred.append(np.nan); mask.append(False)
            pred, mask = np.array(pred), np.array(mask)
            ceil = (float(np.sqrt(((te.oh.to_numpy()[mask] - pred[mask]) ** 2).mean()))
                    if mask.any() else np.nan)
            rows.append(dict(moderator=mod, heldout=d, n_levels=len(te), k_fitted=k,
                             rmse_card=rmse(te.oc), rmse_k=rmse(k * te.oc),
                             rmse_zero=rmse(0.0), rmse_humanmean=ceil, ceil_cov=int(mask.sum()),
                             win_vs_card=rmse(k * te.oc) < rmse(te.oc),
                             zero_beats_card=rmse(0.0) < rmse(te.oc)))
    loso = pd.DataFrame(rows)
    print(loso.round(3).to_string(index=False))

    print("\n  A HUMAN anchor predicting another human anchor (rmse_humanmean) is the empirical")
    print("  ceiling: no offset table built from surveys can do better than one real study does")
    print("  at predicting another. Read rmse_k against it, not against zero.")
    if "rmse_humanmean" in loso:
        z = loso.dropna(subset=["rmse_humanmean"])
        print(f"  mean over folds: card {z.rmse_card.mean():.2f} | k*card {z.rmse_k.mean():.2f} | "
              f"zero {z.rmse_zero.mean():.2f} | human-mean {z.rmse_humanmean.mean():.2f} pp")

    print("\n=== 3. verdict per moderator (PREREG V4) ===")
    ver = []
    for mod, g in loso.groupby("moderator"):
        all_m = held[held.moderator == mod]
        b_full = slope(all_m.oc, all_m.oh)
        bs = [slope(all_m.oc.values[i], all_m.oh.values[i])
              for i in (rng.integers(0, len(all_m), len(all_m)) for _ in range(boot))]
        lo, hi = np.percentile(bs, [2.5, 97.5])
        v1 = not (lo <= 1.0 <= hi)
        folds = len(g)
        wins = int(g.win_vs_card.sum())
        mean_gain = float((g.rmse_card - g.rmse_k).mean())
        v4b = (mean_gain > 0) and (wins / folds >= 2 / 3)
        ver.append(dict(moderator=mod, b=b_full, b_lo=lo, b_hi=hi, V1_flagged=v1,
                        folds=folds, folds_won=wins, mean_rmse_gain_pp=mean_gain,
                        zero_beats_card_folds=int(g.zero_beats_card.sum()),
                        RECOMMEND=("SHRINK to k=%.2f" % b_full) if (v1 and v4b) else
                                  ("measured, not recommended" if v1 else "no change")))
    ver = pd.DataFrame(ver)
    print(ver.round(3).to_string(index=False))
    ver.to_csv(out_dir / "loso_verdict.csv", index=False)

    print("\n=== 4. per LEVEL: what the held-out anchors say about each of the 27 offsets ===")
    lv = []
    for (mod, l), g in held.groupby(["moderator", "level"]):
        b_l = slope(g.oc, g.oh)
        lv.append(dict(moderator=mod, level=l, n_cells=len(g),
                       n_datasets=g.dataset.nunique(), n_resp=int(g.n.sum()),
                       card_mean=float(g.oc.mean()), human_mean=float(g.oh.mean()),
                       ratio=b_l, sign_agree=float((np.sign(g.oc) == np.sign(g.oh)).mean()),
                       mean_abs_err=float((g.oh - g.oc).abs().mean())))
    lv = pd.DataFrame(lv).sort_values(["moderator", "level"])
    lv.to_csv(out_dir / "per_level.csv", index=False)
    print(lv.round(3).to_string(index=False))
    loso.to_csv(out_dir / "loso_folds.csv", index=False)
    if len(hh):
        hh.to_csv(out_dir / "human_human.csv", index=False)
    print(f"\nwrote {out_dir}/loso_folds.csv, loso_verdict.csv, human_human.csv")
    return 0



# ---- 5. sensitivity: which anchors, and what GAP4 ------------------------------------------
SAMPLE_TYPE = {          # how the anchor's respondents were recruited (adapter descriptions)
    "orchinik2024": "quota", "dablander2025": "quota", "voelkel2026": "quota",
    "kim2024": "convenience", "altenmueller2024": "convenience", "koetke2024": "convenience",
    "bbprime2025": "screened",        # Prolific, skewed young AND screened to climate believers
    "gligoric2025": "screened",       # conservatives only
}


def run_sens(out_dir):
    df = load(out_dir)
    held = df[df.status.str.startswith("heldout")].copy()
    held["stype"] = held.dataset.map(SAMPLE_TYPE)
    print("=== 5a. pooled b per moderator by ANCHOR SUBSET (b<1 = the card exaggerates) ===")
    subsets = {
        "all held-out": held,
        "slider items only": held[held.scale == "slider"],
        "coarse items only": held[held.scale == "coarse"],
        "quota panels only": held[held.stype == "quota"],
        "drop screened samples": held[held.stype != "screened"],
    }
    rows = []
    for nm, g in subsets.items():
        for mod, gg in g.groupby("moderator"):
            if len(gg) < 4:
                continue
            rows.append(dict(subset=nm, moderator=mod, n_points=len(gg),
                             n_datasets=gg.dataset.nunique(), b=slope(gg.oc, gg.oh),
                             r=float(np.corrcoef(gg.oc, gg.oh)[0, 1])))
    t = pd.DataFrame(rows).pivot_table(index="subset", columns="moderator", values="b")
    print(t.round(3).to_string())
    print("\n  (n points per cell)")
    print(pd.DataFrame(rows).pivot_table(index="subset", columns="moderator",
                                         values="n_points").to_string())

    print("\n=== 5b. GAP4: the coarse->slider gap factor the card applies (deposited 0.80) ===")
    print("  A coarse anchor's offset enters as raw x GAP4, so b scales linearly in it. The")
    print("  slider anchors are unaffected and are the only fixed point in the table.")
    for g4 in (0.6, 0.8, 1.0, 1.25):
        h = held.copy()
        h["oh2"] = np.where(h.scale == "coarse", h.oh / 0.80 * g4, h.oh)
        line = {mod: slope(gg.oc, gg.oh2) for mod, gg in h.groupby("moderator")}
        print("   GAP4 = %.2f  " % g4 + "  ".join(f"{k} {v:.3f}" for k, v in sorted(line.items())))
    tr = held[(held.family == "trust")]
    print("\n  trust family only, per anchor (the target's own construct):")
    for ds, g in tr.groupby("dataset"):
        print(f"    {ds:18s} scale={g.scale.iloc[0]:7s} sample={SAMPLE_TYPE.get(ds,'?'):11s} "
              f"b={slope(g.oc, g.oh):+.3f}  r={np.corrcoef(g.oc, g.oh)[0,1]:+.3f}  n={len(g)}")
    return 0


# ---- 6. the decision table: what would each candidate package do to the scored row? ---------
def run_package(out_dir):
    """Score candidate offset packages the way the frozen table scores them: RMSE, in pp, of the
    control-condition subgroup mean against a human study the package was not fitted on.

    Every multiplier is LOSO-honest: the k applied to anchor D is fitted on the other anchors
    only. A package is a per-moderator multiplier, so it preserves the card's identity
    sum_l share_l * offset_l = 0 exactly (scaling a share-centred block keeps it centred) - which
    is why a multiplier is the only correction shape this arm will recommend for a whole block.
    """
    df = load(out_dir)
    held = df[df.status.str.startswith("heldout")].copy()
    PKG = {
        "P0 deposited card":            {},
        "P1 shrink non-party":          {"age_band": "loso", "education": "loso",
                                         "income": "loso", "race": "loso"},
        "P2 shrink everything":         {m: "loso" for m in held.moderator.unique()},
        "P3 all-zero subgroup table":   {m: 0.0 for m in held.moderator.unique()},
        "P4 flat 0.5 haircut":          {m: 0.5 for m in held.moderator.unique()},
        "P5 non-party x0.30":           {m: 0.30 for m in held.moderator.unique()
                                         if m != "party"},
        "P6 non-party x0.50":           {m: 0.50 for m in held.moderator.unique()
                                         if m != "party"},
        "P7 non-party x0.30, party x0.85": dict({m: 0.30 for m in held.moderator.unique()
                                                 if m != "party"}, party=0.85),
    }
    rows = []
    for nm, spec in PKG.items():
        for d, g in held.groupby("dataset"):
            pred = []
            for _, x in g.iterrows():
                k = spec.get(x.moderator, 1.0)
                if k == "loso":
                    tr = held[(held.moderator == x.moderator) & (held.dataset != d)]
                    k = slope(tr.oc, tr.oh) if len(tr) >= 3 else 1.0
                pred.append(k * x.oc)
            e = g.oh.to_numpy() - np.array(pred)
            rows.append(dict(package=nm, anchor=d, n=len(g),
                             rmse=float(np.sqrt((e ** 2).mean()))))
    r = pd.DataFrame(rows)
    t = r.pivot_table(index="package", columns="anchor", values="rmse")
    t["MEAN"] = t.mean(axis=1)
    n_by = r.groupby("anchor").n.first()
    t["POOLED"] = [float(np.sqrt(np.average(r[r.package == p].set_index("anchor").rmse ** 2,
                                            weights=n_by.reindex(
                                                r[r.package == p].anchor).to_numpy())))
                   for p in t.index]
    pd.set_option("display.width", 220)
    print("=== subgroup-offset RMSE (pp) against each held-out anchor, LOSO-honest ===")
    print(t.round(3).to_string())
    t.to_csv(out_dir / "packages.csv")
    print("\n  The frozen table's 'demographic baseline RMSE' row is exactly this quantity on the")
    print("  target's own control arm. POOLED weights an anchor by its number of scored cells.")
    return 0

if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--out", default="runs/_offsets")
    a.add_argument("--boot", type=int, default=2000)
    a.add_argument("--seed", type=int, default=17)
    a.add_argument("--sens", action="store_true", help="section 5: anchor-subset and GAP4 sensitivity")
    a.add_argument("--package", action="store_true", help="section 6: candidate packages, scored")
    n = a.parse_args()
    if n.sens:
        sys.exit(run_sens(RUN / n.out))
    if n.package:
        sys.exit(run_package(RUN / n.out))
    sys.exit(main(RUN / n.out, n.boot, n.seed))
