#!/usr/bin/env python
"""Validate the party-imputation route (OPEN.md item 9) against CES's real joint.

    /opt/kernel/venv/bin/python tools/validate_party_imputation.py

Four measurements, all weighted, all deterministic (SEED below):

  A  smoothing/fallback cost, isolated: split CES 2024 in half, fit the hierarchical donor of
     tools/build_pool.py:impute_party on half 1, apply it to half 2's demographic cell table,
     compare against half 2's REAL weighted joint.  No ACS involved, so nothing here is frame
     difference -- it is conditional independence + fallback, and nothing else.
  B  the same, after raking the imputed half-2 pool onto half-1's party x {income, education,
     race, age_band, gender} conditionals (mirrors build_pool:assoc_targets).  A -> B is what
     the raking fix buys.  It is near-vacuous on the two-ways by construction, so the three-ways
     are the informative rows.
  C  inputs/pool/joint.csv and inputs/pool/joint_marginal_exact.csv against CES's real weighted
     joint, with the difference decomposed into (i) demographic frame and (ii) party-conditional
     error:  p(party,s) - q(party,s) = [p(s)-q(s)] p(party|s) + q(s) [p(party|s)-q(party|s)].
  D  CES opt-in composition vs the ACS census base on the five demographic moderators and their
     two-ways, plus where in X the donor is actually being asked to speak (fallback level by ACS
     weight, thin/unrepresentative regions).

Writes inputs/measured/party_imputation_validation.json.  Reads only; writes nothing else.
"""
import json, sys, time
from itertools import combinations
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / "tools"))
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402
import build_pool as bp  # the route under test, imported so this validates THAT code  # noqa: E402

LV = ssb.spec.load()["moderators"]
DEMOS = ["age_band", "gender", "race", "education", "income"]
SEED = 20260815
SPLIT_SEED = 20260901
THIN = 30.0  # build_pool's weighted-unit threshold

TWOWAYS = [("party", x) for x in ["gender", "age_band", "race", "education", "income"]]
THREEWAYS = [("party", "race", "education"), ("party", "race", "age_band"),
             ("party", "education", "income"), ("party", "gender", "age_band")]
SURFACES = TWOWAYS + THREEWAYS


# ---------------------------------------------------------------- small helpers
def surf(df, cols, wcol="weight"):
    """Normalised weighted distribution over `cols`."""
    s = df.groupby(list(cols), observed=True)[wcol].sum()
    return s / s.sum()


def cmp_surf(p, q):
    """L1 (total variation x2), TV and max cell error, in pp of the sample."""
    idx = p.index.union(q.index)
    a, b = p.reindex(idx).fillna(0.0).to_numpy(float), q.reindex(idx).fillna(0.0).to_numpy(float)
    d = np.abs(a - b)
    return {"l1_pp": round(100 * d.sum(), 4), "tv_pp": round(50 * d.sum(), 4),
            "max_cell_pp": round(100 * d.max(), 4), "cells": int(len(idx))}


def table(P, Q, wp="weight", wq="weight"):
    return {"__".join(s): cmp_surf(surf(P, s, wp), surf(Q, s, wq)) for s in SURFACES}


def decompose(P, Q, cols, wp="weight", wq="weight"):
    """Split the L1 on surface `cols` into a demographic-frame and a party-conditional part.

        p(party,s) - q(party,s) = [p(s)-q(s)] p(party|s) + q(s) [p(party|s)-q(party|s)]
    so  L1_total <= L1_frame + L1_conditional, with
        L1_frame = sum_s |p(s)-q(s)|   and   L1_cond = sum_s q(s) sum_party |p(party|s)-q(party|s)|.
    """
    dem = [c for c in cols if c != "party"]
    p, q = surf(P, cols, wp), surf(Q, cols, wq)
    idx = p.index.union(q.index)
    p, q = p.reindex(idx).fillna(0.0), q.reindex(idx).fillna(0.0)
    pdm, qdm = p.groupby(level=dem).sum(), q.groupby(level=dem).sum()
    key = idx.to_frame(index=False)[dem]
    key = pd.MultiIndex.from_frame(key) if len(dem) > 1 else pd.Index(key[dem[0]])
    pd_v, qd_v = pdm.reindex(key).to_numpy(float), qdm.reindex(key).to_numpy(float)
    pc = np.divide(p.to_numpy(float), pd_v, out=np.zeros(len(idx)), where=pd_v > 0)
    qc = np.divide(q.to_numpy(float), qd_v, out=np.zeros(len(idx)), where=qd_v > 0)
    frame = 100 * float((pdm - qdm).abs().sum())
    cond = 100 * float(np.sum(qd_v * np.abs(pc - qc)))
    tot = cmp_surf(p, q)
    return {"total_l1_pp": tot["l1_pp"], "frame_l1_pp": round(frame, 4),
            "party_conditional_l1_pp": round(cond, 4),
            "dominant": "frame" if frame > cond else "party_conditional",
            "max_cell_pp": tot["max_cell_pp"]}


# ---------------------------------------------------------------- the donor, traced
def donor_tables(ces):
    cc = ces.dropna(subset=["party"])
    keys = [["age_band", "gender", "race", "education", "income"],
            ["age_band", "gender", "race", "education"], ["age_band", "race", "education"],
            ["race", "education"], ["race"], []]
    tabs = []
    for k in keys:
        t = (cc.groupby(k + ["party"], observed=True).w.sum().unstack("party") if k
             else cc.groupby("party").w.sum().to_frame().T)
        tabs.append((k, t.reindex(columns=LV["party"], fill_value=0.0).fillna(0)))
    return tabs


def impute_party_traced(cells, ces):
    """build_pool.impute_party, plus the fallback level each cell resolved at."""
    tabs = donor_tables(ces)
    def probs(row):
        for lvl, (k, t) in enumerate(tabs):
            if not k:
                v = t.iloc[0].to_numpy(float)
            else:
                key = tuple(row[x] for x in k)
                key = key[0] if len(k) == 1 else key
                if key not in t.index:
                    continue
                v = t.loc[key].to_numpy(float)
            if v.sum() >= THIN:
                return v / v.sum(), lvl, float(v.sum())
        return np.full(4, 0.25), len(tabs), 0.0
    out, trace = [], []
    for _, r in cells.iterrows():
        p, lvl, mass = probs(r)
        trace.append((lvl, mass))
        for party, pp in zip(LV["party"], p):
            if pp > 0:
                out.append({**{m: r[m] for m in DEMOS}, "party": party, "weight": r.w * pp})
    cells = cells.copy()
    cells["donor_level"] = [x[0] for x in trace]
    cells["donor_mass"] = [x[1] for x in trace]
    return pd.DataFrame(out), cells


LEVEL_NAMES = ["age+gender+race+educ+income", "age+gender+race+educ", "age+race+educ",
               "race+educ", "race", "pooled", "uniform"]


# ---------------------------------------------------------------- A and B
def split_half(ces, seed=SPLIT_SEED):
    """Seeded half/half split of the complete-case CES.  Weights are kept on their native scale
    and then rescaled so each half carries the SAME total weight as the full file (60,000-odd
    units).  That matters: build_pool's fallback rule is an absolute 30-weighted-unit threshold,
    so a donor fitted on an un-rescaled half would fall back far more often than the production
    donor does.  Rescaled, the same cells fall back as in production; only the estimation noise
    is larger, and the `raw_scale` variant below brackets that."""
    base = ces.dropna(subset=DEMOS + ["party"]).copy()
    base = base[base.w > 0]
    total = base.w.sum()
    rng = np.random.default_rng(seed)
    o = rng.permutation(len(base))
    h1 = base.iloc[o[: len(base) // 2]].copy()
    h2 = base.iloc[o[len(base) // 2:]].copy()
    return h1, h2, total


def rescale(h, total=None):
    h = h.copy()
    if total is not None:
        h["w"] = h.w * (total / h.w.sum())
    return h


def impute_and_rake(cells, donor, donor_for_rake):
    """impute_party, then IPF onto the donor's five party x moderator conditionals -- the exact
    structure of build_pool:assoc_targets, with the pool's own demographic margins held fixed."""
    imp, traced = impute_party_traced(cells, donor)
    ref = bp.impute_party(cells, donor)
    assert len(imp) == len(ref) and abs(float(imp.weight.sum()) - float(ref.weight.sum())) < 1e-9, \
        "traced donor diverged from build_pool.impute_party"
    imp["weight"] = imp.weight / imp.weight.sum()
    T_agr = imp.groupby(["age_band", "gender", "race"], observed=True).weight.sum()
    T_edu = imp.groupby("education", observed=True).weight.sum()
    T_inc = imp.groupby("income", observed=True).weight.sum()
    cp = donor_for_rake

    def assoc_targets(P_):
        tg = [(["age_band", "gender", "race"], T_agr), (["education"], T_edu), (["income"], T_inc)]
        for X in ["income", "education", "race", "age_band", "gender"]:
            cond = (cp.groupby([X, "party"], observed=True).w.sum().unstack("party")
                    .reindex(columns=LV["party"]).fillna(0))
            cond = cond.div(cond.sum(axis=1), axis=0)
            marg = P_.groupby(X, observed=True).weight.sum()
            tg.append(([X, "party"], pd.Series({(x, p): float(marg[x] * cond.loc[x, p])
                                                for x in marg.index if x in cond.index for p in LV["party"]})))
        return tg

    raked = imp.assign(weight=bp.ipf(imp, assoc_targets))
    raked["weight"] = raked.weight / raked.weight.sum()
    return imp, raked, traced


def run_AB(ces):
    h1r, h2r, total = split_half(ces)
    real2 = h2r.rename(columns={"w": "weight"}).copy()
    real2["weight"] = real2.weight / real2.weight.sum()
    real1 = h1r.rename(columns={"w": "weight"}).copy()
    real1["weight"] = real1.weight / real1.weight.sum()
    cells2 = h2r.groupby(DEMOS, observed=True).w.sum().rename("w").reset_index()
    cells2 = cells2[cells2.w > 0]

    res = {"n_half1": int(len(h1r)), "n_half2": int(len(h2r)), "cells_half2": int(len(cells2)),
           "null_two_real_halves": table(real1, real2)}

    for tag, sc in (("", total), ("_raw_scale", None)):
        h1, h2 = rescale(h1r, sc), rescale(h2r, sc)
        cells = cells2.copy()
        if sc is not None:
            cells["w"] = cells.w * (total / cells.w.sum())
        A, B, traced = impute_and_rake(cells, h1, h1)               # cross-half donor: the route
        Ao, Bo, _ = impute_and_rake(cells, h2, h2)                  # self-donor oracle: smoothing only
        tA, tB, tAo, tBo = table(A, real2), table(B, real2), table(Ao, real2), table(Bo, real2)
        res["A_plain_imputation" + tag] = tA
        res["B_after_two_way_raking" + tag] = tB
        res["oracle_A_self_donor" + tag] = tAo
        res["oracle_B_self_donor_raked" + tag] = tBo
        res["delta_A_minus_B_l1_pp" + tag] = {k: round(tA[k]["l1_pp"] - tB[k]["l1_pp"], 4) for k in tA}
        res["delta_A_minus_B_max_cell_pp" + tag] = {k: round(tA[k]["max_cell_pp"] - tB[k]["max_cell_pp"], 4)
                                                    for k in tA}
        wt = traced.w.sum()
        res["donor_level_share_of_half2_weight" + tag] = {
            LEVEL_NAMES[int(k)]: round(float(v), 6)
            for k, v in (traced.groupby("donor_level").w.sum() / wt).items()}
        res["donor_level_share_of_half2_cells" + tag] = {
            LEVEL_NAMES[int(k)]: round(float(v), 6)
            for k, v in traced.donor_level.value_counts(normalize=True).items()}
    return res, (h1r, h2r)


# ---------------------------------------------------------------- C
def boot_null(ces, B=16, seed=SPLIT_SEED):
    """CES's own sampling-noise floor on each surface: bootstrap-resample the complete-case CES
    and measure the same statistics against the original.  Any residual in C below this floor is
    not distinguishable from CES noise."""
    base = ces.dropna(subset=DEMOS + ["party"]).rename(columns={"w": "weight"}).copy()
    base["weight"] = base.weight / base.weight.sum()
    rng = np.random.default_rng(seed)
    acc = {"__".join(s_): {"total_l1_pp": [], "party_conditional_l1_pp": [], "max_cell_pp": []} for s_ in SURFACES}
    n = len(base)
    for _ in range(B):
        b = base.iloc[rng.integers(0, n, n)]
        for s_ in SURFACES:
            d = decompose(b, base, s_)
            for m in acc["__".join(s_)]:
                acc["__".join(s_)][m].append(d[m])
    return {k: {m: {"mean": round(float(np.mean(v)), 4), "sd": round(float(np.std(v)), 4)}
                for m, v in d.items()} for k, d in acc.items()}


def run_C(ces, acs_cells):
    real = ces.dropna(subset=DEMOS + ["party"]).rename(columns={"w": "weight"}).copy()
    real["weight"] = real.weight / real.weight.sum()
    out = {"ces_sampling_noise_null_bootstrap": boot_null(ces)}
    # the pre-raking object run 02 called "plain imputation": ACS cells x P(party|X), no IPF at all
    plain = bp.impute_party(acs_cells, ces)
    plain["weight"] = plain.weight / plain.weight.sum()
    for name in ("joint.csv", "joint_marginal_exact.csv", "plain_imputation_no_raking"):
        P = plain if name == "plain_imputation_no_raking" else pd.read_csv(RUN / "inputs" / "pool" / name)
        P = P.copy()
        P["weight"] = P.weight / P.weight.sum()
        out[name] = {
            "surfaces": table(P, real),
            "decomposition": {"__".join(s_): decompose(P, real, s_) for s_ in SURFACES},
            "demographic_only": {"__".join(d): cmp_surf(surf(P, d), surf(real, d))
                                 for d in [(x,) for x in DEMOS] + list(combinations(DEMOS, 2))},
            "party_marginal": cmp_surf(surf(P, ("party",)), surf(real, ("party",))),
            "cells": int(len(P)),
        }
    return out


def acs_citizenship(per):
    """CIT (1-4 citizen, 5 not a citizen) joined onto build_pool's adult person table.
    The CES sampling frame is the ACS *citizen* sample, so this is the frame difference that
    matters for D; the pool of record is all non-GQ adults."""
    parts = []
    for f in ("psam_pusa", "psam_pusb"):
        for ch in pd.read_sas(bp.ACS / "unix_pus" / f"{f}.sas7bdat", format="sas7bdat",
                              chunksize=200000, iterator=True):
            d = ch[["SERIALNO", "SPORDER", "AGEP", "CIT"]]
            parts.append(d[d.AGEP >= 18].copy())
    c = pd.concat(parts, ignore_index=True)
    for col in ("SERIALNO", "CIT"):
        c[col] = c[col].str.decode("utf-8") if c[col].dtype == object else c[col]
    c["CIT"] = pd.to_numeric(c.CIT, errors="coerce")
    out = per.merge(c[["SERIALNO", "SPORDER", "CIT"]], on=["SERIALNO", "SPORDER"], how="left")
    return out


# ---------------------------------------------------------------- D
def run_D(ces, acs_cells, acs_cells_cit=None):
    A = acs_cells.rename(columns={"w": "weight"})
    C = ces.dropna(subset=DEMOS).rename(columns={"w": "weight"}).copy()
    comp = {"__".join(k): cmp_surf(surf(A, k), surf(C, k))
            for k in [(x,) for x in DEMOS] + list(combinations(DEMOS, 2))}
    worst_cells = {}
    for k in [(x,) for x in DEMOS] + list(combinations(DEMOS, 2)):
        p, q = surf(A, k), surf(C, k)
        idx = p.index.union(q.index)
        d = (p.reindex(idx).fillna(0) - q.reindex(idx).fillna(0))
        j = d.abs().idxmax()
        worst_cells["__".join(k)] = {"cell": j if isinstance(j, str) else list(j),
                                     "acs_pct": round(100 * float(p.get(j, 0.0)), 3),
                                     "ces_pct": round(100 * float(q.get(j, 0.0)), 3),
                                     "diff_pp": round(100 * float(d[j]), 3)}
    # where is the donor actually asked to speak?
    _, traced = impute_party_traced(acs_cells, ces)
    tot = traced.w.sum()
    lvl_w = (traced.groupby("donor_level").w.sum() / tot)
    ces_c = ces.dropna(subset=DEMOS + ["party"])
    ces_cell = ces_c.groupby(DEMOS, observed=True).agg(ces_w=("w", "sum"), ces_n=("w", "size")).reset_index()
    m = traced.merge(ces_cell, on=DEMOS, how="left").fillna({"ces_w": 0.0, "ces_n": 0})
    m["acs_share"] = m.w / tot
    fb = m[m.donor_level > 0].sort_values("acs_share", ascending=False)
    top_fb = [{"cell": {d: r[d] for d in DEMOS}, "acs_pct_of_adults": round(100 * r.acs_share, 4),
               "ces_weighted_units_in_cell": round(float(r.ces_w), 2),   # threshold is 30
               "ces_n_in_cell": int(r.ces_n),
               "resolved_at": LEVEL_NAMES[int(r.donor_level)]} for _, r in fb.head(10).iterrows()]
    # thin/unrepresentative regions: coarse blocks where CES has least mass per ACS mass
    blocks = {}
    for k in [("race", "education"), ("race", "income"), ("education", "income"), ("age_band", "education"),
              ("race", "age_band")]:
        p, q = surf(A, k), surf(C, k)
        idx = p.index.union(q.index)
        p, q = p.reindex(idx).fillna(0), q.reindex(idx).fillna(0)
        nn = ces_c.groupby(list(k), observed=True).size().reindex(idx).fillna(0)
        ratio = (q / p.replace(0, np.nan))
        j = ratio.idxmin()
        blocks["__".join(k)] = {"thinnest_block": list(j), "acs_pct": round(100 * float(p[j]), 3),
                                "ces_pct": round(100 * float(q[j]), 3),
                                "ces_over_acs": round(float(ratio[j]), 3), "ces_n": int(nn[j])}
    # what does dropping income actually cost?  TV distance between P(party | 5-key) and
    # P(party | 4-key) over CES cells where BOTH are well estimated (>= 100 weighted units),
    # weighted by the ACS weight of the matching cells.
    k5 = ["age_band", "gender", "race", "education", "income"]
    k4 = ["age_band", "gender", "race", "education"]
    t5 = ces_c.groupby(k5 + ["party"], observed=True).w.sum().unstack("party").reindex(columns=LV["party"]).fillna(0)
    t4 = ces_c.groupby(k4 + ["party"], observed=True).w.sum().unstack("party").reindex(columns=LV["party"]).fillna(0)
    m5 = t5.sum(axis=1)
    ok = m5[m5 >= 100].index
    p5 = t5.loc[ok].div(m5.loc[ok], axis=0)
    idx4 = pd.MultiIndex.from_tuples([tuple(x[:4]) for x in ok], names=k4)
    p4 = t4.div(t4.sum(axis=1), axis=0).reindex(idx4)
    tv = 0.5 * (p5.to_numpy(float) - p4.to_numpy(float)).__abs__().sum(axis=1)
    aw = A.groupby(k5, observed=True).weight.sum()
    aw = aw.reindex(ok).fillna(0.0).to_numpy(float)
    drop_cost = {"cells": int(len(ok)),
                 "acs_weight_covered_pct": round(100 * float(aw.sum() / A.weight.sum()), 3),
                 "acs_weighted_mean_TV_pp": round(100 * float((tv * aw).sum() / aw.sum()), 3),
                 "unweighted_mean_TV_pp": round(100 * float(np.mean(tv)), 3),
                 "p90_TV_pp": round(100 * float(np.quantile(tv, 0.9)), 3)}

    cit = {}
    if acs_cells_cit is not None:
        Ac = acs_cells_cit.rename(columns={"w": "weight"})
        cit["composition_L1_acs_citizens_vs_ces"] = {
            "__".join(k): cmp_surf(surf(Ac, k), surf(C, k))
            for k in [(x,) for x in DEMOS] + list(combinations(DEMOS, 2))}
        cit["composition_L1_acs_all_vs_acs_citizens"] = {
            "__".join(k): cmp_surf(surf(A, k), surf(Ac, k))
            for k in [(x,) for x in DEMOS] + list(combinations(DEMOS, 2))}
        cit["noncitizen_share_of_acs_adults_pct"] = round(
            100 * float(1 - Ac.weight.sum() / A.weight.sum()), 3)
        nc = []
        for k in [("race",), ("education",), ("race", "education")]:
            pa = A.groupby(list(k), observed=True).weight.sum()
            pc = Ac.groupby(list(k), observed=True).weight.sum().reindex(pa.index).fillna(0.0)
            r = (1 - pc / pa).sort_values(ascending=False)
            nc.append({"__".join(k): [{"cell": (j if isinstance(j, str) else list(j)),
                                       "noncitizen_pct_of_that_cell": round(100 * float(r[j]), 2),
                                       "acs_pct_of_adults": round(100 * float(pa[j] / pa.sum()), 3)}
                                      for j in r.index[:4]]})
        cit["most_non_citizen_regions"] = nc

    return {
        "composition_L1": comp, "worst_cell_per_margin": worst_cells,
        "citizen_frame": cit,
        "cost_of_dropping_income_from_the_key": drop_cost,
        "donor_level_share_of_acs_weight": {LEVEL_NAMES[int(k)]: round(float(v), 6) for k, v in lvl_w.items()},
        "acs_weight_share_needing_fallback": round(float(1 - lvl_w.get(0, 0.0)), 6),
        "acs_cells": int(len(traced)),
        "largest_fallback_cells_by_acs_weight": top_fb,
        "thinnest_ces_blocks": blocks,
        "acs_weight_in_cells_with_zero_ces_respondents": round(
            float(m.loc[m.ces_n == 0, "acs_share"].sum()), 6),
    }


# ---------------------------------------------------------------- main
def main():
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    ces = bp.ces_frame(rng)
    out = {"built": time.strftime("%Y-%m-%dT%H:%M:%S"), "seed": SEED, "split_seed": SPLIT_SEED,
           "ces": {"path": bp.CES, "n_rows": int(len(ces)),
                   "n_complete_six_way": int(len(ces.dropna(subset=DEMOS + ["party"]))),
                   "weight_col": "commonweight"}}
    print("A/B: split-half self-donor ...")
    ab, _ = run_AB(ces)
    out["A_B_split_half"] = ab
    print("ACS cells ...")
    per = acs_citizenship(bp.acs_persons())
    acs_cells = per.groupby(DEMOS, observed=True).PWGTP.sum().rename("w").reset_index()
    acs_cells = acs_cells[acs_cells.w > 0]
    acs_cells_cit = (per[per.CIT != 5].groupby(DEMOS, observed=True).PWGTP.sum()
                     .rename("w").reset_index())
    acs_cells_cit = acs_cells_cit[acs_cells_cit.w > 0]
    del per
    print("C: real pool vs CES joint ...")
    out["C_pool_vs_ces"] = run_C(ces, acs_cells)
    print("D: CES vs ACS composition ...")
    out["D_ces_vs_acs"] = run_D(ces, acs_cells, acs_cells_cit)
    out["coding_notes"] = coding_notes()
    out["headlines"] = headlines(out)
    p = RUN / "inputs" / "measured" / "party_imputation_validation.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(out, indent=1, default=str))
    print("wrote", p, "in %.0f s" % (time.time() - t0))


def coding_notes():
    raw = pd.read_csv(bp.CES, usecols=["pid3", "commonweight", "faminc_new", "race", "gender4", "educ"],
                      low_memory=False)
    w = raw.commonweight.fillna(0)
    notes = {
        "pid3_code_5_is_Not_sure_not_Independent": {
            "codebook": "page_pid3: 1 Democrat, 2 Republican, 3 Independent, 4 Other, 5 Not sure",
            "build_pool_maps": "5 -> Independent",
            "rows": int((raw.pid3 == 5).sum()),
            "share_of_ces_weight_pct": round(100 * float(w[raw.pid3 == 5].sum() / w.sum()), 3),
            "independent_share_pct_with_5": round(100 * float(w[raw.pid3.isin([3, 5])].sum() /
                                                              w[raw.pid3.isin([1, 2, 3, 4, 5])].sum()), 3),
            "independent_share_pct_without_5": round(100 * float(w[raw.pid3 == 3].sum() /
                                                                 w[raw.pid3.isin([1, 2, 3, 4])].sum()), 3),
        },
        "faminc_new_97_prefer_not_to_say_dropped": {
            "rows": int((raw.faminc_new == 97).sum()),
            "share_of_ces_weight_pct": round(100 * float(w[raw.faminc_new == 97].sum() / w.sum()), 3),
            "plus_missing_rows": int(raw.faminc_new.isna().sum()),
        },
        "race_code_8_is_Middle_Eastern": {"build_pool_maps": "8 -> Other (matches 5/6/7)",
                                          "rows": int((raw.race == 8).sum())},
        "educ_codes": "1 no HS, 2 HS grad, 3 some college, 4 2-year, 5 4-year, 6 postgrad; "
                      "build_pool 3,4 -> Some college or Associate's degree, 6 split MA/PhD at 11.431% (ACS)",
        "gender4_codes": "1 Man, 2 Woman, 3 Non-binary, 4 Other; build_pool 3,4 -> Other",
        "faminc_new_band_edges_checked": "codes 1-3 <30k; 4-5 30-49,999; 6 = $50-59,999 split 60/40 at "
                                         "$56k (uniform-correct); 7-9 <100k; 10-11 100-149,999; "
                                         "12 = $150-199,999 split 36/64 at $168k (uniform-correct); 13-16 >=168k",
    }
    return notes


def headlines(out):
    """The numbers the report quotes, all read back out of `out` itself."""
    ab, C, D = out["A_B_split_half"], out["C_pool_vs_ces"], out["D_ces_vs_acs"]
    tw = ["__".join(s_) for s_ in TWOWAYS]
    th = ["__".join(s_) for s_ in THREEWAYS]
    g = lambda t, ks, m="l1_pp": {k: t[k][m] for k in ks}
    return {
        "A_pure_fallback_cost_L1_pp": {"two_way": g(ab["oracle_A_self_donor"], tw),
                                       "three_way": g(ab["oracle_A_self_donor"], th)},
        "A_cross_half_L1_pp": {"two_way": g(ab["A_plain_imputation"], tw),
                               "three_way": g(ab["A_plain_imputation"], th)},
        "A_sampling_null_two_real_halves_L1_pp": {"two_way": g(ab["null_two_real_halves"], tw),
                                                  "three_way": g(ab["null_two_real_halves"], th)},
        "B_after_raking_pure_L1_pp": {"two_way": g(ab["oracle_B_self_donor_raked"], tw),
                                      "three_way": g(ab["oracle_B_self_donor_raked"], th)},
        "B_after_raking_cross_half_L1_pp": {"two_way": g(ab["B_after_two_way_raking"], tw),
                                            "three_way": g(ab["B_after_two_way_raking"], th)},
        "C_party_conditional_L1_pp": {n: {k: C[n]["decomposition"][k]["party_conditional_l1_pp"]
                                          for k in tw + th}
                                      for n in ("joint.csv", "joint_marginal_exact.csv",
                                                "plain_imputation_no_raking")},
        "C_frame_L1_pp": {n: {k: C[n]["decomposition"][k]["frame_l1_pp"] for k in tw + th}
                          for n in ("joint.csv", "joint_marginal_exact.csv", "plain_imputation_no_raking")},
        "C_ces_noise_floor_conditional_L1_pp": {k: C["ces_sampling_noise_null_bootstrap"][k]
                                                ["party_conditional_l1_pp"]["mean"] for k in tw + th},
        "C_dominant": {n: {k: C[n]["decomposition"][k]["dominant"] for k in tw + th}
                       for n in ("joint.csv", "joint_marginal_exact.csv", "plain_imputation_no_raking")},
        "D_composition_L1_pp": {k: v["l1_pp"] for k, v in D["composition_L1"].items() if "__" not in k},
        "D_fallback_share_of_acs_weight": D["acs_weight_share_needing_fallback"],
        "D_cost_of_dropping_income_TV_pp": D["cost_of_dropping_income_from_the_key"]["acs_weighted_mean_TV_pp"],
    }


if __name__ == "__main__":
    main()
