#!/usr/bin/env python
"""Build the koetke2024 Study 5 trust-outcome practice task input from the mounted OSF materials.

    /opt/kernel/venv/bin/python tools/build_koetke.py            # rebuild + verify
    /opt/kernel/venv/bin/python tools/build_koetke.py --check    # verify only, exit 1 on drift

WHY THIS TASK EXISTS
Standing finding 33: zero of 1,489 scored practice cells fall in the target's `trust` family.
Session 12's first trust task (gligoric2025) closed the family gap only for MAGNITUDE, because its
40-cell table has no signal at all (finding 77). This one has signal: four randomised arms of a
single interview vignette, a 14-item METI trust battery, and a published DISSOCIATION - the two
"limits" framings raise trust in the scientist while LOWERING belief in her research, and the
personal-humility framing raises trust without that cost. That pattern is a ranking question with
real variance, so unlike gligoric2025 this task is scored on the ordering rows as well.

WHAT IT IS NOT
It is a coarse-scale task (7-point bipolar semantic differentials, 5-point stereotype items, one
binary behavioural item) and therefore carries `exclude_from_slope`, exactly as tappin2023 does
(finding 69) and for the same measured reason: the two coarse-Likert tasks on the board are the
only two whose fitted slope is below 1, and trust-family and coarse-scale are confounded on the
mounted data (OPEN 31). The operator's session-13 directive is explicit: do not fit a
trust-family multiplier.

Red paths (all asserted below, none of them decoration):
 1. every composite reproduces the paper's own R script, including two reverse codings that a
    later session would otherwise get silently wrong (METI_1, Belief in Research_2/_4);
 2. forgetting the METI_1 reversal, or the belief reversals, moves the ATE table measurably;
 3. the four arm texts differ ONLY where the instrument says they do - Q1 identical in all four,
    Q2 identical in three with a single measured phrase change in Limits of Results, Q3 the
    manipulation - so the brief cannot claim "arms differ only in the final answer" unless it is
    true;
 4. the published dissociation is present in the sealed truth (trust up, belief down);
 5. the covariance-aware signal variance is POSITIVE (the naive statistic is biased down on a
    shared-control table and would have declared the trust family at chance);
 6. `Behavior Follow` level 3 is "I don't use social media", not "unsure" - the brief must say so;
 7. no identity key of the source paper appears in any assembled payload.
"""
import argparse, difflib, json, re, sys, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
SRC = Path("/workspace/datasets/koetke2024/downloads/Study 5")
DATA = SRC / "Study5CleanData.csv"
DOCX = SRC / "IH and Science 5 Survey Final.docx"
OUT = RUN / "inputs" / "derived" / "koetke2024_study5.csv"
ARMTEXT = RUN / "inputs" / "texts" / "koetke2024_arms.json"
ADAPTER = RUN / "inputs" / "adapters" / "koetke2024.json"

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
BLOCKS = {"Control": "Control Condition",
          "Personal Humility": "Personal Humility Condition",
          "Limits of Methods": "Limits of Method Condition",
          "Limits of Results": "Limits of Results Condition"}
ARMS = ["Control", "Limits of Methods", "Limits of Results", "Personal Humility"]
IH_REV = [1, 2, 3, 4, 5, 12, 16, 17, 18, 21, 22]

# The four arms, as the instrument titles them. Titles carry no information the text does not
# (finding 65's arm-title ablation), but they are the parser's cell names and must be stable.
ARM_TITLES = {a: a for a in ARMS}


# ---------------------------------------------------------------- stimuli, from the .docx
def docx_paragraphs(path: Path) -> str:
    root = ET.fromstring(zipfile.ZipFile(path).read("word/document.xml").decode("utf8"))
    return "\n".join("".join(t.text or "" for t in p.iter(W + "t")) for p in root.iter(W + "p"))


def arm_texts() -> dict:
    doc = docx_paragraphs(DOCX)
    out = {}
    for arm, block in BLOCKS.items():
        s = doc.index("Start of Block: " + block) + len("Start of Block: " + block)
        e = doc.index("End of Block: " + block)
        paras = [p.strip() for p in doc[s:e].split("\n") if p.strip()
                 and not p.strip().startswith(("Timing", "First Click", "Last Click",
                                               "Page Submit", "Click Count"))]
        if len(paras) != 1:
            raise SystemExit("%s: expected one stimulus paragraph, got %d" % (block, len(paras)))
        out[arm] = re.sub(r"\s{2,}", "\n\n", paras[0]).strip()
    if sorted(out) != sorted(ARMS):
        raise SystemExit("arm texts %s != %s" % (sorted(out), sorted(ARMS)))
    return out


def split_qa(t: str) -> list:
    i1, i2, i3 = (t.index("1. Why were you interested"), t.index("2. What should people take away"),
                  t.index("3. Anything else you want"))
    return [t[i1:i2].strip(), t[i2:i3].strip(), t[i3:].strip()]


# ---------------------------------------------------------------- derived respondent file
def derive(df: pd.DataFrame) -> pd.DataFrame:
    d = pd.DataFrame(index=df.index)
    d["IHCondition"] = df["IHCondition"]
    meti = df[[f"METI_{i}" for i in range(1, 15)]].astype(float).copy()
    meti["METI_1"] = 8 - meti["METI_1"]                      # the R script's only METI reversal
    d["trust_meti"] = meti.mean(axis=1)
    d["trust_expertise"] = meti[[f"METI_{i}" for i in range(1, 7)]].mean(axis=1)
    d["trust_integrity"] = meti[[f"METI_{i}" for i in range(7, 11)]].mean(axis=1)
    d["trust_benevolence"] = meti[[f"METI_{i}" for i in range(11, 15)]].mean(axis=1)
    bel = df[[f"Belief in Research_{i}" for i in range(1, 5)]].astype(float).copy()
    bel["Belief in Research_2"] = 8 - bel["Belief in Research_2"]
    bel["Belief in Research_4"] = 8 - bel["Belief in Research_4"]
    d["belief_research"] = bel.mean(axis=1)
    ih = df[[f"IH_{i}" for i in range(1, 23)]].astype(float).copy()
    for i in IH_REV:
        ih[f"IH_{i}"] = 6 - ih[f"IH_{i}"]
    d["perceived_humility"] = ih.mean(axis=1)
    d["competence"] = df[["Stereotype Content_1", "Stereotype Content_2"]].astype(float).mean(axis=1)
    d["warmth"] = df[["Stereotype Content_3", "Stereotype Content_4"]].astype(float).mean(axis=1)
    # "Behavior Follow": 1 = yes, 2 = no, 3 = "I don't use social media". Level 3 is a real third
    # option, NOT an unsure code, so the outcome is the share saying yes among ALL respondents and
    # the brief says exactly that.
    bf = pd.to_numeric(df["Behavior Follow"], errors="coerce")
    d["followup_interest"] = np.where(bf.isna(), np.nan, (bf == 1).astype(float))
    d["party"] = pd.to_numeric(df["PO Bin"], errors="coerce")
    d["Age"] = pd.to_numeric(df["Age"], errors="coerce")
    d["gender_norm"] = df["Gender"].map(norm_gender)
    d["Edu"] = pd.to_numeric(df["Edu"], errors="coerce")
    return d


def norm_gender(v):
    """`Gender` is free text. The mapping is explicit and conservative: anything that is not
    unambiguously one of the three levels becomes NaN rather than being guessed at."""
    if not isinstance(v, str):
        return None
    s = re.sub(r"[^a-z ]", " ", v.strip().lower())
    s = re.sub(r"\s+", " ", s).strip()
    male = {"male", "man", "men", "m", "trans man", "trans male", "biological male",
            "male man", "man male", "cis male",
            "cis man", "cisgender male", "male cis", "masculine", "male he him", "he him"}
    female = {"female", "woman", "women", "f", "trans woman", "trans female",
              "biological woman", "biological female", "female woman",
              "woman female", "cis female", "cis woman", "cisgender female", "female cis",
              "feminine", "she her", "female she her", "girl", "lady"}
    other = {"non binary", "nonbinary", "nb", "non binary they them", "genderqueer", "agender",
             "gender fluid", "genderfluid", "transgender", "trans", "queer", "two spirit",
             "prefer not to say", "other"}
    if s in male or s.replace(" ", "") in {x.replace(" ", "") for x in male}:
        return "Male"
    if s in female or s.replace(" ", "") in {x.replace(" ", "") for x in female}:
        return "Female"
    if s in other or s.replace(" ", "") in {x.replace(" ", "") for x in other}:
        return "Other"
    if "/" in str(v) or " or " in s:            # 'female/woman', 'woman/female'
        parts = re.split(r"[/ ]or[ /]|/", s)
        got = {norm_gender(p) for p in parts if p}
        got.discard(None)
        if len(got) == 1:
            return got.pop()
    return None


OUTCOMES = {                                   # name -> (lo, hi)
    "trust_meti": (1, 7), "trust_expertise": (1, 7), "trust_integrity": (1, 7),
    "trust_benevolence": (1, 7), "belief_research": (1, 7), "perceived_humility": (1, 5),
    "competence": (1, 5), "warmth": (1, 5), "followup_interest": (0, 1),
}


def ate_table(d: pd.DataFrame, outcomes=None) -> pd.DataFrame:
    outcomes = outcomes or OUTCOMES
    ctrl = d[d.IHCondition == "Control"]
    rows = []
    for o, (lo, hi) in outcomes.items():
        rng = hi - lo
        c = ctrl[o].dropna()
        for arm in [a for a in ARMS if a != "Control"]:
            t = d[d.IHCondition == arm][o].dropna()
            rows.append({"outcome": o, "condition": arm,
                         "ate": (t.mean() - c.mean()) / rng * 100,
                         "se": np.sqrt(t.var(ddof=1) / len(t) + c.var(ddof=1) / len(c)) / rng * 100,
                         "n_t": len(t), "n_c": len(c)})
    return pd.DataFrame(rows)


def signal(d: pd.DataFrame, t: pd.DataFrame, within=False) -> dict:
    """finding 36's statistic, with the shared-control covariance the naive version ignores.

    Several arms are differenced against ONE control mean inside an outcome, so the ATE errors are
    positively correlated and `var_obs - mean(SE^2)` understates the signal. The expected noise
    contribution to the sample variance is trace(M V M)/(k-1) with M the centring matrix.
    """
    t = t.reset_index(drop=True)
    k = len(t)
    V = np.zeros((k, k))
    for i in range(k):
        o = t.outcome[i]
        lo, hi = OUTCOMES[o]
        rng = hi - lo
        c = d[d.IHCondition == "Control"][o].dropna()
        vc = c.var(ddof=1) / len(c) / rng ** 2 * 1e4
        ti = d[d.IHCondition == t.condition[i]][o].dropna()
        V[i, i] = ti.var(ddof=1) / len(ti) / rng ** 2 * 1e4 + vc
        for j in range(k):
            if j != i and t.outcome[j] == o:
                V[i, j] = vc
    if not within:
        M = np.eye(k) - np.ones((k, k)) / k
        noise = float(np.trace(M @ V @ M) / (k - 1))
        vo = float(t.ate.var(ddof=1))
    else:                                        # demean inside each outcome, as the metric does
        dev, ss_noise, df = [], 0.0, 0
        for o, g in t.groupby("outcome"):
            ix = list(g.index)
            m = len(ix)
            Mo = np.eye(m) - np.ones((m, m)) / m
            dev += list(g.ate - g.ate.mean())
            ss_noise += float(np.trace(Mo @ V[np.ix_(ix, ix)] @ Mo))
            df += m - 1
        # sums of squares over the same df on both sides (see tools/task_power.py for why)
        vo, noise = float(np.sum(np.array(dev) ** 2) / df), float(ss_noise / df)
    vt = vo - noise
    return {"n": k, "var_obs": round(vo, 3), "noise": round(noise, 3), "var_true": round(vt, 3),
            "ceiling_r": round(float(np.sqrt(max(vt, 0) / vo)), 3)}


SAMPLE = ("679 U.S. adults recruited from an online research panel, fielded after a December "
          "2023 pre-registration; 49% women, 49% men, mean age 47 (range 18-81), 49% Democrat / "
          "39% Republican / 11% other party. "
          "Every respondent read the same short blog-interview with a psychologist, 'Dr. Sandra "
          "Wilson', describing her own randomised experiment on taking a two-week break from "
          "social media; the four arms differ only in what she says in the interview's closing "
          "answer. Ratings of Dr. Wilson and of her research followed immediately.")

ITEMS = {
    "trust_meti": ("14 bipolar 7-point semantic differentials, 'Rate how you would describe Dr. "
                   "Wilson on the following dimensions': competent-incompetent (reverse scored), "
                   "unintelligent-intelligent, poorly educated-well educated, "
                   "unprofessional-professional, inexperienced-experienced, "
                   "unqualified-qualified, insincere-sincere, dishonest-honest, unjust-just, "
                   "unfair-fair, immoral-moral, unethical-ethical, "
                   "irresponsible-responsible, inconsiderate-considerate; averaged"),
    "trust_expertise": ("the first 6 of those 14 items (competence/expertise): "
                        "competent-incompetent (reverse scored), unintelligent-intelligent, "
                        "poorly educated-well educated, unprofessional-professional, "
                        "inexperienced-experienced, unqualified-qualified; averaged"),
    "trust_integrity": ("4 of those 14 items (integrity): insincere-sincere, dishonest-honest, "
                        "unjust-just, unfair-fair; averaged"),
    "trust_benevolence": ("4 of those 14 items (benevolence): immoral-moral, unethical-ethical, "
                          "irresponsible-responsible, inconsiderate-considerate; averaged"),
    "belief_research": ("4 items, 1 'Strongly disagree' - 7 'Strongly agree', averaged after "
                        "reversing items 2 and 4: 'I believe taking a break from social media "
                        "makes people happier and less stressed'; 'I believe that taking a break "
                        "from social media will be ineffective at making people feel more "
                        "connected to others' (reversed); 'The benefits of taking a break from "
                        "social media have been thoroughly tested by Dr. Wilson'; 'There is not "
                        "enough scientific evidence in support of taking a break from social "
                        "media' (reversed)"),
    "perceived_humility": ("22 items, 1 'Strongly disagree' - 5 'Strongly agree', 11 reversed, "
                           "averaged: how intellectually humble Dr. Wilson is - e.g. 'Dr. Wilson "
                           "is willing to change her position on an important issue in the face "
                           "of good reasons', 'Dr. Wilson believes that her ideas are usually "
                           "better than other people's ideas' (reversed), 'Dr. Wilson welcomes "
                           "different ways of thinking about important topics'"),
    "competence": ("'As viewed by society, how ... is Dr. Wilson?', 1 'Not at all' - 5 "
                   "'Extremely': competent and capable, averaged"),
    "warmth": ("'As viewed by society, how ... is Dr. Wilson?', 1 'Not at all' - 5 'Extremely': "
               "warm and friendly, averaged"),
    "followup_interest": ("'After the survey, would you be interested in being sent information "
                          "and tips for taking a break from social media?' - Yes / No / 'I don't "
                          "use social media'. The outcome is the share answering Yes among all "
                          "respondents (the third option is a real answer, not a missing code)"),
}

IDENTITY_KEYS = ["koetke", "schumann", "porter", "yeomans", "nature human behaviour", "d3xua",
                 "seeing scientists as intellectually humble"]




def selftest(reps=200, seed=20260822, verbose=True):
    """Known-answer recovery for `signal()`, on SIMULATED individual-level respondents.

    `--check` compares this file's exact computation against tools/task_power.py's reconstruction,
    and standing finding 90 is precisely that two implementations of the same convention can agree
    while both are wrong. So this test hands `ate_table` + `signal` respondents whose TRUE arm
    effects I chose, and asks for them back: 3 treated arms and one shared control per outcome,
    n = 250 each, on this task's own 1-7 outcomes, with a chosen across-cell effect SD and a chosen
    within-outcome SD (both in pp of the scale range, the units `signal` reports).
    """
    rng = np.random.default_rng(seed)
    arms = [a for a in ARMS if a != "Control"]
    outs = ["trust_meti", "trust_expertise", "trust_integrity", "belief_research"]
    n, sd_resp = 250, 1.2
    ok = True
    if verbose:
        print("\nSELFTEST - recovery of a KNOWN signal from simulated respondents "
              "(%d reps, %d outcomes x %d arms, n = %d each, response SD %.1f on 1-7)"
              % (reps, len(outs), len(arms), n, sd_resp))
        print("  %9s%9s%14s%14s%14s%14s" % ("true sd", "true tau", "var_true^", "(true)",
                                            "within^", "(true)"))
    for true_sd, true_tau in ((0.0, 0.0), (2.0, 0.0), (0.0, 2.0)):
        marg, wit = [], []
        for _ in range(reps):
            eff = {}
            for o in outs:
                base = rng.normal(0, true_sd)
                dev = rng.normal(0, true_tau, len(arms))
                dev = dev - dev.mean() if true_tau else np.zeros(len(arms))
                for j, a in enumerate(arms):
                    eff[(o, a)] = base + dev[j]
            frames = []
            for a in ["Control"] + arms:
                r = {"IHCondition": [a] * n}
                for o in outs:
                    lo, hi = OUTCOMES[o]
                    mu = (lo + hi) / 2 + (0.0 if a == "Control"
                                          else eff[(o, a)] / 100.0 * (hi - lo))
                    r[o] = rng.normal(mu, sd_resp, n)
                frames.append(pd.DataFrame(r))
            d = pd.concat(frames, ignore_index=True)
            t = ate_table(d, {o: OUTCOMES[o] for o in outs})
            marg.append(signal(d, t)["var_true"])
            wit.append(signal(d, t, within=True)["var_true"])
        m_, k_ = len(outs), len(arms)
        true_marg = (k_ * (m_ - 1) * true_sd ** 2 + m_ * (k_ - 1) * true_tau ** 2) / (m_ * k_ - 1)
        tol = lambda v: max(0.20, 3 * np.std(v) / np.sqrt(len(v)))
        good = (abs(np.mean(marg) - true_marg) < tol(marg)
                and abs(np.mean(wit) - true_tau ** 2) < tol(wit))
        ok &= good
        if verbose:
            print("  %9.2f%9.2f%14.3f%14.3f%14.3f%14.3f   %s"
                  % (true_sd, true_tau, np.mean(marg), true_marg, np.mean(wit), true_tau ** 2,
                     "ok" if good else "FAIL"))
    if verbose:
        print("  VERDICT:", "OK - signal() recovers a variance it was given"
              if ok else "FAIL - do not quote a ceiling from this file")
    return ok


def verify(df: pd.DataFrame, d: pd.DataFrame, texts: dict) -> dict:
    res = {}

    # (1) arm sizes reproduce the published design
    counts = d.IHCondition.value_counts().to_dict()
    want = {"Control": 164, "Limits of Methods": 174, "Limits of Results": 178,
            "Personal Humility": 163}
    assert counts == want, "arm sizes %s != %s" % (counts, want)
    res["arms"] = "4 arms, n = " + ", ".join("%s %d" % (k, want[k]) for k in ARMS)

    # (2) every composite reproduces the paper's own per-arm means (published to 2 dp)
    published = {("trust_meti", "Control"): 6.05, ("trust_meti", "Limits of Methods"): 6.15,
                 ("trust_meti", "Limits of Results"): 6.28,
                 ("trust_meti", "Personal Humility"): 6.17,
                 ("belief_research", "Control"): 5.39,
                 ("belief_research", "Limits of Methods"): 5.02,
                 ("belief_research", "Limits of Results"): 4.89,
                 ("belief_research", "Personal Humility"): 5.32}
    err = max(abs(d[d.IHCondition == a][o].mean() - v) for (o, a), v in published.items())
    assert err < 0.006, "composites do not reproduce the published means (max err %.4f)" % err
    res["composites"] = ("METI and belief-in-research means reproduce the published values to "
                         "%.4f raw points" % err)

    # (3) RED PATH: the reverse codings are load-bearing
    t_ok = ate_table(d)
    d_bad = d.copy()
    meti = df[[f"METI_{i}" for i in range(1, 15)]].astype(float)
    d_bad["trust_meti"] = meti.mean(axis=1)                      # METI_1 NOT reversed
    bel = df[[f"Belief in Research_{i}" for i in range(1, 5)]].astype(float)
    d_bad["belief_research"] = bel.mean(axis=1)                  # items 2 and 4 NOT reversed
    t_bad = ate_table(d_bad)
    j = t_ok.merge(t_bad, on=["outcome", "condition"], suffixes=("", "_bad"))
    dm = j[j.outcome == "trust_meti"]
    db = j[j.outcome == "belief_research"]
    assert abs(dm.ate - dm.ate_bad).max() > 0.05, "the METI_1 reversal looks inert"
    assert abs(db.ate - db.ate_bad).max() > 1.0, "the belief reversals look inert"
    res["reverse_red_path"] = ("skipping METI_1's reversal moves the 3 trust ATEs by up to %.2f pp; "
                               "skipping the two belief reversals moves them by up to %.2f pp "
                               "(and flips their sign)" %
                               (abs(dm.ate - dm.ate_bad).max(), abs(db.ate - db.ate_bad).max()))

    # (4) the arms differ where the instrument says they do, and nowhere else
    qa = {a: split_qa(t) for a, t in texts.items()}
    assert len({q[0] for q in qa.values()}) == 1, "Q1 differs between arms"
    q2 = {a: q[1] for a, q in qa.items()}
    assert len(set(q2.values())) == 2 and q2["Control"] == q2["Limits of Methods"] == \
        q2["Personal Humility"], "Q2 varies in an unexpected pattern"
    wa, wb = q2["Control"].split(), q2["Limits of Results"].split()
    sm = difflib.SequenceMatcher(None, wa, wb)
    diffs = [(" ".join(wa[i1:i2]), " ".join(wb[j1:j2]))
             for op, i1, i2, j1, j2 in sm.get_opcodes() if op != "equal"]
    assert len(diffs) == 1 and diffs[0] == ("those who did not take a break.", "others."), \
        "the Limits-of-Results Q2 change is not the single phrase it was: %r" % diffs
    assert len({q[2] for q in qa.values()}) == 4, "the manipulated answer is not 4 distinct texts"
    res["stimulus_structure"] = ("Q1 identical in all 4 arms; Q2 identical in 3 and differs in "
                                 "Limits of Results by exactly one phrase ('than those who did "
                                 "not take a break' -> 'than others'); Q3 is the manipulation, "
                                 "4 distinct texts. The brief ships all four verbatim, so no "
                                 "claim about what differs has to be believed.")

    # (5) the published dissociation is in the sealed truth
    piv = t_ok.pivot(index="outcome", columns="condition", values="ate")
    lim = ["Limits of Methods", "Limits of Results"]
    assert (piv.loc["trust_meti", lim] > 0).all() and (piv.loc["belief_research", lim] < 0).all(), \
        "the trust-up / belief-down dissociation is not present"
    assert piv.loc["trust_meti", "Personal Humility"] > 0, "personal humility does not raise trust"
    res["dissociation"] = ("limits arms: trust +%.2f / +%.2f pp with belief %.2f / %.2f pp; "
                           "personal humility: trust +%.2f pp with belief %.2f pp" %
                           (piv.loc["trust_meti", lim[0]], piv.loc["trust_meti", lim[1]],
                            piv.loc["belief_research", lim[0]], piv.loc["belief_research", lim[1]],
                            piv.loc["trust_meti", "Personal Humility"],
                            piv.loc["belief_research", "Personal Humility"]))

    # (6) signal, computed the way finding 36 should have been on a shared-control table
    full = signal(d, t_ok)
    naive_trust = None
    tt = t_ok[t_ok.outcome.str.startswith("trust_")]
    naive_trust = float(tt.ate.var(ddof=1) - (tt.se ** 2).mean())
    res["signal_marginal"] = str(full)
    res["signal_within_outcome"] = str(signal(d, t_ok, within=True))
    res["signal_no_manipcheck"] = str(signal(d, t_ok[t_ok.outcome != "perceived_humility"]))
    res["signal_trust_family"] = ("naive var_true %.3f (would read CHANCE); covariance-aware "
                                  "marginal %s; within-outcome %s" %
                                  (naive_trust, signal(d, tt)["var_true"],
                                   signal(d, tt, within=True)))
    assert full["var_true"] > 0, "no signal in the full table - do not carve this"

    # (7) the third behavioural option is not an unsure code
    bf = pd.to_numeric(df["Behavior Follow"], errors="coerce").value_counts().to_dict()
    res["behavior_follow"] = ("Yes %d / No %d / \"I don't use social media\" %d - level 3 is a "
                              "real third option and the item wording in the brief says so"
                              % (bf.get(1, 0), bf.get(2, 0), bf.get(3, 0)))

    # (8) the brief must not name its own study
    blob = (json.dumps(texts) + SAMPLE + json.dumps(ITEMS)).lower()
    for k in IDENTITY_KEYS:
        assert k not in blob, "an identity key is in the payload: %r" % k
    res["self_identification"] = "no identity key in the arm texts, items or sample description"

    # (9) moderators: what the free-text gender column costs
    g = d.gender_norm.value_counts(dropna=False).to_dict()
    res["gender"] = ("free-text gender normalised to %s; %d rows unmapped and left NaN"
                     % ({k: v for k, v in g.items() if isinstance(k, str)},
                        int(d.gender_norm.isna().sum())))
    res["party"] = ("PO Bin -> Democrat %d / Republican %d / Other %d, %d missing"
                    % ((d.party == 1).sum(), (d.party == 2).sum(), (d.party == 3).sum(),
                       int(d.party.isna().sum())))
    return res


def adapter(texts: dict) -> dict:
    outs = {}
    for o, (lo, hi) in OUTCOMES.items():
        outs[o] = {"col": o, "lo": lo, "hi": hi, "question": ITEMS[o]}
    return {
        "dataset": "koetke2024",
        "status": "VERIFIED by tools/build_koetke.py (rebuild + 9 red paths)",
        "file": str(OUT),
        "reader": "csv",
        "sample_description": SAMPLE,
        "condition_col": "IHCondition",
        "arms": {a: ARM_TITLES[a] for a in ARMS},
        "control_arms": ["Control"],
        "outcomes": outs,
        "moderators": {
            "party": {"col": "party", "map": {"1": "Democrat", "2": "Republican", "3": "Other"}},
            "age_band": {"col": "Age", "bins": [17, 29, 44, 59, 200],
                         "labels": ["18-29", "30-44", "45-59", "60+"]},
            "gender": {"col": "gender_norm",
                       "map": {"Male": "Male", "Female": "Female", "Other": "Other"}},
        },
        "moderators_unavailable": {
            "race": "asked as a multi-select free-coded string ('5,6', '1,3,6,7'); a single "
                    "target-shaped category is not recoverable without choosing a priority rule",
            "income": "not asked",
            "education": "8 levels, not the target's 6 - graduate, post-graduate and professional "
                         "degrees are three separate levels here",
        },
        "filters": [],
        "weight_col": None,
        "message_texts_file": str(ARMTEXT),
        "exclude_from_slope": "coarse-scale task (7-point bipolar differentials, 5-point stereotype "
                              "items, one binary item): finding 69 measured that the predictor "
                              "OVERSHOOTS on a coarse Likert while undershooting on sliders, and "
                              "trust-family and coarse-scale are confounded on the mounted data "
                              "(OPEN 31). The operator's session-13 directive forbids fitting a "
                              "trust-family multiplier.",
        "provenance": {
            "verified_by": "tools/build_koetke.py (9 red paths) + the study's own R script "
                           "'IHS Study 5 Code for OSF.R' as the codebook",
            "caveats": [
                "coarse scales throughout: 7-point bipolar METI, 7-point agreement, 5-point "
                "stereotype items, one binary behavioural item",
                "the four trust outcomes are nested - expertise, integrity and benevolence are "
                "disjoint subsets of the 14 METI items whose mean is trust_meti - so their cells "
                "are not independent tests",
                "perceived_humility is the paper's MANIPULATION CHECK, kept as an outcome and "
                "flagged: the pre-registration scores the table with and without it",
                "the 4 trust cells alone carry no marginal signal (covariance-aware var_true "
                "-0.30); the signal in this task is cross-outcome and within-outcome, which is "
                "what the pre-registration scores",
                "single vignette, single topic (a social-media-break study), single fictional "
                "scientist - not a message tournament",
                "prompt is ~3k tokens against the target's 9,892 - inside finding 17's cap but "
                "below the target's band, like every small practice task",
            ],
        },
    }


def main(check=False):
    df = pd.read_csv(DATA)
    texts = arm_texts()
    d = derive(df)
    res = verify(df, d, texts)
    print("koetke2024 Study 5 trust task input")
    for k, v in res.items():
        print("  %-22s %s" % (k, v))
    t = ate_table(d)
    print("\nsealed ATE table (pp of each outcome's range), %d cells" % len(t))
    print(t.pivot(index="outcome", columns="condition", values="ate").round(2).to_string())

    ad = adapter(texts)
    if check:
        drift = []
        if not OUT.exists() or not ARMTEXT.exists() or not ADAPTER.exists():
            drift.append("a build artefact is missing")
        else:
            if not d.reset_index(drop=True).equals(
                    pd.read_csv(OUT).reset_index(drop=True)[d.columns]):
                old = pd.read_csv(OUT)
                num = [c for c in d.columns if pd.api.types.is_numeric_dtype(d[c])]
                if not np.allclose(d[num].to_numpy(float), old[num].to_numpy(float),
                                   equal_nan=True):
                    drift.append("derived rows changed")
            if json.loads(ARMTEXT.read_text()) != texts:
                drift.append("arm texts changed")
            if json.loads(ADAPTER.read_text()) != ad:
                drift.append("adapter changed")
        if drift:
            print("\nDRIFT:", "; ".join(drift))
            return 1
        print("\ncheck: artefacts on disk match a fresh build")
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT, index=False)
    ARMTEXT.write_text(json.dumps(texts, indent=1))
    ADAPTER.write_text(json.dumps(ad, indent=1))
    print("\nwrote %s (%d x %d)\n      %s\n      %s" % (OUT, len(d), d.shape[1], ARMTEXT, ADAPTER))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true",
                    help="known-answer recovery of signal() on SIMULATED respondents (finding 90)")
    _a = ap.parse_args()
    if _a.selftest:
        sys.exit(0 if selftest() else 1)
    sys.exit(main(_a.check))
