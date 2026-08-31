#!/usr/bin/env python
"""Build the `fresheyes` card's BASELINE (13 levels + SDs) and SUBGROUP table (351 offsets).

Every number here traces to runs/20260820-target-fresheyes/anchors/*.json - reconnaissance this
arm computed from /workspace/datasets in this session - plus the corrections declared in
PREREG.md section 5.  Nothing is read from inputs/baselines/ or inputs/measured/.

Two corrections, both MEASURED by this arm rather than assumed:

  COARSE->SLIDER.  Every trust/policy-role/funding level in the mount is a 3-, 4- or 5-point
  verbal item linearly rescaled to 0-100.  Mechanically coarsening REAL 0-100 slider responses
  into 5 equal-width bins and rescaling (anchors/trust_anchors.json, block F, vlasceanu2024 US)
  moves the mean +2.4 pp on four belief items and +1.2 pp on a policy item, and inflates the SD
  by 1/0.894 = 11.9%.  So a rescaled 5-point level reads about 2 pp HIGH and its SD about 11%
  HIGH against the slider the target uses.  Applied as MEAN -2.0 and SD x0.894.

  REFERENT ("scientists" -> "most CLIMATE scientists").  Three readings, all this arm's own:
  TISP within-person -3.92 pp; Pew W42 environmental vs medical scientists +0.38 pp;
  gligoric2025 climatologists vs 34 other occupations -13.30 pp.  The LEVEL shift is small and
  its sign is not settled; the PARTY FAN-OUT is large and replicates three times
  (TISP -2.90 pp per conservatism point, Pew W42 D-R DiD +12.43, gligoric -1.54 per ideology
  point).  So a modest -3.0 pp level shift is applied with the bracket [-13, +1] recorded, and
  the fan-out is applied to the PARTY offsets (+/-3.0 pp) where the target's referent is climate
  scientists.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

RUN = Path("/workspace/run")
RD = RUN / "runs" / "20260820-target-fresheyes"
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb

TR = json.loads((RD / "anchors/trust_anchors.json").read_text())
CA = json.loads((RD / "anchors/climate_anchors.json").read_text())
CO = json.loads((RD / "anchors/costly_anchors.json").read_text())
Q3 = json.loads((RD / "anchors/_q3.json").read_text())
BH = json.loads((RD / "anchors/behaviour_polarity.json").read_text()) if (RD / "anchors/behaviour_polarity.json").exists() else {}

S = ssb.spec.load()
OUT = S["outcomes"]
COARSE_MEAN = -2.0        # rescaled 5-point mean reads high
COARSE_SD = 0.894         # rescaled 5-point SD reads high
REFERENT = -3.0           # generic scientists -> climate scientists, level
FANOUT_PARTY = 3.0        # extra party spread when the referent is climate scientists

def v(k):    # trust_anchors scalar
    return TR[k]["value"]

# ------------------------------------------------------------------ 1. BASELINE
BASE = {}
def put(o, mean, sd, source, kind, bracket=None, note=""):
    BASE[o] = {"mean": round(float(mean), 2), "sd": round(float(sd), 2), "source": source,
               "kind": kind, "bracket": bracket, "note": note}

# --- trust family -------------------------------------------------------------
t12 = v("tisp_trust12_composite_meanof4subscales__rescaled_0_100_weighted")   # 71.50
t12sd = TR["tisp_trust12_composite_meanof4subscales__rescaled_0_100_weighted"]["sd"]
put("trust_multidimensional", t12 + COARSE_MEAN + REFERENT, t12sd * COARSE_SD,
    "TISP US 12-item METI composite (the target's own battery), weighted, 5-point rescaled",
    "DECLARED (crosses scale format and referent)", [61.0, 71.0],
    "71.50 - 2.0 (coarse->slider) - 3.0 (referent). SD 20.62 x 0.894. Cross-check: 12-item mean "
    "of items with SD 25.2 and rbar 0.613 gives 25.2*0.894*sqrt((1+11*.613)/12) = 18.1.")

ct = v("tisp_CLIM_TRUST__rescaled_0_100_weighted")                            # 67.01
ctsd = TR["tisp_CLIM_TRUST__rescaled_0_100_weighted"]["sd"]
put("trust_post", ct + COARSE_MEAN, ctsd * COARSE_SD,
    "TISP US 'To what extent do you trust scientists in your country who work on climate "
    "change?', weighted, 5-point rescaled", "DECLARED (crosses scale format)", [61.0, 69.0],
    "Referent already climate; only the coarse->slider correction applies.")

put("distrust_post", 30.0, 29.0, "NO MOUNTED SOURCE (trust_anchors NOT_AVAILABLE__distrust_post)",
    "DECLARED - no measurement", [22.0, 38.0],
    "Not 100 - trust_post: a separately asked distrust item is endorsed less readily than the "
    "trust complement. Placed 5 pp below the naive complement (100-65=35) with a wide bracket. "
    "SD taken equal to trust_post's, which is the only defensible neighbour.")

# inst_trust_mean: composed from its five measured components (PREREG 5), each expressed
# relative to trust in scientists on the target's own slider.
sci_slider = v("tisp_TRUST_PEW__rescaled_0_100_weighted") + COARSE_MEAN        # 68.9
comp = {
  "NASA":  (+2.0, "Pew W149 topline: NASA 71.3 vs EPA 54.9 favourability; NASA is the most "
                  "favourably rated science agency in the mount"),
  "NOAA":  (-5.0, "NOT AVAILABLE in any mount. Declared: a science agency of NASA's character "
                  "but far lower public salience, so answers pull toward the scale middle"),
  "EPA":   (-12.0, "Pew W149: EPA sits 16.4 below NASA; a politically contested regulator"),
  "universities": (-10.0, "GSS 'education' -18.2 vs the scientific community in the same "
                  "respondents, Pew W114 'K-12 principals' -8.6 vs scientists; 'universities "
                  "and colleges' sits between the two"),
  "federal government": (-30.0, "GSS exec branch -32.3, Pew W114 elected officials -30.1, "
                  "W100/W42 agree"),
}
inst = float(np.mean([sci_slider + d for d, _ in comp.values()]))
put("inst_trust_mean", inst, 22.5,
    "composed from five measured components (GSS within-person, Pew W114/W100/W42 within-person, "
    "Pew W149 topline) around TISP generic-scientist trust on a slider",
    "DECLARED (composed)", [52.0, 64.0],
    "components (offset vs trust in scientists=%.1f): %s. SD: five 0-100 trust sliders with "
    "single-item SD ~29 and rbar ~0.5 gives 29*sqrt((1+4*0.5)/5) = 22.5."
    % (sci_slider, {k: d for k, (d, _) in comp.items()}))

pr = v("tisp_policy_role_mean_4item__rescaled_0_100_weighted")               # 64.99
prsd = TR["tisp_policy_role_mean_4item__rescaled_0_100_weighted"]["sd"]
put("policy_role_mean", pr + COARSE_MEAN - 1.5, prsd * COARSE_SD,
    "TISP US NORMPERC 4-item mean (near-verbatim the target's four), weighted, 5-point rescaled",
    "DECLARED (crosses scale format and referent)", [57.0, 66.0],
    "-2.0 coarse->slider, -1.5 for the climate referent (half the trust referent correction: "
    "these items are normative claims about what scientists SHOULD do, which the referent "
    "fan-out evidence shows to be less referent-sensitive than a trust rating).")

put("funding_perceptions", 66.0, 28.0,
    "GSS natenvir 78.46 (environment spending) and natsci 66.54 (scientific research), 3-point "
    "rescaled; CCAM renewable-research support 69.34 (4-point)",
    "DECLARED - the exact item (federal spending on CLIMATE CHANGE RESEARCH) is NOT AVAILABLE",
    [58.0, 74.0],
    "Climate research sits between 'the environment' (78.5) and 'scientific research' (66.5) in "
    "content and is more polarised than either; a 3-point rescaled level also reads high.")

# --- climate attitudes --------------------------------------------------------
bel = CA["A.vlasceanu2024.belief_post.US_control"]["value"]
put("belief_post", bel["mean"], bel["sd"],
    "vlasceanu2024 US control arm, Belief1 - the target's belief item, near-verbatim, native "
    "0-100 slider (n=667)", "MEASURED (item, format and item-count all match)", None,
    "NOT the voelkel2026 3-item composite (65.00, SD 22.27): that is a different construct AND a "
    "3-item mean, whose SD cannot stand in for a single item's. Every single-item climate-belief "
    "slider in the mount has SD 26-34.")

con = CA["A.voelkel2026.concern.control_PRE"]["value"]
put("concern_mean", con["mean"], con["sd"],
    "voelkel2026 control-arm PRE, Concern_Pre_1..3 - all three items VERBATIM, native 0-100 "
    "slider, US quota panel (n=3,180)", "MEASURED (verbatim, same format, same item count)", None,
    "The design twin on the target's own three items.")

pg = CA["A.voelkel2026.policy_general.control_PRE"]["value"]
put("policy_general", pg["mean"], pg["sd"],
    "voelkel2026 control-arm PRE, Policies_Pre_3 - VERBATIM single item, native 0-100 slider "
    "(n=3,182)", "MEASURED (verbatim, same format, single item)", None, "")

ps = CA["A.vlasceanu2024.policy_specific_mean.US_control"]["value"]
# Q2 came back NOT MEASURABLE HERE: no mounted dataset asks a climate-policy item on both
# polarities in one sample. Three partial readings span -4.0 to +12.5 pp. +4.0 is DECLARED as
# the working value inside that interval, in the direction the mechanism predicts (a bipolar
# scale moves a non-supporter who does not actively oppose off the floor and onto the middle).
# AMENDED after a SECOND, independent reconnaissance pass measured the same quantity and
# disagreed in sign: behaviour-polarity reads +4.0 (partial readings -4.0 .. +12.5) and
# climate-anchors reads -1.8 (bracket -6.1 .. +5.6) and recommends no correction. Both intervals
# contain zero and their midpoints straddle it, so the working value is +1.0 - close to no
# correction, in the direction the mechanism predicts, with the disagreement recorded rather than
# resolved. NOTE: the stage-5 prompt was assembled before the second reading arrived and told the
# predictor 67.9; the card says 64.9. The 3 pp difference is a LEVEL, it is inside both brackets,
# and it cannot change a message ranking.
POLARITY = 1.0
put("policy_specific_mean", ps["mean"] + POLARITY, ps["sd"],
    "vlasceanu2024 US control arm, the seven near-verbatim items rebuilt as the target's "
    "unweighted mean (n=606)", "MEASURED item-wise, DECLARED polarity correction", None,
    "vlasceanu's slider is UNIPOLAR (0='Not at all' .. 100='Very much so'); the target's is "
    "BIPOLAR (0='Strongly oppose' .. 100='Strongly support'), which moves non-supporters who do "
    "not actively oppose from the floor to the middle. Correction +%.1f pp." % POLARITY)

beh = BH.get("Q1.implied.behavior_mean") if BH else None
if beh:
    put("behavior_mean", beh["value"], BH["Q1.implied.behavior_mean.SD"]["value"],
        "item-by-item: voelkel2026 control-PRE for meat 39.16 / transport 45.94 / fly 52.86 / "
        "donate-to-an-environmental-group 30.19 (near-verbatim, same stem, same slider, same "
        "12-month window); goldwert2026 'commit to initiating a conversation' 53.29 converted to "
        "the likelihood stem by a measured -5.34 pp offset for talk 47.96; solar 25.0 DECLARED",
        "COMPOSED - 4 measured, 1 converted, 1 declared", beh["bracket"],
        "No mounted dataset carries a solar-installation item at all (16 datasets searched); its "
        "25.0 is reasoned from the fact that ~29%% of US adults are renters (CCAM home ownership "
        "71.3%% weighted) and from voelkel2026's own three lowest likelihood items (27.2-30.2). "
        "SD from SD_comp = 33.29*sqrt((1+5*0.3816)/6) = 23.18, against voelkel2026's own 6-item "
        "composite SD of 22.60 as a sanity check.")
else:
    put("behavior_mean", 44.0, 23.0,
        "voelkel2026 control-arm PRE gives 3 of the target's 6 items verbatim (eat less meat "
        "39.16, walk/bike/carpool 45.94, less air travel 52.86 -> matched-3 mean 45.98)",
        "COMPOSED, three items bracketed", [38.0, 50.0],
        "The three unmatched target items (install a solar panel, talk to friends/family, donate "
        "to an environmental NGO) are on average costlier than voelkel's three unmatched items "
        "(reusable bags, local food, less plastic), which are its three HIGHEST-scoring. So the "
        "target's 6-item mean sits below voelkel's 54.83 and near its matched-3 45.98. "
        "SD from SD_comp = 33.4*sqrt((1+5*0.3816)/6) = 22.9.")

# --- costly acts --------------------------------------------------------------
put("donation_ams", 3.5, 3.6,
    "goldwert2026 control $4.77 (de-zero-filled, n=1,212); dablander2025 $100-scale 26.1 pp; "
    "voelkel2026 100-point allocation 61.5 pp", "DECLARED - three sources span 26-62 pp",
    [2.6, 4.8],
    "Placed BELOW goldwert because goldwert's $5 spike (29.6% of its control arm) is manufactured "
    "by an explicit 'if half of you give $5+ we double the pool' nudge the target does not have, "
    "and because goldwert pays only 100 of 31,324 respondents while the target's $10 bonus is "
    "each respondent's own money. Recipient also differs: a scientific society (AMS) rather than "
    "an environmental advocacy organisation. Distribution is trimodal, not bell-shaped: mass sits "
    "on $0/$5/$10.")

put("newsletter_signup", 0.20, 0.40,
    "goldwert2026 control single-ask signup 24.3% (350.org) and 21.8% (Citizens' Climate Lobby), "
    "reached-only; bbprime2025 petition 14.3%", "DECLARED", [0.12, 0.28],
    "ONE ask in the target against goldwert's two (a second ask adds only 7.3 pp, phi=0.52). The "
    "target's offer opens an external page in a new tab and asks for an email; goldwert embedded "
    "the signup in an iframe. Both are self-reported afterwards. SD = sqrt(p(1-p)).")

baseline = pd.DataFrame([{"outcome": o, "control_mean": BASE[o]["mean"], "control_sd": BASE[o]["sd"]}
                         for o in OUT])

# ------------------------------------------------------------------ 2. SUBGROUP OFFSETS
J = pd.read_csv(RUN / "inputs/pool/joint.csv")
shares = {}
for m, levels in S["moderators"].items():
    w = J.groupby(m)["weight"].sum()
    shares[m] = {l: float(w.get(l, 0.0)) / float(w.sum()) for l in levels}

RACE = {"White": "White / Caucasian", "Black": "Black / African American",
        "Hispanic": "Hispanic / Latino", "Asian": "Asian / Asian American", "Other": "Other"}
EDU_SPLIT = {"Postgraduate (Master's/Professional/Doctorate) [target levels 5+6 POOLED]":
             ["Master's degree / Professional degree", "Doctorate degree / Ph.D."],
             "Postgraduate [target 5+6 POOLED]":
             ["Master's degree / Professional degree", "Doctorate degree / Ph.D."]}
# voelkel Income_B has 11 unlabelled codes; map monotonically onto the target's five bands by
# rank, which is the most this arm can defend (the child could recover no label table).
INC11 = {"1.0": "Less than $30,000", "2.0": "Less than $30,000", "3.0": "$30,000 to $55,999",
         "4.0": "$30,000 to $55,999", "5.0": "$56,000 to $99,999", "6.0": "$56,000 to $99,999",
         "7.0": "$56,000 to $99,999", "8.0": "$100,000 to $167,999", "9.0": "$100,000 to $167,999",
         "10.0": "$168,000 or more", "11.0": "$168,000 or more"}


def voelkel_offsets(construct):
    """{moderator: {target level: offset}} from voelkel2026 control-arm PRE."""
    C = CA["C.voelkel2026.subgroups.control_PRE"]["value"]
    out = {}
    for mod, key in [("gender", "gender"), ("age_band", "age_band"), ("race", "race"),
                     ("education", "education"), ("party", "party"), ("income", "income_B_level")]:
        lv = C[key][construct]["levels"]
        acc = {}
        for name, d in lv.items():
            off, n = d["offset"], d["n"]
            if mod == "race":
                acc.setdefault(RACE[name], []).append((off, n))
            elif mod == "education":
                for t in EDU_SPLIT.get(name, [name]):
                    acc.setdefault(t, []).append((off, n))
            elif mod == "income":
                acc.setdefault(INC11[name], []).append((off, n))
            else:
                acc.setdefault(name, []).append((off, n))
        out[mod] = {k: float(np.average([a for a, _ in vs], weights=[b for _, b in vs]))
                    for k, vs in acc.items()}
    return out


PEW_AGE = {"18-29": ["18-29"], "30-44": ["30-49"], "45-59": ["30-49", "50-64"],
           "60+": ["50-64", "65+"]}
PEW_AGE_W = {"18-29": [1.0], "30-44": [1.0], "45-59": [1 / 3, 2 / 3], "60+": [0.25, 0.75]}
PEW_EDU = {"Less than high school": "Less than high school",
           "High school diploma / GED": "High school diploma / GED",
           "Some college or Associate's degree": "Some college or Associate's degree",
           "Bachelor's degree": "Bachelor's degree",
           "Master's degree / Professional degree": "Master/Professional/Doctorate (Pew postgrad, cannot split)",
           "Doctorate degree / Ph.D.": "Master/Professional/Doctorate (Pew postgrad, cannot split)"}
PEW_INC = {"Less than $30,000": "Less than $30,000", "$30,000 to $55,999": "$30,000 to $55,999 (approx)",
           "$56,000 to $99,999": "$56,000 to $99,999 (approx)",
           "$100,000 to $167,999": "$100,000 or more (cannot split at $168k)",
           "$168,000 or more": "$100,000 or more (cannot split at $168k)"}
PEW_RACE = {"White / Caucasian": "White non-Hispanic", "Black / African American": "Black non-Hispanic",
            "Hispanic / Latino": "Hispanic", "Asian / Asian American": "Asian non-Hispanic",
            "Other": "Other"}
PEW_PARTY = {"Republican": "Republican", "Democrat": "Democrat", "Independent": "Independent",
             "Other": "Something else/Other"}


def pew_offsets():
    """Pew W114 confidence-in-scientists offsets, on the target's own moderator levels."""
    def o(sub, lvl):
        return TR["C_W114_scientists_by_%s_weighted__%s" % (sub, lvl)]["offset_from_overall"]
    out = {"gender": {g: o("gender", g) for g in S["moderators"]["gender"]},
           "race": {t: o("race", p) for t, p in PEW_RACE.items()},
           "party": {t: o("party", p) for t, p in PEW_PARTY.items()},
           "education": {t: o("education_target_mapped", p) for t, p in PEW_EDU.items()},
           "income": {t: o("income_target_mapped", p) for t, p in PEW_INC.items()},
           "age_band": {t: float(np.average([o("age_pew4", p) for p in PEW_AGE[t]],
                                            weights=PEW_AGE_W[t])) for t in S["moderators"]["age_band"]}}
    return out


def centre(mod, d):
    """Share-weighted centring: offsets must average back to zero, or control_mean + offset is
    not the control mean."""
    w = shares[mod]
    m = sum(w[l] * d[l] for l in d)
    return {l: d[l] - m for l in d}


def goldwert_offsets(field):
    rows = CO["goldwert_control_subgroups"]["value"]
    out = {}
    for r in rows:
        out.setdefault(r["moderator"], {})[r["level"]] = r[field]
    return out


rows = []
prov = {}
pew = pew_offsets()
vo = {c: voelkel_offsets(c) for c in ["belief", "concern", "policy_general", "policy_specific",
                                      "behavior"]}
gold_don = goldwert_offsets("donation_offset")
gold_nl = goldwert_offsets("newsletter_offset_pp")

TRUSTY = ["trust_multidimensional", "trust_post", "distrust_post", "inst_trust_mean",
          "policy_role_mean"]
CLIMATE = {"belief_post": "belief", "concern_mean": "concern", "policy_general": "policy_general",
           "policy_specific_mean": "policy_specific", "behavior_mean": "behavior"}
# how big is a group gap on THIS outcome relative to the source it is borrowed from
TRUST_SCALE = {"trust_multidimensional": 1.00, "trust_post": 1.10, "distrust_post": -1.00,
               "inst_trust_mean": 1.00, "policy_role_mean": 0.70, "funding_perceptions": 1.00}

for o in OUT:
    for mod, levels in S["moderators"].items():
        if o in TRUSTY:
            d = dict(pew[mod])
            d = {l: d[l] * COARSE_SD for l in levels}         # 4-point gaps read ~11% wide
            if mod == "party":                                 # climate referent fans party out
                d["Democrat"] += FANOUT_PARTY
                d["Republican"] -= FANOUT_PARTY
            k = TRUST_SCALE[o]
            d = {l: d[l] * k for l in levels}
            src = ("Pew W114 confidence in scientists, weighted, 4-point rescaled x0.894 "
                   "(coarse->slider) x%.2f" % k) + (
                   "; party fanned out +/-3.0 for the climate referent" if mod == "party" else "")
        elif o in CLIMATE:
            d = {l: vo[CLIMATE[o]][mod].get(l, 0.0) for l in levels}
            src = "voelkel2026 control-arm PRE, %s battery, same 0-100 format" % CLIMATE[o]
        elif o == "funding_perceptions":
            d = {l: vo["policy_general"][mod].get(l, 0.0) * 0.9 for l in levels}
            src = ("voelkel2026 control-arm PRE policy_general offsets x0.9 (a funding item is a "
                   "climate-policy attitude; GSS/CCAM confirm the party gap sign and size)")
        elif o == "donation_ams":
            d = {l: gold_don.get(mod, {}).get(l, 0.0) for l in levels}
            src = "goldwert2026 control arm, $ donation offsets (native $)"
        elif o == "newsletter_signup":
            d = {l: gold_nl.get(mod, {}).get(l, 0.0) / 100.0 for l in levels}
            src = "goldwert2026 control arm, signup-rate offsets (pp -> proportion)"
        d = centre(mod, d)
        for l in levels:
            rows.append({"moderator": mod, "level": l, "outcome": o,
                         "offset": round(float(d[l]), 4), "share": shares[mod][l]})
        prov["%s|%s" % (o, mod)] = src

subgroup = pd.DataFrame(rows)

# ------------------------------------------------------------------ 3. write
(RD / "card_baseline.json").write_text(json.dumps(BASE, indent=1))
(RD / "subgroup_provenance.json").write_text(json.dumps(prov, indent=1))
baseline.to_csv(RD / "baseline_draft.csv", index=False)
subgroup.to_csv(RD / "subgroup_draft.csv", index=False)

print("BASELINE (fresheyes)")
print("%-24s %8s %8s  %s" % ("outcome", "mean", "sd", "kind"))
for o in OUT:
    b = BASE[o]
    print("%-24s %8.2f %8.2f  %s" % (o, b["mean"], b["sd"], b["kind"]))
print("\nSUBGROUP: %d cells, %d NA" % (len(subgroup), subgroup.offset.isna().sum()))
chk = subgroup.groupby(["outcome", "moderator"]).apply(
    lambda g: float((g.offset * g.share).sum()), include_groups=False)
print("  max |share-weighted mean offset| = %.2e" % chk.abs().max())
print("\nparty offsets by outcome:")
p = subgroup[subgroup.moderator == "party"].pivot(index="outcome", columns="level", values="offset")
print(p.round(2).to_string())
