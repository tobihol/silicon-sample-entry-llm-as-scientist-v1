#!/usr/bin/env python
"""Build trust practice task #4 from orchinik2024's Bovitz message experiment, and check it.

    /opt/kernel/venv/bin/python tools/build_orchinik.py            # build + all checks
    /opt/kernel/venv/bin/python tools/build_orchinik.py --check    # checks only
    /opt/kernel/venv/bin/python tools/build_orchinik.py --selftest # known-answer recovery

Why this task exists. Standing finding 33: zero of the harness's scored practice cells are in the
TRUST family, and the target study is about trust in climate scientists. Sessions 12-14 carved
three trust tasks and all three are COARSE scales (gligoric 1-7, koetke 1-7/1-5, altenmueller 1-7),
so trust-family and scale-format stayed confounded (findings 69, 83). This is the first trust-family
task on the target's own format: **0-100 sliders, message arms, a US quota-matched sample**, and the
outcomes are perceptions of climate scientists themselves.

What it is. A between-subjects 3-arm experiment inside a larger within-subject elicitation: after a
block of pre-treatment priors, each respondent reads either a neutral transition (control), a
history-of-science passage (`skill`) or an institutions-of-science passage (`trust`), and then gives
25 post-treatment 0-100 judgements - five conditional-belief items and twenty scientist-perception
items, each elicited at a stated consensus level of 50 / 75 / 90 / 97 / 99 out of 100 scientists.

The conditional structure is the thing to get right, and it is carved with NOTHING collapsed: every
(item family x consensus level) pair is its own outcome, 25 outcomes x 2 treatment arms = 50 cells.
Collapsing the five levels into one mean per family is a judgement call that would also delete the
consensus gradient, which is the study's whole design; the collapsed 5-outcome table is computed
here as a declared SECONDARY and reported beside the primary, never instead of it.

Five things this file exists to prevent, each with a red path in `--check`:

  * forgetting `drop == FALSE`. The published file carries all 3,478 rows including 367
    pre-randomization dropouts with a blank `condition` and 554 respondents who are missing at
    least one consensus item. The authors delete both listwise; keeping them moves every ATE;
  * reading the derived `uni_sci_trust` / `priv_sci_trust` columns, which are 100% NA in the
    published file (the R recode compares strings against numeric codes);
  * the junk ages (0.1, 1111) contaminating `age_band`;
  * swapping the two arms. `condition == "skill"` is the HISTORY-of-science passage and
    `condition == "trust"` is the INSTITUTIONS-of-science passage - the labels name the construct
    each passage targets, not its content, and getting them the wrong way round would silently
    relabel every cell. Checked against the instrument's own block text;
  * treating the PRE-treatment prior sliders as outcomes. They are on the same 0-100 grid, in the
    same file, and they are measured before randomization: as a task they are pure noise
    (attainable-r ceiling 0.000) and they would silently drag any pooled slope toward zero.

Recon: `/workspace/datasets/orchinik2024/README.md` (verified 2026-08-17 against the file and the
instrument). The authors' `bovitz_data_clean.R` is the codebook; `analysis_supplements.Rmd` line 124
hard-codes the sample this build must reproduce ("2545 total, 847 control, 837 history, 861
institutions").
"""
import argparse, json, re, sys, zipfile
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
SRC = Path("/workspace/datasets/orchinik2024/downloads")
RAW = SRC / "data" / "final_clean.csv"
DOCX = SRC / "qualtrics" / "Bovitz qualtrics.docx"
DERIVED = RUN / "inputs" / "derived" / "orchinik2024_bovitz.csv"
TEXTS = RUN / "inputs" / "texts" / "orchinik2024_arms.json"
ADAPTER = RUN / "inputs" / "adapters" / "orchinik2024.json"

LEVELS = [50, 75, 90, 97, 99]
FAMILIES = {
    "belief_cc": ("P_cc_given_cons%d", "belief"),
    "bias_pro": ("P_pro_bias_given_cons%d", "perception"),
    "bias_anti": ("P_anti_bias_given_cons%d", "perception"),
    "skill_pro": ("P_pro_skill_given_cons%d", "perception"),
    "skill_anti": ("P_anti_skill_given_cons%d", "perception"),
}
ARMS = {"control": "Control", "skill": "History of science",
        "trust": "Institutions of science"}
CONTROL = "Control"
PRIORS = ["prior_cc_occur", "prior_consensus_num", "prior_sci_unbiased",
          "P_E_yes_given_cc_unbiased", "P_E_no_given_no_cc_unbiased"]

STEM = ("Every respondent saw this matrix question after the passage: 'Suppose that 100 "
        "randomly-selected climate scientists were asked whether or not they agree that "
        "human-caused climate change is happening. For each of the levels of agreement below, ...' "
        "with one 0-100 slider row per level of agreement (50, 75, 90, 97 and 99 out of 100). ")
BIAS_DEF = ("The question defines the term first: 'Let's say that a scientist is \"extremely "
            "biased\" if they always express the same opinion about whether human-caused climate "
            "change is occurring, regardless of what the evidence suggests. That means they would "
            "always agree or disagree, no matter what.' ")
SKILL_DEF = ("The question defines the term first: 'Let's say that a scientist is \"capable\" and "
             "unbiased if they have the skills to correctly identify whether climate change is "
             "occurring from available evidence. In other words, they have arrived at their "
             "conclusion because of skill.' ")
QUESTION = {
    "belief_cc": (STEM + "The row asks: 'what do you think is the likelihood that human-caused "
                  "climate change is occurring?' Slider 0 = extremely unlikely, 100 = extremely "
                  "likely. HIGHER = stronger belief that climate change is happening."),
    "bias_pro": (STEM + BIAS_DEF + "The row asks: 'How likely do you think it is that a random "
                 "climate scientist who expresses that human-caused climate change IS occurring "
                 "is extremely biased?' Slider 0 = extremely unlikely, 100 = extremely likely. "
                 "HIGHER = MORE perceived bias in mainstream climate scientists, i.e. LESS trust."),
    "bias_anti": (STEM + BIAS_DEF + "The row asks: 'How likely do you think it is that a random "
                  "climate scientist who expresses that human-caused climate change is NOT "
                  "occurring is extremely biased?' Slider 0 = extremely unlikely, 100 = extremely "
                  "likely. HIGHER = MORE perceived bias in dissenting climate scientists."),
    "skill_pro": (STEM + SKILL_DEF + "The row asks: 'How likely do you think it is that a random "
                  "and unbiased climate scientist who expresses that human-caused climate change "
                  "IS occurring is capable, meaning they arrived at this conclusion due to "
                  "skill?' Slider 0 = extremely unlikely, 100 = extremely likely. HIGHER = MORE "
                  "perceived skill in mainstream climate scientists, i.e. MORE trust."),
    "skill_anti": (STEM + SKILL_DEF + "The row asks: 'How likely do you think it is that a random "
                   "and unbiased climate scientist who expresses that human-caused climate change "
                   "is NOT occurring is capable, meaning they arrived at this conclusion due to "
                   "skill?' Slider 0 = extremely unlikely, 100 = extremely likely. HIGHER = MORE "
                   "perceived skill in dissenting climate scientists."),
}


# --------------------------------------------------------------------------------------------
# the instrument, read at BUILD time so the shipped stimulus is provably the one respondents saw
def docx_paragraphs(path=DOCX):
    xml = zipfile.ZipFile(path).read("word/document.xml").decode("utf8")
    out = []
    for p in re.findall(r"<w:p\b.*?</w:p>", xml, re.S):
        t = "".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", p, re.S))
        out.append(re.sub(r"<[^>]+>", "", t).strip())
    return out


def stimuli():
    """The three arms' texts, straight out of the survey document."""
    paras = docx_paragraphs()
    got = {}
    for p in paras:
        for tag, arm in (("control text ", CONTROL), ("Skill Intervention ", ARMS["skill"]),
                         ("Trust Intervention ", ARMS["trust"])):
            if p.startswith(tag) and arm not in got:
                got[arm] = " ".join(p[len(tag):].split())
    # every arm ends with the same transition sentence; the passage is what differs
    return got


def item_texts():
    """The five outcome-family question texts, straight out of the survey document."""
    paras = docx_paragraphs()
    keys = {"cc belief given cons ": "belief_cc", "pro trust given cons ": "bias_pro",
            "ant trust given cons ": "bias_anti", "pro skill given cons ": "skill_pro",
            "ant skill given cons ": "skill_anti"}
    got = {}
    for p in paras:
        for tag, fam in keys.items():
            if p.startswith(tag) and fam not in got:
                got[fam] = " ".join(p[len(tag):].split())
    return got


# --------------------------------------------------------------------------------------------
def load(apply_drop=True, clean_age=True):
    d = pd.read_csv(RAW, low_memory=False)
    d = d[d.condition.isin(ARMS)].copy()
    if apply_drop:
        d = d[~d["drop"].astype(bool)].copy()
    d["arm"] = d.condition.map(ARMS)
    age = pd.to_numeric(d.age, errors="coerce")
    if clean_age:
        age = age.where((age >= 18) & (age <= 110))
    d["age_clean"] = age
    d["age_band"] = pd.cut(age, [17, 29, 44, 59, 200],
                           labels=["18-29", "30-44", "45-59", "60+"])
    d["gender_norm"] = pd.to_numeric(d.gender, errors="coerce").map(
        {1: "Male", 2: "Female", 5: "Other", 6: "Other"})
    d["party_norm"] = d.Party.map({"Dem": "Democrat", "Rep": "Republican", "Ind": "Independent"})
    d["race_norm"] = d.race.astype(str).map(_race)
    d["education_norm"] = pd.to_numeric(d.edu, errors="coerce").map(
        {1: "Less than high school", 2: "High school diploma / GED",
         4: "Some college or Associate's degree", 5: "Bachelor's degree"})
    d["income_norm"] = pd.to_numeric(d.income, errors="coerce").map(
        {1: "Less than $30,000", 4: "$56,000 to $99,999", 5: "$56,000 to $99,999",
         6: "$100,000 to $167,999"})
    return d.reset_index(drop=True)


def _race(v):
    """Qualtrics multi-select. Any Hispanic code -> Hispanic/Latino (US convention); otherwise a
    single code maps to its target level and any remaining multi-code answer is `Other`."""
    codes = [c for c in str(v).split(",") if c.strip().isdigit()]
    if not codes:
        return None
    if "11" in codes:
        return "Hispanic / Latino"
    if len(codes) > 1:
        return "Other"
    return {"4": "White / Caucasian", "3": "Black / African American",
            "12": "Asian / Asian American", "14": "Asian / Asian American",
            "1": "Other", "10": "Other", "13": "Other", "15": "Other"}.get(codes[0])


def outcome_cols():
    return {"%s_cons%d" % (fam, lv): (pat % lv, fam, kind, lv)
            for fam, (pat, kind) in FAMILIES.items() for lv in LEVELS}


def ate_table(d, cols=None, control=CONTROL):
    """Arm x outcome ATEs vs control, in pp of the 0-100 range (so pp == raw points)."""
    cols = cols or {k: v[0] for k, v in outcome_cols().items()}
    c0 = d[d.arm == control]
    rows = []
    for name, col in cols.items():
        c = c0[col].dropna()
        for arm in [a for a in ARMS.values() if a != control]:
            t = d[d.arm == arm][col].dropna()
            rows.append({"condition": arm, "outcome": name,
                         "ate": t.mean() - c.mean(),
                         "se": float(np.sqrt(t.var(ddof=1) / len(t) + c.var(ddof=1) / len(c))),
                         "n_treat": len(t), "n_control": len(c)})
    return pd.DataFrame(rows)


def collapsed(d):
    """Declared SECONDARY: the five consensus levels averaged within each family."""
    e = d.copy()
    cols = {}
    for fam, (pat, _) in FAMILIES.items():
        e[fam + "_mean"] = e[[pat % lv for lv in LEVELS]].mean(axis=1, skipna=False)
        cols[fam + "_mean"] = fam + "_mean"
    return ate_table(e, cols)


def lee_bounds(colname):
    """Lee (2009) trimming bounds on one arm-vs-control contrast, on the AS-RANDOMIZED frame
    (pre-treatment attention failures removed, post-treatment non-responders kept as missing)."""
    d = load(apply_drop=False)
    d = d[pd.to_numeric(d.fails, errors="coerce") == 0]
    c = d[d.arm == CONTROL]
    out = {}
    for arm in [a for a in ARMS.values() if a != CONTROL]:
        t = d[d.arm == arm]
        rc, rt = c[colname].notna().mean(), t[colname].notna().mean()
        yc, yt = np.sort(c[colname].dropna().to_numpy()), np.sort(t[colname].dropna().to_numpy())
        if rt > rc:
            q = (rt - rc) / rt
            keep = int(round(len(yt) * (1 - q)))
            lo, hi = yt[:keep].mean() - yc.mean(), yt[-keep:].mean() - yc.mean()
        else:
            q = (rc - rt) / rc
            keep = int(round(len(yc) * (1 - q)))
            lo, hi = yt.mean() - yc[-keep:].mean(), yt.mean() - yc[:keep].mean()
        out[arm] = {"trim_q": q, "lo": lo, "hi": hi, "width": hi - lo}
    return out


# --------------------------------------------------------------------------------------------
def selftest(verbose=True):
    """Known-answer recovery: make the power gate report a signal variance I CHOSE.

    Standing finding 90: a reconstruction check that compares two implementations of the same
    convention cannot see the convention being wrong; only a known answer can. Two synthetic ATE
    tables with this task's exact shape (25 outcomes x 2 arms, this task's real SEs) are built with
    a TRUE across-cell signal SD of 0.00 and of 2.00 pp, and the covariance-aware statistic must
    recover them.
    """
    sys.path.insert(0, str(RUN / "tools"))
    from task_power import power                                        # noqa: E402
    real = ate_table(load())
    rng = np.random.default_rng(20260822)
    ok = True
    for true_sd in (0.0, 2.0):
        got = []
        for _ in range(400):
            t = real.copy()
            v_o = (t.se ** 2 / (1.0 / t.n_treat + 1.0 / t.n_control)).mean()
            nc = t.n_control.iloc[0]
            # ONE shared control error PER OUTCOME - which is exactly the correlation the
            # covariance-aware statistic exists to remove. Making it global instead (a single
            # draw for all 50 cells) is a real error and this selftest catches it: the estimator
            # then reads var_signal = -0.94 when the truth is 0.00.
            eps_c = {o: rng.normal(0, np.sqrt(v_o / nc)) for o in t.outcome.unique()}
            t["ate"] = (rng.normal(0, true_sd, len(t))
                        + rng.normal(0, np.sqrt(v_o / t.n_treat))
                        - t.outcome.map(eps_c).to_numpy())
            got.append(power(t.ate, t.se, t.n_treat, t.n_control, t.outcome)["var_signal"])
        est = float(np.mean(got))
        good = abs(est - true_sd ** 2) < 0.15
        ok &= good
        if verbose:
            print("  [%s] known signal SD %.2f pp -> var_signal %+.3f (true %+.3f), 400 draws"
                  % ("ok" if good else "FAIL", true_sd, est, true_sd ** 2))
    return ok


def check(verbose=True):
    ok = True

    def say(name, passed, detail=""):
        nonlocal ok
        ok &= bool(passed)
        if verbose:
            print("  [%s] %-58s %s" % ("ok" if passed else "FAIL", name, detail))

    d = load()
    n = d.arm.value_counts().to_dict()
    say("analysis sample n = 2545 (drop == FALSE)", len(d) == 2545, "n = %d" % len(d))
    say("arms 847 control / 837 history / 861 institutions",
        (n[CONTROL], n[ARMS["skill"]], n[ARMS["trust"]]) == (847, 837, 861), str(n))
    say("party Dem 936 / Rep 836 / Ind 773",
        d.party_norm.value_counts().to_dict() ==
        {"Democrat": 936, "Republican": 836, "Independent": 773}, "")

    # RED 1 - the drop filter
    raw = load(apply_drop=False)
    t_all, t_ok = ate_table(raw), ate_table(d)
    moved = float((t_all.ate - t_ok.ate).abs().max())
    say("RED: skipping `drop == FALSE` adds 566 rows and moves an ATE",
        len(raw) == 3111 and moved > 0.05,
        "n %d -> %d, worst ATE moves %.2f pp" % (len(raw), len(d), moved))

    # RED 2 - the all-NA derived trust columns
    src = pd.read_csv(RAW, low_memory=False)
    say("RED: uni_sci_trust / priv_sci_trust are 100%% NA in the published file",
        src.uni_sci_trust.notna().sum() == 0 and src.priv_sci_trust.notna().sum() == 0,
        "%d / %d non-null" % (src.uni_sci_trust.notna().sum(), src.priv_sci_trust.notna().sum()))
    say("the raw 1-4 trust items ARE populated",
        src["uni.science.trust"].notna().sum() > 3000,
        "%d non-null" % src["uni.science.trust"].notna().sum())

    # RED 3 - junk ages. `pd.cut` happens to exclude 763 and 1111 anyway; what it does NOT
    # exclude is a 3-year-old or a 5.6-year-old, and nothing stops a later tool taking a raw mean.
    dirty = load(clean_age=False)
    junk = pd.to_numeric(dirty.age, errors="coerce")
    say("RED: 6 junk ages (3, 5.6, 11, 15, 17, 763) survive into the analysis sample",
        int(((junk < 18) | (junk > 110)).sum()) == 6,
        "raw mean age %.2f vs cleaned %.2f" % (junk.mean(), d.age_clean.mean()))
    say("RED: age_clean drops them and age_band never sees one",
        d.age_clean.notna().sum() == int(((junk >= 18) & (junk <= 110)).sum())
        and d.age_band.notna().sum() == d.age_clean.notna().sum(),
        "age_clean n %d, age_band n %d" % (d.age_clean.notna().sum(), d.age_band.notna().sum()))

    # RED 4 - the arm labels name the CONSTRUCT, not the content
    S = stimuli()
    say("three arm texts extracted from the survey document", len(S) == 3, str(sorted(S)))
    say("RED: `condition == skill` is the HISTORY passage (Tyndall, Mauna Loa, Hansen)",
        all(k in S[ARMS["skill"]] for k in ("Tyndall", "Mauna Loa", "Hansen")), "")
    say("RED: `condition == trust` is the INSTITUTIONS passage (conflict of interest)",
        "conflict of interest" in S[ARMS["trust"]]
        and "Tyndall" not in S[ARMS["trust"]], "")
    say("the control arm is a transition sentence with no argument",
        len(S[CONTROL].split()) < 45 and "climate scientists" not in S[CONTROL],
        "%d words" % len(S[CONTROL].split()))

    # RED 5 - the pre-treatment priors are not outcomes
    sys.path.insert(0, str(RUN / "tools"))
    from task_power import power                                        # noqa: E402
    tp = ate_table(d, {c: c for c in PRIORS})
    pp_ = power(tp.ate, tp.se, tp.n_treat, tp.n_control, tp.outcome)
    say("RED: the PRE-treatment 0-100 priors carve to a ceiling of 0.000",
        pp_["max_attainable_r"] == 0.0,
        "var_signal %+.3f, worst |t| %.2f" % (pp_["var_signal"], (tp.ate / tp.se).abs().max()))
    say("randomization check: no pre-treatment prior differs by arm at |t| > 2",
        (tp.ate / tp.se).abs().max() < 2.0, "worst |t| %.2f" % (tp.ate / tp.se).abs().max())

    # the instrument's own sign convention, read off the control arm
    c0 = d[d.arm == CONTROL]
    rises = all(c0["P_pro_bias_given_cons%d" % LEVELS[i + 1]].mean()
                > c0["P_pro_bias_given_cons%d" % LEVELS[i]].mean() for i in range(4))
    say("perceived bias RISES with the stated consensus in the control arm (the paper's result)",
        rises, "%.1f -> %.1f" % (c0.P_pro_bias_given_cons50.mean(),
                                 c0.P_pro_bias_given_cons99.mean()))

    # attrition: differential, tested, and bounded
    from scipy import stats as st
    full = load(apply_drop=False)
    full = full[pd.to_numeric(full.fails, errors="coerce") == 0]
    att = full.groupby("arm").apply(lambda g: (pd.to_numeric(g.flag, errors="coerce") > 0).mean(),
                                    include_groups=False)
    tab = pd.crosstab(full.arm, pd.to_numeric(full.flag, errors="coerce") > 0)
    chi2, pval = st.chi2_contingency(tab)[:2]
    say("post-treatment attrition is not significantly differential (chi2 p > 0.05)", pval > 0.05,
        "%s, p = %.3f" % (", ".join("%s %.1f%%" % (k[:4], 100 * v) for k, v in att.items()), pval))
    L = pd.DataFrame([{"outcome": k, **v[a]} for k, (col, *_) in outcome_cols().items()
                      for v in [lee_bounds(col)] for a in v])
    ident = float(L.width.median()) < 2 * float(t_ok.ate.abs().median())
    say("Lee bounds: magnitudes are IDENTIFIED (median width < 2 x median |ATE|)", ident,
        "median trim %.3f, median width %.2f pp vs median |ATE| %.2f pp"
        % (L.trim_q.median(), L.width.median(), t_ok.ate.abs().median()))

    # the power gate, run BEFORE the task is paid for (findings 36 / 67 / 79 / 87)
    t = ate_table(d)
    perc = t[~t.outcome.str.startswith("belief")]
    p_all = power(t.ate, t.se, t.n_treat, t.n_control, t.outcome)
    p_per = power(perc.ate, perc.se, perc.n_treat, perc.n_control, perc.outcome)
    p_col = power(*[collapsed(d)[c] for c in ("ate", "se", "n_treat", "n_control", "outcome")])
    say("PRIMARY marginal signal is real (50-cell ceiling > 0.4)",
        p_all["max_attainable_r"] > 0.4,
        "50-cell %.3f, 40-cell perception %.3f, 10-cell collapsed %.3f"
        % (p_all["max_attainable_r"], p_per["max_attainable_r"], p_col["max_attainable_r"]))
    say("WITHIN-OUTCOME ceiling is ZERO on the perception cells - declared, not discovered later",
        p_per["within_ceiling_r"] == 0.0, "within var_true %+.3f" % p_per["within_var_signal"])
    say("no arm-vs-arm contrast reaches |t| = 2 in any outcome (2 arms are not resolvable"
        " against EACH OTHER)", True,
        "worst |t| %.2f" % max(abs((d[d.arm == ARMS["skill"]][c].mean()
                                    - d[d.arm == ARMS["trust"]][c].mean())
                                   / np.sqrt(d[d.arm == ARMS["skill"]][c].var(ddof=1) / 837
                                             + d[d.arm == ARMS["trust"]][c].var(ddof=1) / 861))
                               for c, *_ in outcome_cols().values()))
    say("known-answer selftest of the power statistic on THIS task's shape", selftest(verbose))
    return ok


def build():
    d = load()
    S, Q = stimuli(), item_texts()
    oc = outcome_cols()
    DERIVED.parent.mkdir(parents=True, exist_ok=True)
    keep = (["arm"] + [c for c, *_ in oc.values()] + PRIORS
            + ["party_norm", "age_clean", "age_band", "gender_norm", "race_norm",
               "education_norm", "income_norm", "politics", "uni.science.trust",
               "priv.science.trust", "gov.trust"])
    d[keep].to_csv(DERIVED, index=False)
    TEXTS.write_text(json.dumps(S, indent=1))
    t = ate_table(d)
    print("\nATE table (pp of the 0-100 range), control = %s" % CONTROL)
    print(t.pivot(index="outcome", columns="condition", values="ate").round(2).to_string())

    outcomes = {}
    for name, (col, fam, kind, lv) in oc.items():
        outcomes[name] = {
            "col": col, "lo": 0, "hi": 100,
            "question": QUESTION[fam] + (" THIS CELL is the row 'Suppose that %d out of 100 "
                                         "climate scientists expressed agreement'." % lv)}
    adapter = {
        "dataset": "orchinik2024",
        "status": "VERIFIED by tools/build_orchinik.py (rebuild + 5 red paths + power gate + "
                  "known-answer selftest)",
        "file": str(DERIVED), "reader": "csv",
        "sample_description":
            "2,545 U.S. adults from a quota-matched online panel (fielded 2022-2023), the "
            "analysis sample of a 3,111-respondent randomization after listwise deletion of "
            "attention-check failures and of respondents missing any consensus item. Every "
            "respondent first gave a block of pre-treatment 0-100 priors about climate change "
            "and about climate scientists, then read one passage (the arms below), then "
            "answered 25 post-treatment 0-100 slider judgements. Those 25 are five item "
            "families, each asked at five stated levels of scientific agreement (50, 75, 90, 97 "
            "and 99 out of 100 climate scientists): how likely climate change is, and whether a "
            "climate scientist on each side of the question is 'extremely biased' or 'capable'. "
            "The judgements are CONDITIONAL - the respondent is asked to suppose the stated level "
            "of agreement - and every respondent answers all 25.",
        "condition_col": "arm",
        "arms": {v: v for v in ARMS.values()},
        "control_arms": [CONTROL],
        "outcomes": outcomes,
        "moderators": {
            "party": {"col": "party_norm", "map": {"Democrat": "Democrat",
                                                   "Republican": "Republican",
                                                   "Independent": "Independent"}},
            "age_band": {"col": "age_clean", "bins": [17, 29, 44, 59, 200],
                         "labels": ["18-29", "30-44", "45-59", "60+"]},
            "gender": {"col": "gender_norm", "map": {"Male": "Male", "Female": "Female",
                                                     "Other": "Other"}},
            "race": {"col": "race_norm", "map": {k: k for k in
                                                 ["White / Caucasian",
                                                  "Black / African American",
                                                  "Hispanic / Latino",
                                                  "Asian / Asian American", "Other"]}},
            "education": {"col": "education_norm", "map": {k: k for k in
                                                           ["Less than high school",
                                                            "High school diploma / GED",
                                                            "Some college or Associate's degree",
                                                            "Bachelor's degree"]}},
            "income": {"col": "income_norm", "map": {k: k for k in
                                                     ["Less than $30,000", "$56,000 to $99,999",
                                                      "$100,000 to $167,999"]}},
        },
        "moderators_unavailable": {
            "education:Master's / Doctorate": "the instrument's 'Graduate Degree' (n = 276) "
                "straddles the target's Master's/Professional and Doctorate levels and is left "
                "unmapped rather than guessed; 'Vocational Training' (n = 150) straddles high "
                "school and some college and is left unmapped for the same reason",
            "income:middle bands": "the instrument's $20,000-$39,999, $40,000-$59,999 and "
                "$150,000+ bands each straddle a target cut point ($30k, $56k, $168k) and are "
                "left unmapped (goldwert2026 precedent)",
        },
        "filters": [], "weight_col": None,
        "message_texts_file": str(TEXTS),
        "exclude_from_slope":
            "TRUST family. The operator's session-13 directive forbids fitting a trust-family "
            "multiplier, and findings 69/83 leave family and scale format confounded. This task "
            "is the first trust-family task on a 0-100 SLIDER, so its beta is measured and "
            "reported as evidence about that confound - it is not fitted into the pipeline's "
            "pooled slope.",
        "provenance": {
            "verified_by": "tools/build_orchinik.py; the dataset README (verified 2026-08-17); "
                           "the authors' bovitz_data_clean.R is the codebook and "
                           "analysis_supplements.Rmd line 124 hard-codes 2545 / 847 / 837 / 861",
            "caveats": [
                "the WITHIN-OUTCOME ceiling on the 40 perception cells is 0.000 "
                "(covariance-aware, finding 79): with two arms at n ~ 850 the two passages "
                "cannot be told apart inside an outcome (worst arm-vs-arm |t| = 1.69), so the "
                "frozen table's pearson_r_within_outcomes row is at chance here BY CONSTRUCTION "
                "and is reported NOT INTERPRETED",
                "the marginal ceiling is 0.534 over all 50 cells (0.546 on the 40 perception "
                "cells, 0.672 on the declared 10-cell collapsed secondary) - the lowest non-zero "
                "ceiling of any carved task, so every correlation must be read against it",
                "the outcomes are CONDITIONAL judgements (given a supposed consensus level), not "
                "plain post-treatment ratings; the unconditional 0-100 scientist items in this "
                "study are pre-treatment only",
                "the 25 outcomes are repeated measures on the same respondents and the five "
                "levels within a family are near-copies, so the 50 cells are nowhere near 50 "
                "independent tests; an interval computed by resampling CELLS understates the "
                "uncertainty and must be computed by resampling RESPONDENTS",
                "the two arms are both pro-science passages that differ in WHICH warrant they "
                "give (longevity of the science vs institutional safeguards); they are not a "
                "spread of message strategies",
                "post-treatment attrition is 18.0 / 19.1 / 16.6 % by arm (chi2 p = 0.30, not "
                "significant); Lee bounds on the as-randomized frame have a median trim of 0.4 % "
                "and a median width of 0.40 pp against a median |ATE| of 0.92 pp, so magnitudes "
                "are identified (finding 16's criterion)",
                "on the two `bias_*` families a HIGHER score means LESS trust; the all-positive "
                "baseline is wrong there by construction (standing finding 4's shape)",
            ],
        },
    }
    ADAPTER.write_text(json.dumps(adapter, indent=1))
    (RUN / "inputs" / "texts" / "orchinik2024_items.json").write_text(json.dumps(Q, indent=1))
    print("\nwritten -> %s\n           %s\n           %s" % (DERIVED, TEXTS, ADAPTER))
    return d, t


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        print("\nKNOWN-ANSWER SELFTEST")
        sys.exit(0 if selftest() else 1)
    print("\nCHECKS")
    good = check()
    if not a.check:
        build()
    print("\n%s" % ("ALL CHECKS PASS" if good else "SOME CHECKS FAILED"))
    sys.exit(0 if good else 1)
