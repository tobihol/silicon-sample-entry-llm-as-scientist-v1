#!/usr/bin/env python
"""Measure the CLIMATE-REFERENT PARTISAN FAN-OUT twice, independently, and pool it.

    /opt/kernel/venv/bin/python tools/measure_referent_fanout.py    # ~20 s
    -> inputs/measured/referent_fanout.json

The quantity: when the trust question moves from "scientists" to a climate-adjacent
referent, how much WIDER does the political gap get? It is the single largest judgement
call in `inputs/baselines/` (OPEN item 13), so it is measured on two mounted sources whose
weaknesses do not overlap.

  LEG A - Pew ATP W42, right cut, wrong referent.
    Form 1 rates medical AND environmental research scientists on the same five-item
    battery, within person, with Pew's party variable. Weakness: the referent is 2019
    "environmental research scientists" (framed around plants, animals and organisms),
    and it is read off a JSON of measured cells rather than recomputed here.

  LEG B - TISP US, right referent, weaker cut.
    The same respondents answer TRUST_PEW ("How much confidence do you have in scientists
    to act in the best interests of the public?") and CLIM_TRUST ("To what extent do you
    trust scientists in your country who work on climate change?") on the SAME 5-point
    scale - exactly the target's referent contrast, with no cross-format chaining.
    Weakness: TISP has no party item, only two 5-point political self-placements, so the
    cut is ideology blocks (1-2 vs 4-5), which are less separated than party groups.

A third leg (gligoric2025: trust in CLIMATOLOGISTS against 30 other randomly assigned scientist
types, control arm, ideology cut) is computed and reported but NOT pooled into the adopted value:
at SE 3.5 pp it moves the constant by 0.03 pp, which is below the resolution of anything
downstream, so it is corroboration rather than an input.

All legs are additive fan-outs in pp of scale range, and the additive form is what
transfers: TISP's generic gap is 9.7 pp against Pew's 21.6, so a MULTIPLICATIVE stretch
computed in one source (2.07) is meaningless in the other (1.55) while the additive
numbers agree at 10.4 vs 11.8. `tools/build_baselines.py` reads the pooled additive value
from this file and expresses it as a stretch of the party contrast only so that it
distributes over four levels and preserves centring.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd, pyreadstat

RUN = Path(__file__).resolve().parents[1]
D = Path("/workspace/datasets")


def wstat(y, w):
    y, w = np.asarray(y, float), np.asarray(w, float)
    m = np.isfinite(y) & np.isfinite(w) & (w > 0)
    mu = float(np.average(y[m], weights=w[m]))
    se = float(np.sqrt((w[m] ** 2 * (y[m] - mu) ** 2).sum()) / w[m].sum())
    return mu, se, int(m.sum())


def main():
    out = {"quantity": "additive partisan fan-out in pp of scale range when the trust referent "
                       "becomes climate-adjacent"}

    # ---- leg A: Pew W42, within person, party ------------------------------------------------
    pew = json.loads((RUN / "inputs" / "measured" / "pew_atp_trust.json").read_text())
    a = pew["derived"]["within_person_referent_shift_w42_form1"]["RQ4_A_to_E_composite"][
        "env_minus_med_within_person"]["party3_with_leaners"]
    rep = a["1::Rep/Lean Rep"]; dem = a["2::Dem/Lean Dem"]
    fan_a = dem["diff_0_100_pp"] - rep["diff_0_100_pp"]
    se_a = float(np.sqrt(dem["se_pp"] ** 2 + rep["se_pp"] ** 2))
    out["leg_a_pew_w42"] = {
        "referent": "medical -> environmental research scientists (5-item RQ4 battery, within person)",
        "cut": "F_PARTYSUM_FINAL (Rep/Lean vs Dem/Lean)", "fanout_pp": fan_a, "se_pp": se_a,
        "n_unweighted": rep["n_unweighted"] + dem["n_unweighted"],
        "source": "inputs/measured/pew_atp_trust.json (recomputable from ATP_W42.sav; verified "
                  "against the raw file to 0.01 pp)"}

    # ---- leg B: TISP US, within person, ideology ---------------------------------------------
    cols = ["COUNTRY_CODE", "WEIGHT_CNTRY", "CLIM_TRUST", "TRUST_PEW", "DEM_POL_conservative",
            "DEM_POL_right"]
    t, _ = pyreadstat.read_sav(D / "tisp/downloads/ds_final.sav", usecols=cols)
    u = t[t.COUNTRY_CODE == "USA"].copy()
    u["w"] = pd.to_numeric(u.WEIGHT_CNTRY, errors="coerce").fillna(0)
    r100 = lambda x: (pd.to_numeric(x, errors="coerce") - 1) / 4 * 100
    u["clim"], u["gen"] = r100(u.CLIM_TRUST), r100(u.TRUST_PEW)
    u["diff"] = u.clim - u.gen
    legs = {}
    for col in ["DEM_POL_conservative", "DEM_POL_right"]:
        v = pd.to_numeric(u[col], errors="coerce")
        lo, hi = u[v.isin([1, 2])], u[v.isin([4, 5])]          # least vs most conservative/right
        d_lo, d_hi = wstat(lo["diff"], lo.w), wstat(hi["diff"], hi.w)
        g_lo, g_hi = wstat(lo.gen, lo.w), wstat(hi.gen, hi.w)
        c_lo, c_hi = wstat(lo.clim, lo.w), wstat(hi.clim, hi.w)
        legs[col] = {"fanout_pp": d_lo[0] - d_hi[0], "se_pp": float(np.sqrt(d_lo[1] ** 2 + d_hi[1] ** 2)),
                     "generic_gap_pp": g_lo[0] - g_hi[0], "climate_gap_pp": c_lo[0] - c_hi[0],
                     "multiplicative_stretch_here": (c_lo[0] - c_hi[0]) / (g_lo[0] - g_hi[0]),
                     "n_unweighted": d_lo[2] + d_hi[2]}
    out["leg_b_tisp_us"] = {
        "referent": "scientists -> scientists in your country who work on climate change "
                    "(same 5-point item, within person)",
        "cut": "DEM_POL_* 5-point self-placement, blocks 1-2 vs 4-5", "by_scale": legs,
        "overall_within_person_level_shift_pp": wstat(u["diff"], u.w)[0],
        "primary": "DEM_POL_conservative"}
    fan_b = legs["DEM_POL_conservative"]["fanout_pp"]
    se_b = legs["DEM_POL_conservative"]["se_pp"]

    # ---- leg C: gligoric2025, randomised referent, the exact climate scientist ---------------
    # 35 scientist types, FOUR randomly assigned to each respondent, two 1-7 trust items each,
    # control arm only. The referent is "climatologists" - the closest wording on any mounted
    # file to the target's "climate scientists" - and the assignment is randomised, so the
    # type contrast is causal. Its weakness is the cut: `PolIdentification` in this file does not
    # behave like a party scale (r = 0.24 with ideology, and trust in climatologists is FLAT
    # across it while the ideology gradient is monotone 75 -> 54), so only `Ideology` is used;
    # the sample is also an unweighted, conservative-skewed convenience panel.
    gl = pd.read_csv(D / "gligoric2025/downloads/Main Study/Analyses (data and codes)/dataMainStudy.csv",
                     low_memory=False)
    ctrl = gl[gl.Condition == "Control"].reset_index(drop=True)
    occs = sorted({c.rsplit("_", 1)[0] for c in gl.columns
                   if c.endswith(("_1", "_2")) and not c.startswith("Believability")})
    CLIMATE = ["climatologists", "environmental scient", "ecologists", "meteorologists",
               "oceanographers", "hydrologist"]
    long = []
    for o in occs:
        t = ctrl[[o + "_1", o + "_2"]].mean(axis=1)
        m = t.notna()
        long.append(pd.DataFrame({"rid": ctrl.index[m], "occ": o, "trust100": (t[m] - 1) / 6 * 100,
                                  "ideo": ctrl.Ideology[m]}))
    long = pd.concat(long)
    sub = long[(long.occ == "climatologists") | (~long.occ.isin(CLIMATE))].copy()
    sub["climate"] = (sub.occ == "climatologists").astype(int)
    sub["lib"] = (sub.ideo <= 5).astype(int)                     # 1 = extremely liberal .. 10 = extremely conservative
    X = np.column_stack([np.ones(len(sub)), sub.climate, sub.lib, sub.climate * sub.lib])
    y = sub.trust100.to_numpy(float)
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ beta
    XtXi = np.linalg.inv(X.T @ X)
    meat = np.zeros((4, 4))
    for _, idx in sub.groupby("rid").indices.items():            # cluster on the respondent
        s_ = X[idx].T @ r[idx]
        meat += np.outer(s_, s_)
    se_c = float(np.sqrt(np.diag(XtXi @ meat @ XtXi))[3])
    fan_c = float(beta[3])
    bal = lambda d: 0.5 * d[d.lib == 1].trust100.mean() + 0.5 * d[d.lib == 0].trust100.mean()
    out["leg_c_gligoric2025"] = {
        "referent": "climatologists vs 30 non-climate scientist types (4 types randomly assigned per "
                    "respondent, two 1-7 trust items each), control arm",
        "cut": "Ideology 1-5 vs 6-10", "fanout_pp": fan_c, "se_pp": se_c,
        "n_obs": int(len(sub)), "n_respondents": int(sub.rid.nunique()),
        "ideology_balanced_level_pp": {"climatologists": bal(sub[sub.climate == 1]),
                                       "other_sciences": bal(sub[sub.climate == 0]),
                                       "difference": bal(sub[sub.climate == 1]) - bal(sub[sub.climate == 0])},
        "climatologists_rank": "largest ideology gap of all 35 types (16.2 pp; environmental "
                               "scientists 16.1; median type ~4.6)",
        "not_used_for_the_adopted_value": "SE 3.5 pp; pooling it moves the constant by 0.03 pp, "
                                          "below the resolution of anything downstream, so it is "
                                          "recorded as corroboration and every artefact stays on the "
                                          "two-leg value"}

    w = np.array([1 / se_a ** 2, 1 / se_b ** 2])
    pooled = float(np.dot(w, [fan_a, fan_b]) / w.sum())
    w3 = np.array([1 / se_a ** 2, 1 / se_b ** 2, 1 / se_c ** 2])
    pooled3 = float(np.dot(w3, [fan_a, fan_b, fan_c]) / w3.sum())
    out["pooled"] = {"fanout_pp": pooled, "se_pp": float(np.sqrt(1 / w.sum())),
                     "method": "inverse-variance over legs A and B (the two precise ones)",
                     "three_leg_value_not_adopted": {"fanout_pp": pooled3,
                                                     "se_pp": float(np.sqrt(1 / w3.sum())),
                                                     "why": "leg C moves it by %.2f pp" % (pooled3 - pooled)},
                     "adopted_by": "tools/build_baselines.py (PEW_FANOUT)",
                     "stretch_on_pew_party_gap": 1 + pooled / 21.55,
                     "why_additive": "TISP's generic ideology gap is %.1f pp against Pew's 21.6, so a "
                                     "multiplicative stretch fitted in one source (%.2f) does not "
                                     "transfer to the other (%.2f) while the additive numbers agree "
                                     "(%.1f vs %.1f)" % (legs["DEM_POL_conservative"]["generic_gap_pp"],
                                                         legs["DEM_POL_conservative"]["multiplicative_stretch_here"],
                                                         1 + fan_a / 21.55, fan_b, fan_a)}
    p = RUN / "inputs" / "measured" / "referent_fanout.json"
    p.write_text(json.dumps(out, indent=1))
    print("  leg A (Pew, party)      %.2f pp (SE %.2f)" % (fan_a, se_a))
    print("  leg B (TISP, ideology)  %.2f pp (SE %.2f)" % (fan_b, se_b))
    print("  leg C (gligoric, ideol) %.2f pp (SE %.2f)  [corroboration only]" % (fan_c, se_c))
    print("  pooled                  %.2f pp (SE %.2f) -> stretch %.3f  -> %s"
          % (pooled, out["pooled"]["se_pp"], out["pooled"]["stretch_on_pew_party_gap"], p))


if __name__ == "__main__":
    main()
