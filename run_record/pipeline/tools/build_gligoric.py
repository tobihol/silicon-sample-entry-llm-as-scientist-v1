#!/usr/bin/env python
"""Build the gligoric2025 trust-outcome practice task input from the mounted OSF materials.

    /opt/kernel/venv/bin/python tools/build_gligoric.py            # rebuild + verify
    /opt/kernel/venv/bin/python tools/build_gligoric.py --check    # verify only, exit 1 on drift

WHY THIS TASK EXISTS AND WHAT IT IS NOT
Standing finding 33: zero of 1,489 scored practice cells fall in the target's `trust` family, so
every magnitude claim the harness makes about the target's four trust outcomes is a cross-family
extrapolation. notes/DATA_GLIGORIC.md ruled this dataset NOT CARVABLE as a sixth *scored* task,
and that ruling is not overturned here - it is honoured. `tools/task_power.py`'s statistic on the
40-cell table is var_signal = -1.00, i.e. the observed spread of the ATEs is SMALLER than sampling
noise alone predicts, so every Section-1 metric on it has chance expectation and the attainable-r
ceiling is zero (finding 36). What the task can measure is the one thing that does not need signal
in the truth: whether the predictor's MAGNITUDES on a real randomised trust experiment land inside
the equivalence bound the published paper reports (d < 0.1). That, and nothing else, is what
runs/_trusttask/PREREG.md declares as pass/fail before any call.

Three structural facts, all verified below rather than asserted:
 1. Only conservatives were randomised. A QSF branch routes Ideology 1-5 straight to a block that
    hard-sets Condition = Control, so the 1,110 liberals in the control arm were never randomised.
    The adapter therefore carries a REQUIRED filter, and verify() measures what forgetting it costs.
 2. Every respondent rates exactly 4 of 35 occupations, chosen at random by Qualtrics
    (TotalRandSubset: 4). An outcome is the mean over whichever of the 4 fall in its cluster, so
    cluster outcomes are thinner than the overall one by design, not by attrition.
 3. `RespectableConservatives` pipes two randomised names that the data file does not record. The
    arm is a 4-way mixture we cannot condition on; the brief shows both alternatives explicitly
    rather than silently picking one.
"""
import argparse, html, json, re, sys, warnings
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
SRC = Path("/workspace/datasets/gligoric2025/downloads/Main Study")
DATA = SRC / "Analyses (data and codes)" / "dataMainStudy.csv"
QSF = SRC / "Materials" / "Qualtrics file.qsf"
OUT = RUN / "inputs" / "derived" / "gligoric2025_trust.csv"
ARMTEXT = RUN / "inputs" / "texts" / "gligoric2025_arms.json"
ADAPTER = RUN / "inputs" / "adapters" / "gligoric2025.json"

# The occupation clusters. Every one of the 35 occupations is in exactly one cluster (asserted),
# so the five cluster outcomes partition the battery and the overall outcome is their share-weighted
# whole. They are thematic, fixed here before any prediction, and chosen to put the target's own
# construct - climate science - in its own cell.
CLUSTERS = {
    "trust_climate_env": ["climatologists", "environmental scient", "ecologists", "meteorologists",
                          "oceanographers", "hydrologist", "geologists"],
    "trust_life_medical": ["medical researchers", "epidemiologists", "virologists", "microbiologists",
                           "geneticists", "biologists", "biochemists", "neuroscientists",
                           "marine biologists", "botanists", "zoologists", "food scientists"],
    "trust_physical_eng": ["physicists", "astrophysicists", "astronomers", "chemists",
                           "nuclear physicists", "nuclear scientists", "rocket scientists",
                           "paleontologists", "archaeologists"],
    "trust_social": ["psychologists", "sociologists", "anthropologists"],
    "trust_quant_tech": ["mathematicians", "statisticians", "data scientists", "computer scientists"],
}
# The data file truncates two column names ("environmental scient", "hydrologist"). Those are
# storage artefacts and must not reach a stimulus description, so the brief shows the occupation
# as the instrument words it.
DISPLAY = {"environmental scient": "environmental scientists", "hydrologist": "hydrologists"}
ARMS = ["Control", "Norms", "ConservativeScientists", "RespectableConservatives", "ValueBased",
        "Co-Benefit"]
PIPES = {"Politician": ["Henry Kissinger", "George W. Bush"],
         "Intellectual": ["William F. Buckley", "Ayn Rand"]}


# ---------------------------------------------------------------- message texts, from the flow
def _text(h: str) -> str:
    s = re.sub(r"<br\s*/?>", "\n", str(h))
    s = re.sub(r"</p>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\n{3,}", "\n\n", html.unescape(s).replace("\xa0", " ")).strip()


def arm_texts() -> dict:
    """Resolve arm -> message text through the QSF FLOW, never by block-name matching.

    FL_53 is the BlockRandomizer over the six arms; each Group sets the embedded field `Condition`
    and then shows one block whose FIRST element is the message (a `DB` descriptive-text question).
    """
    qsf = json.loads(QSF.read_text(encoding="utf-8", errors="ignore"))
    els = qsf["SurveyElements"]
    blocks = {}
    for e in els:
        pl = e["Payload"]
        if e["Element"] != "BL":
            continue
        for v in (pl.values() if isinstance(pl, dict) and "BlockElements" not in pl
                  else ([pl] if isinstance(pl, dict) else pl)):
            if isinstance(v, dict) and "ID" in v:
                blocks[v["ID"]] = v
    qs = {e["Payload"]["QuestionID"]: e["Payload"] for e in els if e["Element"] == "SQ"}
    flow = [e for e in els if e["Element"] == "FL"][0]["Payload"]

    rnd = []
    def find(n):
        if n.get("FlowID") == "FL_53":
            rnd.append(n)
        for c in n.get("Flow", []) or []:
            find(c)
    find(flow)
    if not rnd:
        raise SystemExit("QSF: the arm randomiser FL_53 is gone - the instrument changed")

    out = {}
    for g in rnd[0]["Flow"]:
        cond, bids = None, []
        def rec(n):
            nonlocal cond
            for f in n.get("EmbeddedData") or []:
                if f.get("Field") == "Condition":
                    cond = f.get("Value")
            if n.get("Type") in ("Standard", "Block") and n.get("ID"):
                bids.append(n["ID"])
            for c in n.get("Flow", []) or []:
                rec(c)
        rec(g)
        qids = [x["QuestionID"] for b in bids for x in blocks[b]["BlockElements"]
                if x["Type"] == "Question"]
        msg = next(q for q in qids if qs[q].get("QuestionType") == "DB")
        t = _text(qs[msg]["QuestionText"])
        # The two piped names are themselves randomised and NOT recorded in the data file, so the
        # arm is a 4-way mixture. Showing both alternatives is the only honest rendering: picking
        # one would describe a stimulus 50% of that arm never saw.
        for field, opts in PIPES.items():
            t = t.replace("${e://Field/%s}" % field, " or ".join(opts))
        out[cond] = t
    if sorted(out) != sorted(ARMS):
        raise SystemExit("QSF arms %s != expected %s" % (sorted(out), sorted(ARMS)))
    return out


# ---------------------------------------------------------------- derived respondent file
def occupations(df: pd.DataFrame) -> list:
    return [c[:-2] for c in df.columns if c.endswith("_1")
            and c[:-2] + "_2" in df.columns and not c.startswith(("Gender", "Believability"))]


def derive(df: pd.DataFrame) -> pd.DataFrame:
    occ = occupations(df)
    i1 = df[[o + "_1" for o in occ]].to_numpy(float)
    i2 = df[[o + "_2" for o in occ]].to_numpy(float)
    per_occ = (i1 + i2) / 2.0                      # the authors' own per-occupation trust score
    d = pd.DataFrame(index=df.index)
    d["Condition"] = df.Condition
    # The filter is a COLUMN, not a silent pre-filter of the file: an adapter that forgets it is
    # then a visible defect rather than an invisible one, and verify() measures the bias it causes.
    d["conservative"] = (df.Ideology > 5).astype(int)
    d["Ideology"], d["PolIdentification"] = df.Ideology, df.PolIdentification
    d["Gender"], d["Age"], d["Education"] = df.Gender, df.Age, df.Education
    # a respondent whose 4 random occupations miss a cluster entirely has NaN there:
    # missing BY DESIGN, not attrition, and nanmean says so loudly on an empty slice.
    with np.errstate(all="ignore"), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        d["trust_overall"] = np.nanmean(per_occ, axis=1)
        d["credibility"] = np.nanmean(i1, axis=1)
        d["trustworthiness"] = np.nanmean(i2, axis=1)
        ix = {o: k for k, o in enumerate(occ)}
        for name, lst in CLUSTERS.items():
            d[name] = np.nanmean(per_occ[:, [ix[o] for o in lst]], axis=1)
    d["n_rated"] = np.isfinite(per_occ).sum(axis=1)
    return d


OUTCOMES = ["trust_overall", "credibility", "trustworthiness"] + list(CLUSTERS)


def ate_table(d: pd.DataFrame, conservatives_only=True) -> pd.DataFrame:
    g = d[d.conservative == 1] if conservatives_only else d
    ctrl = g[g.Condition == "Control"]
    rows = []
    for o in OUTCOMES:
        cv = ctrl[o].dropna().to_numpy()
        for arm in [a for a in ARMS if a != "Control"]:
            av = g[g.Condition == arm][o].dropna().to_numpy()
            sc = 100.0 / 6.0
            rows.append({"outcome": o, "condition": arm,
                         "ate": (av.mean() - cv.mean()) * sc,
                         "se": np.sqrt(av.var(ddof=1) / len(av) + cv.var(ddof=1) / len(cv)) * sc,
                         "n_t": len(av), "n_c": len(cv)})
    return pd.DataFrame(rows)


def verify(df: pd.DataFrame, d: pd.DataFrame, texts: dict) -> dict:
    """Six red paths. Each one is a fact the task's honesty depends on, checked on the data."""
    occ = occupations(df)
    res = {}

    # (1) exactly 4 of 35 occupations rated, and the two items are answered together
    n1 = df[[o + "_1" for o in occ]].notna().sum(axis=1)
    n2 = df[[o + "_2" for o in occ]].notna().sum(axis=1)
    assert set(n1.unique()) == {4} and (n1 == n2).all(), "the 4-of-35 subset design does not hold"
    res["subset_design"] = "every respondent rated exactly 4 of %d occupations on both items" % len(occ)

    # (2) the clusters partition the battery - no occupation counted twice or dropped
    flat = [o for v in CLUSTERS.values() for o in v]
    assert sorted(flat) == sorted(occ), "clusters do not partition the 35 occupations"
    res["clusters"] = "%d occupations partitioned into %d clusters" % (len(occ), len(CLUSTERS))

    # (3) conservatives-only randomisation: no liberal is in any message arm
    lib = df[df.Ideology <= 5]
    assert set(lib.Condition.unique()) == {"Control"}, "a liberal appears in a message arm"
    res["randomised_sample"] = ("%d conservatives randomised over 6 arms; %d liberals are in the "
                                "control arm and were NEVER randomised"
                                % (int((df.Ideology > 5).sum()), len(lib)))

    # (4) RED PATH: forgetting the filter biases every ATE, and by how much
    a_ok, a_bad = ate_table(d, True), ate_table(d, False)
    j = a_ok.merge(a_bad, on=["outcome", "condition"], suffixes=("", "_unfiltered"))
    bias = (j.ate_unfiltered - j.ate)
    assert abs(bias).max() > 0.5, "the filter appears inert - check the branch"
    res["filter_red_path"] = ("dropping the Ideology>5 filter moves every one of %d ATEs by "
                              "%.2f to %.2f pp (mean %.2f) - the control arm silently gains "
                              "1,110 never-randomised liberals"
                              % (len(j), bias.min(), bias.max(), bias.mean()))

    # (5) the published null reproduces: no signal to predict (finding 36's statistic)
    var_obs, mean_se2 = a_ok.ate.var(ddof=1), (a_ok.se ** 2).mean()
    res["var_signal"] = float(var_obs - mean_se2)
    res["signal"] = ("var(observed ATE) %.3f - mean(SE^2) %.3f = %.3f pp^2; attainable-r ceiling %s"
                     % (var_obs, mean_se2, var_obs - mean_se2,
                        "ZERO (negative signal variance)" if var_obs < mean_se2 else "positive"))

    # (6) the equivalence bound this task is graded on, from the control arm's own SD
    sd = d[(d.conservative == 1) & (d.Condition == "Control")].trust_overall.std(ddof=1)
    res["equivalence_bound_pp"] = float(0.1 * sd / 6.0 * 100)
    res["equivalence"] = ("control-arm SD %.3f raw points -> d = 0.1 is %.3f pp of the 1-7 range"
                          % (sd, res["equivalence_bound_pp"]))

    # (7) the brief must not name its own study
    blob = json.dumps(texts) + SAMPLE
    for k in ["gligori", "van kleef", "rutjens", "nature human behaviour", "n63mz"]:
        assert k not in blob.lower(), "an identity key is in the payload: %r" % k
    res["self_identification"] = "no identity key in the arm texts or the sample description"
    return res


SAMPLE = ("6,690 U.S. self-identified conservatives (1-10 ideology self-placement, 6-10), recruited "
          "from an online river panel and quota-balanced on gender, May-June 2024. Each respondent "
          "read one short message about scientists (or a bare instruction in the control arm) and "
          "then rated 4 scientific occupations, drawn at random from a fixed list of 35, on two "
          "7-point bipolar items. Liberals were routed past the messages and are excluded here.")

ITEM_Q = ("mean of two 7-point bipolar items - 'not credible : credible' and 'untrustworthy : "
          "trustworthy' - asked as 'Please rate how you view <occupation> using the following "
          "attributes', averaged over %s")


def adapter(texts: dict) -> dict:
    outs = {}
    outs["trust_overall"] = {"col": "trust_overall", "lo": 1, "hi": 7,
                             "question": ITEM_Q % "all 4 occupations the respondent rated"}
    outs["credibility"] = {"col": "credibility", "lo": 1, "hi": 7,
                           "question": ("the 'not credible : credible' item alone (7-point), "
                                        "averaged over all 4 occupations rated")}
    outs["trustworthiness"] = {"col": "trustworthiness", "lo": 1, "hi": 7,
                               "question": ("the 'untrustworthy : trustworthy' item alone "
                                            "(7-point), averaged over all 4 occupations rated")}
    for name, lst in CLUSTERS.items():
        outs[name] = {"col": name, "lo": 1, "hi": 7,
                      "question": ITEM_Q % ("whichever of the respondent's 4 rated occupations are "
                                            + ", ".join(DISPLAY.get(o, o) for o in lst))}
    return {
        "dataset": "gligoric2025",
        "status": "VERIFIED by tools/build_gligoric.py (rebuild + 7 red paths)",
        "file": str(OUT),
        "reader": "csv",
        "sample_description": SAMPLE,
        "condition_col": "Condition",
        "arms": {a: a for a in ARMS},
        "control_arms": ["Control"],
        "outcomes": outs,
        "moderators": {
            "gender": {"col": "Gender", "map": {"1": "Male", "2": "Female", "3": "Other"}},
            "age_band": {"col": "Age", "bins": [17, 29, 44, 59, 200],
                         "labels": ["18-29", "30-44", "45-59", "60+"]},
        },
        "moderators_unavailable": {
            "race": "not asked",
            "income": "not asked",
            "party": "not asked; only a 1-10 ideology self-placement, and the randomised sample is "
                     "6-10 BY CONSTRUCTION, so no ideology contrast is estimable from randomised "
                     "data at all",
            "education": "6 levels but not the target's 6 - level 6 merges Master's/professional "
                         "with doctorate and level 5 ('currently studying postgraduate') is "
                         "ambiguous",
        },
        "filters": [{"col": "conservative", "eq": 1}],
        "weight_col": None,
        "message_texts_file": str(ARMTEXT),
        "exclude_from_slope": "conservatives-only subgroup task whose ATE table has NEGATIVE signal "
                              "variance (var_obs < mean SE^2): its magnitudes are not identified, "
                              "so it cannot inform a fitted slope (findings 16, 36)",
        "provenance": {
            "verified_by": "notes/DATA_GLIGORIC.md (recon) + tools/build_gligoric.py (red paths)",
            "caveats": [
                "the randomised sample is US self-identified conservatives ONLY - this is a "
                "subgroup task, not a general-population one",
                "each respondent rates 4 of 35 occupations at random, so cluster outcomes are "
                "thinner than the overall outcome by design",
                "RespectableConservatives pipes two randomised names that the data file does not "
                "record: the arm is a 4-way mixture and the brief shows both alternatives",
                "the published result is a NULL: all five arms equivalence-bounded below d = 0.1, "
                "and the 40-cell table's signal variance is negative",
                "BelievabilityExper_1..3 are 100% missing in Control and cannot be an outcome",
                "no respondent id, no weights; Age min is 16 (13 rows under 18)",
                "prompt is ~1.5k tokens against the target's 9,892 - out of finding 17's size band "
                "on the LOW side",
            ],
        },
    }


def main(check=False):
    df = pd.read_csv(DATA, low_memory=False)
    texts = arm_texts()
    d = derive(df)
    res = verify(df, d, texts)
    print("gligoric2025 trust task input")
    for k, v in res.items():
        print("  %-22s %s" % (k, v))
    t = ate_table(d, True)
    print("\nsealed ATE table (pp of the 1-7 range), %d cells" % len(t))
    print(t.pivot(index="outcome", columns="condition", values="ate").round(2).to_string())
    print("\nmedian |ATE| %.2f pp against median SE %.2f pp" % (t.ate.abs().median(), t.se.median()))
    if check:
        for p in (OUT, ARMTEXT, ADAPTER):
            if not p.exists():
                raise SystemExit("missing %s - run without --check" % p)
        old = pd.read_csv(OUT)
        if len(old) != len(d) or not np.allclose(old.trust_overall.fillna(-9),
                                                 d.trust_overall.fillna(-9)):
            raise SystemExit("DRIFT: %s does not match a fresh derivation" % OUT)
        print("\n--check: derived file, texts and adapter all present and reproducible")
        return res
    OUT.parent.mkdir(parents=True, exist_ok=True)
    ARMTEXT.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT, index=False)
    ARMTEXT.write_text(json.dumps(texts, indent=1, ensure_ascii=False))
    ADAPTER.write_text(json.dumps(adapter(texts), indent=1, ensure_ascii=False))
    print("\nwritten:\n  %s\n  %s\n  %s" % (OUT, ARMTEXT, ADAPTER))
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    a = ap.parse_args()
    main(a.check)
