#!/usr/bin/env python
"""Rebuild the dablander2025 practice-task input (task 12) - a registered-report null on
scientist credibility, with a real 0-100 donation slider.

    /opt/kernel/venv/bin/python tools/build_dablander.py            # build + every check
    /opt/kernel/venv/bin/python tools/build_dablander.py --power    # the gate, no writes

Dablander, Sachisthal & Aron 2025, Royal Society Open Science 12:241001 (Registered Report),
OSF ktjh6. 3,359 US Prolific respondents (age/sex representative, October 2024) read one of six
fictional news articles: a 2 x 3 between-subjects design of protest form
{legal march, civil disobedience} x scientist involvement {none, endorses, joins}. The vignettes
are verbatim from the paper's electronic supplementary material (CC BY 4.0), pp. 7-9.

WHY THIS TASK.
  * It adds **5 message arms** to a pool in which every interval is clustered on the arm
    (finding 60c: the bootstrap half-width falls as n^-0.506 in ARMS, not in draws or respondents).
  * `ScienceCredibility` is a **trust-family** outcome - credibility of environmental scientists in
    general - and the authors' pre-registered prediction for it was a NULL (H9), which the data
    bore out. The harness has four trust tasks whose human median |ATE| runs 0.42 / 2.16 / 4.33 /
    1.14 pp; this is a fifth reading, from a study designed to find nothing there.
  * `Donation_1` is a real 0-100 allocation of a $100 bonus (10 participants were drawn and paid) -
    the second costly-act outcome on the board after goldwert2026, and the target carries one.

WHAT IS WRONG WITH IT, stated before the carve.
  * There is **no pure control arm.** The reference is `Legal march - no scientist`, the least
    intense cell, so every "ATE" here is a contrast against a protest article and not against
    nothing. The 2 x 3 structure means the five contrasts are not five independent messages.
  * The **attention check is differential**: 274 of the 3,149 who finished failed it and 85% of
    those are in the civil-disobedience arms. The authors' pipeline (which this build reproduces
    exactly, to their published n) therefore analyses arms of unequal size, and the CD arms are
    the ones that lost people. Carrying the exclusion is right - it is the published estimand -
    and it is a selection risk that is declared, not solved.
  * The item **stems** are not in the deposit (only the response labels and the authors' own
    one-line descriptions in the code and the design table). The brief carries those descriptions,
    marked as such. This is a milder version of kim2024's problem and it is in the same place.
  * `SourceCredibility` (trust in Dr. Fraser himself) exists only in the four scientist arms, so it
    has no value in the reference arm and cannot be an outcome of this carve. Recorded, not used.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(RUN / "tools"))
import ssb  # noqa: E402
from task_power import power  # noqa: E402

SRC = Path("/workspace/datasets/dablander2025/downloads/data")
TITLE = {"V_LegalXNone": "Legal march - no scientist",
         "V_LegalXEndorse": "Legal march - scientist endorses",
         "V_LegalXJoin": "Legal march - scientist joins",
         "V_CDXNone": "Civil disobedience - no scientist",
         "V_CDXEndorse": "Civil disobedience - scientist endorses",
         "V_CDXJoin": "Civil disobedience - scientist joins"}
CONTROL = "Legal march - no scientist"
EXPECT_AFTER_AC, EXPECT_ANALYSED = 2875, 2856

OUTCOMES = {
    "policy_support": ("PolicySupport", 1, 5, True,
        "Agreement with a statement that offshore oil and gas drilling should be EXPANDED, "
        "5-point 'Strongly disagree' - 'Strongly agree'. Scored REVERSED here, so HIGHER = MORE "
        "SUPPORT FOR CLIMATE POLICY. (The authors' own label for this outcome is 'policy "
        "support'; the verbatim item stem is not in the public deposit.)"),
    "activist_support": ("ActivistSupport", 1, 5, False,
        "Support for the climate activists described in the article, 5-point 'Not at all' - "
        "'A great deal'. HIGHER = MORE SUPPORT."),
    "science_credibility": ("ScienceCredibility", 1, 5, False,
        "Credibility of environmental scientists IN GENERAL, 5-point 'Not at all' - 'A great "
        "deal'. HIGHER = MORE CREDIBLE. This is the study's trust outcome."),
    "perceived_radicalness": ("Radical", 1, 5, False,
        "How radical the activists' actions were perceived to be, 5-point 'Not at all radical' - "
        "'Extremely radical'. HIGHER = MORE RADICAL."),
    "donation": ("Donation_1", 0, 100, False,
        "Allocation of a potential $100 bonus to one of eight climate NGOs, 0-100 slider in "
        "dollars. Ten participants were drawn at random and their allocation was actually paid, "
        "so this is a costly act and not a hypothetical. HIGHER = MORE DONATED."),
}
NOT_AN_OUTCOME = {"SourceCredibility":
                  "credibility of Dr. Fraser himself - asked only in the four scientist arms, so "
                  "it has no value in the reference arm and no ATE is defined"}

MODERATORS = {
    "party_lean": ("PoliticalAffiliation", {1: "Democrat", 2: "Democrat", 3: "Independent",
                                            4: "Republican", 5: "Republican"}),
    "gender": ("Gender", {1: "Male", 2: "Female", 3: "Other", 4: "Other", 5: "Other"}),
}
AGE_BAND = {1: "18-29", 2: "30-44", 3: "30-44", 4: "45-59", 5: "60+", 6: "60+", 7: "60+"}

# ---- the six vignettes, verbatim from rsos241001_si_001.pdf pp. 7-9 (CC BY 4.0) --------------
LEGAL_BASE = ("Climate Protesters March on New York, Calling for End to Fossil Fuels\n\n"
 "New York, NY. Ahead of U.N. meetings this week, thousands gathered in Midtown to demand that "
 "the US government and other governments stop new oil and gas drilling. The climate activists "
 "marched peacefully through the streets of Manhattan. The protest was facilitated by the police "
 "without any incidents.\n\n"
 "Scientists say the world needs to limit warming to 1.5 degrees Celsius (2.7 degrees Fahrenheit) "
 "above pre-industrial levels to avoid the most catastrophic impacts of climate change. To meet "
 "that goal, the International Energy Agency (IEA) says that no new oil and gas fields can be "
 "explored.")
CD_BASE = ("Climate Activists Block Federal Reserve Bank, Calling for End to Fossil Fuels\n\n"
 "New York, NY. Ahead of U.N. meetings this week, hundreds gathered in Midtown to demand that the "
 "US government and other governments stop new oil and gas drilling. The climate activists marched "
 "to the Federal Reserve bank and blockaded several entrances using their bodies. More than one "
 "hundred activists were arrested.\n\n"
 "Scientists say the world needs to limit warming to 1.5 degrees Celsius (2.7 degrees Fahrenheit) "
 "above pre-industrial levels to avoid the most catastrophic impacts of climate change. To meet "
 "that goal, the International Energy Agency (IEA) says that no new oil and gas fields can be "
 "explored.")
QUOTE = ("\u201cThe government is not responding appropriately to the science. It is irresponsible "
 "to be approving new oil and gas infrastructure during a climate crisis. They urgently need to "
 "stop.\u201d")
JOIN_LEGAL = ("\n\nDr. Alex Fraser, Environmental scientist at Rochester University, was one of the "
 "people marching during the protest, saying " + QUOTE + "\n\nDr. Fraser added: \u201cScientists "
 "are not used to joining activists, but we have had enough with being ignored for so long. This "
 "is why I marched alongside them today.\u201d")
JOIN_CD = ("\n\nDr. Alex Fraser, Environmental scientist at Rochester University, was one of the "
 "people getting arrested during the protest, saying " + QUOTE + "\n\nDr. Fraser added: "
 "\u201cScientists are not used to joining activists, but we have had enough with being ignored "
 "for so long. This is why I joined the blockade and was arrested alongside them today.\u201d")
ENDORSE = ("\n\nDr. Alex Fraser, Environmental scientist at Rochester University, endorsed the "
 "action, saying " + QUOTE + "\n\nDr. Fraser added: \u201cScientists are not used to endorsing "
 "activists, but we have had enough with being ignored for so long. This is why I am speaking out "
 "today.\u201d")
TEXTS = {"Legal march - no scientist": LEGAL_BASE,
         "Legal march - scientist endorses": LEGAL_BASE + ENDORSE,
         "Legal march - scientist joins": LEGAL_BASE + JOIN_LEGAL,
         "Civil disobedience - no scientist": CD_BASE,
         "Civil disobedience - scientist endorses": CD_BASE + ENDORSE,
         "Civil disobedience - scientist joins": CD_BASE + JOIN_CD}


# ------------------------------------------------------------------------------------ build
def build():
    d = pd.read_csv(SRC / "dat_num_all.csv")
    raw_arms = d.condition.value_counts().to_dict()
    d = d[d.Progress == 100].copy()
    n_finished = len(d)
    d["legal"] = d.condition.str.contains("Legal")
    # the authors' attention check: the CORRECT answer depends on the arm (analysis.Rmd 112-115).
    # Reading AC_Protest == 1 as "correct" for everyone keeps 1,755 of 3,149 and destroys the CD
    # arms (56-103 per arm); it is the single easiest way to get this dataset wrong.
    d = d[((~d.legal) & (d.AC_Protest == 2)) | (d.legal & (d.AC_Protest == 1))]
    n_after_ac = len(d)
    oa = pd.read_csv(SRC / "openAnswers_coded.csv")
    usable = set(oa.loc[oa.Usable == 1, "ResponseId"])
    check = oa.loc[(oa.Usable == 1) & (oa.Check == 1), "ResponseId"].tolist()
    remove = set(check[:3] + check[4:5] + check[6:])       # analysis.Rmd: df_check[-c(4, 6)]
    d = d[d.ResponseId.isin(usable) & ~d.ResponseId.isin(remove)]
    n_analysed = len(d)

    out = pd.DataFrame({"arm": d.condition.map(TITLE)})
    for name, (col, lo, hi, rev, _q) in OUTCOMES.items():
        out[name] = pd.to_numeric(d[col], errors="coerce").to_numpy()
    out["source_credibility"] = pd.to_numeric(d["SourceCredibility"], errors="coerce").to_numpy()
    for m, (col, mp) in MODERATORS.items():
        out[m] = pd.to_numeric(d[col], errors="coerce").map(mp).to_numpy()
    out["age_band"] = pd.to_numeric(d["Age"], errors="coerce").map(AGE_BAND).to_numpy()
    out = out.reset_index(drop=True)

    checks = {
        "randomised_arm_counts": raw_arms,
        "n_finished_progress100": int(n_finished),
        "n_after_attention_check": int(n_after_ac),
        "n_analysed": int(n_analysed),
        "published_after_ac": EXPECT_AFTER_AC, "published_analysed": EXPECT_ANALYSED,
        "arm_counts_analysed": out.arm.value_counts().to_dict(),
        "total_exclusion_loss_by_form": {
            "legal": int(sum(v for k, v in raw_arms.items() if "Legal" in k)
                         - sum(v for k, v in out.arm.value_counts().items() if "Legal" in k)),
            "civil_disobedience": int(sum(v for k, v in raw_arms.items() if "CD" in k)
                                      - sum(v for k, v in out.arm.value_counts().items()
                                            if "Civil" in k))},
        "source_credibility_in_reference_arm":
            int(out.loc[out.arm == CONTROL, "source_credibility"].notna().sum()),
        "n_nonmissing": {k: int(out[k].notna().sum()) for k in OUTCOMES},
        "vignette_chars": {k: len(v) for k, v in TEXTS.items()},
    }
    fail = []
    if n_after_ac != EXPECT_AFTER_AC:
        fail.append("after the attention check: %d rows, the paper says %d"
                    % (n_after_ac, EXPECT_AFTER_AC))
    if n_analysed != EXPECT_ANALYSED:
        fail.append("analysed: %d rows, the paper says %d" % (n_analysed, EXPECT_ANALYSED))
    if checks["source_credibility_in_reference_arm"] != 0:
        fail.append("SourceCredibility is present in the reference arm; it should not be")
    if set(out.arm) != set(TITLE.values()):
        fail.append("arm titles do not match the six conditions")
    if fail:
        raise SystemExit("DABLANDER BUILD REFUSED:\n  - " + "\n  - ".join(fail))
    return out, checks


def adapter() -> dict:
    return {
        "dataset": "dablander2025",
        "status": "VERIFIED by tools/build_dablander.py (rebuild to the published n + red paths)",
        "file": str(RUN / "inputs" / "derived" / "dablander2025.csv"),
        "reader": "csv",
        "sample_description":
            "2,856 U.S. adults recruited on Prolific in October 2024, quota-representative on age "
            "and sex, who finished the survey, correctly identified which kind of protest they had "
            "read about, and gave a coherent free-text description of the article. Each read ONE "
            "fictional news article about a climate protest in New York and then answered the "
            "items below. There is no no-article control: the reference arm below is the least "
            "intense article (a peaceful legal march with no scientist in it). Arms are unequal in "
            "size (398-524) because the attention check removed 85% of its failures from the "
            "civil-disobedience arms. Item stems are given as the authors describe them; the "
            "verbatim stems are not in the public deposit.",
        "condition_col": "arm",
        "arms": {v: v for v in TITLE.values()},
        "control_arms": [CONTROL],
        "outcomes": {n: {"col": n, "lo": lo, "hi": hi,
                         **({"reverse": True} if rev else {}), "question": q}
                     for n, (c, lo, hi, rev, q) in OUTCOMES.items()},
        "moderators": {
            "party_lean": {"col": "party_lean",
                           "map": {k: k for k in ["Democrat", "Independent", "Republican"]}},
            "gender": {"col": "gender", "map": {k: k for k in ["Male", "Female", "Other"]}},
            "age_band": {"col": "age_band",
                         "map": {k: k for k in ["18-29", "30-44", "45-59", "60+"]}},
        },
        "moderators_unavailable": {"race": "collected by Prolific but not in the survey export",
                                   "education": "collected, 7 categories, not carried here",
                                   "income": "collected, 13 categories, not carried here"},
        "filters": [],
        "weight_col": None,
        "message_texts_file": str(RUN / "inputs" / "texts" / "dablander2025_arms.json"),
        "exclude_from_slope":
            "there is no true control arm - every contrast is against another protest article, so "
            "an 'ATE' here is a difference between two treatments and its magnitude is not the "
            "quantity the pooled slope is fitted on; and the outcomes are 5-point items plus one "
            "dollar allocation, not the target's sliders (finding 69).",
        "provenance": {
            "verified_by": "tools/build_dablander.py, which reproduces the paper's own n at both "
                           "exclusion steps (2,875 then 2,856); vignettes verbatim from "
                           "rsos241001_si_001.pdf pp. 7-9 (CC BY 4.0)",
            "caveats": [
                "NO PURE CONTROL: the reference is `Legal march - no scientist`",
                "2 x 3 factorial, so the five contrasts are not five independent messages",
                "differential attrition: 85% of the 274 attention-check failures are in the "
                "civil-disobedience arms, so the CD arms are smaller AND selected",
                "the verbatim item stems are not in the deposit; the brief carries the authors' "
                "own descriptions and the exact response labels",
                "`SourceCredibility` is asked only in the four scientist arms and is therefore not "
                "an outcome of this carve (no value exists in the reference arm)",
                "registered report: H8 and H9 (no effect of scientist engagement on source or "
                "general science credibility) were PRE-REGISTERED NULLS and the data supported "
                "them, so the science_credibility row of this task is a null by design",
            ]}}


# ------------------------------------------------------------------------------- red paths
def redpaths(out: pd.DataFrame):
    ad = adapter()
    d = out.copy()
    d["_arm"] = d["arm"]
    res = []
    truth = ssb.task.true_ates(d, ad)
    p = power(truth.ate, truth.se, truth.n_treat, truth.n_control, truth.outcome)

    # R1 - the attention check read the naive way destroys the CD arms.
    raw = pd.read_csv(SRC / "dat_num_all.csv")
    naive = raw[(raw.Progress == 100) & (raw.AC_Protest == 1)]
    n_cd = int(naive.condition.str.contains("CD").sum())
    res.append(("RED PATH the attention check is arm-dependent",
                "reading AC_Protest==1 as correct for everyone keeps %d rows and only %d CD "
                "respondents (against %d) -> OK, refused by the n check"
                % (len(naive), n_cd, int((out.arm.str.contains("Civil")).sum()))))
    assert n_cd < 0.25 * int((out.arm.str.contains("Civil")).sum())

    # R2 - policy_support must be reversed, and the sign of its correlation is the proof.
    # The derived file stores the RAW item (agreement that offshore drilling should be EXPANDED);
    # `reverse` is applied inside ssb.task.true_ates, so the check is on the raw column.
    r = float(out[["policy_support", "activist_support"]].corr().iloc[0, 1])
    ps = truth[truth.outcome == "policy_support"]
    adn = dict(ad, outcomes={**ad["outcomes"],
                             "policy_support": {k: v for k, v in ad["outcomes"]["policy_support"].items()
                                                if k != "reverse"}})
    psn = ssb.task.true_ates(d, adn)
    psn = psn[psn.outcome == "policy_support"]
    res.append(("RED PATH reverse coding on policy_support",
                "raw corr(drilling-should-expand, activist support) = %+.2f, so the item runs "
                "AGAINST climate policy and must be reversed; forgetting it negates all %d cells "
                "(%s -> %s) -> OK"
                % (r, len(ps), np.round(ps.ate.to_numpy(), 2), np.round(psn.ate.to_numpy(), 2))))
    assert r < -0.4 and np.allclose(ps.ate.to_numpy(), -psn.ate.to_numpy(), atol=1e-9)

    # R3 - SourceCredibility cannot be an outcome: no value exists in the reference arm.
    adx = dict(ad, outcomes={**ad["outcomes"],
                             "source_credibility": {"col": "source_credibility", "lo": 1, "hi": 5}})
    tx = ssb.task.true_ates(d, adx)
    bad = tx[tx.outcome == "source_credibility"]
    res.append(("RED PATH SourceCredibility as an outcome",
                "%d cells, %d finite -> %s" % (len(bad), int(np.isfinite(bad.ate).sum()),
                                               "correctly undefined" if not np.isfinite(bad.ate).any()
                                               else "FAIL")))
    assert not np.isfinite(bad.ate).any()

    # R4 - the vignettes must be nested: each treated text must contain its base article verbatim.
    nested = all(TEXTS[k].startswith(LEGAL_BASE if "Legal" in k else CD_BASE) for k in TEXTS)
    lens = {k: len(v) for k, v in TEXTS.items()}
    res.append(("RED PATH vignette assembly is nested and the deltas are the manipulation",
                "every arm starts with its own base article: %s; scientist paragraph adds "
                "%d-%d chars -> OK"
                % (nested, min(lens[k] - lens["Legal march - no scientist"] for k in lens
                               if "Legal" in k and "no scientist" not in k),
                   max(lens[k] - lens["Civil disobedience - no scientist"] for k in lens
                       if "Civil" in k and "no scientist" not in k))))
    assert nested

    # R5 - the pre-registered null must actually read as a null here.
    sc = truth[truth.outcome == "science_credibility"]
    res.append(("RED PATH the registered-report null (H9) reproduces",
                "science_credibility |ATE| %.2f-%.2f pp, worst |t| %.2f -> %s"
                % (sc.ate.abs().min(), sc.ate.abs().max(), (sc.ate / sc.se).abs().max(),
                   "null, as pre-registered" if (sc.ate / sc.se).abs().max() < 2 else "FAIL")))
    assert (sc.ate / sc.se).abs().max() < 2
    return res, truth, p


# ------------------------------------------------------------------------------------ main
def main(power_only=False):
    out, checks = build()
    print("BUILD CHECKS\n" + json.dumps(checks, indent=1))
    res, truth, p = redpaths(out)
    print("\nRED PATHS")
    for name, r in res:
        print("  %-56s %s" % (name, r))
    print("\nPOWER GATE (covariance-aware, findings 79/87), %d cells" % len(truth))
    print("  var_observed %.3f  var_noise %.3f  var_signal %+.3f" %
          (p["var_observed"], p["var_noise"], p["var_signal"]))
    print("  MARGINAL attainable r       %.3f" % p["max_attainable_r"])
    print("  WITHIN-OUTCOME attainable r %.3f" % p["within_ceiling_r"])
    print("  median |ATE| %.2f pp, median SE %.2f pp" % (p["median_abs_ate"], p["median_se"]))
    print("\nTHE TABLE")
    print(truth.assign(t=(truth.ate / truth.se).round(2))[
        ["condition", "outcome", "ate", "se", "t", "n_treat", "n_control"]
    ].round(3).to_string(index=False))
    sc = truth[truth.outcome == "science_credibility"]
    print("\nTRUST-FAMILY CELLS: median |ATE| %.2f pp (pre-registered null H9)"
          % sc.ate.abs().median())
    if power_only:
        return 0
    (RUN / "inputs" / "derived").mkdir(parents=True, exist_ok=True)
    out.to_csv(RUN / "inputs" / "derived" / "dablander2025.csv", index=False)
    (RUN / "inputs" / "texts" / "dablander2025_arms.json").write_text(
        json.dumps(TEXTS, indent=1, ensure_ascii=False))
    (RUN / "inputs" / "adapters" / "dablander2025.json").write_text(
        json.dumps(adapter(), indent=1, ensure_ascii=False))
    (RUN / "inputs" / "derived" / "dablander2025_checks.json").write_text(json.dumps(checks, indent=1))
    print("\nwrote inputs/derived/dablander2025.csv (%d x %d), 6 texts, adapter, checks" % out.shape)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--power", action="store_true")
    raise SystemExit(main(ap.parse_args().power))
