#!/usr/bin/env python
"""Measure the FOUR-point-verbal -> 0-100-slider gap transfer factor (GAP4).

    /opt/kernel/venv/bin/python tools/measure_gap_transfer.py     # ~20 s
    -> inputs/measured/gap_transfer_4point.json

Why this exists. `tools/build_baselines.py` carries subgroup offsets from sources that
ask coarse verbal items onto a target that asks 0-100 sliders. Standing finding 10
measured that crossing for a THREE-point scale (TISP vs vlasceanu2024, five near-verbatim
policy items) and found gaps shrink by 0.63-0.93. The Pew anchor added in OPEN item 2 is
a FOUR-point scale, so the same quantity has to be measured again rather than assumed.

Design. Three constructs are measured twice in the mounted data on the same US population:
CCAM 2021-2024 asks them on 4-point verbal scales (weighted, n=8,234) and voelkel2026 asks
them on 0-100 sliders (pre-treatment, n=13,821). For each construct and each moderator the
group offsets are computed the same way `build_baselines.offsets` computes them - centred
on the deposit pool's own shares - and the slider offsets are regressed on the rescaled
4-point offsets through the origin. The slope IS the transfer factor.

What it is not. The item wordings are near, not verbatim (CCAM `worry` vs voelkel2026
`Concern_Pre`), so this measures the transfer of a GAP across a scale format AND a
wording, which is exactly the operation build_baselines performs. It says nothing about
LEVELS: the same three pairs disagree on level by -1.6 to +12.6 pp, which is why no
4-point level bridge is claimed anywhere in this harness.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd, pyreadstat

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402

RUN = Path(__file__).resolve().parents[1]
D = Path("/workspace/datasets")
LV = ssb.spec.load()["moderators"]


def wmean(y, w):
    y, w = np.asarray(y, float), np.asarray(w, float)
    m = np.isfinite(y) & np.isfinite(w)
    return float(np.average(y[m], weights=w[m])) if m.sum() > 2 else np.nan


def offsets(group, value, weight, mod, shares, min_n=100):
    d = pd.DataFrame({"g": np.asarray(group), "v": np.asarray(value, float),
                      "w": np.asarray(weight, float)}).dropna()
    gm = d.groupby("g").apply(lambda z: pd.Series({"m": wmean(z.v, z.w), "n": len(z)}))
    ok = [l for l in LV[mod] if l in gm.index and gm.loc[l, "n"] >= min_n]
    if len(ok) < 2:
        return {}
    wt = sum(shares[(mod, l)] for l in ok)
    centre = sum(shares[(mod, l)] * gm.loc[l, "m"] for l in ok) / wt
    return {l: (gm.loc[l, "m"] - centre, int(gm.loc[l, "n"])) for l in ok}


def main():
    pool = pd.read_csv(RUN / "inputs" / "pool" / "joint.csv")
    shares = {(m, l): float(pool[pool[m] == l].weight.sum()) for m in LV for l in LV[m]}

    v = pd.read_csv(D / "voelkel2026/downloads/CCC - Data - Recoded.csv", low_memory=False)
    vmods = {"gender": v.Gender,
             "age_band": pd.cut(2024 - pd.to_numeric(v.YOB, errors="coerce"), bins=[17, 29, 44, 59, 200],
                                labels=LV["age_band"]),
             "race": v.Race.map({1.0: "White / Caucasian", 2.0: "Black / African American",
                                 3.0: "Hispanic / Latino", 4.0: "Asian / Asian American", 5.0: "Other"}),
             "party": v.Party_N.map({1: "Democrat", 2: "Democrat", 3: "Independent", 4: "Independent",
                                     5: "Independent", 6: "Republican", 7: "Republican", 8: "Other"})}
    VCOL = {"concern": "Concern_Pre", "policy_general": "Policies_Pre_3", "belief": "Belief_Pre"}

    cc, _ = pyreadstat.read_sav(D / "ccam/downloads/CCAM SPSS Data 2008-2024.sav")
    cc = cc[cc.year >= 13].copy()                                    # 2021-2024
    cmods = {"gender": cc.gender.map({1.0: "Male", 2.0: "Female"}),
             "age_band": pd.cut(pd.to_numeric(cc.age, errors="coerce"), bins=[17, 29, 44, 59, 200],
                                labels=LV["age_band"]),
             "race": cc.race.map({1.0: "White / Caucasian", 2.0: "Black / African American", 3.0: "Other",
                                  4.0: "Hispanic / Latino", 5.0: "Other"}),
             "party": cc.party_w_leaners.map({1.0: "Republican", 2.0: "Democrat", 3.0: "Independent", 4.0: "Other"})}
    lin = lambda col, lo, hi: (pd.to_numeric(cc[col], errors="coerce").where(lambda y: y > 0) - lo) / (hi - lo) * 100
    cause = cc.cause_recoded.where(cc.cause_recoded > 0)
    CVAL = {"concern": lin("worry", 1, 4), "policy_general": lin("priority", 1, 4),
            "belief": pd.Series(np.select([cause == 6, cause == 5, cause == 4, cause == 3],
                                          [100.0, 60.0, 15.0, 0.0], default=np.nan), index=cc.index)}

    rows = []
    for mod in ["gender", "age_band", "race", "party"]:
        for construct in CVAL:
            a = offsets(cmods[mod], CVAL[construct], cc.weight_wave, mod, shares)
            b = offsets(vmods[mod], pd.to_numeric(v[VCOL[construct]], errors="coerce"),
                        np.ones(len(v)), mod, shares)
            for l in set(a) & set(b):
                rows.append({"moderator": mod, "construct": construct, "level": l,
                             "likert4_offset_pp": a[l][0], "slider_offset_pp": b[l][0],
                             "n_ccam": a[l][1], "n_voelkel2026": b[l][1]})
    R = pd.DataFrame(rows)
    # 'Other' is dropped from the fit: CCAM folds Asian into race-Other and party-Other is a
    # different residual category in each source, so those pairs compare unlike groups.
    F = R[R.level != "Other"]

    def slope(d):
        x, y = d.likert4_offset_pp.values, d.slider_offset_pp.values
        return {"slope": float((x * y).sum() / (x * x).sum()), "r": float(np.corrcoef(x, y)[0, 1]),
                "n_pairs": int(len(d))}

    out = {"what": "gap transfer factor: slider offset per pp of rescaled 4-point offset, through the origin",
           "sources": {"likert4": "CCAM 2021-2024 (weight_wave), 4-point verbal items",
                       "slider": "voelkel2026 PRE, 0-100 sliders, all arms pre-treatment"},
           "constructs": {"concern": "CCAM worry / voelkel2026 Concern_Pre",
                          "policy_general": "CCAM priority / voelkel2026 Policies_Pre_3",
                          "belief": "CCAM cause_recoded / voelkel2026 Belief_Pre"},
           "excluded": "level 'Other' (race-Other and party-Other are not the same group across sources)",
           "pooled": slope(F),
           "by_moderator": {m: slope(d) for m, d in F.groupby("moderator")},
           "by_construct": {c: slope(d) for c, d in F.groupby("construct")},
           "party_and_race_only": slope(F[F.moderator.isin(["party", "race"])]),
           "gaps_at_least_3pp": slope(F[F.likert4_offset_pp.abs() >= 3]),
           "adopted_GAP4": 0.80,
           "level_bridge_not_measurable": {
               "note": "the same three construct pairs disagree on LEVEL by -1.6 to +12.6 pp, so no "
                       "4-point level bridge is claimed; only gaps transfer",
               "diff_slider_minus_likert4_pp": {}},
           "pairs": R.to_dict("records")}
    for c, col in VCOL.items():
        lk = wmean(CVAL[c], cc.weight_wave)
        sl = float(pd.to_numeric(v[col], errors="coerce").mean())
        out["level_bridge_not_measurable"]["diff_slider_minus_likert4_pp"][c] = round(sl - lk, 2)
    p = RUN / "inputs" / "measured" / "gap_transfer_4point.json"
    p.write_text(json.dumps(out, indent=1))
    print("  pooled slope %.3f (r %.3f, n %d) -> %s" % (out["pooled"]["slope"], out["pooled"]["r"],
                                                        out["pooled"]["n_pairs"], p))


if __name__ == "__main__":
    main()
