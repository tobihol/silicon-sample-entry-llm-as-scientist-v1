#!/usr/bin/env python
"""Build trust practice task #3 from altenmueller2024 Study 4b, and check it can be trusted.

    /opt/kernel/venv/bin/python tools/build_altenmueller.py            # build + all red paths
    /opt/kernel/venv/bin/python tools/build_altenmueller.py --check    # red paths only

Study 4b (US MTurk, n = 741 after the preregistered attention check; n = 495 in the two
preregistered arms) describes a research institute as **sociological** or **economic** - discipline
as a stereotyped proxy for the scientists' politics - and measures the METI trust battery, policy
support, information-seeking and perceived ideological similarity. It is the harness's first
SOURCE-IDENTITY task: every other carved task manipulates a message.

Three things this file exists to prevent, each with a red path in `--check`:

  * dropping the Qualtrics header wrong. The R script drops SEVEN rows, not three: two leftover
    header rows and five experimenter test trials that carry a real `condition` and all-NaN DVs;
  * compositing with pandas' default. `rowMeans` is `na.rm = FALSE`, so one missing item makes the
    composite NA - `skipna=True` silently keeps a respondent the authors dropped;
  * the attention filter. R's `subset()` drops NA, so the 11 respondents with a MISSING attention
    check go too; a fillna'd comparison keeps them and moves n from 741 to 752.

Everything shipped is checked against the paper: SI Table S5's means and SDs, and the four
two-sided interaction p-values that the authors' own Rmd hard-codes.

Recon: `notes/DATA_ALTENMUELLER.md`.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
SRC = Path("/workspace/datasets/altenmueller2024/downloads")
RAW = SRC / "Data & Code" / "Data" / "rawdata_study4b.csv"
PDF = SRC / "Materials" / "Qualtrics Survey Study 4b.pdf"
DERIVED = RUN / "inputs" / "derived" / "altenmueller2024_study4b.csv"
TEXTS = RUN / "inputs" / "texts" / "altenmueller2024_arms.json"
ADAPTER = RUN / "inputs" / "adapters" / "altenmueller2024.json"

NUMERIC = ["competent", "intelligent", "educated", "professional", "experienced", "qualified",
           "honest", "sincere", "just", "fair", "moral", "ethical", "responsible", "considerate",
           "similarity", "support", "information_seeking", "attention_check", "lawyer",
           "politicized", "age", "pol_orientation", "pol_preference"]
EXPERTISE = ["competent", "intelligent", "educated", "professional", "experienced", "qualified"]
MORALITY = ["honest", "sincere", "just", "fair", "moral", "ethical", "responsible", "considerate"]
ARMS = {"economic research institute": "Economic institute",
        "sociological research institute": "Sociological institute",
        "economic and sociological research institute": "Interdisciplinary institute"}
CONTROL = "Economic institute"
OUTCOMES = {"trust_expertise": ("expertise", 1, 7), "trust_morality": ("moralTrust", 1, 7),
            "policy_support": ("support", 1, 7),
            "information_seeking": ("information_seeking", 1, 7),
            "perceived_similarity": ("similarity", 1, 7)}


def load(drop_rows=7, skipna=False, attention_na_keeps=False):
    raw = pd.read_csv(RAW, dtype=str, keep_default_na=False, na_values=[""])
    d = raw.iloc[drop_rows:].copy()
    for c in NUMERIC:
        d[c] = pd.to_numeric(d[c], errors="coerce")
    d["expertise"] = d[EXPERTISE].mean(axis=1, skipna=skipna)
    d["moralTrust"] = d[MORALITY].mean(axis=1, skipna=skipna)
    d["conservative"] = d[["pol_orientation", "pol_preference"]].mean(axis=1)
    if attention_na_keeps:
        d = d[d.attention_check.fillna(1) == 1]
    else:
        d = d[d.attention_check == 1]
    d["arm"] = d.condition.map(ARMS)
    d["party_lean"] = pd.cut(d.pol_preference, [0, 3, 4, 7],
                             labels=["Democrat", "Independent", "Republican"])
    d["age_band"] = pd.cut(d.age, [17, 29, 44, 59, 200],
                           labels=["18-29", "30-44", "45-59", "60+"])
    d["gender_norm"] = d.gender.map({"1": "Female", "2": "Male", "3": "Other"})
    return d.reset_index(drop=True)


def ate_table(d, arms=None):
    arms = arms or [a for a in ARMS.values() if a != CONTROL]
    c0 = d[d.arm == CONTROL]
    rows = []
    for o, (col, lo, hi) in OUTCOMES.items():
        rng = hi - lo
        c = c0[col].dropna()
        for a in arms:
            t = d[d.arm == a][col].dropna()
            rows.append({"condition": a, "outcome": o, "moderator_level": "",
                         "ate": (t.mean() - c.mean()) / rng * 100,
                         "se": float(np.sqrt(t.var(ddof=1) / len(t) + c.var(ddof=1) / len(c))
                                     / rng * 100),
                         "n_treat": len(t), "n_control": len(c)})
    return pd.DataFrame(rows)


def stimuli():
    """Extract the three vignettes from the survey PDF at BUILD time, so the shipped text is
    provably the instrument's and not a transcription."""
    import pdfplumber
    with pdfplumber.open(PDF) as pdf:
        page = pdf.pages[1].extract_text()
    blocks, cur = {}, None
    keys = {"Economists Manipulation": "Economic institute",
            "Interdisciplinary Manipulation": "Interdisciplinary institute",
            "METI": None}
    text, order = [], ["Sociological institute"]
    for line in page.split("\n"):
        if line.strip() in keys:
            blocks[order[-1]] = " ".join(text).strip()
            text = []
            nxt = keys[line.strip()]
            if nxt is None:
                break
            order.append(nxt)
            continue
        if line.startswith("Please read the description below") or line.startswith("text."):
            continue
        text.append(line.strip())
    return {k: " ".join(v.split()) for k, v in blocks.items()}


def check(verbose=True):
    ok = True

    def say(name, passed, detail=""):
        nonlocal ok
        ok &= bool(passed)
        if verbose:
            print("  [%s] %-52s %s" % ("ok" if passed else "FAIL", name, detail))

    d = load()
    say("n after the preregistered attention check = 741", len(d) == 741, "n = %d" % len(d))
    per = d.arm.value_counts().to_dict()
    say("per-arm n = 250 / 245 / 246",
        (per["Economic institute"], per["Sociological institute"],
         per["Interdisciplinary institute"]) == (250, 245, 246), str(per))
    ana = d[d.arm != "Interdisciplinary institute"]
    say("preregistered two-arm n = 495", len(ana) == 495, "n = %d" % len(ana))

    # RED PATH 1 - dropping only the two extra header rows keeps five experimenter test trials.
    # They do NOT survive the attention filter (their attention_check is NaN), so the analysed n is
    # unharmed and only the PRE-exclusion count is wrong - which is exactly the kind of silent
    # error that makes an exclusion table irreproducible. The check is stated on the count that
    # actually moves.
    raw = pd.read_csv(RAW, dtype=str, keep_default_na=False, na_values=[""])
    say("RED: dropping 2 header rows leaves 5 experimenter test rows in the frame",
        len(raw.iloc[2:]) == len(raw.iloc[7:]) + 5,
        "pre-exclusion n = %d vs %d" % (len(raw.iloc[2:]), len(raw.iloc[7:])))
    say("RED: those five rows carry a real condition and all-NaN METI",
        raw.iloc[2:7][EXPERTISE].isna().all().all() and raw.iloc[2:7].condition.notna().all(),
        "%d rows" % len(raw.iloc[2:7]))
    say("RED: they are invisible after the attention filter, so the analysed n hides the error",
        len(load(drop_rows=2)) == len(d), "n = %d either way" % len(d))

    # RED PATH 2 - rowMeans(na.rm = FALSE)
    lax = load(skipna=True)
    say("RED: skipna=True keeps a respondent the authors dropped",
        lax.expertise.notna().sum() == d.expertise.notna().sum() + 1,
        "%d vs %d non-null expertise" % (lax.expertise.notna().sum(), d.expertise.notna().sum()))

    # RED PATH 3 - subset() drops NA
    keep = load(attention_na_keeps=True)
    say("RED: keeping a missing attention check moves n 741 -> 752", len(keep) == 752,
        "n = %d" % len(keep))

    # published check 1 - SI Table S5 on the preregistered n = 495
    si = {"expertise": (6.17, 0.92), "moralTrust": (5.45, 1.05),
          "information_seeking": (5.63, 1.32), "support": (5.12, 1.14),
          "similarity": (4.24, 1.31), "conservative": (3.40, 1.75)}
    worst = 0.0
    for k, (m, s) in si.items():
        worst = max(worst, abs(ana[k].mean() - m), abs(ana[k].std(ddof=1) - s))
    say("SI Table S5 means and SDs reproduce to 2dp", worst <= 0.005, "worst |diff| %.4f" % worst)

    # published check 2 - the four interaction p-values hard-coded in the authors' Rmd
    from scipy import stats as st
    rmd = {"expertise": 0.26111, "moralTrust": 0.07550, "support": 0.05927,
           "information_seeking": 0.01048}
    worst_p = 0.0
    a2 = ana.copy()
    a2["soc"] = (a2.arm == "Sociological institute").astype(float)
    a2["cc"] = a2.conservative - a2.conservative.mean()
    for dv, p_pub in rmd.items():
        s = a2.dropna(subset=[dv, "soc", "cc"])
        X = np.column_stack([np.ones(len(s)), s.soc, s.cc, s.soc * s.cc])
        b, *_ = np.linalg.lstsq(X, s[dv].values, rcond=None)
        resid = s[dv].values - X @ b
        dof = len(s) - X.shape[1]
        cov = np.linalg.pinv(X.T @ X) * (resid @ resid) / dof
        tval = b[3] / np.sqrt(cov[3, 3])
        p = 2 * st.t.sf(abs(tval), dof)
        worst_p = max(worst_p, abs(p - p_pub))
    say("the Rmd's four interaction p-values reproduce", worst_p < 5e-5,
        "worst |diff| %.2e" % worst_p)

    # the stimuli, and the claim that the two preregistered arms are word-for-word twins
    S = stimuli()
    say("three vignettes extracted from the survey PDF", len(S) == 3, str(sorted(S)))
    a = S["Sociological institute"].replace("sociological", "X").replace("sociologists", "Y")
    b_ = S["Economic institute"].replace("economic", "X").replace("economists", "Y")
    say("RED: soc and eco vignettes are identical once the discipline words are masked",
        a == b_, "%d vs %d chars" % (len(S["Sociological institute"]), len(S["Economic institute"])))
    say("the exploratory arm is NOT a pure word swap (7 words longer)",
        len(S["Interdisciplinary institute"].split()) >
        len(S["Sociological institute"].split()) + 3,
        "%d vs %d words" % (len(S["Interdisciplinary institute"].split()),
                            len(S["Sociological institute"].split())))

    # the power gate, run BEFORE the task is paid for (findings 36 / 67 / 79)
    sys.path.insert(0, str(RUN / "tools"))
    from task_power import power                                        # noqa: E402
    t10 = ate_table(d)
    p10 = power(t10.ate, t10.se, t10.n_treat, t10.n_control, t10.outcome)
    t5 = t10[t10.condition == "Sociological institute"]
    p5 = power(t5.ate, t5.se, t5.n_treat, t5.n_control, t5.outcome)
    say("marginal signal is real (10-cell ceiling > 0.6)", p10["max_attainable_r"] > 0.6,
        "ceiling %.3f (5-cell primary %.3f)" % (p10["max_attainable_r"], p5["max_attainable_r"]))
    say("WITHIN-OUTCOME ceiling is ZERO - declared, not discovered later",
        p10["within_ceiling_r"] == 0.0,
        "within var_true %.3f" % p10["within_var_signal"])
    return ok


def build():
    d = load()
    S = stimuli()
    DERIVED.parent.mkdir(parents=True, exist_ok=True)
    cols = ["arm", "expertise", "moralTrust", "support", "information_seeking", "similarity",
            "conservative", "pol_orientation", "pol_preference", "party_lean", "age", "age_band",
            "gender_norm"]
    d[cols].to_csv(DERIVED, index=False)
    TEXTS.write_text(json.dumps(S, indent=1))
    t = ate_table(d)
    print("\nATE table (pp of the 1-7 scale range), control = %s" % CONTROL)
    print(t.round(2).to_string(index=False))
    adapter = {
        "dataset": "altenmueller2024",
        "status": "VERIFIED by tools/build_altenmueller.py (rebuild + red paths + published checks)",
        "file": str(DERIVED), "reader": "csv",
        "sample_description":
            "741 U.S. adults on MTurk who passed a preregistered attention check (250 / 245 / 246 "
            "per arm), fielded 2022. Every respondent is asked to IMAGINE coming across a report "
            "by scientists from a research institute, and reads a four-sentence description of "
            "that institute; the arms differ only in the institute's discipline. They then rate "
            "the scientists who work there on 14 bipolar trust adjectives, say how much they "
            "would support an unspecified policy those researchers suggest, how interested they "
            "would be in the researchers' further findings, and how ideologically similar to "
            "themselves the scientists feel.",
        "condition_col": "arm",
        "arms": {v: v for v in ARMS.values()},
        "control_arms": [CONTROL],
        "outcomes": {
            "trust_expertise": {"col": "expertise", "lo": 1, "hi": 7, "question":
                "6 bipolar 7-point semantic differentials completing 'In my view, scientists who "
                "work at this research institute are likely to be ...': incompetent-competent, "
                "unintelligent-intelligent, poorly educated-well educated, "
                "unprofessional-professional, inexperienced-experienced, unqualified-qualified; "
                "averaged (no item is reverse scored)"},
            "trust_morality": {"col": "moralTrust", "lo": 1, "hi": 7, "question":
                "the other 8 items of the same battery: dishonest-honest, insincere-sincere, "
                "unjust-just, unfair-fair, immoral-moral, unethical-ethical, "
                "irresponsible-responsible, inconsiderate-considerate; averaged"},
            "policy_support": {"col": "support", "lo": 1, "hi": 7, "question":
                "'Please imagine that researchers from this institute suggest a new policy. This "
                "policy results from their research and theorizing, suggesting that this policy "
                "would have positive consequences for society.' - 'How much do you think would you "
                "support such a policy?', 1 'Not at all' - 7 'Completely'. The policy itself is "
                "never specified"},
            "information_seeking": {"col": "information_seeking", "lo": 1, "hi": 7, "question":
                "'How much would you be interested in learning about further findings and "
                "suggestions from these researchers?', 1 'Not at all' - 7 'Completely'"},
            "perceived_similarity": {"col": "similarity", "lo": 1, "hi": 7, "question":
                "'In terms of my own political and ideological views, I feel similar to these "
                "scientists.', 1 'Not at all' - 7 'Completely'"},
        },
        "moderators": {
            "party_lean": {"col": "party_lean", "map": {"Democrat": "Democrat",
                                                        "Independent": "Independent",
                                                        "Republican": "Republican"}},
            "age_band": {"col": "age_band", "map": {"18-29": "18-29", "30-44": "30-44",
                                                    "45-59": "45-59", "60+": "60+"}},
            "gender": {"col": "gender_norm", "map": {"Male": "Male", "Female": "Female",
                                                     "Other": "Other"}},
        },
        "moderators_unavailable": {
            "race": "not asked", "income": "not asked", "education": "not asked",
        },
        "filters": [], "weight_col": None,
        "message_texts_file": str(TEXTS),
        "exclude_from_slope":
            "source-IDENTITY manipulation, not a message intervention, on a coarse 7-point bipolar "
            "scale, in the trust family. Findings 69 and 83 leave scale format and family "
            "confounded, and the operator's session-13 directive forbids fitting a trust-family "
            "multiplier.",
        "provenance": {
            "verified_by": "tools/build_altenmueller.py; recon in notes/DATA_ALTENMUELLER.md; the "
                           "authors' analysis_study4b.Rmd is the codebook",
            "caveats": [
                "the WITHIN-OUTCOME ceiling of this task is 0.000 (covariance-aware, finding 79): "
                "two identity labels at n~245 each cannot be told apart, so the frozen table's "
                "pearson_r_within_outcomes row is at chance here by construction and is not "
                "interpreted",
                "the third arm (interdisciplinary) is the authors' EXPLORATORY arm and is excluded "
                "from every preregistered analysis in the paper; it is carried here as declared "
                "secondary cells and is not part of the primary contrast",
                "the two preregistered vignettes are word-for-word twins apart from the discipline "
                "words, so the lexical distance between them is near zero - which is the point of "
                "carving it",
                "hypothetical framing: respondents imagine a report they never read; there is no "
                "actual message, no actual policy and no actual finding",
                "MTurk 2022, not a census-quota panel",
                "trust_expertise and trust_morality are disjoint halves of one 14-item battery, so "
                "their cells are not independent tests",
                "the paper's own result is an INTERACTION with respondent conservatism; the "
                "marginal contrast this task scores is not the paper's headline",
            ],
        },
    }
    ADAPTER.write_text(json.dumps(adapter, indent=1))
    print("\nwritten -> %s\n           %s\n           %s" % (DERIVED, TEXTS, ADAPTER))
    return d, t


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    print("\nCHECKS")
    good = check()
    if not a.check:
        build()
    print("\n%s" % ("ALL CHECKS PASS" if good else "SOME CHECKS FAILED"))
    sys.exit(0 if good else 1)
