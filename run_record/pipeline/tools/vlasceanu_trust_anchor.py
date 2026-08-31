#!/usr/bin/env python
"""TASK_16 item 2: check the card's trust control levels and spreads against the only US
quota-panel 0-100 climate-trust sliders on the mounted data. 0 model calls.

    /opt/kernel/venv/bin/python tools/vlasceanu_trust_anchor.py

The operator's session-16 scouting found that vlasceanu2024's CONTROL arm carries three 0-100
sliders that were fielded as INDEPENDENT variables and therefore have no ATE - but do have a real
distribution: `Trust_sci1` ("On average, how competent are climate change research scientists?"),
`Trust_sci2` ("On average, how much do you trust scientific research about climate change?") and
`Trust_gov` ("On average, how much do you trust your government?"), n = 4,824 across 63 countries
and n = 628 in the US.

THE MAPPING RULE, STATED BEFORE ANY NUMBER WAS COMPUTED
-------------------------------------------------------
R1  Levels are compared **US to US**. A level is a property of a population; the 63-country pool is
    reported as context and is never an anchor for a US card.
R2  A comparison is ITEM-MATCHED only if construct, referent AND response format all match. All
    three anchor items are 0-100 sliders, so findings 10 and 14's coarse-scale corrections do NOT
    apply and must not be invented here; what does differ is the ANCHORING - the anchor items are
    unipolar (0 = "Not at all") while the target's trust battery is bipolar (0 = "Very
    incompetent"), and a unipolar-vs-bipolar swap moves a level with no change in the construct.
R3  A card change is RECOMMENDED only if (a) the comparison is item-matched under R2 and (b) the
    level differs by more than 5 pp or the SD ratio falls outside [0.80, 1.25]. Otherwise the
    reading is reported and nothing is changed. (Both halves of R3 are needed: RUNBOOK 2a forbids
    editing a prediction because a diagnostic looked bad, and finding 9 is the standing example of
    a level imported from a sample-matched but item-mismatched source and wrong by 10 pp.)
R4  Spread and distribution SHAPE are compared separately from level, because the card's Tier-1
    distribution rows are scored on shape and the format parameters were fitted on a different
    instrument (voelkel2026's climate-attitude sliders, standing finding 6).
R5  Anything that implies a card change is written up as PENDING-OPERATOR and not applied.
"""
import json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
SRC = Path("/workspace/datasets/vlasceanu2024/downloads/data_notimers.csv")
CARD = RUN / "runs" / "20260815-target-01" / "card" / "baseline.csv"
ITEMS = {
    "Trust_sci1_1": ("On average, how competent are climate change research scientists?",
                     "trust_competence_1 / trust_multidimensional"),
    "Trust_sci2_1": ("On average, how much do you trust scientific research about climate change?",
                     "trust_post"),
    "Trust_gov_1": ("On average, how much do you trust your government?",
                    "inst_trust_federal_gov (a component of inst_trust_mean)"),
}


def shape(x):
    x = pd.Series(x).dropna()
    return {"n": len(x), "mean": float(x.mean()), "sd": float(x.std(ddof=1)),
            "p_mult5": float((x % 5 == 0).mean()), "p_mult10": float((x % 10 == 0).mean()),
            "p_at_0": float((x == 0).mean()), "p_at_50": float((x == 50).mean()),
            "p_at_100": float((x == 100).mean())}


def main():
    d = pd.read_csv(SRC, low_memory=False, encoding="latin-1")
    ctrl = d[d.Trust_sci2_1.notna()]
    # control-arm only, plus exactly one row whose condName is blank - dropped rather than
    # explained away, and asserted so a later re-run notices if that ever changes
    assert set(ctrl.condName.dropna().unique()) == {"Control"} and ctrl.condName.isna().sum() == 1
    ctrl = ctrl[ctrl.condName == "Control"]
    us = ctrl[ctrl.country.astype(str).str.lower().str.startswith("usa")]
    card = pd.read_csv(CARD).set_index("outcome")
    fp = json.loads((RUN / "inputs" / "format_params.json").read_text())
    vk = fp["_evidence"]["sliders"]["measured"]

    print(__doc__.split("THE MAPPING RULE")[0])
    print("1. THE ANCHOR ITSELF  (control arm only - these were IVs, so there is no ATE)")
    print("   %-14s%-8s%7s%9s%8s%9s%9s%9s%9s"
          % ("item", "sample", "n", "mean", "sd", "p_mult5", "p_at_0", "p_at_50", "p_at_100"))
    got = {}
    for col in ITEMS:
        for lab, fr in (("US", us), ("63c", ctrl)):
            s = shape(fr[col])
            got[(col, lab)] = s
            print("   %-14s%-8s%7d%9.2f%8.2f%9.3f%9.3f%9.3f%9.3f"
                  % (col.replace("_1", ""), lab, s["n"], s["mean"], s["sd"], s["p_mult5"],
                     s["p_at_0"], s["p_at_50"], s["p_at_100"]))

    print("\n2. LEVELS against the deposited card  (rule R1: US to US)")
    print("   %-24s%9s%9s%12s%10s   %s"
          % ("card outcome", "card", "anchor", "difference", "matched?", "ruling"))
    rows = [("trust_multidimensional", "Trust_sci1_1", False,
             "single COMPETENCE item vs a 12-item four-subscale composite; and unipolar vs bipolar"),
            ("trust_post", "Trust_sci2_1", False,
             "the anchor's referent is the RESEARCH, the card's is the SCIENTISTS; unipolar vs "
             "bipolar"),
            ("inst_trust_mean", "Trust_gov_1", False,
             "the anchor is ONE of the card composite's five institutions, and 'your government' "
             "is not 'the federal government'")]
    for out, col, matched, why in rows:
        c, a = float(card.control_mean[out]), got[(col, "US")]["mean"]
        print("   %-24s%9.1f%9.2f%+12.2f%10s   %s"
              % (out, c, a, a - c, "yes" if matched else "NO", "report only (R2 fails)"))
        print("      %s" % why)

    print("\n3. SPREAD  (rule R4) - the part that is item-matched enough to mean something")
    for out, col in (("trust_post", "Trust_sci2_1"), ("distrust_post", "Trust_sci2_1"),
                     ("funding_perceptions", "Trust_sci1_1")):
        c, a = float(card.control_sd[out]), got[(col, "US")]["sd"]
        print("   %-24s card SD %5.1f   anchor SD %5.2f   ratio %.2f   %s"
              % (out, c, a, c / a, "INSIDE [0.80, 1.25]" if 0.8 <= c / a <= 1.25 else "OUTSIDE"))
    cm = float(card.control_sd["trust_multidimensional"])
    print("   %-24s card SD %5.1f   single-item anchors 27.0-28.8 -> ratio %.2f, which is what a "
          "12-item\n%*smean SHOULD look like, not a disagreement"
          % ("trust_multidimensional", cm, cm / 27.0, 30, ""))

    print("\n4. DISTRIBUTION SHAPE against inputs/format_params.json  (fitted on voelkel2026's"
          " climate-attitude sliders)")
    print("   %-26s%10s%10s%10s%10s" % ("", "p_mult5", "p_at_0", "p_at_50", "p_at_100"))
    print("   %-26s%10.3f%10.3f%10.3f%10.3f"
          % ("format_params (voelkel2026)", vk["p_mult5"], vk["p_at_0"], vk["p_at_50"],
             vk["p_at_100"]))
    for col in ITEMS:
        for lab in ("US", "63c"):
            s = got[(col, lab)]
            print("   %-26s%10.3f%10.3f%10.3f%10.3f"
                  % ("%s %s" % (col.replace("_1", ""), lab), s["p_mult5"], s["p_at_0"],
                     s["p_at_50"], s["p_at_100"]))
    us5 = np.mean([got[(c, "US")]["p_mult5"] for c in ITEMS])
    all5 = np.mean([got[(c, "63c")]["p_mult5"] for c in ITEMS])
    print("   mean p_mult5: US %.3f, 63-country %.3f, format_params %.3f"
          % (us5, all5, vk["p_mult5"]))

    print("\nVERDICT")
    print("  * NO CARD CHANGE IS RECOMMENDED. Not one of the three comparisons is item-matched")
    print("    under rule R2, so R3's first condition fails before its second is even reached.")
    print("  * What the check DOES confirm: the card's single-item trust SD of 30.0 against a")
    print("    measured 28.8 (ratio 1.04) and 27.0 (1.11) on real US climate-trust sliders, and a")
    print("    composite SD of 20.6 that is 0.76 of a single item - the shape a 12-item mean has.")
    print("  * What it FLAGS, in one direction: both US climate-trust items sit ~6 pp ABOVE the")
    print("    card's control level (68.95 and 67.86 against 62.7 and 62.1). Neither is")
    print("    item-matched and both are unipolar against the target's bipolar anchoring, which is")
    print("    a known level-shifting difference - but two independent items agreeing in sign is")
    print("    worth recording, and it points UP.")
    print("  * A third reading for standing finding 6 (the heaping RATE transfers): on the same")
    print("    instrument, US respondents put %.1f%% of answers on a multiple of 5 against %.1f%%"
          % (100 * us5, 100 * all5))
    print("    across all 63 countries, and the deposited format parameter is %.1f%%. The rate is"
          % (100 * vk["p_mult5"]))
    print("    less invariant than finding 6 read it - and this instrument's sliders START at 0")
    print("    and require a drag, which is a UI difference that can produce exactly this.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
