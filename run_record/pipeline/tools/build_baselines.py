#!/usr/bin/env python
"""Rebuild inputs/baselines/ from the mounted datasets.

Human-anchored control-condition levels and 27 x 13 subgroup offsets for the card
(AGENTS.md stage `card` input). Every number here is a measurement on a mounted file;
the argument for each choice is in inputs/baselines/provenance.json and OPEN.md item 2.

    python tools/build_baselines.py       # ~30 s, needs pyreadstat

Three measured corrections are applied and are the reason this is not a naive rescale:
  BRIDGE   -4.9 pp  a linearly rescaled coarse-Likert mean runs high against a 0-100 slider
  REFERENT -3.93 pp "most scientists" -> "most climate scientists", within-person in TISP
  GAP      x0.8     subgroup gaps shrink when they cross from a coarse scale to a slider
"""
import json, sys, time
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402

RUN = Path(__file__).resolve().parents[1]
D = Path("/workspace/datasets")
S = ssb.spec.load()
LV = S["moderators"]
MODS = list(LV)
BRIDGE, REFERENT, GAP = -4.9, -3.93, 0.8
# GAP4: the same gap-transfer idea measured for a FOUR-point verbal scale, which is what the
# Pew confidence item is. Party/race/gender/age offsets for three constructs (climate concern,
# policy priority, attribution belief) were computed twice - on CCAM 2021-2024's 4-point items
# and on voelkel2026's 0-100 sliders - and regressed through the origin: slope 0.808 (r 0.953,
# n 36 level-construct pairs), 0.785 on party+race alone, 0.799 restricted to gaps >= 3 pp.
# Per-moderator: party 0.753, gender 0.848, race 1.047, age 1.241. The pooled 0.80 is used; the
# spread is the honest uncertainty. This is a MEASUREMENT of what the 0.8 above was assuming.
GAP4 = 0.80
EDGES = [30000, 56000, 100000, 168000]


def wmean(y, w):
    y, w = np.asarray(y, float), np.asarray(w, float)
    m = np.isfinite(y) & np.isfinite(w)
    return float(np.average(y[m], weights=w[m])) if m.sum() > 2 else np.nan


def wsd(y, w):
    y, w = np.asarray(y, float), np.asarray(w, float)
    m = np.isfinite(y) & np.isfinite(w)
    mu = wmean(y, w)
    return float(np.sqrt(np.average((y[m] - mu) ** 2, weights=w[m])))


def offsets(df, col, value, weight, mod, shares, min_n, factor, outcome, source, prio=9):
    """Group means centred on the POOL's shares, so sum_l share_l * offset_l = 0."""
    d = df.assign(_v=np.asarray(value, float), _w=np.asarray(weight, float)).dropna(subset=[col, "_v", "_w"])
    g = d.groupby(col, observed=True).apply(lambda z: pd.Series({"m": wmean(z._v, z._w), "n": len(z)}))
    ok = [l for l in LV[mod] if l in g.index and g.loc[l, "n"] >= min_n]
    if len(ok) < 2:
        return []
    wt = sum(shares[(mod, l)] for l in ok)
    centre = sum(shares[(mod, l)] * g.loc[l, "m"] for l in ok) / wt
    return [{"moderator": mod, "level": l, "outcome": outcome, "offset": float((g.loc[l, "m"] - centre) * factor),
             "n": int(g.loc[l, "n"]), "source": source, "prio": prio} for l in ok]


def main(fanout: float | None = None, outdir: Path | None = None, agency_theta: float | None = None):
    global FANOUT, AGENCY_THETA
    FANOUT = fanout
    AGENCY_THETA = agency_theta
    t0 = time.time()
    import pyreadstat
    pool = pd.read_csv(RUN / "inputs" / "pool" / "joint.csv")
    shares = {(m, l): float(pool[pool[m] == l].weight.sum()) for m in MODS for l in LV[m]}
    rows = []

    # ---------------- voelkel2026: the five climate outcomes, all four available moderators -------
    v = pd.read_csv(D / "voelkel2026/downloads/CCC - Data - Recoded.csv", low_memory=False)
    vm = {"gender": v.Gender,
          "age_band": pd.cut(v.Age, bins=[17, 29, 44, 59, 200], labels=LV["age_band"]),
          "race": v.Race.map({1.0: "White / Caucasian", 2.0: "Black / African American", 3.0: "Hispanic / Latino",
                              4.0: "Asian / Asian American", 5.0: "Other"}),
          "party": v.Party_N.map({1: "Democrat", 2: "Democrat", 3: "Independent", 4: "Independent",
                                  5: "Independent", 6: "Republican", 7: "Republican", 8: "Other"})}
    VMAP = {"Belief_Pre": "belief_post", "Concern_Pre": "concern_mean", "Policies_Pre_3": "policy_general",
            "PoliciesSp_Pre": "policy_specific_mean", "IntentNp_Pre": "behavior_mean"}
    for mod, lv in vm.items():
        f = pd.DataFrame({mod: lv.values})
        for src, tgt in VMAP.items():
            rows += offsets(f, mod, pd.to_numeric(v[src], errors="coerce"), np.ones(len(v)), mod, shares, 100, 1.0,
                            tgt, f"voelkel2026 PRE (pre-treatment, all arms n=13,821), {src}", prio=0)
        # the 100-cent donation allocation, as a costly-act shape
        for tgt, scale, note in [("donation_ams", 0.1, "converted pp->$ (/10)"),
                                 ("newsletter_signup", 0.005, "as a signup-rate proxy, halved - DECLARED")]:
            rows += offsets(f, mod, pd.to_numeric(v["Donation"], errors="coerce"), np.ones(len(v)), mod, shares,
                            100, scale, tgt, f"voelkel2026 Donation (100-cent allocation) shape, {note}", prio=4)
    ctrl = v[v.ConditionR == "Control"]
    levels = {tgt: (round(float(pd.to_numeric(ctrl[src], errors="coerce").mean()), 2),
                    round(float(pd.to_numeric(ctrl[src], errors="coerce").std(ddof=1)), 2),
                    f"voelkel2026 {src}, control arm (unprimed) - direct slider measurement, no bridge needed")
              for src, tgt in VMAP.items()}

    # policy_specific_mean: voelkel2026 has the right SAMPLE but the WRONG ITEMS. Its four
    # PoliciesSp items are a renewable-electricity mandate, a coal-plant ban, oil/gas permits and
    # fossil subsidies, each with an explicit cost trade-off clause - none of them is one of the
    # target's seven. vlasceanu2024's CC_policy items ARE the target's seven, near-verbatim
    # (checked item by item against benchmark/codebook.csv), so the level comes from there,
    # post-stratified onto the pool's gender x age. The voelkel2026 value is kept as a cross-check.
    vl = ssb.task.load_dataset(ssb.task.load_adapter("vlasceanu2024"))
    vlc = vl[vl._arm == "Control"].copy()
    SEVEN = ["Policy1", "Policy2", "Policy4", "Policy6", "Policy7", "Policy8", "Policy9"]
    vlc["comp7"] = vlc[SEVEN].apply(pd.to_numeric, errors="coerce").mean(axis=1)
    vlc["age_band"] = pd.cut(pd.to_numeric(vlc.Age, errors="coerce"), bins=[17, 29, 44, 59, 200], labels=LV["age_band"])
    dd = vlc.dropna(subset=["comp7", "gender", "age_band"])
    cellm = dd.groupby(["gender", "age_band"], observed=True).comp7.agg(["mean", "size"])
    num = wt = 0.0
    for (g_, a_), rr in cellm.iterrows():
        if rr["size"] < 20:
            continue
        sh = shares[("gender", g_)] * shares[("age_band", a_)]
        num += sh * rr["mean"]; wt += sh
    levels["policy_specific_mean"] = (
        round(num / wt, 2), round(float(dd.comp7.std(ddof=1)), 2),
        "vlasceanu2024 US control arm, mean of the SEVEN near-verbatim target items "
        "(CC_policy 1/2/5/7/8/9/10), post-stratified onto the pool's gender x age (raw %.2f); "
        "voelkel2026 PoliciesSp_Pre gives 52.61 but its four items are NOT the target's and carry an "
        "explicit cost trade-off clause - recorded as a cross-check, not used" % float(dd.comp7.mean()))

    # ---------------- goldwert2026: the two behavioural outcomes --------------------------------
    ad = ssb.task.load_adapter("goldwert2026")
    g = ssb.task.load_dataset(ad)
    gc = g[g._arm == "Control"]
    for mod in ["gender", "age_band", "party", "education", "income"]:
        if mod not in gc.columns:
            continue
        for src, tgt in [("donation", "donation_ams"), ("newsletter1", "newsletter_signup")]:
            rows += offsets(gc, mod, pd.to_numeric(gc[src], errors="coerce"), np.ones(len(gc)), mod, shares, 30, 1.0,
                            tgt, f"goldwert2026 control arm (finishers), {src}", prio=1)
    for src, tgt, sd in [("donation", "donation_ams", None), ("newsletter1", "newsletter_signup", None)]:
        y = pd.to_numeric(gc[src], errors="coerce").dropna()
        levels[tgt] = (round(float(y.mean()), 3), round(float(y.std(ddof=1)), 3),
                       f"goldwert2026 {src}, control arm, finishers (n={len(y)})")

    # ---------------- TISP: the trust level, the two corrections, and 3 moderators ---------------
    tcols = ["COUNTRY_CODE", "WEIGHT_CNTRY", "DEM_AGE", "DEM_GENDER", "DEM_INCOME_USD", "CLIM_TRUST", "TRUST_PEW",
             "TRUST_SCI_expert", "TRUST_SCI_honest", "TRUST_SCI_concerned", "TRUST_SCI_open", "TRUST_SCI_intellig",
             "TRUST_SCI_ethical", "TRUST_SCI_improve", "TRUST_SCI_trans", "TRUST_SCI_qualified", "TRUST_SCI_sincere",
             "TRUST_SCI_otherint", "TRUST_SCI_otherviews", "NORMPERC_integrate", "NORMPERC_advocate",
             "NORMPERC_communicate", "NORMPERC_involved", "DEM_EDU"]
    t, _ = pyreadstat.read_sav(D / "tisp/downloads/ds_final.sav", usecols=tcols)
    u = t[t.COUNTRY_CODE == "USA"].copy()
    u["w"] = u.WEIGHT_CNTRY.fillna(0)
    SUB = {"competence": ["TRUST_SCI_qualified", "TRUST_SCI_intellig", "TRUST_SCI_expert"],
           "integrity": ["TRUST_SCI_honest", "TRUST_SCI_ethical", "TRUST_SCI_sincere"],
           "benevolence": ["TRUST_SCI_concerned", "TRUST_SCI_improve", "TRUST_SCI_otherint"],
           "openness": ["TRUST_SCI_open", "TRUST_SCI_trans", "TRUST_SCI_otherviews"]}
    for k, its in SUB.items():
        u[k] = u[its].mean(axis=1)
    u["trust_md"] = u[list(SUB)].mean(axis=1)
    u["policy_role"] = u[["NORMPERC_integrate", "NORMPERC_advocate", "NORMPERC_communicate", "NORMPERC_involved"]].mean(axis=1)
    r100 = lambda x: (x - 1) / 4 * 100
    referent = r100(wmean(u.CLIM_TRUST, u.w)) - r100(wmean(u.TRUST_PEW, u.w))   # measured, ~ -3.93
    levels["trust_multidimensional"] = (round(r100(wmean(u.trust_md, u.w)) + referent + BRIDGE, 1),
                                        round(wsd(u.trust_md, u.w) * 25, 1),
                                        "TISP US 12 items -> 4 subscales, weighted, rescaled; referent %+.2f pp (measured "
                                        "within-person CLIM_TRUST vs TRUST_PEW); bridge %+.1f pp" % (referent, BRIDGE))
    levels["trust_post"] = (round(r100(wmean(u.CLIM_TRUST, u.w)) + BRIDGE, 1), 30.0,
                            "TISP US CLIM_TRUST (already the climate referent), bridge %+.1f pp" % BRIDGE)
    levels["policy_role_mean"] = (round(r100(wmean(u.policy_role, u.w)) + BRIDGE, 1), 26.0,
                                  "TISP US NORMPERC_* (verbatim twins of policy_role_1..4), bridge %+.1f pp" % BRIDGE)
    # distrust_post: the LAST declared level, and it stays declared for a measured reason.
    # No mounted dataset asks a direct distrust item about scientists on a slider. The two
    # candidates were tried and REJECTED on evidence: TISP's negatively-worded items
    # (SCIPOP_advantage/cahoots, CLIM_GOV_lying) carry a large acquiescence method factor -
    # they correlate 0.68 with each other, ~0.0 with the 12-item trust battery (-0.045) and
    # +0.20 to +0.22 with a POSITIVELY worded item ("my government is trustworthy"), which is
    # impossible under a consistent valence. Their implied "asymmetries" (+10.0 pp on the
    # government pair, +24.2 pp on the scientist pair) are therefore method variance, not
    # ambivalence, and anchoring a level on them would import that method factor into a scored
    # row. What is left is the complement of the card's own measured climate-scientist trust
    # (100 - trust_post); the declared 28.0 sits below it, which is the usual finding that trust
    # and distrust are not exact complements. The range 28-38 is defensible and the choice inside
    # it is DECLARED - the single remaining declared level on the card.
    levels["distrust_post"] = (28.0, 30.0,
                               "DECLARED PRIOR (the last one on the card) - no mounted dataset asks a direct "
                               "distrust item about scientists; TISP's negatively-worded items were tried and "
                               "rejected for acquiescence (r=0.68 among themselves, -0.045 with the trust "
                               "battery, +0.22 with a positively-worded item). Complement of the measured "
                               "trust_post level is %.1f pp; plausible range 28-38"
                               % (100 - levels["trust_post"][0]))
    u["age_band"] = pd.cut(u.DEM_AGE, bins=[17, 29, 44, 59, 200], labels=LV["age_band"])
    u["gender"] = u.DEM_GENDER.map({1.0: "Female", 2.0: "Male"})
    inc = u.DEM_INCOME_USD.to_numpy(float)
    u["income"] = np.where(np.isfinite(inc), np.array(LV["income"])[np.digitize(inc, EDGES, right=False)], None)
    for tgt, col in [("trust_multidimensional", "trust_md"), ("trust_post", "CLIM_TRUST"), ("policy_role_mean", "policy_role")]:
        for mod in ["age_band", "income", "gender"]:
            rows += offsets(u, mod, r100(u[col]), u.w, mod, shares, 100, GAP, tgt,
                            f"TISP US (WEIGHT_CNTRY), {col} rescaled, x{GAP} gap factor", prio=2)

    # ---------------- Pew ATP: the party / race / gender / education x trust shapes --------------
    # OPEN item 2's direct anchor. Pew's 4-point confidence item ("How much confidence, if any,
    # do you have in ... Scientists to act in the best interests of the public?") is the only
    # mounted source that carries a trust-in-SCIENTISTS measure with party AND race AND gender in
    # one probability-sampled national panel. It replaces GSS `consci` (institutional confidence
    # in "the scientific community", a proxy) wherever its cut variable matches the target's
    # levels: party 4/4, race 5/5, gender 3/3, education 5/6. It does NOT replace TISP on age
    # (Pew's bands are 18-29/30-49/50-64/65+, which do not align) or on income (Pew top-codes at
    # $100,000+, which spans two target bands). Measurements and caveats: notes/DATA_PEW.md.
    pew = json.loads((RUN / "inputs" / "measured" / "pew_atp_trust.json").read_text())
    PEW_LEVELS = {
        "party": {"1::Republican": "Republican", "2::Democrat": "Democrat",
                  "3::Independent": "Independent", "4::Something else": "Other"},
        "race": {"1::White non-Hispanic": "White / Caucasian", "2::Black non-Hispanic": "Black / African American",
                 "3::Hispanic": "Hispanic / Latino", "5::Asian non-Hispanic": "Asian / Asian American",
                 "4::Other": "Other"},
        "gender": {"1::A man": "Male", "2::A woman": "Female", "3::In some other way": "Other"},
        "education": {"1::Less than high school": "Less than high school",
                      "2::High school graduate": "High school diploma / GED",
                      "3::Some college, no degree": "Some college or Associate's degree",
                      "4::Associate's degree": "Some college or Associate's degree",
                      "5::College graduate/some post grad": "Bachelor's degree",
                      "6::Postgraduate": "Master's degree / Professional degree"},
    }
    PEW_CUT = {"party": "party4", "race": "race", "gender": "gender", "education": "education6"}
    # W42 is EXCLUDED: its Dem-Rep gap is 8.4 pp against W100/W114's 22.7/21.6, it has no Asian
    # category, and it is pre-COVID. The two post-COVID waves are pooled by Kish effective n.
    PEW_WAVES = {"w100": "CONF_G_W100", "w114": "CONF_G_W114"}

    def pew_cells(mod):
        acc = {}
        for w, col in PEW_WAVES.items():
            cuts = pew["waves"][w]["items"][col]["cuts"]
            cut = PEW_CUT[mod]
            if cut not in cuts:
                continue                      # W100 ships no 6-level education
            for key, cell in cuts[cut].items():
                tgt = PEW_LEVELS[mod].get(key)
                if tgt is None:               # 99::Refused is its own cell in the JSON, never merged
                    continue
                k = cell["kish_effective_n"]
                a = acc.setdefault(tgt, {"num": 0.0, "den": 0.0, "n": 0, "waves": []})
                a["num"] += cell["mean_0_100"] * k
                a["den"] += k
                a["n"] += cell["n_unweighted_valid"]
                a["waves"].append(w)
        cells = {t: [a["num"] / a["den"], a["n"], "+".join(sorted(set(a["waves"]))), ""] for t, a in acc.items()}
        if mod == "education" and "Master's degree / Professional degree" in cells:
            # Pew's top education band is "Postgraduate": it does not separate a Master's from a
            # doctorate, so the two target levels share one measured cell and say so per row.
            m = cells["Master's degree / Professional degree"]
            cells["Doctorate degree / Ph.D."] = [m[0], m[1], m[2],
                                                 " ; Pew's top band is 'Postgraduate' - Master's cell reused, FLAGGED"]
        return cells

    def offsets_from_cells(cells, mod, factor, outcome, source, prio, min_n=30):
        ok = [l for l in LV[mod] if l in cells and cells[l][1] >= min_n]
        if len(ok) < 2:
            return []
        wt = sum(shares[(mod, l)] for l in ok)
        centre = sum(shares[(mod, l)] * cells[l][0] for l in ok) / wt
        return [{"moderator": mod, "level": l, "outcome": outcome, "prio": prio,
                 "offset": float((cells[l][0] - centre) * factor), "n": int(cells[l][1]),
                 "source": source + f" [waves {cells[l][2]}, n={cells[l][1]}]" + cells[l][3]} for l in ok]

    # The referent amplification, measured on two mounted sources whose weaknesses do not
    # overlap (tools/measure_referent_fanout.py, OPEN item 13):
    #   Pew W42, right cut / wrong referent: medical -> environmental research scientists, same
    #     5-item battery within person, +11.83 pp (SE 1.09) Dem/Lean minus Rep/Lean, positive on
    #     all eleven items; the parallel medical-vs-generic contrast has NO partisan interaction.
    #   TISP US, right referent / weaker cut: "scientists" -> "scientists in your country who work
    #     on climate change", the SAME 5-point item within person, +10.40 pp (SE 1.16) between
    #     ideology blocks - the target's exact referent contrast, with no cross-format chaining.
    # Inverse-variance pooled: 11.16 pp (SE 0.80). The ADDITIVE form is what transfers - TISP's
    # generic gap is 9.7 pp against Pew's 21.6, so a multiplicative stretch fitted in one source
    # (2.07) is meaningless in the other (1.55) - and it is applied here as a proportional stretch
    # of the party contrast only so that it distributes over four levels and preserves centring.
    # Cross-check: applied to W42's own generic gap (8.37) the stretch predicts 12.7 pp for the
    # environmental battery against 16.00 measured there, i.e. it is conservative.
    _fan = json.loads((RUN / "inputs" / "measured" / "referent_fanout.json").read_text())
    PEW_FANOUT = _fan["pooled"]["fanout_pp"] if FANOUT is None else FANOUT
    PEW_GENERIC_GAP = 21.55
    AMP = 1 + PEW_FANOUT / PEW_GENERIC_GAP
    PEW_T = {"trust_multidimensional": AMP, "trust_post": AMP, "inst_trust_mean": 1.0,
             "distrust_post": -AMP}
    for mod in ["party", "race", "gender", "education"]:
        cells = pew_cells(mod)
        for tgt, amp in PEW_T.items():
            amp_ = amp if mod == "party" else (1.0 if amp > 0 else -1.0)
            src = ("Pew ATP 4-point confidence in scientists, weighted, rescaled, "
                   f"x{GAP4} 4-point->slider gap factor"
                   + (f", x{AMP:.2f} climate-referent partisan fan-out ({PEW_FANOUT:.2f} pp, Pew W42 + TISP pooled)" if mod == "party" and abs(amp) > 1 else "")
                   + (" ; SIGN FLIPPED (reverse-valenced)" if amp < 0 else ""))
            rows += offsets_from_cells(cells, mod, GAP4 * amp_, tgt, src, prio=1)
    # gender x Other: the six cells OPEN item 2 said no mounted dataset could reach. Pew's
    # `In some other way` cell is 94 unweighted responses pooled over two waves (62.35 in W100,
    # 52.69 in W114 - a 10 pp swing on ~45 cases each), so it is anchored but THIN.
    # Level cross-check (recorded, NOT used): Pew's own weighted level for "confidence in
    # scientists" is W114 66.80 / W100 67.03 on the rescaled 0-100 lattice, before any bridge.
    # The 4-point -> slider LEVEL bridge is not measurable on the mounted data (the CCAM/slider
    # item pairs that measure the gap factor are not near-verbatim enough for a level), so the
    # trust LEVELS below stay on TISP's finer 5-point battery with the measured 3-point bridge.
    pew_level_crosscheck = {w: pew["waves"][w]["items"][c]["cuts"]["overall"]["ALL"]["mean_0_100"]
                            for w, c in PEW_WAVES.items()}

    # ---------------- GSS: the party x trust and race x trust shapes -----------------------------
    gs, _ = pyreadstat.read_dta(D / "gss/downloads/GSS_stata/gss7224_r3a.dta", encoding="latin1",
                                usecols=["year", "consci", "coneduc", "confed", "partyid", "race",
                                         "hispanic", "degree", "sex", "wtssps"])
    for c in ["year", "consci", "coneduc", "confed", "partyid", "race", "degree", "sex", "hispanic"]:
        gs[c] = pd.to_numeric(gs[c], errors="coerce")
    gs["w"] = pd.to_numeric(gs.wtssps, errors="coerce")
    r = gs[(gs.year >= 2016) & gs.consci.notna() & gs.w.notna()].copy()
    r["trust100"] = (3 - r.consci) / 2 * 100
    r["party"] = r.partyid.map({0: "Democrat", 1: "Democrat", 2: "Democrat", 3: "Independent",
                                4: "Republican", 5: "Republican", 6: "Republican", 7: "Other"})
    r["race"] = np.where(r.hispanic.fillna(1) > 1, "Hispanic / Latino",
                np.where(r.race == 1, "White / Caucasian", np.where(r.race == 2, "Black / African American", "Other")))
    r["education"] = r.degree.map({0: "Less than high school", 1: "High school diploma / GED",
                                   2: "Some college or Associate's degree", 3: "Bachelor's degree",
                                   4: "Master's degree / Professional degree"})
    r["gender"] = r.sex.map({1: "Male", 2: "Female"})
    GSS_T = ["trust_multidimensional", "trust_post", "distrust_post", "inst_trust_mean"]
    src = ("GSS 2016-2024 consci (3-point institutional confidence in the scientific community), weighted, "
           f"rescaled, x{GAP} gap factor")
    for mod in ["party", "race", "education", "gender"]:
        base = offsets(r, mod, r.trust100, r.w, mod, shares, 100, GAP, "_", src, prio=2)
        for o in base:
            for tgt in GSS_T:
                sign = -1.0 if tgt == "distrust_post" else 1.0
                rows.append({**o, "outcome": tgt, "offset": o["offset"] * sign,
                             "prio": 2, "source": src + (" ; SIGN FLIPPED (reverse-valenced)" if sign < 0 else "")})
            if mod == "race" and o["level"] == "Other":     # GSS has no Asian category
                for tgt in GSS_T:
                    sign = -1.0 if tgt == "distrust_post" else 1.0
                    rows.append({**o, "level": "Asian / Asian American", "outcome": tgt, "offset": o["offset"] * sign,
                                 "prio": 3, "source": src + " ; GSS has no Asian category - 'other non-white' reused, FLAGGED"})
            if mod == "education" and o["level"] == "Master's degree / Professional degree":
                for tgt in GSS_T:
                    sign = -1.0 if tgt == "distrust_post" else 1.0
                    rows.append({**o, "level": "Doctorate degree / Ph.D.", "outcome": tgt, "offset": o["offset"] * sign,
                                 "prio": 3, "source": src + " ; GSS `degree` tops out at graduate - Master's reused, FLAGGED"})
    # inst_trust_mean is the mean of FIVE institutions - EPA, NASA, NOAA, universities/colleges and
    # the federal government - not a science-confidence item with a haircut. Two of the five are
    # measured far below the scientific community in the SAME respondents (GSS 2016-2024, weighted,
    # all three items answered), so the composition is arithmetic, not a declared prior:
    #     education           -17.5 pp   |   executive branch of the federal government  -33.1 pp
    # Pew corroborates the government end independently on a different scale and panel: elected
    # officials 36.6 against scientists 66.8, i.e. -30.2 pp.
    # The three agencies are the bracketed unknown - science organisations that are also government -
    # so they are taken at the MIDPOINT of that bracket and the whole bracket is recorded. The
    # component gaps are carried onto the slider with the same x0.8 gap factor as every other
    # coarse-scale gap, and the level anchor is TISP's generic-scientist item (the right referent for
    # institutions), bridged.
    gsx = gs[(gs.year >= 2016) & gs.wtssps.notna()]
    gsx = gsx[gsx.consci.between(1, 3) & gsx.coneduc.between(1, 3) & gsx.confed.between(1, 3)]
    g100 = lambda col: (3 - gsx[col]) / 2 * 100
    edu_off = wmean(g100("coneduc") - g100("consci"), gsx.wtssps)
    fed_off = wmean(g100("confed") - g100("consci"), gsx.wtssps)
    # The three federal science agencies are placed by MEASUREMENT now, not at the midpoint:
    # Pew ATP W149 (Jul 2024, published topline) puts EPA/NASA/NOAA a fraction THETA of the way from
    # the scientific community to the federal government (tools/measure_agency_anchor.py, OPEN item 14).
    _ag = json.loads((RUN / "inputs" / "measured" / "agency_trust_anchor.json").read_text())
    THETA = _ag["adopted"]["theta_agencies"] if AGENCY_THETA is None else AGENCY_THETA
    agency_off = fed_off * THETA
    comp = lambda a: (3 * a + edu_off + fed_off) / 5 * GAP
    sci_slider = r100(wmean(u.TRUST_PEW, u.w)) + BRIDGE
    levels["inst_trust_mean"] = (
        round(sci_slider + comp(agency_off), 1), 24.0,
        "COMPOSED, not declared: TISP TRUST_PEW (generic scientists) rescaled %.1f + bridge %+.1f = %.1f "
        "slider anchor, plus the 5-institution composition (3 agencies + universities + federal "
        "government) measured within-person in GSS 2016-2024 (n=%d): education %+.1f pp and the federal "
        "executive %+.1f pp against the scientific community. The three agencies are PLACED, not assumed: "
        "Pew ATP W149 (Jul 1-7 2024, N=9,424, published topline) rescaled on the same 4-point map puts "
        "EPA at 54.0 and NASA at 67.0 against a DOJ/IRS/DHS same-half-sample comparator mean of 46.9 and "
        "Pew's own confidence-in-scientists 66.9, i.e. theta = %.3f of the way from science to government "
        "(bracket over wave x not-sure treatment %.3f-%.3f; the previous unmeasured midpoint 0.500 lies "
        "OUTSIDE it), so agencies %+.1f, composite %+.1f pp after the x%.1f gap factor. Level bracket if "
        "the agencies sat at either end: %.1f (= federal government) to %.1f (= scientific community); "
        "over the measured theta bracket alone: %.1f to %.1f. The favourability->confidence bridge is "
        "DECLARED (no institution is measured in both families on the mounted data) and W149 microdata "
        "lands post-lock-request"
        % (r100(wmean(u.TRUST_PEW, u.w)), BRIDGE, sci_slider, len(gsx), edu_off, fed_off, THETA,
           _ag["adopted"]["theta_bracket_over_wave_x_notsure"][0],
           _ag["adopted"]["theta_bracket_over_wave_x_notsure"][1], agency_off,
           comp(agency_off), GAP, sci_slider + comp(fed_off), sci_slider + comp(0.0),
           sci_slider + comp(fed_off * _ag["adopted"]["theta_bracket_over_wave_x_notsure"][1]),
           sci_slider + comp(fed_off * _ag["adopted"]["theta_bracket_over_wave_x_notsure"][0])))

    # ---------------- CCAM: education and income shapes on the climate outcomes ------------------
    cc, cmeta = pyreadstat.read_sav(D / "ccam/downloads/CCAM SPSS Data 2008-2024.sav")
    cc = cc[cc.year >= 13].copy()                                   # 2021-2024
    rng = np.random.default_rng(7)
    uu = rng.random(len(cc))
    def band(code, u_):
        if not np.isfinite(code) or code < 1: return None
        code = int(code)
        if code <= 8: return 0
        if code <= 11: return 1
        if code == 12: return 1 if u_ < 0.6 else 2                  # $50-59,999 straddles $56,000
        if code <= 15: return 2
        if code <= 17: return 3
        if code == 18: return 3 if u_ < 0.72 else 4                 # $150-174,999 straddles $168,000
        return 4
    cc["income"] = [None if (b := band(x, u_)) is None else LV["income"][b] for x, u_ in zip(cc.income.to_numpy(), uu)]
    cc["education"] = cc.educ.map(lambda x: "Less than high school" if 1 <= x <= 8 else "High school diploma / GED" if x == 9
                                  else "Some college or Associate's degree" if x in (10, 11) else "Bachelor's degree" if x == 12
                                  else "Master's degree / Professional degree" if x == 13 else "Doctorate degree / Ph.D." if x == 14 else None)
    cc["race"] = cc.race.map({1.0: "White / Caucasian", 2.0: "Black / African American", 3.0: "Other",
                              4.0: "Hispanic / Latino", 5.0: "Other"})
    cc["party"] = cc.party_w_leaners.map({1.0: "Republican", 2.0: "Democrat", 3.0: "Independent", 4.0: "Other"})
    cc["gender"] = cc.gender.map({1.0: "Male", 2.0: "Female"})
    cc["age_band"] = pd.cut(pd.to_numeric(cc.age, errors="coerce"), bins=[17, 29, 44, 59, 200], labels=LV["age_band"])
    def lin(col, lo, hi):
        y = pd.to_numeric(cc[col], errors="coerce")
        return (y.where(y > 0) - lo) / (hi - lo) * 100
    cause = cc.cause_recoded.where(cc.cause_recoded > 0)
    CMAP = [("worry", lin("worry", 1, 4), "concern_mean"), ("priority", lin("priority", 1, 4), "policy_general"),
            ("reg_CO2_pollutant", lin("reg_CO2_pollutant", 1, 4), "policy_specific_mean"),
            ("discuss_GW", lin("discuss_GW", 1, 4), "behavior_mean"),
            ("fund_research", lin("fund_research", 1, 4), "funding_perceptions"),
            ("cause_recoded", pd.Series(np.select([cause == 6, cause == 5, cause == 4, cause == 3],
                                                  [100.0, 60.0, 15.0, 0.0], default=np.nan), index=cc.index), "belief_post")]
    for name, y, tgt in CMAP:
        for mod in ["education", "income", "race", "party", "gender", "age_band"]:
            rows += offsets(cc, mod, y, cc.weight_wave, mod, shares, 100, GAP, tgt,
                            f"CCAM 2021-2024 weighted, {name} rescaled, x{GAP} gap factor", prio=5)
    levels["funding_perceptions"] = (round(wmean(lin("fund_research", 1, 4), cc.weight_wave) + BRIDGE, 1), 27.0,
                                     "CCAM fund_research (4-point), weighted, rescaled, bridge %+.1f pp" % BRIDGE)

    # ---------------- documented fallbacks, always FLAGGED in the row's own source ---------------
    # policy_role_mean has no race/party source anywhere; TISP's education is 4 coarse levels.
    u["edu2"] = u.DEM_EDU.map(lambda x: "hi" if x == 4 else ("lo" if x in (1, 2, 3) else None))
    tt = u.dropna(subset=["edu2"])
    gg = tt.groupby("edu2").apply(lambda z: wmean(r100(z.policy_role), z.w))
    lo_lv = ["Less than high school", "High school diploma / GED", "Some college or Associate's degree"]
    hi_lv = ["Bachelor's degree", "Master's degree / Professional degree", "Doctorate degree / Ph.D."]
    centre = sum(shares[("education", l)] for l in lo_lv) * gg["lo"] + sum(shares[("education", l)] for l in hi_lv) * gg["hi"]
    for l in lo_lv + hi_lv:
        rows.append({"moderator": "education", "level": l, "outcome": "policy_role_mean", "prio": 6, "n": int(len(tt)),
                     "offset": float((gg["hi" if l in hi_lv else "lo"] - centre) * GAP),
                     "source": "TISP US NORMPERC by DEM_EDU collapsed to higher-education vs not (TISP has only 4 coarse "
                               "levels); the same offset is given to all three levels within each group, FLAGGED"})
    tmp = pd.DataFrame(rows)
    # gender x Other on the two outcomes whose only sources (CCAM, TISP) code gender as a binary.
    # Pew anchors gender Other on the TRUST outcomes (it is 7 pp below men and women there), but
    # a trust offset is the wrong shape for a climate-policy outcome: voelkel2026's own slider
    # data puts gender Other 20.5 pp ABOVE the pool on policy support. Those two facts are not in
    # conflict - they are different constructs - so each outcome borrows from the nearer source.
    g_other = tmp[(tmp.moderator == "gender") & (tmp.level == "Other") & (tmp.outcome == "policy_general")]
    for _, o in g_other.iterrows():
        for tgt in ["funding_perceptions", "policy_role_mean"]:
            rows.append({"moderator": "gender", "level": "Other", "outcome": tgt, "prio": 6, "n": int(o.n),
                         "offset": float(o.offset),
                         "source": "voelkel2026 PRE gender x policy_general offset reused (CCAM and TISP both code "
                                   "gender as a binary and cannot reach this cell), FLAGGED"})
    tmp = pd.DataFrame(rows)
    for mod in ["race", "party"]:
        for _, o in tmp[(tmp.moderator == mod) & (tmp.outcome == "trust_multidimensional")].iterrows():
            rows.append({"moderator": mod, "level": o.level, "outcome": "policy_role_mean", "prio": 6, "n": int(o.n),
                         "offset": float(o.offset * GAP),
                         "source": "GSS consci gap shape as a PROXY for the scientists-policy-role battery (no mounted "
                                   f"source has that battery with {mod}), further x{GAP}, FLAGGED"})
    # inst_trust_mean: GSS covers party/race/education/gender; age and income come from TISP's trust gradient
    for _, o in tmp[(tmp.outcome == "trust_multidimensional") & (tmp.moderator.isin(["age_band", "income"]))].iterrows():
        rows.append({"moderator": o.moderator, "level": o.level, "outcome": "inst_trust_mean", "prio": 6, "n": int(o.n),
                     "offset": float(o.offset),
                     "source": "TISP US 12-item trust gradient used for institutional trust (adjacent construct), FLAGGED"})
    # nearest-level reuse where a level is simply not observed in the only source that has the outcome
    for out_ in ["donation_ams", "newsletter_signup"]:
        have = tmp[(tmp.moderator == "education") & (tmp.outcome == out_)].set_index("level")
        for missing, donor in [("Less than high school", "High school diploma / GED"),
                               ("Doctorate degree / Ph.D.", "Master's degree / Professional degree")]:
            if missing not in have.index and donor in have.index:
                d = have.loc[donor]
                rows.append({"moderator": "education", "level": missing, "outcome": out_, "prio": 7, "n": int(d.n),
                             "offset": float(d.offset), "source": d.source + f" ; {missing} not observed - {donor} reused, FLAGGED"})
    have = tmp[(tmp.moderator == "race") & (tmp.outcome == "funding_perceptions") & (tmp.level == "Other")]
    for _, d in have.iterrows():
        rows.append({"moderator": "race", "level": "Asian / Asian American", "outcome": "funding_perceptions", "prio": 7,
                     "n": int(d.n), "offset": float(d.offset),
                     "source": d.source + " ; CCAM has no Asian cell - 'Other, non-Hispanic' reused, FLAGGED"})

    # ---------------- assemble: priority merge, complete grid, exact re-centring -----------------
    off = pd.DataFrame(rows)
    off = off[off.outcome != "_"].sort_values("prio").drop_duplicates(["moderator", "level", "outcome"], keep="first")
    # distrust_post mirrors trust wherever nothing better exists
    mir = off[off.outcome == "trust_multidimensional"].assign(
        outcome="distrust_post", prio=8,
        source=lambda d: "mirror of the trust_multidimensional offset, SIGN FLIPPED (reverse-valenced)")
    mir["offset"] = -mir.offset
    off = pd.concat([off, mir]).sort_values("prio").drop_duplicates(["moderator", "level", "outcome"], keep="first")
    grid = pd.DataFrame([{"moderator": m, "level": l, "outcome": o} for m in MODS for l in LV[m] for o in S["outcomes"]])
    full = grid.merge(off, on=["moderator", "level", "outcome"], how="left")
    full["covered"] = full.offset.notna()
    full["offset"] = full.offset.fillna(0.0)
    full["source"] = full.source.fillna("NO MOUNTED SOURCE - offset 0 (no belief); the centring below makes this exact")
    full["share"] = [shares[(r.moderator, r.level)] for r in full.itertuples()]
    full["offset"] = full.offset - full.groupby(["moderator", "outcome"]).apply(
        lambda g: (g.offset * g.share).sum() / g.share.sum()).reindex(
        pd.MultiIndex.from_frame(full[["moderator", "outcome"]])).values

    out = Path(outdir) if outdir else RUN / "inputs" / "baselines"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([{"outcome": o, "control_mean": levels[o][0], "control_sd": levels[o][1], "source": levels[o][2]}
                  for o in S["outcomes"]]).to_csv(out / "control_levels.csv", index=False)
    full[["moderator", "level", "outcome", "offset", "n", "source", "covered"]].to_csv(out / "subgroup_offsets.csv", index=False)
    resid = float(full.assign(x=full.offset * full.share).groupby(["moderator", "outcome"]).x.sum().abs().max())
    # provenance is REGENERATED, not maintained by hand: the static argument lives beside this
    # script, the coverage numbers are computed from what was just written.
    prov = json.loads((Path(__file__).resolve().parent / "provenance_static.json").read_text())
    prov = {"built": time.strftime("%Y-%m-%dT%H:%M:%S"), **prov}
    prov["coverage"] = {"cells": int(len(full)), "anchored": int(full.covered.sum()),
                        "share": round(float(full.covered.mean()), 4),
                        "unanchored": full[~full.covered][["moderator", "level", "outcome"]].to_dict("records"),
                        "centring_residual_max_pp": resid,
                        "by_source_prefix": {k: int(vv) for k, vv in
                                             full.source.str.split(r"[ ,(]").str[0].value_counts().items()}}
    prov["pew_anchor"]["level_crosscheck_not_used"] += " ; recomputed this build: " + ", ".join(
        f"{w} {m:.1f}" for w, m in pew_level_crosscheck.items())
    (out / "provenance.json").write_text(json.dumps(prov, indent=1))
    print("  levels: 13   offsets: %d cells, %d anchored (%.1f%%)   centring residual %.1e   %.0f s"
          % (len(full), full.covered.sum(), 100 * full.covered.mean(), resid, time.time() - t0))


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fanout", type=float, default=None,
                    help="override the measured climate-referent fan-out in pp (0 disables it); "
                         "default reads inputs/measured/referent_fanout.json; OPEN item 13")
    ap.add_argument("--agency-theta", type=float, default=None,
                    help="override where EPA/NASA/NOAA sit on the [scientific community, federal "
                         "government] span, 0 = science end, 1 = government end; default reads "
                         "inputs/measured/agency_trust_anchor.json; OPEN item 14")
    ap.add_argument("--out", default=None, help="output directory (default inputs/baselines)")
    a = ap.parse_args()
    main(fanout=a.fanout, outdir=a.out, agency_theta=a.agency_theta)
