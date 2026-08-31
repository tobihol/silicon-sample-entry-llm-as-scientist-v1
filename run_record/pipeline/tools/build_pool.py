#!/usr/bin/env python
"""Rebuild inputs/pool/ from the mounted ACS and CES files.

Reproduces the pool of record exactly (run 20260815-dryrun-02). ~40 s, ~3 GB peak.
Every choice here is argued in inputs/pool/provenance.json and OPEN.md items 1 and 9.

    python tools/build_pool.py            # writes inputs/pool/joint.csv (+ the variant)
"""
import json, sys, time
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402

RUN = Path(__file__).resolve().parents[1]
ACS = Path("/workspace/datasets/acs/downloads")
CES = "/workspace/datasets/ces/downloads/CCES24_Common_OUTPUT_vv_topost_final.csv"
LV = ssb.spec.load()["moderators"]
MODS = list(LV)
EDGES = [30000, 56000, 100000, 168000]          # the target's nominal band edges
EDU3 = {"Less than high school": "HS or less", "High school diploma / GED": "HS or less",
        "Some college or Associate's degree": "Some college", "Bachelor's degree": "Bachelor or Postgraduate",
        "Master's degree / Professional degree": "Bachelor or Postgraduate",
        "Doctorate degree / Ph.D.": "Bachelor or Postgraduate"}
TWIN_EDU3 = {"Bachelor or Postgraduate": 0.37331, "Some college": 0.33492, "HS or less": 0.29177}  # voelkel2026
P_OTHER = 0.00933                                # voelkel2026, the target's exact 3-level gender item
SEED = 20260815


def acs_persons():
    cols = ["SERIALNO", "SPORDER", "PWGTP", "AGEP", "SEX", "RAC1P", "HISP", "SCHL", "PINCP", "ADJINC"]
    parts = []
    for f in ("psam_pusa", "psam_pusb"):
        for ch in pd.read_sas(ACS / "unix_pus" / f"{f}.sas7bdat", format="sas7bdat", chunksize=200000, iterator=True):
            d = ch[cols]
            parts.append(d[d.AGEP >= 18].copy())
    per = pd.concat(parts, ignore_index=True)
    for c in ("SERIALNO", "SEX", "RAC1P", "HISP", "SCHL", "ADJINC"):
        per[c] = per[c].str.decode("utf-8")
    hus = []
    for f in ("psam_husa", "psam_husb"):
        for ch in pd.read_sas(ACS / "unix_hus" / f"{f}.sas7bdat", format="sas7bdat", chunksize=200000, iterator=True):
            hus.append(ch[["SERIALNO", "HINCP"]].copy())
    hus = pd.concat(hus, ignore_index=True)
    hus["SERIALNO"] = hus.SERIALNO.str.decode("utf-8")
    m = per.merge(hus, on="SERIALNO", how="left")
    m = m[~m.SERIALNO.str.contains("GQ")].copy()          # an online panel does not reach group quarters
    m["age_band"] = pd.cut(m.AGEP, bins=[17, 29, 44, 59, 200], labels=LV["age_band"])
    m["gender"] = m.SEX.map({"1": "Male", "2": "Female"})
    m["race"] = np.where(m.HISP.ne("01"), "Hispanic / Latino",
                np.where(m.RAC1P.eq("1"), "White / Caucasian",
                np.where(m.RAC1P.eq("2"), "Black / African American",
                np.where(m.RAC1P.eq("6"), "Asian / Asian American", "Other"))))
    schl = pd.to_numeric(m.SCHL, errors="coerce")
    m["education"] = np.select([schl <= 15, schl.isin([16, 17]), schl.isin([18, 19, 20]), schl == 21,
                                schl.isin([22, 23]), schl == 24], LV["education"], default=None)
    inc = m.HINCP * 1.013097                               # ADJINC to 2018 dollars; NO further inflation (OPEN item 1)
    m["income"] = np.array(LV["income"])[np.digitize(inc.to_numpy(float), EDGES, right=False)]
    return m


def ces_frame(rng):
    want = ["commonweight", "birthyr", "gender4", "educ", "race", "hispanic", "pid3", "faminc_new"]
    c = pd.read_csv(CES, usecols=want, low_memory=False)
    c["age_band"] = pd.cut(2024 - c.birthyr, bins=[17, 29, 44, 59, 200], labels=LV["age_band"])
    c["gender"] = c.gender4.map({1: "Male", 2: "Female", 3: "Other", 4: "Other"})
    c["race"] = c.race.map({1: "White / Caucasian", 2: "Black / African American", 3: "Hispanic / Latino",
                            4: "Asian / Asian American", 5: "Other", 6: "Other", 7: "Other", 8: "Other"})
    c.loc[c.hispanic == 1, "race"] = "Hispanic / Latino"   # same precedence rule as ACS
    c["party"] = c.pid3.map({1: "Democrat", 2: "Republican", 3: "Independent", 4: "Other", 5: "Independent"})
    c["education"] = c.educ.map({1: "Less than high school", 2: "High school diploma / GED",
                                 3: "Some college or Associate's degree", 4: "Some college or Associate's degree",
                                 5: "Bachelor's degree"})
    pg = c.educ == 6                                       # CES pools all postgrads; ACS gives the split
    c.loc[pg, "education"] = np.where(rng.random(pg.sum()) < 0.11431, "Doctorate degree / Ph.D.",
                                      "Master's degree / Professional degree")
    def band(code, u):
        if not np.isfinite(code) or code == 97: return None
        code = int(code)
        if code <= 3: return 0
        if code <= 5: return 1
        if code == 6: return 1 if u < 0.6 else 2           # $50-59,999 straddles $56,000
        if code <= 9: return 2
        if code <= 11: return 3
        if code == 12: return 3 if u < 0.36 else 4         # $150-199,999 straddles $168,000
        if code <= 16: return 4
        return None
    u = rng.random(len(c))
    c["income"] = [None if (b := band(x, uu)) is None else LV["income"][b] for x, uu in zip(c.faminc_new.to_numpy(), u)]
    c["w"] = c.commonweight.fillna(0)
    return c


def impute_party(cells, ces):
    """P(party | X) from CES with a hierarchical fallback; thin cells borrow from coarser ones."""
    cc = ces.dropna(subset=["party"])
    keys = [["age_band", "gender", "race", "education", "income"], ["age_band", "gender", "race", "education"],
            ["age_band", "race", "education"], ["race", "education"], ["race"], []]
    tabs = []
    for k in keys:
        t = (cc.groupby(k + ["party"], observed=True).w.sum().unstack("party") if k
             else cc.groupby("party").w.sum().to_frame().T)
        tabs.append((k, t.reindex(columns=LV["party"], fill_value=0.0).fillna(0)))
    def probs(row):
        for k, t in tabs:
            if not k:
                v = t.iloc[0].to_numpy(float)
            else:
                key = tuple(row[x] for x in k)
                key = key[0] if len(k) == 1 else key
                if key not in t.index: continue
                v = t.loc[key].to_numpy(float)
            if v.sum() >= 30.0:                            # 30 weighted units before a cell speaks for itself
                return v / v.sum()
        return np.full(4, 0.25)
    out = []
    for _, r in cells.iterrows():
        for party, p in zip(LV["party"], probs(r)):
            if p > 0:
                out.append({**{m: r[m] for m in MODS if m != "party"}, "party": party, "weight": r.w * p})
    return pd.DataFrame(out)


def ipf(P, targets, outer=6, inner=60):
    w = np.array(P.weight.to_numpy(float), copy=True)
    idx = {tuple(k): P.groupby(k, observed=True).indices for k, _ in targets(P)}
    for _ in range(outer):
        tg = targets(P.assign(weight=w))
        for _ in range(inner):
            dev = 0.0
            for k, T in tg:
                cur = pd.Series(w).groupby([P[x] for x in k], observed=True).sum()
                for key, ii in idx[tuple(k)].items():
                    tgt, got = float(T.get(key, 0.0)), float(cur.get(key, 0.0))
                    if got > 0 and tgt > 0:
                        w[ii] *= tgt / got
                        dev = max(dev, abs(tgt - got))
                w /= w.sum()
            if dev < 1e-8: break
    return w


def main():
    t0 = time.time()
    rng = np.random.default_rng(SEED)
    per = acs_persons()
    ces = ces_frame(rng)
    cells = per.groupby(["age_band", "gender", "race", "education", "income"], observed=True).PWGTP.sum().rename("w").reset_index()
    pool = impute_party(cells, ces)

    # gender "Other": ACS has no such category. Inject at the design twin's rate, allocated by age
    # using CES's age profile of non-binary respondents.
    co = ces.dropna(subset=["age_band"])
    p_age = (co[co.gender == "Other"].groupby("age_band", observed=True).w.sum() /
             co.groupby("age_band", observed=True).w.sum())
    p_age = (p_age * P_OTHER / (co[co.gender == "Other"].w.sum() / co.w.sum())).clip(0, 0.2)
    base = pool.copy(); base["weight"] = base.weight * (1 - base.age_band.map(p_age).astype(float))
    oth = pool.groupby(["age_band", "race", "education", "income", "party"], observed=True).weight.sum().reset_index()
    oth["weight"] = oth.weight * oth.age_band.map(p_age).astype(float)
    oth["gender"] = "Other"
    P = pd.concat([base, oth[base.columns]], ignore_index=True)
    P = P[P.weight > 0].reset_index(drop=True)
    P["weight"] /= P.weight.sum()
    P["edu3"] = P.education.map(EDU3)

    T_agr = P.groupby(["age_band", "gender", "race"], observed=True).weight.sum()   # the census quota
    T_agr = T_agr / T_agr.sum()
    T_edu3 = pd.Series(TWIN_EDU3)
    inc = ces.dropna(subset=["income"])
    T_inc = inc.groupby("income").w.sum() / inc.w.sum()                             # CES self-report instrument
    cp = ces.dropna(subset=MODS)

    def marginal_targets(P_):
        return [(["age_band", "gender", "race"], T_agr), (["edu3"], T_edu3), (["income"], T_inc),
                (["party"], cp.groupby("party").w.sum() / cp.w.sum())]

    def assoc_targets(P_):
        tg = [(["age_band", "gender", "race"], T_agr), (["edu3"], T_edu3), (["income"], T_inc)]
        for X in ["income", "education", "race", "age_band", "gender"]:
            cond = cp.groupby([X, "party"], observed=True).w.sum().unstack("party").reindex(columns=LV["party"]).fillna(0)
            cond = cond.div(cond.sum(axis=1), axis=0)
            marg = P_.groupby(X, observed=True).weight.sum()
            tg.append(([X, "party"], pd.Series({(x, p): float(marg[x] * cond.loc[x, p])
                                                for x in marg.index if x in cond.index for p in LV["party"]})))
        return tg

    out = RUN / "inputs" / "pool"
    out.mkdir(parents=True, exist_ok=True)

    def save(P_, name):
        j = P_.groupby(MODS, observed=True).weight.sum().reset_index()
        j = j[j.weight > 0]
        j["weight"] /= j.weight.sum()
        j.to_csv(out / name, index=False)
        print(f"  {name}: {len(j)} cells")

    # 1. the marginal-exact pool: census 3-way + the two panel/instrument margins + party
    P_marg = P.assign(weight=ipf(P, marginal_targets))
    save(P_marg, "joint_marginal_exact.csv")
    # 2. the pool of record: START from the marginal-exact pool, then rake party's 2-way
    #    associations onto CES's conditionals. Order matters - the 2-way targets are built from
    #    the CURRENT marginals, so raking them from the raw pool would pin the marginals to ACS
    #    and silently undo the education and income adjustments (measured: 7.2 and 2.4 pp off).
    save(P_marg.assign(weight=ipf(P_marg, assoc_targets)), "joint.csv")
    print("built in %.0f s" % (time.time() - t0))


if __name__ == "__main__":
    main()
