#!/usr/bin/env python
"""Rebuild the tappin2023 practice-task input from the mounted OSF materials.

    /opt/kernel/venv/bin/python tools/build_tappin.py            # rebuild + verify
    /opt/kernel/venv/bin/python tools/build_tappin.py --check    # verify only, exit 1 on drift

tappin2023 needs a derived analysis file for two reasons that are properties of the design, not
of this harness:

 1. The data ships as `data_RM.rds` (R serialization) in long format, 126,264 rows = 5,261
    respondents x 24 issues, of which only the 5 issues each respondent actually saw carry an
    outcome (`item_seen`). We convert with Rscript (the mounted R), never by hand.
 2. There is NO 48-level message id. Which of an issue's two ~150-word messages a respondent saw
    is deterministic: always the one arguing AGAINST their own party leader's position on that
    issue. arm = item x direction, and direction = the opposite of `biden` (Democrats) or `trump`
    (Republicans). The README documents it; this script REFUSES to write a file unless two
    independent checks confirm it on the data (see verify()).

The 48 arms each argue about a different policy, so a pooled control mean over 24 issues is not
any arm's counterfactual. The derived file therefore carries a `cell` column (item x direction)
and the adapter sets `control_strata: "cell"`, which makes ssb.task.true_ates difference each arm
against the control respondents who were asked about THAT issue in THAT party group.
"""
import argparse, json, subprocess, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
SRC = Path("/workspace/datasets/tappin2023/downloads/replication_materials/data/data_RM.rds")
RAW = RUN / "runs" / "_scratch" / "tappin_RM.csv"          # the plain conversion, not an input
OUT = RUN / "inputs" / "derived" / "tappin2023_cells.csv"  # the adapter's `file`
ARMTEXT = RUN / "inputs" / "texts" / "tappin2023_arms.json"          # verbatim SI messages
BRIEFTEXT = RUN / "inputs" / "texts" / "tappin2023_brief_arms.json"  # what the brief shows

GENDER = {1: "Male", 2: "Female", 3: "Other"}
RACE = {1: "White / Caucasian", 2: "Black / African American",
        3: "American Indian or Alaska Native", 4: "Asian / Asian American",
        5: "Native Hawaiian or Pacific Islander", 6: "Other"}
EDU = {1: "Less than high school", 2: "High school graduate", 3: "Some college",
       4: "2-year degree", 5: "4-year degree", 6: "Postgraduate"}


def convert():
    """readRDS -> csv, through the mounted R. Deterministic and re-runnable."""
    if RAW.exists():
        return
    RAW.parent.mkdir(parents=True, exist_ok=True)
    script = ('d <- readRDS("%s"); write.csv(d, "%s", row.names=FALSE, na="")' % (SRC, RAW))
    subprocess.run(["Rscript", "-e", script], check=True, capture_output=True, text=True)


def derive(tp: pd.DataFrame) -> pd.DataFrame:
    d = tp[tp.item_seen.astype(str).str.lower().isin(["true", "1"])].copy()
    d = d[d.likertAgree.notna() & d.condition.isin(
        ["Info-only", "Control", "Both", "Cue-only"])].copy()
    leader = np.where(d.republican == 1, d.trump, d.biden)     # the respondent's OWN party leader
    d["leader_stance"] = leader
    d["direction"] = np.where(leader == "agrees", "against", "in favor")   # message counters leader
    d["audience"] = np.where(d.republican == 1, "Republican", "Democrat")
    d["arm_title"] = d.item_label.str.strip() + " (" + d.direction + ")"
    d["cell"] = "item" + d.item.astype(int).astype(str) + "_" + d.direction.str.replace(" ", "_")
    d["condition_arm"] = np.where(d.condition.isin(["Info-only", "Both"]), d.arm_title, "Control")
    # Two outcomes, one per cue block. A cell is NaN outside its block, so ssb.task.true_ates
    # differences `agree_nocue` against the no-cue control rows of the same issue and
    # `agree_leader_cue` against the cue-only rows - the paper's own 2x2, expressed without any
    # change to the harness beyond `control_strata`.
    d["agree_nocue"] = d.likertAgree.where(d.condition.isin(["Control", "Info-only"]))
    d["agree_leader_cue"] = d.likertAgree.where(d.condition.isin(["Cue-only", "Both"]))
    d["gender"] = d.gender_survey.map(GENDER)
    d["race"] = d.race_survey.map(RACE)                        # multi-select combos -> NaN
    d["education"] = d.education_survey.map(EDU)
    keep = ["pid", "item", "item_label", "item_text", "cell", "direction", "audience",
            "arm_title", "condition_arm", "condition", "agree_nocue", "agree_leader_cue",
            "likertAgree", "likertAgree_recoded",
            "party7", "republican", "ideo7", "age_survey", "gender", "race", "education",
            "PK_sum", "cue_type"]
    return d[keep].reset_index(drop=True)


def verify(d: pd.DataFrame, tp: pd.DataFrame) -> dict:
    """Two RED PATHS on the arm derivation, both falsifiable on the data itself.

    The derivation is the only judgement call in this task, and a wrong one silently mislabels
    every arm's direction, which would look like a predictor failure rather than a data bug.
    """
    s = tp[tp.item_seen.astype(str).str.lower().isin(["true", "1"]) & tp.likertAgree.notna()].copy()
    own = np.where(s.republican == 1, s.trump, s.biden)
    swapped = np.where(s.republican == 1, s.biden, s.trump)
    # (1) `likertAgree_recoded` is documented as "agreement with the IN-PARTY LEADER's position".
    #     Reproducing it fixes which leader column belongs to which party, exactly.
    rec_own = float((np.where(own == "agrees", s.likertAgree, 8 - s.likertAgree)
                     == s.likertAgree_recoded).mean())
    rec_swap = float((np.where(swapped == "agrees", s.likertAgree, 8 - s.likertAgree)
                      == s.likertAgree_recoded).mean())
    # (2) The messages are persuasive (the paper's headline). If direction were flipped, the
    #     direction-signed ATE would be negative - i.e. messages would push readers AWAY from
    #     what they argue, on 24 of 24 issues. It is a sign test on the derivation.
    t = arm_table(d)
    t = t[t.outcome == "agree_nocue"]
    sgn = np.where(t.direction == "in favor", 1.0, -1.0)
    signed = float((t.ate_pp * sgn).mean())
    share = float((t.ate_pp * sgn > 0).mean())
    checks = {
        "recoded_reproduced_with_own_leader": rec_own,
        "recoded_reproduced_with_leaders_swapped": rec_swap,
        "mean_direction_signed_ate_pp": signed,
        "share_arms_moving_in_argued_direction": share,
        "n_arms": int(t.arm_title.nunique()),
        "n_cells": int(len(arm_table(d))),
        "n_per_arm_treat": [int(t.n_treat.min()), int(t.n_treat.max())],
        "n_per_arm_control": [int(t.n_control.min()), int(t.n_control.max())],
        "arms_spanning_one_party": bool(d.groupby("arm_title").audience.nunique().max() == 1),
    }
    fail = []
    if rec_own < 0.999:
        fail.append("recoded not reproduced from the in-party leader's stance (%.3f)" % rec_own)
    if rec_swap > 0.5:
        fail.append("the swapped-leader mapping fits too (%.3f): the check is not diagnostic"
                    % rec_swap)
    if signed <= 0 or share < 0.6:
        fail.append("direction-signed ATE %.2f pp on %.0f%% of arms: the derivation is backwards"
                    % (signed, 100 * share))
    if checks["n_arms"] != 48:
        fail.append("%d arms, expected 48" % checks["n_arms"])
    if not checks["arms_spanning_one_party"]:
        fail.append("an arm spans both parties; the design says it cannot")
    checks["failures"] = fail
    return checks


def arm_table(d: pd.DataFrame) -> pd.DataFrame:
    """The per-arm ATE table, stratum-matched, in pp of the 1-7 scale range. Used by verify() and
    by tools/task_power.py; it is NOT the sealed truth (ssb.task.carve writes that)."""
    rows = []
    for (arm, cell), g in d.groupby(["arm_title", "cell"]):
        for oc in ("agree_nocue", "agree_leader_cue"):
            tr = g.loc[g.condition_arm == arm, oc].dropna()
            ct = g.loc[g.condition_arm == "Control", oc].dropna()
            if len(tr) < 3 or len(ct) < 3:
                continue
            rows.append({"arm_title": arm, "cell": cell, "outcome": oc,
                         "direction": g.direction.iloc[0],
                         "audience": g.audience.iloc[0], "n_treat": len(tr), "n_control": len(ct),
                         "control_mean_pp": (ct.mean() - 1) / 6 * 100,
                         "ate_pp": (tr.mean() - ct.mean()) / 6 * 100,
                         "se_pp": np.sqrt(tr.var(ddof=1) / len(tr) + ct.var(ddof=1) / len(ct)) / 6 * 100})
    return pd.DataFrame(rows).sort_values("arm_title").reset_index(drop=True)


def compose_brief_texts(d: pd.DataFrame) -> dict:
    """What the predictor sees per arm: the policy statement it was asked to agree with, who read
    it, and the verbatim message. The item wording is arm-specific here (48 different policies),
    and finding 65 measured that item wordings carry almost all of the predictable signal - so it
    belongs in the arm, not in a single shared outcome description."""
    msgs = json.loads(ARMTEXT.read_text())
    out, missing = {}, []
    for arm, g in d.groupby("arm_title"):
        if arm not in msgs:
            missing.append(arm)
            continue
        out[arm] = ("Policy statement respondents rated: \"%s\"\n"
                    "Readers of this message: self-identified %ss (including leaners).\n"
                    "The message argues %s the policy statement:\n\n%s"
                    % (g.item_text.iloc[0], g.audience.iloc[0], g.direction.iloc[0], msgs[arm].strip()))
    if missing:
        raise SystemExit("no verbatim message text for %d arm(s): %s" % (len(missing), missing[:5]))
    out["Control"] = ("No message. Respondents rated the same policy statements with no "
                      "persuasive message and no party-leader cue.")
    return out


def main(check_only=False):
    convert()
    tp = pd.read_csv(RAW, low_memory=False)
    d = derive(tp)
    v = verify(d, tp)
    print(json.dumps({k: x for k, x in v.items() if k != "failures"}, indent=1))
    if v["failures"]:
        raise SystemExit("ARM DERIVATION REFUSED:\n  - " + "\n  - ".join(v["failures"]))
    print("arm derivation checks PASS (%d arms, n_treat %d-%d, n_control %d-%d)"
          % (v["n_arms"], *v["n_per_arm_treat"], *v["n_per_arm_control"]))
    if check_only:
        if not OUT.exists():
            raise SystemExit("%s missing" % OUT)
        old = pd.read_csv(OUT, low_memory=False)
        same = old.shape == d.shape and bool((old.condition_arm.values == d.condition_arm.values).all())
        print("derived file %s" % ("MATCHES" if same else "DRIFTED"))
        return 0 if same else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    d.to_csv(OUT, index=False)
    print("wrote %s  (%d rows x %d cols)" % (OUT, *d.shape))
    if ARMTEXT.exists():
        BRIEFTEXT.write_text(json.dumps(compose_brief_texts(d), indent=1, ensure_ascii=False))
        print("wrote %s (%d arms + Control)" % (BRIEFTEXT, len(json.loads(BRIEFTEXT.read_text())) - 1))
    else:
        print("NOTE: %s not present yet - brief texts not composed" % ARMTEXT)
    (RUN / "runs" / "_scratch" / "tappin_arm_table.csv").write_text(arm_table(d).to_csv(index=False))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true")
    sys.exit(main(ap.parse_args().check))
