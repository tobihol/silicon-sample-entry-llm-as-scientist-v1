#!/usr/bin/env python
"""Rebuild the kim2024 practice-task input (task 11) - the first US message -> trust ATE anchor.

    /opt/kernel/venv/bin/python tools/build_kim.py            # build + every check
    /opt/kernel/venv/bin/python tools/build_kim.py --power    # the gate, printed, no writes

Kim & Liu 2024, "Persuading Climate Skeptics with Facts" (Harvard Dataverse doi:10.7910/DVN/ABEHSN).
3,007 US MTurk respondents, three arms randomised by eight Qualtrics block randomisers:
`control` (a text about cryptocurrency), `consensus` (the 97% scientific-consensus message) and
`causal` (an explanation of WHY scientists concluded humans cause warming). Trust in climate
scientists is asked PRE (`q11`) and POST (`q40`) on the same 4-point item.

WHY THIS TASK, AND WHAT IS WRONG WITH IT - both stated before the carve.

  * It is the harness's FIRST randomised US general-population message -> trust-in-climate-
    scientists ATE. Findings 78/84/88/94 built a four-task magnitude series (human median |ATE|
    0.42 / 2.16 / 4.33 / 1.14 pp against predicted 0.90 / 1.20 / 1.60 / 0.80) in which no task
    was a US message experiment about climate scientists. This one is.
  * **The verbatim message texts are NOT in the deposit.** They are in neither the .sav labels,
    the authors' R script, the knit HTML, nor the two READMEs; they would have to come from the
    paper's appendix, which is not mounted. So the brief cannot carry the stimulus. It carries
    the manipulation-check descriptions the respondents themselves were shown
    (`q48`'s value labels, verbatim) plus the design facts on the deposit's own record. That is
    a materially WEAKER brief than every other task here, and standing finding 65 measured what
    deleting prompt content costs (item wordings: rho -0.408, r_within -0.273). It is declared in
    the adapter, in the brief itself, in the scoreboard note and in the pre-registration, and the
    task is `exclude_from_slope`.
  * MTurk 2021, not a probability panel; single 4-point trust item, not a slider; no race and no
    income on file, so those moderators do not exist here.
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

SRC = Path("/workspace/datasets/kim2024/downloads/s.sav")
ARMS = ["control", "consensus", "causal"]
# Readable arm titles. Finding 65 measured that arm titles carry almost nothing (renaming every
# frame `Message A...` moves r_within by -0.005), so this is legibility, not information.
TITLE = {"control": "Control (unrelated text)", "consensus": "Scientific consensus",
         "causal": "Causal evidence"}
EXPECT_N = {"control": 1008, "consensus": 994, "causal": 1005}     # README, verified counts

# Post-treatment outcomes. `rev` means the raw code runs HIGH = less of the construct, so the
# carve reverses it and every ATE below is in "more of the named construct" units.
OUTCOMES = {
    "trust_climate_scientists": ("q40", 1, 4, True,
        "'How much, if at all, [do] you trust climate scientists to give full and accurate "
        "information about global climate change?' 1 'A lot' / 2 'Some' / 3 'Not too much' / "
        "4 'None at all'. Scored so that HIGHER = MORE TRUST."),
    "consensus_perceived": ("q41_7", 0, 100, False,
        "'To the best of your knowledge, what percentage of climate scientists have concluded "
        "that human-caused global warming is happening?' 0-100 slider."),
    "belief_human_cause": ("q31", 1, 3, True,
        "'...the world's temperature may have been going up slowly over the past 100 years. Do "
        "you think this is happening?' - cause attribution: 1 'Mostly by human activity' / "
        "2 'About equally' / 3 'Mostly by natural causes'. HIGHER = MORE HUMAN-CAUSED."),
    "human_contribution": ("q36", 1, 4, True,
        "'How much do you think human activity, such as the burning of fossil fuels, contributes "
        "to global climate change?' 1 'A great deal' - 4 'Not at all'. HIGHER = MORE."),
    "natural_contribution": ("q37", 1, 4, True,
        "'How much do you think natural patterns in the Earth's environment contribute to global "
        "climate change?' 1 'A great deal' - 4 'Not at all'. HIGHER = MORE. Note the direction: a "
        "message that raises human attribution may LOWER this one."),
    "evidence_human": ("q38", 1, 4, True,
        "'How much evidence is there to support the idea that human activity ... contributes to "
        "global climate change?' 1 'A great deal' - 4 'Not at all'. HIGHER = MORE EVIDENCE."),
    "evidence_natural": ("q39", 1, 4, True,
        "'How much evidence is there to support the idea that natural patterns ... contribute to "
        "global climate change?' 1 'A great deal' - 4 'Not at all'. HIGHER = MORE EVIDENCE."),
    "policy_fedgov_more": ("q42", 1, 5, True,
        "'Do you think the federal government should be doing more about rising temperatures?' "
        "1 'Should be doing much more' - 5 'Should be doing much less'. HIGHER = MORE ACTION."),
    "policy_green_new_deal": ("q43", 6, 12, True,
        "'Do you support or oppose the Green New Deal?' 7-point, raw Qualtrics codes 6 'Strongly "
        "support' - 12 'Strongly oppose'. HIGHER = MORE SUPPORT."),
    "policy_paris": ("q44", 4, 10, True,
        "'Do you support or oppose the executive action ... to have the United States recommit to "
        "the Paris Agreement?' 7-point, raw codes 4 'Strongly support' - 10 'Strongly oppose'. "
        "HIGHER = MORE SUPPORT."),
    "policy_priority": ("q45", 1, 4, True,
        "'...should dealing with global climate change be a top priority?' 1 'A top priority' - "
        "4 'It should not be done'. HIGHER = HIGHER PRIORITY."),
}
# Pre-treatment items. NOT outcomes. Carving them is the randomization red path.
PRE = {"trust_pre": ("q11", 1, 4, True), "belief_pre": ("q7", 1, 3, True)}

MODERATORS = {
    "party_lean": ("q5", {1: "Republican", 2: "Republican", 3: "Republican",
                          4: "Independent", 5: "Democrat", 6: "Democrat", 7: "Democrat"}),
    "gender": ("q12", {1: "Male", 2: "Female"}),
    "education": ("q14", {1: "No degree", 2: "No degree", 3: "No degree", 4: "Some college",
                          5: "BA+", 6: "BA+", 7: "BA+", 8: "BA+"}),
}

ARM_DESCRIPTIONS = {
    "consensus":
        "A short message about the scientific consensus on climate change. The respondents' own "
        "manipulation-check description of it, verbatim from the instrument: \"It explained that "
        "there is a 97% consensus among climate scientists.\" The paper's title and abstract "
        "describe it as CONSENSUS MESSAGING: a statement that 97% of climate scientists have "
        "concluded that human-caused global warming is happening. No causal mechanism is given.",
    "causal":
        "A short message giving causal evidence for climate change. The respondents' own "
        "manipulation-check description of it, verbatim from the instrument: \"It explained why "
        "scientists have concluded that human activities are causing climate change.\" The paper "
        "describes it as CAUSAL EVIDENCE: an explanation of the mechanism and reasoning by which "
        "scientists reached that conclusion. It is longer than the consensus message. No consensus "
        "percentage is stated.",
    "control":
        "A short control text on an unrelated topic. The respondents' own manipulation-check "
        "description of it, verbatim from the instrument: \"It discussed cryptocurrency.\"",
}
STIMULUS_CAVEAT = (
    "IMPORTANT - READ BEFORE PREDICTING. The verbatim message texts of this study are not "
    "available: they are not in the public data deposit, and this brief therefore describes each "
    "arm rather than reproducing it. Every description above is either verbatim from the "
    "instrument's own manipulation-check item (which the respondents themselves answered) or from "
    "the paper's title and abstract. You are being asked to predict effects from a DESCRIPTION of "
    "a message, not from the message. Nothing else about the task changes.")


# ------------------------------------------------------------------------------------ build
def _arm(df: pd.DataFrame) -> pd.Series:
    """The arm is not a column. Eight Qualtrics block randomisers each carry three indicator
    columns FL_<block>_DO_<arm>; a respondent's arm is the one flagged in whichever block they
    saw. This is exactly `RP Replication.R` lines 29-33."""
    fl = [c for c in df.columns if c.startswith("FL_") and "_DO_" in c]
    arm = pd.Series(index=df.index, dtype=object)
    hits = pd.Series(0, index=df.index)
    for c in fl:
        a = c.split("_DO_")[1]
        m = df[c].fillna(0) == 1
        arm[m] = a
        hits += m.astype(int)
    return arm, hits, fl


def build():
    import pyreadstat
    df, meta = pyreadstat.read_sav(str(SRC))
    arm, hits, fl = _arm(df)
    df["_arm"] = arm
    # Store the READABLE TITLE in the derived file, not the raw code. If the adapter had to
    # rename an arm, the raw code would appear in the brief's prose ("consensus n = 994") beside
    # the title, and a model answers with whichever name it saw - which cost a paid batch this
    # session. One name per arm, fixed at the source.
    out = pd.DataFrame({"arm": df["_arm"].map(TITLE)})
    for name, (col, lo, hi, rev, _q) in {**OUTCOMES, **{k: v + ("",) for k, v in PRE.items()}}.items():
        out[name] = pd.to_numeric(df[col], errors="coerce")
    for m, (col, mp) in MODERATORS.items():
        out[m] = pd.to_numeric(df[col], errors="coerce").map(mp)
    age = pd.to_numeric(df["q13"], errors="coerce")
    out["age_band"] = pd.cut(age, [17, 29, 44, 59, 200], labels=["18-29", "30-44", "45-59", "60+"])
    out["manip_check"] = pd.to_numeric(df["q48"], errors="coerce")
    out = out[out.arm.isin(TITLE.values())].reset_index(drop=True)

    counts = out.arm.map({v: k for k, v in TITLE.items()}).value_counts().to_dict()
    # manipulation check: did each arm's respondents recognise WHICH message they read?
    mc_key = {"consensus": 1.0, "causal": 2.0, "control": 3.0}   # q48's own value codes
    mc = {a: float((out.loc[out.arm == TITLE[a], "manip_check"] == mc_key[a]).mean())
          for a in ARMS}
    checks = {
        "rows": int(len(out)), "arm_counts": {k: int(v) for k, v in counts.items()},
        "randomiser_blocks": len(fl) // 3,
        "exactly_one_indicator": {"min": int(hits.min()), "max": int(hits.max())},
        "manipulation_check_correct_share": {k: round(v, 3) for k, v in mc.items()},
        "n_nonmissing": {k: int(out[k].notna().sum()) for k in OUTCOMES},
        "pre_post_trust_r": float(out[["trust_pre", "trust_climate_scientists"]].corr().iloc[0, 1]),
    }
    fail = []
    for a in ARMS:
        if counts.get(a) != EXPECT_N[a]:
            fail.append("arm %s: %s rows, README says %d" % (a, counts.get(a), EXPECT_N[a]))
    if hits.max() > 1:
        fail.append("a respondent is flagged in more than one arm indicator")
    for a in ARMS:
        if mc[a] < 0.6:
            fail.append("manipulation check: only %.0f%% of the %s arm named their own message"
                        % (100 * mc[a], a))
    if not (0.85 < checks["pre_post_trust_r"] < 0.95):
        fail.append("pre-post trust r = %.3f, README says ~0.90" % checks["pre_post_trust_r"])
    if fail:
        raise SystemExit("KIM BUILD REFUSED:\n  - " + "\n  - ".join(fail))
    return out, checks


def adapter() -> dict:
    return {
        "dataset": "kim2024",
        "status": "VERIFIED by tools/build_kim.py (rebuild + red paths + published checks)",
        "file": str(RUN / "inputs" / "derived" / "kim2024.csv"),
        "reader": "csv",
        "sample_description":
            STIMULUS_CAVEAT + "\n\n"
            "3,007 U.S. adults recruited on Amazon Mechanical Turk, fielded 2021 by the "
            "University of Pennsylvania. Arm sizes are listed separately below. A "
            "convenience sample, not a census-quota panel: relative to the U.S. adult population "
            "MTurk skews younger, more educated, more online and somewhat more Democratic. "
            "Respondents answered a pre-treatment block (including their trust in climate "
            "scientists and their attribution of warming), then read one short text, then "
            "answered the post-treatment block below.",
        "condition_col": "arm",
        "arms": {TITLE[a]: TITLE[a] for a in ARMS},
        "control_arms": [TITLE["control"]],
        "outcomes": {n: {"col": n, "lo": lo, "hi": hi,
                         **({"reverse": True} if rev else {}), "question": q}
                     for n, (c, lo, hi, rev, q) in OUTCOMES.items()},
        "moderators": {
            "party_lean": {"col": "party_lean", "map": {k: k for k in
                                                        ["Democrat", "Independent", "Republican"]}},
            "gender": {"col": "gender", "map": {"Male": "Male", "Female": "Female"}},
            "education": {"col": "education", "map": {k: k for k in
                                                      ["No degree", "Some college", "BA+"]}},
            "age_band": {"col": "age_band", "map": {k: k for k in
                                                    ["18-29", "30-44", "45-59", "60+"]}},
        },
        "moderators_unavailable": {"race": "not asked", "income": "not asked"},
        "filters": [],
        "weight_col": None,
        "message_texts_file": str(RUN / "inputs" / "texts" / "kim2024_arms.json"),
        "exclude_from_slope":
            "the verbatim stimuli are not in the deposit, so the predictor is given a DESCRIPTION "
            "of each message rather than the message (see provenance.caveats); and this is a "
            "trust-family task on a coarse 4-point item, which the operator's session-13 directive "
            "and standing findings 69/83 both keep out of any pooled multiplier.",
        "provenance": {
            "verified_by": "tools/build_kim.py; the authors' `RP Replication.R` is the codebook",
            "caveats": [
                "THE VERBATIM MESSAGE TEXTS ARE NOT IN THE DEPOSIT. The brief carries the "
                "respondents' own manipulation-check descriptions (verbatim from the instrument) "
                "plus the paper's title/abstract characterisation. This is a weaker brief than "
                "every other task here and it is stated inside the brief itself.",
                "MTurk convenience sample, 2021; no race and no income variables, so those two "
                "moderators cannot be checked on this task at all",
                "the trust outcome is a single 4-point item, not a slider - the target's "
                "trust_multidimensional is a 12-item four-subscale composite on 0-100 sliders",
                "the arm is derived from eight Qualtrics block randomisers, not a stored column",
                "`consensus_perceived` is the manipulation's own target and its consensus-arm "
                "effect is close to a manipulation check, not a persuasion effect",
                "two outcomes (natural_contribution, evidence_natural) are scored so that HIGHER "
                "means more attribution to NATURAL causes: a message that works should move them "
                "DOWN or not at all",
            ]}}


# ------------------------------------------------------------------------------- red paths
def redpaths(out: pd.DataFrame) -> list[tuple[str, str]]:
    ad = adapter()
    ad["file"] = None
    d = out.copy()
    d["_arm"] = d["arm"]
    res = []

    truth = ssb.task.true_ates(d, ad)
    p = power(truth.ate, truth.se, truth.n_treat, truth.n_control, truth.outcome)

    # R1 - the randomization check IS a red path: pre-treatment items must carry no signal.
    adp = dict(ad, outcomes={k: {"col": k, "lo": v[1], "hi": v[2], "reverse": v[3]}
                             for k, v in PRE.items()})
    tp = ssb.task.true_ates(d, adp)
    pp = power(tp.ate, tp.se, tp.n_treat, tp.n_control, tp.outcome)
    ok = pp["max_attainable_r"] != pp["max_attainable_r"] or pp["max_attainable_r"] < 0.5
    res.append(("RED PATH randomization: the PRE-treatment items carry no arm signal",
                "var_signal %+.3f, attainable r %s, worst |t| %.2f  -> %s"
                % (pp["var_signal"],
                   "0.000" if pp["max_attainable_r"] != pp["max_attainable_r"]
                   else "%.3f" % pp["max_attainable_r"],
                   (tp.ate.abs() / tp.se).max(), "OK" if ok else "FAIL")))
    assert ok, "the pre-treatment items are not balanced across arms"

    # R2 - forgetting the reverse coding flips every sign of the trust effect.
    adr = dict(ad, outcomes={k: {kk: vv for kk, vv in v.items() if kk != "reverse"}
                             for k, v in ad["outcomes"].items()})
    tr = ssb.task.true_ates(d, adr)
    m = truth.outcome == "trust_climate_scientists"
    mr = tr.outcome == "trust_climate_scientists"
    flipped = np.allclose(truth.ate[m].to_numpy(), -tr.ate[mr].to_numpy(), atol=1e-9)
    res.append(("RED PATH reverse coding: dropping it negates every reversed cell",
                "trust ATEs %s vs %s -> %s"
                % (np.round(truth.ate[m].to_numpy(), 3), np.round(tr.ate[mr].to_numpy(), 3),
                   "OK" if flipped else "FAIL")))
    assert flipped

    # R3 - the pp conversion depends on the RANGE, not on where the codes start. Declaring
    # q43's raw 6..12 codes as 1..7 changes NOTHING (both are 6 wide, scale 100/6) - which is the
    # thing worth asserting, because a reader who sees "raw codes 6-12" assumes it must matter.
    # What DOES matter is getting the number of points wrong.
    adsame = dict(ad, outcomes={**ad["outcomes"],
                                "policy_green_new_deal": {**ad["outcomes"]["policy_green_new_deal"],
                                                          "lo": 1, "hi": 7}})
    ts = ssb.task.true_ates(d, adsame)
    a1 = truth.loc[truth.outcome == "policy_green_new_deal", "ate"].to_numpy()
    a2 = ts.loc[ts.outcome == "policy_green_new_deal", "ate"].to_numpy()
    assert np.allclose(a1, a2), "an offset in the raw codes changed the pp scaling"
    adw = dict(ad, outcomes={**ad["outcomes"],
                             "policy_green_new_deal": {**ad["outcomes"]["policy_green_new_deal"],
                                                       "lo": 1, "hi": 5}})
    tw = ssb.task.true_ates(d, adw)
    a3 = tw.loc[tw.outcome == "policy_green_new_deal", "ate"].to_numpy()
    res.append(("RED PATH scale range: only the WIDTH scales, and getting it wrong costs 1.5x",
                "declaring 6-12 as 1-7 (same width) is identical to 1e-12; declaring it 5-point "
                "rescales by %.2fx -> OK" % (abs(a3).mean() / abs(a1).mean())))
    assert abs(abs(a3).mean() / abs(a1).mean() - 1.5) < 1e-6

    # R4 - a control arm that is not in the data must not silently produce a number.
    bad = ssb.task.true_ates(d, dict(ad, control_arms=["placebo"]))
    n_finite = int(np.isfinite(bad.ate).sum())
    res.append(("RED PATH a control arm not present in the data",
                "control_arms=['placebo'] gives %d cells, %d of them finite -> %s"
                % (len(bad), n_finite,
                   "the control set is empty so every ATE is NaN; an unfilled cell aborts "
                   "tools/practice.py rather than scoring" if n_finite == 0 else "FAIL")))
    assert n_finite == 0, "a nonexistent control arm produced finite ATEs"

    return res, truth, p


# ------------------------------------------------------------------------------------ main
def main(power_only=False):
    out, checks = build()
    print("BUILD CHECKS\n" + json.dumps(checks, indent=1))
    res, truth, p = redpaths(out)
    print("\nRED PATHS")
    for name, r in res:
        print("  %-58s %s" % (name, r))

    print("\nPOWER GATE (covariance-aware, standing findings 79/87), %d cells" % len(truth))
    print("  var_observed %.3f  var_noise %.3f  var_signal %+.3f" %
          (p["var_observed"], p["var_noise"], p["var_signal"]))
    print("  MARGINAL attainable r      %.3f" % p["max_attainable_r"])
    print("  WITHIN-OUTCOME attainable r %.3f" % p["within_ceiling_r"])
    print("  median |ATE| %.2f pp, median SE %.2f pp" % (p["median_abs_ate"], p["median_se"]))
    print("\nTHE TABLE")
    print(truth.assign(t=(truth.ate / truth.se).round(2))[
        ["condition", "outcome", "ate", "se", "t", "n_treat", "n_control"]].round(3).to_string(index=False))
    tr = truth[truth.outcome == "trust_climate_scientists"]
    print("\nTRUST CELLS (the reason this task exists): %s, median |ATE| %.2f pp"
          % (", ".join("%s %+.2f pp (t %.2f)" % (r.condition, r.ate, r.ate / r.se)
                       for r in tr.itertuples()), tr.ate.abs().median()))
    if power_only:
        return 0
    (RUN / "inputs" / "derived").mkdir(parents=True, exist_ok=True)
    out.to_csv(RUN / "inputs" / "derived" / "kim2024.csv", index=False)
    texts = {TITLE[a]: ARM_DESCRIPTIONS[a] for a in ARMS}
    (RUN / "inputs" / "texts" / "kim2024_arms.json").write_text(
        json.dumps(texts, indent=1, ensure_ascii=False))
    (RUN / "inputs" / "adapters" / "kim2024.json").write_text(
        json.dumps(adapter(), indent=1, ensure_ascii=False))
    (RUN / "inputs" / "derived" / "kim2024_checks.json").write_text(json.dumps(checks, indent=1))
    print("\nwrote inputs/derived/kim2024.csv (%d x %d), texts, adapter, checks" % out.shape)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--power", action="store_true", help="print the gate, write nothing")
    raise SystemExit(main(ap.parse_args().power))
