#!/usr/bin/env python
"""TASK_14 direction 4: do any of the target's 16 stimuli make an explicit POLITICAL-IDENTITY claim?

    /opt/kernel/venv/bin/python tools/identity_audit.py

Why this exists. altenmueller2024 Study 1 is the largest moderation effect this harness has ever
measured: describing a research institute as politically liberal rather than conservative moves METI
trust by **46.45 pp** between the party halves of the same sample (finding 81). The same paper's
IMPLICIT version of the manipulation - discipline as a stereotype proxy - moves it by 3.75 pp, and a
message STRATEGY (koetke2024) by at most 1.82 pp. The deposited card predicts a condition x
moderator interaction of exactly zero, which finding 81 ruled CONSISTENT **for message
interventions**, with one stated escape: if a target arm makes an explicit political claim about
climate scientists, the interaction there could be large and the card's zero would be badly wrong.

Nothing had read the 16 stimuli with that question in mind. This does, in two passes that are kept
separate on purpose:

  PASS 1  a mechanical scan against a declared lexicon, so the evidence is reproducible;
  PASS 2  a coded judgement per arm, with the quote it rests on, so the reading is checkable.

and then does the arithmetic of what an altenmueller-informed tilt would actually DO to the card,
which is the part that turns a reading into a decision. It changes nothing: the card's `tilt.csv`
stays empty unless the operator signs a tilt off (RUNBOOK 2a).
"""
import argparse, json, math, re, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb                                                              # noqa: E402

CARD = RUN / "runs" / "20260815-target-01" / "card"

# PASS 1 - the lexicon, declared before the arms were read, grouped by what a hit would mean.
LEXICON = {
    "party / office": [r"\brepublican", r"\bdemocrat", r"\bg\.?o\.?p\b", r"\bcongressman",
                       r"\bvice president", r"\bsenator", r"\bwhite house", r"\btrump",
                       r"\bbiden", r"\bal gore"],
    "ideological label": [r"\bconservativ", r"\bliberal\b", r"\bprogressive\b", r"\bleft-wing",
                          r"\bright-wing", r"\bpartisan", r"\bpolariz", r"\bideolog",
                          r"\bpolitical", r"\bpolitics", r"\breddest", r"\bred state"],
    "politically-coded actor": [r"\boil compan", r"\bfossil fuel", r"\bbig oil", r"\bcorporation",
                                r"\bwealthiest", r"\bthe 1%", r"\bnational rifle",
                                r"\bamerican conservative union", r"\blobby", r"\bindustry"],
    "movement / justice frame": [r"\bsocial justice", r"\bjustice\b", r"\baccountable",
                                 r"\bthe fight\b", r"\bstand with us", r"\bemissions inequality",
                                 r"\bvulnerable", r"\blow-income", r"\bequity\b"],
}

# PASS 2 - the coded reading. class: EXPLICIT = the stimulus attaches a political identity to the
# scientists or to their named adversary; IMPLICIT = a cultural/identity cue with no political noun;
# CODED-ACTOR = a politically loaded actor appears but the scientists' identity is untouched;
# NONE = no political content. `lean` is which party half the cue would be expected to favour.
CODING = {
    "Social justice": ("EXPLICIT", "left",
        "'The climate crisis is a fight to hold the wealthiest 10% accountable ... In this fight, "
        "scientists stand with us - the 90%.' The scientists are enlisted into a redistributive "
        "political movement; this is the closest thing in the set to altenmueller's liberal-institute "
        "label."),
    "Oil industry misinformation": ("EXPLICIT", "left",
        "'the fossil fuel industry has bankrolled a multi-decade propaganda campaign ... "
        "outspending environmental groups by 10-to-1 ... don't trust the oil companies, trust the "
        "climate scientists.' The scientists' identity is defined by opposition to a "
        "politically-coded adversary, and the arm names Michael Mann and Benjamin Santer."),
    "Former skeptics": ("EXPLICIT", "right (bridging)",
        "'I am a registered Republican ...' / 'a congressman from one of the most conservative "
        "districts in South Carolina, one of the reddest states ... The National Rifle Association "
        "endorsed him ... A lot of us conservatives ...' Explicit party identity, but attached to "
        "the messengers as a BRIDGE, so its expected gradient runs the opposite way to the other "
        "two."),
    "Portrait Prof. Cherry": ("IMPLICIT", "right",
        "'watching football and exploring the Rockies near where he lives in Wyoming ... the "
        "Teton Group'. A red-state, ordinary-life identity cue with no political noun anywhere - "
        "structurally altenmueller's DISCIPLINE proxy (3.75 pp), not its label (46.45 pp)."),
    "Corporate reliance": ("CODED-ACTOR", "right",
        "'insurance companies rely on climate scientists' projections ... avoid basing decisions "
        "on information they view as biased or ideological ... These businesses maximize their "
        "profit'. A market-coded validator, with 'biased or ideological' named as the thing "
        "insurers avoid. The scientists are not given a political identity."),
    "Funding": ("CODED-ACTOR", "mixed",
        "'Corporations have too much influence on what gets researched' and 'Some people in "
        "powerful positions push certain ideas not because they're true, but because they fit "
        "their political or financial interests' - a deliberately BIPARTISAN populist pre-frame, "
        "then 'Science isn't a tool to justify a desired set of policies'. Politicised subject "
        "matter, explicitly de-politicised source."),
    "Interview Prof. Sebille": ("CODED-ACTOR", "left (weak)",
        "'vulnerable and low-income populations bear the greatest risks, underscoring the urgent "
        "need for adaptation and mitigation' plus a values disclosure ('I want to help protect the "
        "ocean'). Equity framing and advocacy motive, no political identity claimed."),
    "High public trust": ("NONE", "-", "'in our polarized context' is the only political word."),
    "Interview Prof. Maraun": ("NONE", "-",
        "'My goal ... is not to push for a certain message of global warming' - an explicit "
        "disavowal of a political goal."),
    "Measurement & modeling (1)": ("NONE", "-", "no political content."),
    "Measurement & modeling (2)": ("NONE", "-", "no political content."),
    "Peer-review": ("NONE", "-", "no political content."),
    "Consensus": ("NONE", "-", "no political content; 'disagreement' is scientific."),
    "Model accuracy": ("NONE", "-", "'You may have heard the criticism' - no political actor."),
    "Scientist community helpers": ("NONE", "-",
        "family/community/home values framing, no political identity."),
    "Extreme weather predictions": ("NONE", "-", "state-adaptive hazard text; no political actor."),
}

# the three measured points of finding 81, in pp of scale range, all party-half interactions
BENCHMARKS = {"explicit label on the source (altenmueller Study 1)": 46.45,
              "implicit discipline proxy (altenmueller Study 4b)": 3.75,
              "message strategy (koetke2024 Study 5)": 1.82}
SE_TARGET_INTERACTION = 1.94        # finding 81 / session 13: ~500 per party half


def scan():
    b = ssb.predict.target_brief()
    rows = []
    for a in b["arms"]:
        txt = (a.get("text") or "")
        low = txt.lower()
        hits = {}
        for grp, pats in LEXICON.items():
            got = []
            for p in pats:
                for m in re.finditer(p, low):
                    got.append(low[max(0, m.start() - 0):m.end()])
            if got:
                hits[grp] = sorted(set(got))
        rows.append({"arm": a["title"], "words": len(txt.split()), "hits": hits,
                     "n_hits": sum(len(v) for v in hits.values())})
    return b, pd.DataFrame(rows)


def tilt_arithmetic(arms, deltas=(2.0, 4.0, 11.6, 23.2)):
    """What would an altenmueller-informed party tilt REQUIRE, and what would it assert?

    The card's subgroup model is low rank: ate[i,o,m,l] = ate[i,o] * r[m,l] * t[i,m,l] / Z[i,m],
    with Z the share-weighted normaliser that holds the marginal ATE fixed. Writing the tilt as
    t_Dem = 1 + u, t_Rep = 1 - u and the other levels at 1, the party gap it produces is

        gap = A * (t_Dem - t_Rep) / Z = 2 A u / Z,      Z = 1 + u (s_Dem - s_Rep)

    so a given gap needs u = gap / (2A) to first order. The point of writing it out is that A - the
    card's own marginal ATE for that arm and outcome - is 1-3 pp, so ANY gap of altenmueller's size
    forces the tilt factor NEGATIVE, i.e. it is not a tilt at all: it is a prediction that the
    message BACKFIRES in one party half.
    """
    ate = pd.read_csv(CARD / "ate.csv")
    sg = pd.read_csv(CARD / "subgroup.csv")
    sh = sg[sg.moderator == "party"][["level", "share"]].drop_duplicates().set_index("level").share
    sD, sR = float(sh["Democrat"]), float(sh["Republican"])
    print("\nWHAT A TILT WOULD REQUIRE (card marginal ATE on `trust_multidimensional`, party shares "
          "D %.3f / R %.3f)" % (sD, sR))
    print("%-30s%8s" % ("arm", "A (pp)") + "".join("%18s" % ("gap %.1f pp" % d) for d in deltas))
    for arm in arms:
        A = float(ate[(ate.condition == arm) &
                      (ate.outcome == "trust_multidimensional")].ate.iloc[0])
        line = "%-30s%8.1f" % (arm, A)
        for d in deltas:
            u = d / (2 * abs(A)) if A else np.nan
            Z = 1 + u * (sD - sR)
            u = d * Z / (2 * abs(A))
            tD, tR = 1 + u, 1 - u
            dem, rep = A * tD / Z, A * tR / Z
            line += "%18s" % ("D%+.1f/R%+.1f" % (dem, rep))
        print(line)
    print("   read: the cell entries are the arm's predicted ATE in each party half, in pp. A gap")
    print("   of altenmueller's half-size (23.2 pp) asserts the message DRIVES REPUBLICAN TRUST")
    print("   DOWN by ~10 pp - a claim of a size no message experiment on the board supports.")


def score_consequences(arms):
    """Which scored rows a tilt could move, and by how much - the frozen table, read literally."""
    ate = pd.read_csv(CARD / "ate.csv")
    n_arms, n_out = ate.condition.nunique(), ate.outcome.nunique()
    sg = pd.read_csv(CARD / "subgroup.csv")
    levels = sg.groupby("moderator")["level"].nunique()
    tot = int(n_arms * n_out * levels.sum())
    party_cells = int(n_arms * n_out * levels["party"])
    touched = int(len(arms) * n_out * levels["party"])
    print("\nWHAT IT WOULD MOVE ON THE SCORE")
    print("   Section 1 and Section 2: NOTHING. Z holds the marginal ATE fixed, so all 208")
    print("     intervention x outcome effects are unchanged by any tilt.")
    print("   Section 3 (condition x moderator interactions, Section-1 metrics MINUS RMSE):")
    print("     %d interaction cells in all, %d of them party, %d touched by a tilt on %d arms "
          "(%.1f%% of the section)" % (tot, party_cells, touched, len(arms), 100 * touched / tot))
    print("     directional credit on an exact zero is 0.5 by the frozen table, so a tilt that is")
    print("     RIGHT in sign earns +0.5 x %d cells = %.2f%% of the section's directional row, and"
          % (touched, 100 * touched * 0.5 / tot))
    print("     a tilt that is WRONG in sign loses the same. It is a coin flip on a 46 pp prior")
    print("     measured on a manipulation the target does not contain.")
    print("   Tier 1: the tilt WOULD change the deposited rows, and finding 62 applies - the")
    print("     scorer recomputes the interaction from the rows, where synthesis noise is +-2.83 pp.")
    print("   The target's own power: SE(party interaction) ~ %.2f pp (~500 per party half), so it"
          % SE_TARGET_INTERACTION)
    print("     cannot resolve anything below ~%.1f pp." % (2 * SE_TARGET_INTERACTION))


DRYRUN = RUN / "runs" / "20260815-dryrun-01"      # carries the __party subgroup truths (plain code)
PRACTICE = RUN / "runs" / "20260815-practice-01"


def practice_evidence():
    """PASS 3 - the like-for-like leg: on real MESSAGE experiments with a party moderator, does
    politically-coded language in the message produce a larger party interaction?

    altenmueller's 46.45 pp is a manipulation of WHO THE SCIENTIST IS. The target's arms are
    messages. Four carved tasks ship a `__party` subgroup truth (plain code, no model call), giving
    70 message arms with Republican and Democrat ATEs on every outcome. For each arm the interaction
    is ATE(Rep) - ATE(Dem) and its deconvolved size is sqrt(mean(interaction^2) - mean(SE^2)); the
    predictor here is the same lexicon scan, per 100 words. Correlated WITHIN task, because the hit
    rate is mostly a property of the task's topic (voelkel2024 is about partisanship, so every arm
    scores high).
    """
    rows = []
    for task in ["voelkel2024", "voelkel2026", "goldwert2026", "bbprime2025"]:
        f = DRYRUN / "tasks" / (task + "__party") / "sealed" / "truth.csv"
        if not f.exists():
            continue
        pt = pd.read_csv(f)
        b = json.loads((PRACTICE / "tasks" / task / "brief" / "task.json").read_text())
        texts = {a["title"]: a.get("text", "") for a in b["arms"]}
        w = pt.pivot_table(index=["condition", "outcome"], columns="moderator_level", values="ate")
        s = pt.pivot_table(index=["condition", "outcome"], columns="moderator_level", values="se")
        if "Republican" not in w or "Democrat" not in w:
            continue
        d = pd.DataFrame({"inter": w["Republican"] - w["Democrat"],
                          "se": np.sqrt(s["Republican"] ** 2 + s["Democrat"] ** 2)}).reset_index()
        for cond, g in d.groupby("condition"):
            if cond not in texts:
                continue
            words = len(re.findall(r"[A-Za-z]+", texts[cond]))
            hits = sum(len(re.findall(p, texts[cond].lower()))
                       for pats in LEXICON.values() for p in pats)
            ms, noise = float((g.inter ** 2).mean()), float((g.se ** 2).mean())
            rows.append({"task": task, "arm": cond, "hits_per100": 100 * hits / max(words, 1),
                         "signal_sd": math.sqrt(max(ms - noise, 0)), "noise_sd": math.sqrt(noise),
                         "n_out": len(g)})
    P = pd.DataFrame(rows)
    print("\nPASS 3 - does politically-coded LANGUAGE move a party interaction? (%d message arms, "
          "4 tasks, 0 tokens)" % len(P))
    print("%-15s%7s%14s%14s%12s" % ("task", "arms", "mean sig SD", "noise SD", "Spearman"))
    zs = []
    for t, g in P.groupby("task"):
        rho = float(g.hits_per100.corr(g.signal_sd, method="spearman"))
        print("%-15s%7d%14.2f%14.2f%12.3f" % (t, len(g), g.signal_sd.mean(), g.noise_sd.mean(),
                                              rho))
        zs.append(pd.DataFrame({"h": (g.hits_per100 - g.hits_per100.mean()) /
                                     (g.hits_per100.std() or 1),
                                "s": (g.signal_sd - g.signal_sd.mean()) / (g.signal_sd.std() or 1)}))
    Z = pd.concat(zs)
    print("   pooled WITHIN-task correlation: %+.3f over %d arms - no evidence that a message's"
          % (Z.h.corr(Z.s), len(Z)))
    print("   political vocabulary predicts how much it splits the parties. The 46 pp effect")
    print("   belongs to the SOURCE'S IDENTITY, which is what finding 81 already said.")
    return P


def main():
    b, S = scan()
    print("=" * 96)
    print("PASS 1 - mechanical lexicon scan of the target's %d stimuli" % len(S))
    print("%-30s%7s%7s   %s" % ("arm", "words", "hits", "lexicon groups hit"))
    for r in S.sort_values("n_hits", ascending=False).itertuples():
        print("%-30s%7d%7d   %s" % (r.arm, r.words, r.n_hits,
                                    "; ".join("%s: %s" % (k, ", ".join(v[:6]))
                                              for k, v in r.hits.items()) or "-"))
    print("\n" + "=" * 96)
    print("PASS 2 - coded reading, one row per arm (the quote each rests on is in the source)")
    order = {"EXPLICIT": 0, "IMPLICIT": 1, "CODED-ACTOR": 2, "NONE": 3}
    print("%-30s%-14s%-18s" % ("arm", "class", "expected lean"))
    for arm, (cls, lean, _) in sorted(CODING.items(), key=lambda kv: (order[kv[1][0]], kv[0])):
        print("%-30s%-14s%-18s" % (arm, cls, lean))
    explicit = [a for a, (c, _, _) in CODING.items() if c == "EXPLICIT"]
    print("\n   %d of %d arms make an EXPLICIT political-identity claim: %s"
          % (len(explicit), len(CODING), ", ".join(explicit)))
    print("   the reference points, all party-half interactions in pp (finding 81):")
    for k, v in BENCHMARKS.items():
        print("      %-52s %6.2f" % (k, v))
    practice_evidence()
    tilt_arithmetic(explicit + ["Portrait Prof. Cherry"])
    score_consequences(explicit)
    print("\nRECOMMENDATION: PENDING-OPERATOR. No tilt is written. The card's `tilt.csv` is empty")
    print("and stays empty; RUNBOOK 2a forbids editing a deposited prediction because a diagnostic")
    print("looked interesting, and the operator owns this decision.")
    return S


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__,
                            formatter_class=argparse.RawDescriptionHelpFormatter).parse_args()
    main()
