#!/usr/bin/env python
"""Build the beall2017 analysis extract (inputs/derived/beall2017.csv) and check it.

    uv run --with pyreadstat --with pandas python tools/build_beall.py           # build + checks
    SSB_DATASETS=data uv run --with pyreadstat --with pandas python tools/build_beall.py   # host-side

Beall, Myers, Kotcher, Vraga & Maibach (2017, PLOS ONE 12(11): e0187511; CC BY 4.0). US
Qualtrics quota panel, Oct-Nov 2015, N = 2,453. Between-subjects 4 topics x 3 positions = 12
cells: one op-ed excerpt by a fictitious "Dr. Dave Wilson"; outcome = McCroskey & Teven
source-credibility semantic differentials (9 items, 8-point).

Why a derived file at all: neither deposit file carries a single arm column. v1
(`PLOS ONE Data.sav`) has the demographics and twelve exposure indicators Q3-Q14 (exactly one
non-missing per row); v2 (`Updated Plos One Data.sav`, the authors' 2019-correction re-clean) has
the derived Topic/Position/Credibility and the ideology item Q44 but no demographics. Row order
is identical (asserted below on all nine Q19 items), so the two are joined by position.

Checks (each a hard assert):
  * every row has exactly one non-missing column among Q3-Q14;
  * the arm rebuilt from Q3-Q14 equals v2's Topic x Position on all 2,453 rows;
  * credibility (mean of nine, Q19_1/2/7/8 reversed as 9 - x) equals v2's `Credibility` to 1e-9;
  * cell counts equal the README table (flu 206/190/225, marijuana 213/199/205,
    severe weather 197/200/220, climate change 192/202/204).
"""
import json
import os
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyreadstat

RUN = Path(__file__).resolve().parents[1]
SRC = Path(os.environ.get("SSB_DATASETS", "/workspace/datasets")) / "beall2017" / "downloads"
V1 = SRC / "PLOS ONE Data.sav"
V2 = SRC / "Updated Plos One Data.sav"
DOCX = SRC / "pone.0187511.s001.docx"
DERIVED = RUN / "inputs" / "derived" / "beall2017.csv"
TEXTS = RUN / "inputs" / "texts" / "beall2017_arms.json"

TOPICS = ["Flu", "Marijuana", "Severe weather", "Climate change"]
POSITIONS = ["information only", "non-controversial solution", "controversial solution"]
# Q3..Q14 in blocks of three per topic, in position order (README "Arm reconstruction").
QCOLS = [f"Q{i}" for i in range(3, 15)]
ARM_OF_Q = {q: f"{TOPICS[i // 3]} - {POSITIONS[i % 3]}" for i, q in enumerate(QCOLS)}
EXPECTED_N = {"Flu": (206, 190, 225), "Marijuana": (213, 199, 205),
              "Severe weather": (197, 200, 220), "Climate change": (192, 202, 204)}

REVERSED = ["Q19_1", "Q19_2", "Q19_7", "Q19_8"]          # anchored high-to-low in the instrument
COMPETENCE = ["Q19_1", "Q19_3", "Q19_4"]                  # intelligent, competent, expert
GOODWILL = ["Q19_2", "Q19_5", "Q19_7"]                    # concerned, sensitive, cares
TRUSTWORTHINESS = ["Q19_6", "Q19_8", "Q19_9"]             # trustworthy, sincere, honest


def build():
    v1, _ = pyreadstat.read_sav(str(V1))
    v2, _ = pyreadstat.read_sav(str(V2))
    assert len(v1) == len(v2) == 2453, (len(v1), len(v2))
    q19 = [f"Q19_{i}" for i in range(1, 10)]
    a, b = v1[q19].to_numpy(float), v2[q19].to_numpy(float)
    assert np.array_equal(np.isnan(a), np.isnan(b)) and np.nanmax(np.abs(a - b)) == 0, "v1/v2 rows not aligned"

    shown = v1[QCOLS].notna()
    assert (shown.sum(axis=1) == 1).all(), "a row with zero or two stimulus indicators"
    arm = shown.idxmax(axis=1).map(ARM_OF_Q)
    topic = arm.str.split(" - ").str[0]
    position = arm.str.split(" - ").str[1]
    v2_arm = (v2["Topic"].map(dict(enumerate(TOPICS, 1))) + " - "
              + v2["Position"].map(dict(enumerate(POSITIONS, 1))))
    assert (arm.to_numpy() == v2_arm.to_numpy()).all(), "rebuilt arm disagrees with v2 Topic x Position"

    items = v1[q19].copy()
    for c in REVERSED:
        items[c] = 9 - items[c]
    cred = items.mean(axis=1, skipna=True)
    diff = (cred - v2["Credibility"]).abs()
    assert cred.notna().sum() == 2452 and diff.max() < 1e-9, f"credibility mismatch max {diff.max()}"

    out = pd.DataFrame({
        "arm": arm, "topic": topic, "position": position,
        "credibility": cred,
        "competence": items[COMPETENCE].mean(axis=1, skipna=True),
        "goodwill": items[GOODWILL].mean(axis=1, skipna=True),
        "trustworthiness": items[TRUSTWORTHINESS].mean(axis=1, skipna=True),
    })
    for c in q19:
        out[c + "_r" if c in REVERSED else c] = items[c]       # already oriented high = more
    for c in ["Q15", "Q16", "Q17", "Q18_12", "Q18_13", "Q18_14", "Q18_15", "Q20", "Q33"]:
        out[c] = v1[c]
    out["age"] = v1["Q46"]
    out["gender"] = v1["Q47"].map({1.0: "Male", 2.0: "Female"})
    out["education_raw"] = v1["Q48"]
    out["hispanic"] = v1["Q49"].map({1.0: "Hispanic or Latino", 2.0: "Not Hispanic or Latino"})
    out["ideology_raw"] = v2["Q44"]
    out["ideology"] = v2["Q44"].map({1.0: "Liberal", 2.0: "Liberal", 3.0: "Moderate",
                                     4.0: "Conservative", 5.0: "Conservative"})
    out["attn_failed_any"] = (v1[["Attn1", "Attn2", "Attn3"]].astype(str) == "1").any(axis=1).astype(int)

    for t, (n1, n2, n3) in EXPECTED_N.items():
        got = tuple(int((arm == f"{t} - {p}").sum()) for p in POSITIONS)
        assert got == (n1, n2, n3), (t, got)
    return out


def texts():
    """The twelve verbatim stimuli from S1 Appendix 1A (soft hyphens removed)."""
    import docx  # python-docx
    paras = [p.text for p in docx.Document(str(DOCX)).paragraphs]
    paras = [p.replace("­", "-").replace(" ", " ").strip() for p in paras]
    head = re.compile(r"^(Flu|Marijuana|Severe weather|Climate change)\s*-\s*(Informative|Non-?controversial|Controversial)\s*$")
    out, cur = {}, None
    for p in paras:
        if p.startswith("Appendix 1B"):
            break
        m = head.match(p)
        if m:
            pos = {"Informative": POSITIONS[0], "Controversial": POSITIONS[2]}.get(m.group(2), POSITIONS[1])
            cur = f"{m.group(1)} - {pos}"
            out[cur] = []
        elif cur and p:
            out[cur].append(p)
    out = {k: "\n\n".join(v) for k, v in out.items()}
    assert set(out) == set(ARM_OF_Q.values()), sorted(set(ARM_OF_Q.values()) - set(out))
    return out


if __name__ == "__main__":
    df = build()
    DERIVED.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(DERIVED, index=False)
    print(f"wrote {DERIVED}: {df.shape}; credibility M={df.credibility.mean():.3f} SD={df.credibility.std():.3f}")
    print(df.groupby(["topic", "position"]).credibility.mean().round(2).unstack())
    tx = texts()
    TEXTS.write_text(json.dumps(tx, indent=1, ensure_ascii=False))
    print(f"wrote {TEXTS}: {len(tx)} arms, {min(len(v.split()) for v in tx.values())}-{max(len(v.split()) for v in tx.values())} words")
    sys.exit(0)
