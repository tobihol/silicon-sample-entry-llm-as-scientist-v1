#!/usr/bin/env python
"""Audit the card's 351 subgroup offsets against human control arms the builder never saw.

    /opt/kernel/venv/bin/python tools/subgroup_audit.py            # ~2 min, 0 model tokens
    /opt/kernel/venv/bin/python tools/subgroup_audit.py --boot 200 # faster, wider intervals

Pre-registration: runs/_offsets/PREREG.md (written before any human offset was computed).

`inputs/baselines/` was built on 2026-08-15 from Pew ATP, TISP, GSS, CCAM, voelkel2026 PRE and
goldwert2026's control arm. Ten carved tasks never fed it, and one of them - orchinik2024 - is the
first held-out anchor with the target's own shape (US quota panel, 0-100 sliders, climate-scientist
perception, all six moderators). This tool computes, for every held-out dataset's CONTROL arm, the
same share-centred subgroup offsets `tools/build_baselines.offsets` computes, puts coarse-scale
sources on slider footing with the card's own GAP4 = 0.80, and regresses them on the card's offsets
through the origin. The slope IS the audit: b > 1 means the card UNDERSTATES group differences,
b < 1 means it EXAGGERATES them, which is the failure mode the frozen table's demographic
predictability row exists to punish.

Everything it writes goes to runs/_offsets/. It does not touch the card, inputs/, or any tool
another arm owns.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402
from ssb import task as T  # noqa: E402

GAP4 = 0.80                       # the card's own coarse -> slider gap factor (finding 14)
MIN_N = 30                        # build_baselines' own level floor
CARD = "runs/20260815-target-01"

# ---- the construct map, fixed in the prereg -------------------------------------------------
FAM_TARGETS = {
    "trust":     [("trust_multidimensional", +1), ("trust_post", +1),
                  ("inst_trust_mean", +1), ("distrust_post", -1)],
    "belief":    [("belief_post", +1)],
    "concern":   [("concern_mean", +1)],
    "policy":    [("policy_general", +1), ("policy_specific_mean", +1), ("policy_role_mean", +1)],
    "behaviour": [("behavior_mean", +1)],
    "funding":   [("funding_perceptions", +1)],
}

# dataset -> {family: [(outcome, sign)]}, plus scale format and held-out status
SOURCES = {
    "orchinik2024": dict(scale="slider", status="heldout", fam={
        "trust":  [(f"skill_pro_cons{c}", +1) for c in (50, 75, 90, 97, 99)]
                + [(f"bias_pro_cons{c}", -1) for c in (50, 75, 90, 97, 99)],
        "belief": [(f"belief_cc_cons{c}", +1) for c in (50, 75, 90, 97, 99)]}),
    "kim2024": dict(scale="coarse", status="heldout", fam={
        "trust":  [("trust_climate_scientists", +1)],
        "belief": [("belief_human_cause", +1), ("human_contribution", +1), ("evidence_human", +1)],
        "policy": [("policy_fedgov_more", +1), ("policy_green_new_deal", +1),
                   ("policy_paris", +1), ("policy_priority", +1)]}),
    "koetke2024": dict(scale="coarse", status="heldout", fam={
        "trust": [("trust_meti", +1), ("trust_expertise", +1),
                  ("trust_integrity", +1), ("trust_benevolence", +1)]}),
    "altenmueller2024": dict(scale="coarse", status="heldout", fam={
        "trust":  [("trust_expertise", +1), ("trust_morality", +1)],
        "policy": [("policy_support", +1)]}),
    "gligoric2025": dict(scale="coarse", status="heldout-nonparty", fam={
        "trust": [("trust_overall", +1), ("credibility", +1),
                  ("trustworthiness", +1), ("trust_climate_env", +1)]}),
    "dablander2025": dict(scale="coarse", status="heldout", fam={
        "trust":     [("science_credibility", +1)],
        "policy":    [("policy_support", +1)],
        "behaviour": [("donation", +1)]}),
    "bbprime2025": dict(scale="mixed", status="heldout", fam={
        "concern":   [("concern_risk", +1)],
        "behaviour": [("petition_sign", +1), ("petition_sign_intention", +1),
                      ("action_intention", +1)]}),
    # not held out - reported as controls / secondaries only
    "voelkel2026": dict(scale="slider", status="source", fam={
        "belief": [("Belief_Post", +1)], "concern": [("Concern_Post", +1)],
        "policy": [("Policies_Post", +1), ("PoliciesSp_Post", +1)],
        "behaviour": [("IntentNp_Post", +1)]}),
    "vlasceanu2024": dict(scale="slider", status="partial", fam={
        "belief": [(f"Belief{i}", +1) for i in (1, 2, 3, 4)],
        "policy": [(f"Policy{i}", +1) for i in range(1, 10)]}),
    "goldwert2026": dict(scale="slider", status="source", fam={
        "belief": [("belief_1", +1)], "policy": [("policy_1", +1)],
        "behaviour": [("march", +1), ("conversation", +1), ("petition", +1)]}),
    "tappin2023": dict(scale="coarse", status="mismatch", fam={
        "policy": [("agree_nocue", +1)]}),
    "hackenburg2025": dict(scale="slider", status="mismatch", fam={
        "policy": [("oppose_ban_1", +1), ("oppose_ban_3", +1), ("oppose_ban_4", +1)]}),
    "voelkel2024": dict(scale="slider", status="mismatch", fam={
        "behaviour": [("BEPF", +1)]}),
}
MOD_ALIAS = {"party_lean": "party"}


# ---- machinery ------------------------------------------------------------------------------
def pool_shares():
    pool = pd.read_csv(RUN / "inputs/pool/joint.csv")
    LV = ssb.spec.load()["moderators"]
    return {(m, l): float(pool[pool[m] == l].weight.sum()) for m in LV for l in LV[m]}, LV


def dataset_block(name, LV):
    """Control-arm matrix for one dataset: outcomes in pp of range, moderator labels, weights."""
    ad = T.load_adapter(name)
    df = T.load_dataset(ad)
    ctrl = df[df["_arm"].isin(ad["control_arms"])].reset_index(drop=True)
    w = ctrl[ad["weight_col"]].to_numpy(float) if ad.get("weight_col") else np.ones(len(ctrl))
    Y, cols = {}, SOURCES[name]["fam"]
    for fam, lst in cols.items():
        for oname, sign in lst:
            o = ad["outcomes"][oname]
            v = pd.to_numeric(ctrl[o["col"]], errors="coerce").to_numpy(float)
            if o.get("reverse"):
                v = (o["lo"] + o["hi"]) - v
            Y[(fam, oname, sign)] = (v - o["lo"]) / (o["hi"] - o["lo"]) * 100.0
    mods = {}
    for m in ad.get("moderators", {}):
        tgt = MOD_ALIAS.get(m, m)
        if tgt not in LV or m not in ctrl.columns:
            continue
        lab = ctrl[m].astype("object").where(ctrl[m].isin(LV[tgt]))
        mods[tgt] = lab.to_numpy(object)
    return ctrl, w, Y, mods


def offsets_from(vals, w, lab, levels, shares, mod, idx=None, min_n=MIN_N):
    """Share-centred group offsets, identical in convention to build_baselines.offsets."""
    if idx is not None:
        vals, w, lab = vals[idx], w[idx], lab[idx]
    ok = np.isfinite(vals) & np.isfinite(w) & (lab != None)  # noqa: E711
    out, ns = {}, {}
    for l in levels:
        m = ok & (lab == l)
        n = int(m.sum())
        if n >= min_n and w[m].sum() > 0:
            out[l] = float(np.average(vals[m], weights=w[m]))
            ns[l] = n
    if len(out) < 2:
        return {}, {}
    tot = sum(shares[(mod, l)] for l in out)
    if tot <= 0:
        return {}, {}
    centre = sum(shares[(mod, l)] * out[l] for l in out) / tot
    return {l: out[l] - centre for l in out}, ns


def card_offsets(card_sub, mod, fam):
    """Family-mean card offset per level (distrust enters sign-flipped)."""
    rows = card_sub[card_sub.moderator == mod]
    out = {}
    for lvl, g in rows.groupby("level"):
        vals = [s * float(g.loc[g.outcome == t, "offset"].iloc[0])
                for t, s in FAM_TARGETS[fam] if (g.outcome == t).any()]
        if vals:
            out[lvl] = float(np.mean(vals))
    return out


def stats(oc, oh):
    """b (slope through origin), r, RMSE, parity ratio, on the levels both sides carry."""
    lv = [l for l in oc if l in oh]
    if len(lv) < 3:
        return None
    c = np.array([oc[l] for l in lv]); h = np.array([oh[l] for l in lv])
    den = float((c * c).sum())
    b = float((c * h).sum() / den) if den > 1e-12 else np.nan
    r = float(np.corrcoef(c, h)[0, 1]) if c.std() > 1e-9 and h.std() > 1e-9 else np.nan
    rng_h = float(h.max() - h.min())
    return dict(levels=lv, n_levels=len(lv), b=b, r=r,
                rmse=float(np.sqrt(((h - c) ** 2).mean())),
                parity_card=float(c.max() - c.min()), parity_human=rng_h,
                parity_ratio=float((c.max() - c.min()) / rng_h) if rng_h > 1e-9 else np.nan)


def main(boot, seed, out_dir):
    shares, LV = pool_shares()
    card_sub = pd.read_csv(RUN / CARD / "card/subgroup.csv")
    rng = np.random.default_rng(seed)
    rows, draws = [], {}

    for name, meta in SOURCES.items():
        try:
            ctrl, w, Y, mods = dataset_block(name, LV)
        except Exception as e:                                    # a dataset that will not load
            print(f"  {name}: SKIP ({type(e).__name__}: {e})")
            continue
        if len(ctrl) < 100:
            print(f"  {name}: SKIP (control arm {len(ctrl)} < 100)")
            continue
        g = GAP4 if meta["scale"] == "coarse" else 1.0
        bs_idx = [rng.integers(0, len(ctrl), len(ctrl)) for _ in range(boot)]
        print(f"  {name}: {len(ctrl):,} control rows, {len(mods)} moderators, scale={meta['scale']}")
        for mod in mods:
            lab = mods[mod]
            for fam in meta["fam"]:
                oc = card_offsets(card_sub, mod, fam)
                if not oc:
                    continue
                # human family offset = mean over the family's outcomes, coarse sources x GAP4
                def fam_off(idx=None):
                    per = []
                    for (f, oname, sign), v in Y.items():
                        if f != fam:
                            continue
                        o, _ = offsets_from(v, w, lab, LV[mod], shares, mod, idx)
                        if o:
                            per.append({l: sign * o[l] * g for l in o})
                    if not per:
                        return {}
                    keys = set.intersection(*[set(p) for p in per])
                    return {l: float(np.mean([p[l] for p in per])) for l in keys}

                oh = fam_off()
                st = stats(oc, oh)
                if st is None:
                    continue
                _, ns = offsets_from(list(Y.values())[0], w, lab, LV[mod], shares, mod)
                bb = []
                for idx in bs_idx:
                    s2 = stats(oc, fam_off(idx))
                    if s2:
                        bb.append((s2["b"], s2["r"], s2["rmse"], s2["parity_ratio"]))
                bb = np.array(bb) if bb else np.zeros((0, 4))
                q = lambda j, p: float(np.nanpercentile(bb[:, j], p)) if len(bb) else np.nan
                rows.append(dict(dataset=name, status=meta["status"], scale=meta["scale"],
                                 moderator=mod, family=fam, n_levels=st["n_levels"],
                                 levels="|".join(st["levels"]),
                                 n_ctrl=int(sum(ns.get(l, 0) for l in st["levels"])),
                                 b=st["b"], b_lo=q(0, 2.5), b_hi=q(0, 97.5),
                                 r=st["r"], r_lo=q(1, 2.5), r_hi=q(1, 97.5),
                                 rmse=st["rmse"], rmse_lo=q(2, 2.5), rmse_hi=q(2, 97.5),
                                 parity_card=st["parity_card"], parity_human=st["parity_human"],
                                 parity_ratio=st["parity_ratio"],
                                 parity_lo=q(3, 2.5), parity_hi=q(3, 97.5)))
                draws[(name, mod, fam)] = dict(oc=oc, oh=oh, ns=ns, scale=meta["scale"],
                                               status=meta["status"])
    res = pd.DataFrame(rows)
    out_dir.mkdir(parents=True, exist_ok=True)
    res.to_csv(out_dir / "audit_cells.csv", index=False)

    # pooled per moderator over the held-out cells only (V1)
    pooled = []
    held = res[res.status.str.startswith("heldout")]
    for mod, g in held.groupby("moderator"):
        cs, hs = [], []
        for _, r_ in g.iterrows():
            d = draws[(r_.dataset, mod, r_.family)]
            lv = r_.levels.split("|")
            cs += [d["oc"][l] for l in lv]; hs += [d["oh"][l] for l in lv]
        cs, hs = np.array(cs), np.array(hs)
        pooled.append(dict(moderator=mod, n_points=len(cs), n_cells=len(g),
                           b=float((cs * hs).sum() / (cs * cs).sum()),
                           r=float(np.corrcoef(cs, hs)[0, 1]),
                           rmse=float(np.sqrt(((hs - cs) ** 2).mean())),
                           b_cells_median=float(g.b.median())))
    pool_df = pd.DataFrame(pooled)
    pool_df.to_csv(out_dir / "audit_pooled.csv", index=False)
    with open(out_dir / "audit_offsets.json", "w") as f:
        json.dump({f"{k[0]}|{k[1]}|{k[2]}": {"oc": v["oc"], "oh": v["oh"], "ns": v["ns"],
                                             "scale": v["scale"], "status": v["status"]}
                   for k, v in draws.items()}, f, indent=1)

    pd.set_option("display.width", 200)
    print("\n=== held-out cells (b > 1 = the card UNDERSTATES the group difference) ===")
    show = ["dataset", "moderator", "family", "n_levels", "n_ctrl", "b", "b_lo", "b_hi",
            "r", "rmse", "parity_card", "parity_human"]
    print(held.sort_values(["moderator", "family", "dataset"])[show].round(3).to_string(index=False))
    print("\n=== not held out (source / partial / construct-mismatch), reported not pooled ===")
    print(res[~res.status.str.startswith("heldout")].sort_values(["status", "moderator"])[show]
          .round(3).to_string(index=False))
    print("\n=== pooled per moderator, held-out only ===")
    print(pool_df.round(3).to_string(index=False))
    print(f"\nwrote {out_dir}/audit_cells.csv, audit_pooled.csv, audit_offsets.json")
    return 0




# ---- section 5: predictability R^2 and parity gap, deposit vs held-out anchors ---------------
def adj_r2(y, lab, min_n=MIN_N):
    """Adjusted R^2 of one outcome on one moderator's dummies (levels with >= min_n)."""
    ok = np.isfinite(y) & (lab != None)                                       # noqa: E711
    if ok.sum() < 50:
        return np.nan
    yy, ll = y[ok], lab[ok]
    keep = [l for l, c in pd.Series(ll).value_counts().items() if c >= min_n]
    m = np.isin(ll, keep)
    yy, ll = yy[m], ll[m]
    if len(set(ll)) < 2 or len(yy) < 50:
        return np.nan
    X = pd.get_dummies(pd.Series(ll), drop_first=True).astype(float).values
    X = np.column_stack([np.ones(len(X)), X])
    p = X.shape[1] - 1
    if p >= len(yy) - 1:
        return np.nan
    b, _, _, _ = np.linalg.lstsq(X, yy, rcond=None)
    ss = float(((yy - yy.mean()) ** 2).sum())
    if ss <= 0:
        return np.nan
    r2 = 1 - float(((yy - X @ b) ** 2).sum()) / ss
    return 1 - (1 - r2) * (len(yy) - 1) / (len(yy) - p - 1)


def run_r2(out_dir):
    """The frozen table's 'demographic predictability' and 'parity gap' rows, per moderator.

    Extends tools/demographic_predictability.py (finding 54) to the anchors that post-date
    inputs/baselines/. The point of the extension is OPEN item 21: education and income were
    flagged 2.4-8.9x and 3.2x every human value with NO climate reference in the mounted data.
    orchinik2024 is a climate dataset carrying both.

    LEVEL MATCHING IS LOAD-BEARING. A human anchor drops any level with < 30 respondents, so its
    gender gap is usually Male-vs-Female while the deposit's spans Male/Female/Other, and its
    education gap spans 4 levels against the deposit's 6. Comparing those two ranges measures the
    level SET, not the group difference. Every deposit statistic below is therefore recomputed on
    the levels the human anchor actually used; the levels a human anchor cannot see are reported
    separately by --other.
    """
    shares, LV = pool_shares()
    t1 = pd.read_csv(RUN / CARD / "stages/tier1.csv")
    ctrl = t1[t1.condition == "control"]
    rows = []
    for name, meta in SOURCES.items():
        try:
            c, w, Y, mods = dataset_block(name, LV)
        except Exception:
            continue
        if len(c) < 100:
            continue
        for mod, lab in mods.items():
            lab_d = ctrl[mod].to_numpy(object)
            for fam in meta["fam"]:
                vals, gaps, lv_used = [], [], None
                for (f, oname, sign), v in Y.items():
                    if f != fam:
                        continue
                    vals.append(adj_r2(v, lab))
                    o, _ = offsets_from(v, w, lab, LV[mod], shares, mod)
                    if o:
                        gaps.append(max(o.values()) - min(o.values()))
                        lv_used = sorted(o) if lv_used is None else sorted(set(lv_used) & set(o))
                vals = [x for x in vals if np.isfinite(x)]
                if not vals or not lv_used or len(lv_used) < 2:
                    continue
                # deposit, restricted to the SAME levels
                keep = np.isin(lab_d, lv_used)
                dv, dg = [], []
                for t, sign in FAM_TARGETS[fam]:
                    if t not in ctrl.columns:
                        continue
                    y = pd.to_numeric(ctrl[t], errors="coerce").to_numpy(float)
                    dv.append(adj_r2(y[keep], lab_d[keep]))
                    gm = pd.Series(y[keep]).groupby(pd.Series(lab_d[keep])).mean()
                    dg.append(ssb.spec.to_pp(float(gm.max() - gm.min()), t))
                dv = [x for x in dv if np.isfinite(x)]
                sd_h = float(np.mean([np.nanstd(v[np.isfinite(v)], ddof=1)
                                      for (f, o_, s_), v in Y.items() if f == fam]))
                sd_d = float(np.mean([ssb.spec.to_pp(
                    float(pd.to_numeric(ctrl[t], errors="coerce").std()), t)
                    for t, _ in FAM_TARGETS[fam] if t in ctrl.columns]))
                rows.append(dict(dataset=name, status=meta["status"], scale=meta["scale"],
                                 moderator=mod, family=fam, levels="|".join(lv_used),
                                 n_levels=len(lv_used),
                                 r2_hum=float(np.mean(vals)), r2_dep=float(np.mean(dv)),
                                 gap_hum=float(np.mean(gaps)), gap_dep=float(np.mean(dg)),
                                 sd_hum=sd_h * (GAP4 if meta["scale"] == "coarse" else 1.0),
                                 sd_dep=sd_d))
    r = pd.DataFrame(rows)
    r["ratio_r2"] = np.where(r.r2_hum > 1e-4, r.r2_dep / r.r2_hum, np.nan)
    r["ratio_gap"] = r.gap_dep / r.gap_hum
    r["ratio_sd"] = r.sd_dep / r.sd_hum
    r["r2_predicted"] = r.ratio_gap ** 2 / r.ratio_sd ** 2   # the identity, see below
    r.to_csv(out_dir / "predictability.csv", index=False)
    pd.set_option("display.width", 220)
    show = ["dataset", "moderator", "family", "n_levels", "r2_hum", "r2_dep", "ratio_r2",
            "gap_hum", "gap_dep", "ratio_gap", "ratio_sd", "r2_predicted"]
    held = r[r.status.str.startswith("heldout")]
    print("=== HELD-OUT anchors, level-matched (ratio > 1 = the deposit exaggerates) ===")
    print(held.sort_values(["moderator", "family", "dataset"])[show].round(3).to_string(index=False))
    print("\n=== source / partial / construct-mismatch (not pooled) ===")
    print(r[~r.status.str.startswith("heldout")].sort_values(["status", "moderator"])[show]
          .round(3).to_string(index=False))
    print("\n=== median ratio per moderator, held-out only ===")
    print(held.groupby("moderator")[["ratio_r2", "ratio_gap"]].median().round(3).to_string())
    print("\n=== the R^2 row is a RATIO of two things, and only one of them is the offsets ===")
    print("  adj R^2 ~ gap^2 / (gap^2 + residual var), so ratio_r2 ~ ratio_gap^2 / ratio_sd^2.")
    print("  A deposit with the group differences RIGHT and the within-cell SD too SMALL reads as")
    print("  'exaggerates group differences'. Measured on the held-out anchors:")
    hh = held.dropna(subset=["ratio_r2", "r2_predicted"])
    print(f"  corr(log ratio_r2, log r2_predicted) = "
          f"{np.corrcoef(np.log(hh.ratio_r2.clip(1e-3)), np.log(hh.r2_predicted.clip(1e-3)))[0, 1]:+.3f}"
          f"   median ratio_sd = {held.ratio_sd.median():.3f}")
    print("\n=== median ratio per moderator, held-out CLIMATE anchors only ===")
    clim = held[held.dataset.isin(["orchinik2024", "kim2024", "bbprime2025", "dablander2025"])]
    print(clim.groupby("moderator")[["ratio_r2", "ratio_gap"]].median().round(3).to_string())
    return 0


def run_other(out_dir, min_n=30):
    """What do humans say about the levels a control arm is too small to see?

    The deposit's gender parity gap is driven by `Other` (+20.3 pp on funding_perceptions and
    policy_role_mean, -7.0 on trust) and almost no mounted control arm carries 30 such
    respondents. Pooling the FULL sample of every dataset - all arms, because a level's offset is
    a between-person contrast and treatment assignment is orthogonal to it - is the only way to
    read that level at all. The same is done for party `Other` and race `Other`.
    """
    shares, LV = pool_shares()
    card_sub = pd.read_csv(RUN / CARD / "card/subgroup.csv")
    rows = []
    for name, meta in SOURCES.items():
        ad = T.load_adapter(name)
        try:
            df = T.load_dataset(ad)
        except Exception:
            continue
        w = df[ad["weight_col"]].to_numpy(float) if ad.get("weight_col") else np.ones(len(df))
        for m in ad.get("moderators", {}):
            mod = MOD_ALIAS.get(m, m)
            if mod not in LV or m not in df.columns:
                continue
            lab = df[m].astype("object").where(df[m].isin(LV[mod])).to_numpy(object)
            if (lab == "Other").sum() < min_n:
                continue
            for fam, lst in meta["fam"].items():
                per = []
                for oname, sign in lst:
                    o = ad["outcomes"][oname]
                    v = pd.to_numeric(df[o["col"]], errors="coerce").to_numpy(float)
                    if o.get("reverse"):
                        v = (o["lo"] + o["hi"]) - v
                    v = (v - o["lo"]) / (o["hi"] - o["lo"]) * 100.0
                    off, ns = offsets_from(v, w, lab, LV[mod], shares, mod, min_n=min_n)
                    if "Other" in off:
                        g = GAP4 if meta["scale"] == "coarse" else 1.0
                        bs = []
                        for _ in range(200):
                            idx = np.random.default_rng(abs(hash((name, oname, _))) % 2**32
                                                        ).integers(0, len(v), len(v))
                            o2, _n2 = offsets_from(v, w, lab, LV[mod], shares, mod, idx,
                                                   min_n=min_n // 2)
                            if "Other" in o2:
                                bs.append(sign * o2["Other"] * g)
                        per.append((sign * off["Other"] * g, ns["Other"],
                                    float(np.std(bs)) if len(bs) > 20 else np.nan))
                if per:
                    oc = card_offsets(card_sub, mod, fam)
                    rows.append(dict(dataset=name, status=meta["status"], moderator=mod,
                                     family=fam, n_other=int(np.median([p[1] for p in per])),
                                     human_other=float(np.mean([p[0] for p in per])),
                                     se_other=float(np.nanmean([p[2] for p in per])),
                                     card_other=oc.get("Other", np.nan)))
    o = pd.DataFrame(rows)
    o.to_csv(out_dir / "other_levels.csv", index=False)
    print("=== the `Other` levels, measured on FULL samples (all arms) ===")
    print(o.sort_values(["moderator", "family", "dataset"]).round(3).to_string(index=False))
    print("\n=== pooled human `Other` offset vs the card's, HELD-OUT anchors, inverse-variance ===")
    def _agg(g):
        wgt = 1.0 / np.clip(g.se_other.to_numpy(float), 1e-6, None) ** 2
        mu = float(np.average(g.human_other, weights=wgt))
        se = float(np.sqrt(1.0 / wgt.sum()))
        return pd.Series({"n_datasets": len(g), "n_resp": int(g.n_other.sum()),
                          "human_other": mu, "se": se,
                          "lo": mu - 1.96 * se, "hi": mu + 1.96 * se,
                          "card_other": float(g.card_other.iloc[0]),
                          "z_card_vs_human": (float(g.card_other.iloc[0]) - mu) / se})
    agg = o[o.status.str.startswith("heldout")].groupby(["moderator", "family"]).apply(
        _agg, include_groups=False)
    print(agg.round(3).to_string())
    return 0



# ---- section 7: known-answer selftest -------------------------------------------------------
def run_selftest(seed=3):
    """Build the estimator, then make it recover a number chosen in advance (finding 90).

    A synthetic population is generated whose TRUE subgroup offsets are exactly `k` times the
    card's, plus within-person noise. The audit's own `offsets_from` + `stats` are then run on it
    and must return b = k. Two red paths: the share-centring identity (sum_l share_l * offset_l
    must be 0, which is what makes a card offset and a human offset the same object), and a
    k = 0 population, which must return b = 0 rather than something small and positive.
    """
    shares, LV = pool_shares()
    card_sub = pd.read_csv(RUN / CARD / "card/subgroup.csv")
    rng = np.random.default_rng(seed)
    ok = True
    print("=== known-answer selftest: does the audit recover a k it was given? ===")
    for mod in ("party", "age_band", "race"):
        oc = card_offsets(card_sub, mod, "trust")
        lv = [l for l in LV[mod] if l in oc]
        p = np.array([shares[(mod, l)] for l in lv], float); p /= p.sum()
        for k in (0.0, 0.30, 1.00, 1.75):
            # 25 independent populations: a single draw has real sampling error (b's own SE is
            # 0.03-0.05 here, because sum(oc^2) is small when a moderator's offsets are small),
            # so the estimator is judged on the MEAN of the sampling distribution against its own
            # standard error - not against a flat tolerance that a normal draw can fail.
            n, reps = 20000, 25
            bs = []
            for _ in range(reps):
                lab = rng.choice(lv, size=n, p=p)
                y = 60.0 + np.array([k * oc[l] for l in lab]) + rng.normal(0, 22.0, n)
                oh, _ns = offsets_from(y, np.ones(n), lab.astype(object), LV[mod], shares, mod)
                bs.append(stats(oc, oh)["b"])
            mb, se = float(np.mean(bs)), float(np.std(bs, ddof=1) / np.sqrt(reps))
            err = mb - k
            flag = "ok" if abs(err) < 3 * se else "FAIL"
            if flag == "FAIL":
                ok = False
            print(f"  {mod:9s} k={k:4.2f} -> b={mb:+.4f} +/- {se:.4f}  (err {err:+.4f}, "
                  f"{abs(err)/se:.1f} SE)  {flag}")
        # the centring identity, on a population with no group structure at all
        y = 60.0 + rng.normal(0, 22.0, 40000)
        lab = rng.choice(lv, size=40000, p=p)
        oh, _ = offsets_from(y, np.ones(40000), lab.astype(object), LV[mod], shares, mod)
        ident = sum(shares[(mod, l)] * oh[l] for l in oh)
        print(f"  {mod:9s} share-weighted sum of measured offsets = {ident:+.2e} (must be ~0)")
        if abs(ident) > 1e-9:
            ok = False
    # a red path for the GAP4 rule: a coarse source whose gaps are 1/0.8 of the card's must read
    # b = 1 after the x0.8 rule is applied, and b = 1.25 without it.
    oc = card_offsets(card_sub, "party", "trust")
    lv = [l for l in LV["party"] if l in oc]
    oh_raw = {l: oc[l] / GAP4 for l in lv}
    b_with = stats(oc, {l: v * GAP4 for l, v in oh_raw.items()})["b"]
    b_without = stats(oc, oh_raw)["b"]
    print(f"  GAP4 rule: coarse anchor at 1/0.8 the card's gaps -> b={b_with:.4f} with the rule, "
          f"{b_without:.4f} without it")
    ok &= abs(b_with - 1) < 1e-9 and abs(b_without - 1.25) < 1e-9
    print("SELFTEST", "PASS" if ok else "FAIL")
    return 0 if ok else 1


# ---- section 8: POST-HOC - the two-level moderator the prereg's rule excluded ---------------
def run_gender(out_dir):
    """POST-HOC. runs/_offsets/PREREG.md V6 requires 3 usable levels, and gender has 2 in every
    held-out control arm (`Other` is under 30 nearly everywhere), so the primary table has no
    gender row at all. With 2 share-centred levels the slope through the origin IS the signed gap
    ratio - one degree of freedom, not three - so it is reported here, labelled post-hoc, and it is
    not pooled into any per-moderator verdict. `--other` covers the third level separately.
    """
    shares, LV = pool_shares()
    card_sub = pd.read_csv(RUN / CARD / "card/subgroup.csv")
    rows = []
    for name, meta in SOURCES.items():
        try:
            c, w, Y, mods = dataset_block(name, LV)
        except Exception:
            continue
        if len(c) < 100 or "gender" not in mods:
            continue
        lab = mods["gender"]
        g4 = GAP4 if meta["scale"] == "coarse" else 1.0
        for fam in meta["fam"]:
            oc = card_offsets(card_sub, "gender", fam)
            per = []
            for (f, oname, sign), v in Y.items():
                if f != fam:
                    continue
                o, ns = offsets_from(v, w, lab, LV["gender"], shares, "gender")
                if len(o) >= 2:
                    per.append(({l: sign * o[l] * g4 for l in o}, ns))
            if not per:
                continue
            keys = set.intersection(*[set(p[0]) for p in per]) & set(oc)
            keys = sorted(keys)
            if len(keys) < 2:
                continue
            oh = {l: float(np.mean([p[0][l] for p in per])) for l in keys}
            cc = np.array([oc[l] for l in keys]); hh = np.array([oh[l] for l in keys])
            rows.append(dict(dataset=name, status=meta["status"], family=fam,
                             levels="|".join(keys), n=int(sum(per[0][1].get(l, 0) for l in keys)),
                             card_gap=float(cc.max() - cc.min()),
                             human_gap=float(hh.max() - hh.min()),
                             b=float((cc * hh).sum() / (cc * cc).sum())))
    r = pd.DataFrame(rows)
    r.to_csv(out_dir / "gender_posthoc.csv", index=False)
    print("=== POST-HOC: gender, Male vs Female only (b<1 = the card exaggerates) ===")
    print(r.sort_values(["status", "family", "dataset"]).round(3).to_string(index=False))
    h = r[r.status.str.startswith("heldout")]
    print(f"\n  held-out: median b = {h.b.median():+.3f}  (n = {len(h)} cells, "
          f"{h.dataset.nunique()} datasets); sign agrees with the card in "
          f"{int((h.b > 0).sum())}/{len(h)}")
    print(f"  card gender M-F gap median {h.card_gap.median():.2f} pp against human "
          f"{h.human_gap.median():.2f} pp")
    return 0

if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--boot", type=int, default=400)
    a.add_argument("--seed", type=int, default=11)
    a.add_argument("--out", default="runs/_offsets")
    a.add_argument("--r2", action="store_true", help="section 5: predictability R^2 + parity gap")
    a.add_argument("--other", action="store_true", help="section 6: the thin `Other` levels")
    a.add_argument("--selftest", action="store_true", help="section 7: known-answer recovery")
    a.add_argument("--gender", action="store_true", help="section 8: POST-HOC two-level gender")
    n = a.parse_args()
    if n.r2:
        (RUN / n.out).mkdir(parents=True, exist_ok=True)
        sys.exit(run_r2(RUN / n.out))
    if n.other:
        (RUN / n.out).mkdir(parents=True, exist_ok=True)
        sys.exit(run_other(RUN / n.out))
    if n.selftest:
        sys.exit(run_selftest())
    if n.gender:
        (RUN / n.out).mkdir(parents=True, exist_ok=True)
        sys.exit(run_gender(RUN / n.out))
    sys.exit(main(n.boot, n.seed, RUN / n.out))
