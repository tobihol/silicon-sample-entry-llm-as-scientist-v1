#!/usr/bin/env python
"""Rebuild the hackenburg2025 single-issue practice-task input (task 7).

    /opt/kernel/venv/bin/python tools/build_hackenburg.py [--issue solitary_confinement]

Why a derived file rather than a direct adapter read: the control rows carry a NULL
`treatment_message_id`, so the arm column has to be filled before ssb.task.load_dataset can map
arms, and the arms have to be RENAMED. The 73 arm ids are of the form
`<issue>_<model>_<prompt_variant>` - they name the model that wrote each message, which is a
large part of what the task asks the predictor to infer. Titles are therefore `Message 01..73`
in a seeded shuffle, and the id -> title map lives here, next to the data, never in a brief.

Which issue: `solitary_confinement`, on the power gate and nothing else
(notes/DATA_HACKENBURG.md - attainable-r ceiling 0.824 and split-half r +0.590, against 0.16-0.48
for six issues and NEGATIVE signal variance for two). The LLM-authorship caveat is real and is
carried into the adapter, the scoreboard note and the run report: a large share of this task's
signal is message QUALITY (corr(ATE, valence_correct) = +0.591), which is not the same skill as
choosing among competent human-written frames.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
SRC = Path("/workspace/datasets/hackenburg2025/downloads/main_study/code/analysis/"
           "final_data_with_metrics.csv")
STEM = {"solitary_confinement": "confinement", "veteran healthcare": "veterans",
        "worker_pensions": "pensions", "medicaid": "medicaid", "foreign_aid": "foreign_aid",
        "assisted suicide": "suicide", "border_restrictions": "border",
        "felons_voting": "felon_voting", "affirmative_action": "affirmative_action",
        "electoral_college": "electoral_college"}
SEED = 20260817


def build(issue="solitary_confinement"):
    df = pd.read_csv(SRC, low_memory=False)
    d = df[df.issue == issue].copy()
    stem = STEM[issue]
    items = [f"{stem}-1", f"{stem}-2-reversed", f"{stem}-3", f"{stem}-4"]
    ids = sorted(d.loc[d.condition != "control", "treatment_message_id"].dropna().unique())
    rng = np.random.default_rng(SEED)
    order = list(rng.permutation(len(ids)))
    title = {mid: "Message %02d" % (order[i] + 1) for i, mid in enumerate(ids)}
    d["arm"] = d.treatment_message_id.map(title).fillna("Control")
    d.loc[d.condition == "control", "arm"] = "Control"
    d["age_band"] = pd.cut(pd.to_numeric(d.age, errors="coerce"), [17, 29, 44, 59, 200],
                           labels=["18-29", "30-44", "45-59", "60+"])
    keep = ["arm", "condition", "treatment_message_id", "model", "model_family",
            "prompt_variant_number", "treatment_message_word_count", "valence_correct",
            "gender", "age", "age_band", "education", "party_affiliation", "political_party",
            "political_ideology", "political_knowledge"] + items + [f"{stem}_mean"]
    out = d[[c for c in keep if c in d.columns]].reset_index(drop=True)
    texts = {title[mid]: t for mid, t in
             d.loc[d.condition != "control"].groupby("treatment_message_id").treatment_message.first().items()}
    texts["Control"] = ("No message. Control respondents answered the same four items with no "
                        "persuasive message.")
    checks = {
        "issue": issue, "rows": int(len(out)), "n_arms": int(len(ids)),
        "n_control": int((out.arm == "Control").sum()),
        "arm_n_min_med_max": [int(out[out.arm != "Control"].arm.value_counts().min()),
                              int(out[out.arm != "Control"].arm.value_counts().median()),
                              int(out[out.arm != "Control"].arm.value_counts().max())],
        "one_text_per_arm": bool(d[d.condition != "control"].groupby("arm").treatment_message.nunique().max() == 1),
        "control_has_no_message": bool(d.loc[d.condition == "control", "treatment_message"].isna().all()),
        "titles_unique": bool(len(set(title.values())) == len(ids)),
        "human_arm_title": title[d.loc[d.condition == "human", "treatment_message_id"].iloc[0]],
        "items": items,
        "mean_reproduces_composite": float(
            (out[items].mean(axis=1) - out[f"{stem}_mean"]).abs().max()),
    }
    fail = []
    if not checks["one_text_per_arm"]:
        fail.append("an arm has more than one message text")
    if not checks["control_has_no_message"]:
        fail.append("a control row carries a message")
    if checks["n_arms"] != 73:
        fail.append("%d arms, expected 73" % checks["n_arms"])
    if checks["mean_reproduces_composite"] > 1e-9:
        fail.append("the four items do not reproduce %s_mean (max dev %.3g)"
                    % (stem, checks["mean_reproduces_composite"]))
    if fail:
        raise SystemExit("HACKENBURG BUILD REFUSED:\n  - " + "\n  - ".join(fail))
    return out, texts, title, checks, items


def main(issue):
    out, texts, title, checks, items = build(issue)
    print(json.dumps(checks, indent=1))
    (RUN / "inputs" / "derived").mkdir(parents=True, exist_ok=True)
    out.to_csv(RUN / "inputs" / "derived" / "hackenburg_confinement.csv", index=False)
    (RUN / "inputs" / "derived" / "hackenburg_confinement_armmap.json").write_text(
        json.dumps({"seed": SEED, "issue": issue, "message_id_to_title": title}, indent=1))
    (RUN / "inputs" / "texts" / "hackenburg2025_arms.json").write_text(
        json.dumps(texts, indent=1, ensure_ascii=False))
    print("wrote inputs/derived/hackenburg_confinement.csv (%d x %d), the arm map, and %d texts"
          % (*out.shape, len(texts)))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--issue", default="solitary_confinement")
    main(ap.parse_args().issue)
