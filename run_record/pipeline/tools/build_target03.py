#!/usr/bin/env python
"""tools/build_target03.py - the COMBINED candidate card the operator approved in TASK_20.

target-03 is `runs/20260815-target-01`'s card with THREE changes and no others, built into a
NEW run directory. It makes NO model call: the 16 x 13 ATE table, the responsiveness factors
and tilt.csv are copied byte-for-byte, so every Section-1, -2 and -3 prediction is target-01's.

    C1  baseline.control_sd[belief_post]        22.27 -> 26.96   (session 18, runs/_dist/PREREG.md V2)
    C2  subgroup.offset x 0.30 for age_band, education, income, race; party and gender untouched
                                                                  (arm partisan R1, runs/_offsets/)
    C3  subgroup.offset[gender=Other, trust]    -7.04 -> +14.46   (arm partisan R2, rule G-OTHER)

Rule G-OTHER, pre-declared in runs/_target03/PREREG.md section 2 BEFORE this file existed: the
held-out estimate is +18.64 [14.46, 22.82] against a deposited -7.04 (z = -12.05), so the SIGN is
forced and the MAGNITUDE is a judgement. The conservative (nearest-zero) end of the interval is
deposited because (a) both anchors are non-probability panels whose non-binary respondents skew
young and liberal - a bias whose direction on climate trust is known and positive, against a
census-quota target; and (b) this card's `Other` offsets from single-source anchors already read
2.67x and 2.85x the held-out human value on concern and behaviour.

    /opt/kernel/venv/bin/python tools/build_target03.py

Five things it refuses to do, asserted rather than promised (runs/_target03/PREREG.md section 4):

  A1  ate.csv, responsiveness.csv and tilt.csv byte-identical to target-01's.
  A2  Tier 3 equal to target-01's deposited payload to 1e-9.
  A3  Tier 2 main equal to target-01's to 1e-9.
  A4  The Tier-2 condition x moderator INTERACTION CONTRAST equal to target-01's to 1e-9 and
      still exactly 0 - C2 and C3 are LEVEL offsets and Section 3 is scored on interactions
      (standing findings 53, 62). Level means move; that is the point.
  A5  card.validate() empty, clipping_report() empty, and the share-centring identity
      sum_l share_l * offset_l = 0 held to 1e-12 after the re-centring C3 forces.

and one verification the operator asked for by name:

  V1  the 7-of-7 held-out-anchor improvement re-scored from THIS card's subgroup.csv, mapped
      through tools/subgroup_audit.card_offsets, not from an abstract multiplier.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(RUN / "tools"))
import ssb  # noqa: E402

SRC = RUN / "runs/20260815-target-01"
SEED_SCAN = [0, 1, 2, 3, 4]
N_PER, N_CTRL = 2400, 4800

BELIEF_SD = 26.96                                   # C1
SHRINK_BLOCK = ("age_band", "education", "income", "race")   # C2
SHRINK_K = 0.30                                     # --shrink-k overrides (see --help)
TRUST_POS = ("trust_multidimensional", "trust_post", "inst_trust_mean")   # C3
TRUST_NEG = ("distrust_post",)
OTHER_TRUST = 14.46      # rule G-OTHER: the nearest-zero end of [14.46, 22.82]

WINDOW_OPEN, WINDOW_CLOSE = dt.date(2026, 8, 28), dt.date(2026, 8, 31)


def interaction_contrast(t2mod: pd.DataFrame) -> pd.DataFrame:
    """condition x moderator x level x outcome interaction against each moderator's first level.

    (mean[l,i] - mean[l,control]) - (mean[ref,i] - mean[ref,control]).  This is what the
    finalized prereg scores in Section 3 (TASK_08, standing finding 62).
    """
    w = t2mod.pivot_table(index=["moderator", "moderator_level", "outcome"],
                          columns="condition", values="mean")
    eff = w.drop(columns=["control"]).sub(w["control"], axis=0)
    ref = {m: g.index.get_level_values("moderator_level")[0]
           for m, g in eff.groupby(level="moderator")}
    base = eff.reset_index()
    key = base.moderator.map(ref)
    r = base.set_index(["moderator", "moderator_level", "outcome"])
    look = r.reset_index().merge(
        r.reset_index().assign(_ref=lambda d: d.moderator_level),
        left_on=["moderator", "outcome"], right_on=["moderator", "outcome"], suffixes=("", "_r"))
    look = look[look.moderator_level_r == look.moderator.map(ref)]
    cond = [c for c in eff.columns]
    out = look[["moderator", "moderator_level", "outcome"]].copy()
    for c in cond:
        out[c] = look[c].to_numpy() - look[f"{c}_r"].to_numpy()
    return out.sort_values(["moderator", "moderator_level", "outcome"]).reset_index(drop=True)


def apply_changes(crd) -> tuple[pd.DataFrame, dict]:
    """C1/C2/C3 + the re-centring C3 forces. Returns the new subgroup table and a change log."""
    log: dict = {}

    # ---- C1 -------------------------------------------------------------------------------
    old_sd = float(crd.baseline.loc[crd.baseline.outcome == "belief_post", "control_sd"].iloc[0])
    crd.baseline.loc[crd.baseline.outcome == "belief_post", "control_sd"] = BELIEF_SD
    log["C1_belief_post_control_sd"] = [old_sd, BELIEF_SD]

    s = crd.subgroup.copy()
    share = s.drop_duplicates(["moderator", "level"]).set_index(["moderator", "level"])["share"]

    # ---- C3 (before C2, so the two never touch the same cell: gender is not in the block) ---
    g = s.moderator == "gender"
    old_other = float(s[g & (s.level == "Other") & (s.outcome == "trust_post")].offset.iloc[0])
    delta = OTHER_TRUST - old_other
    s.loc[g & (s.level == "Other") & s.outcome.isin(TRUST_POS), "offset"] = OTHER_TRUST
    s.loc[g & (s.level == "Other") & s.outcome.isin(TRUST_NEG), "offset"] = -OTHER_TRUST
    so = float(share[("gender", "Other")])
    smf = float(share[("gender", "Male")] + share[("gender", "Female")])
    c = delta * so / smf                      # re-centring, arithmetic not judgement
    for lvl in ("Male", "Female"):
        s.loc[g & (s.level == lvl) & s.outcome.isin(TRUST_POS), "offset"] -= c
        s.loc[g & (s.level == lvl) & s.outcome.isin(TRUST_NEG), "offset"] += c
    log["C3_gender_Other_trust"] = [old_other, OTHER_TRUST]
    log["C3_recentre_Male_Female_pp"] = -c

    # ---- C2 --------------------------------------------------------------------------------
    blk = s.moderator.isin(SHRINK_BLOCK)
    log["C2_cells_shrunk"] = int(blk.sum())
    log["C2_k"] = SHRINK_K
    s.loc[blk, "offset"] *= SHRINK_K

    crd.subgroup = s[["moderator", "level", "outcome", "offset", "share"]]
    return s, log


def verify_offsets(new_sub: pd.DataFrame, src_sub: pd.DataFrame) -> dict:
    """V1 - re-score the held-out anchors from THIS card, LOSO-honest, exactly as arm
    `partisan` scored the abstract package. Returns a per-anchor table."""
    import subgroup_audit as sa
    import offset_loso as ol

    held = ol.load(RUN / "runs/_offsets")
    held = held[held.status.str.startswith("heldout")].copy()

    def oc_of(sub, mod, fam):
        return sa.card_offsets(sub, mod, fam)

    rows = []
    for nm, sub in (("P0 deposited card (target-01)", src_sub), ("target-03 card", new_sub)):
        cache = {}
        for d, gg in held.groupby("dataset"):
            pred, obs = [], []
            for _, x in gg.iterrows():
                k = (x.moderator, x.family)
                if k not in cache:
                    cache[k] = oc_of(sub, x.moderator, x.family)
                pred.append(cache[k][x.level])
                obs.append(x.oh)
            e = np.array(obs) - np.array(pred)
            rows.append(dict(package=nm, anchor=d, n=len(gg),
                             rmse=float(np.sqrt((e ** 2).mean()))))
    r = pd.DataFrame(rows)
    t = r.pivot_table(index="package", columns="anchor", values="rmse")
    t["MEAN"] = t.mean(axis=1)
    n_by = r.groupby("anchor").n.first()
    t["POOLED"] = [float(np.sqrt(np.average(
        r[r.package == p].set_index("anchor").rmse ** 2,
        weights=n_by.reindex(r[r.package == p].anchor).to_numpy()))) for p in t.index]
    return t


def main(run_id: str, team_id: str, entry: str, version: int) -> int:
    d = ssb.gates.new_run(run_id, source=str(SRC), prereg="runs/_target03/PREREG.md",
                          change="C1 belief_post control_sd 22.27->%.2f; C2 non-party offsets "
                                 "x%.2f; C3 gender=Other x trust -7.04->%+.2f (rule G-OTHER)"
                                 % (BELIEF_SD, SHRINK_K, OTHER_TRUST))
    print(f"run dir: {d}")
    ssb.gates.record(d, "G1_frozen_intact", ssb.gates.frozen_hash() ==
                     json.loads((d / "run.json").read_text())["frozen_sha256"],
                     "APPEND_SYSTEM.md sha256 matches the value recorded at run start")
    src_gates = json.loads((SRC / "gates.json").read_text())
    for g in ("G2_practice_scored", "G3_calibration_fitted"):
        ssb.gates.record(d, g, src_gates[g]["passed"],
                         src_gates[g]["detail"] + " (inherited from %s; no model call)" % SRC.name)

    # ---- the card ---------------------------------------------------------------------------
    shutil.copytree(SRC / "card", d / "card")
    crd = ssb.card.Card.load(d / "card")
    src_crd = ssb.card.Card.load(SRC / "card")
    src_sub = src_crd.subgroup.copy()
    new_sub, log = apply_changes(crd)
    crd.save(d / "card")

    # A1
    for f in ("ate.csv", "responsiveness.csv", "tilt.csv"):
        assert (d / "card" / f).read_bytes() == (SRC / "card" / f).read_bytes(), f"A1: {f} moved"
    print("A1: ate.csv, responsiveness.csv, tilt.csv byte-identical to %s" % SRC.name)
    print("C1: belief_post control_sd %.2f -> %.2f" % tuple(log["C1_belief_post_control_sd"]))
    print("C2: %d offset cells x %.2f  (%s; party and gender untouched)"
          % (log["C2_cells_shrunk"], SHRINK_K, ", ".join(SHRINK_BLOCK)))
    print("C3: gender=Other x trust %+.2f -> %+.2f; Male/Female re-centred by %+.4f pp"
          % (log["C3_gender_Other_trust"][0], OTHER_TRUST, log["C3_recentre_Male_Female_pp"]))

    # A5 - centring, validation, clipping
    worst_centre = 0.0
    for m, grp in crd.subgroup.groupby("moderator"):
        w = grp.groupby("outcome").apply(lambda x: float((x.offset * x.share).sum()),
                                         include_groups=False)
        worst_centre = max(worst_centre, float(w.abs().max()))
    assert worst_centre < 1e-12, f"A5: centring identity broken, {worst_centre:g}"
    problems, clipped = crd.validate(), crd.clipping_report()
    ssb.gates.record(d, "G4_card_complete", not problems and len(clipped) == 0,
                     "%d validation problems, %d clipped cells, centring %.2e"
                     % (len(problems), len(clipped), worst_centre))
    assert not problems and len(clipped) == 0, (problems, clipped)
    print("A5: validate clean, 0 clipped cells, centring identity %.2e" % worst_centre)

    # ---- A2 / A3 / A4 -----------------------------------------------------------------------
    def maxdiff(a, b):
        num = [c for c in a.columns if pd.api.types.is_numeric_dtype(a[c])]
        assert list(a.columns) == list(b.columns) and len(a) == len(b)
        return max(float((a[c].astype(float) - b[c].astype(float)).abs().max()) for c in num)

    w3 = maxdiff(src_crd.tier3(), crd.tier3())
    w2 = maxdiff(src_crd.tier2_main(), crd.tier2_main())
    assert w3 < 1e-9, f"A2 violated: Tier 3 moved by {w3:g} pp"
    assert w2 < 1e-9, f"A3 violated: Tier 2 main moved by {w2:g} pp"
    ic_src = interaction_contrast(src_crd.tier2_moderator())
    ic_new = interaction_contrast(crd.tier2_moderator())
    wi = maxdiff(ic_src, ic_new)
    mx = max(float(ic_new[c].abs().max()) for c in ic_new.columns
             if pd.api.types.is_numeric_dtype(ic_new[c]))
    assert wi < 1e-9 and mx < 1e-9, f"A4 violated: contrast moved {wi:g}, max |contrast| {mx:g}"
    t2m_src, t2m_new = src_crd.tier2_moderator(), crd.tier2_moderator()
    lvl_moved = float((t2m_src["mean"] - t2m_new["mean"]).abs().max())
    n_moved = int(((t2m_src["mean"] - t2m_new["mean"]).abs() > 1e-9).sum())
    print("A2: Tier 3 identical (max |diff| %.3g)   A3: Tier 2 main identical (%.3g)" % (w3, w2))
    print("A4: Tier-2 interaction contrast identical (%.3g) and exactly 0 (max |contrast| %.3g)"
          % (wi, mx))
    print("    Tier-2 moderator LEVEL means: %d of %d cells move, worst %.3f pp (expected)"
          % (n_moved, len(t2m_new), lvl_moved))

    # ---- V1 ---------------------------------------------------------------------------------
    off_tab = verify_offsets(crd.subgroup, src_sub)
    off_tab.to_csv(d / "stages" / "v1_heldout_offsets.csv")
    a = off_tab.loc["P0 deposited card (target-01)"]
    b = off_tab.loc["target-03 card"]
    anchors = [c for c in off_tab.columns if c not in ("MEAN", "POOLED")]
    wins = int(sum(b[c] < a[c] for c in anchors))
    print("\nV1: subgroup-offset RMSE (pp) against each held-out anchor, LOSO-honest")
    print(off_tab.round(3).to_string())
    print("    target-03 beats target-01 on %d of %d held-out anchors "
          "(pooled %.3f -> %.3f pp)" % (wins, len(anchors), a["POOLED"], b["POOLED"]))
    assert wins == len(anchors), f"V1: expected all {len(anchors)} anchors, got {wins}"

    # ---- the inherited calibration artefact ---------------------------------------------------
    # G3 above records the calibration as INHERITED from target-01. A run that inherits a fit must
    # also carry the artefact that describes it: tools/fill_registration.py reads
    # stages/calibration/lambda.json for registration item G.3, and a run without it crashed with
    # a TypeError instead of reporting the inheritance. No fit is performed here.
    (d / "stages" / "calibration").mkdir(parents=True, exist_ok=True)
    shutil.copy(SRC / "stages/calibration/lambda.json", d / "stages/calibration/lambda.json")
    print("calibration: lambda.json inherited from %s (no fit performed; policy 'none' - the "
          "multiplier is NOT applied)" % SRC.name)

    # ---- stage 7 -----------------------------------------------------------------------------
    joint = pd.read_csv(RUN / "inputs/pool/joint.csv")
    scan = []
    for s_ in SEED_SCAN:
        t1s, diags = ssb.synth.synthesize(crd, joint, n_per_intervention=N_PER,
                                          n_control=N_CTRL, seed=s_)
        r = ssb.gates.check_reconstruction(crd, t1s)
        scan.append({"seed": s_, **{k: round(v, 4) for k, v in r.items()},
                     "sd_min": float(diags.sd_ratio.min()), "sd_max": float(diags.sd_ratio.max())})
        print("  seed %d: tier3 %.4f tier2mod %.3f sd_ratio %.4f-%.4f"
              % (s_, r["tier3_rmse_pp"], r["tier2mod_rmse_pp"],
                 scan[-1]["sd_min"], scan[-1]["sd_max"]))
        if s_ == SEED_SCAN[0]:
            t1, diag = t1s, diags
    sc = pd.DataFrame(scan)
    sc.to_csv(d / "stages" / "g6_seed_scan.csv", index=False)
    t1.to_csv(d / "stages" / "tier1.csv", index=False)
    diag.to_csv(d / "stages" / "synth_diagnostics.csv", index=False)
    worst6 = float(sc.tier2mod_rmse_pp.max())
    ssb.gates.record(d, "G6_reconstruction",
                     bool(worst6 < ssb.gates.TOL["G6_tier2mod_rmse_pp"]
                          and sc.tier3_rmse_pp.max() < ssb.gates.TOL["G6_tier3_rmse_pp"]),
                     "seed scan over %d seeds: tier2mod %.3f-%.3f (tol %.2f), tier3 max %.4f"
                     % (len(scan), sc.tier2mod_rmse_pp.min(), worst6,
                        ssb.gates.TOL["G6_tier2mod_rmse_pp"], sc.tier3_rmse_pp.max()))
    sdr = (float(sc.sd_min.min()), float(sc.sd_max.max()))
    ssb.gates.record(d, "G7_dispersion", abs(np.log(sdr[0])) < 0.1 and abs(np.log(sdr[1])) < 0.1,
                     "sd_ratio %.3f-%.3f over the seed scan" % sdr)

    # ---- stage 8 -----------------------------------------------------------------------------
    meta = {k: v for k, v in json.loads((SRC / "submission_T1/metadata.json").read_text()).items()
            if k not in ("prediction_files", "coverage", "tier", "entry")}
    today = dt.date.today()
    meta.update({"team_id": team_id, "built_at": today.isoformat(),
                 "publication_window": f"{WINDOW_OPEN} .. {WINDOW_CLOSE}",
                 "not_for_publication_before": WINDOW_OPEN.isoformat(),
                 "publication_status": (
                     f"NOT-FOR-PUBLICATION - built {today}, {(WINDOW_OPEN - today).days} days "
                     f"before the deposit window opens on {WINDOW_OPEN}"
                     if today < WINDOW_OPEN else
                     ("in-window" if today <= WINDOW_CLOSE
                      else "AFTER THE PREDICTION LOCK - do not deposit")),
                 "variant_note": (
                     "COMBINED candidate card built from %s under the operator's TASK_20 rulings. "
                     "Sections 1-3 are IDENTICAL to %s (Tier 3 and Tier 2 main equal to 1e-9; the "
                     "condition x moderator interaction contrast equal and exactly 0). Three "
                     "changes, all in the baseline/offset layer: belief_post control_sd "
                     "22.27 -> %.2f; age_band/education/income/race subgroup offsets x %.2f; "
                     "gender=Other x trust -7.04 -> %+.2f with Male/Female re-centred %+.4f. "
                     "Pre-registration: runs/_target03/PREREG.md."
                     % (SRC.name, SRC.name, BELIEF_SD, SHRINK_K, OTHER_TRUST,
                        log["C3_recentre_Male_Female_pp"]))})
    res = ssb.deposit.build(d, crd, t1, meta, version=version, entry=entry)
    print(ssb.deposit.summarise(res))
    verdicts = {k: v["verdict"] for k, v in res.items()}
    ssb.gates.record(d, "G5_validator_pass", all("FAIL" not in v for v in verdicts.values()),
                     json.dumps(verdicts))

    ssb.gates.scoreboard_append({
        "run_id": d.name, "stage": "target", "stub": False, "task_id": "TARGET", "n_cells": 208,
        "leak_verdict": "n/a (no sealed truth exists for the target)",
        "cal_beta": float(json.loads((SRC / "stages/summary.json").read_text())
                          ["calibration"]["_pooled"]),
        "note": ("COMBINED candidate from %s (TASK_20): belief_post control_sd 22.27->%.2f, "
                 "non-party offsets x%.2f, gender=Other x trust -7.04->%+.2f. Sections 1-3 "
                 "identical to 1e-9; no model call; G6 worst seed %.3f; V1 %d/%d anchors"
                 % (SRC.name, BELIEF_SD, SHRINK_K, OTHER_TRUST, worst6, wins, len(anchors)))})
    ssb.gates.record(d, "G8_recorded", True, "scoreboard row appended through the locked path")
    v = ssb.gates.verdict(d)
    print("\ngates:", json.dumps(v))
    (d / "stages" / "summary.json").write_text(json.dumps(
        {"run": str(d), "source": str(SRC), "prereg": "runs/_target03/PREREG.md",
         "changes": log, "verdict": v, "validator": verdicts, "seed_scan": scan,
         "a2_tier3_max_abs_diff": w3, "a3_tier2main_max_abs_diff": w2,
         "a4_interaction_max_abs_diff": wi, "a4_max_abs_contrast": mx,
         "tier2mod_level_cells_moved": n_moved, "tier2mod_level_worst_pp": lvl_moved,
         "v1_anchors_won": [wins, len(anchors)],
         "v1_pooled_rmse_pp": {"target-01": float(a["POOLED"]), "target-03": float(b["POOLED"])},
         "centring_identity": worst_centre, "model_calls": 0}, indent=1))
    return 0 if v["may_finish"] else 1


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--run-id", default="20260823-target-03")
    a.add_argument("--team-id", default="team_31")
    a.add_argument("--entry", default="primary")
    a.add_argument("--version", type=int, default=1)
    a.add_argument("--shrink-k", type=float, default=SHRINK_K,
                   help="C2 multiplier for the non-party offset blocks. 0.30 is the operator's "
                        "TASK_20 ruling (target-03). 0.50 is package P6 of the SAME "
                        "pre-registered table (runs/_offsets/packages.csv), which also wins 7 of "
                        "7 anchors on the demographic-baseline-RMSE row and is far better "
                        "calibrated on the parity-gap and predictability rows.")
    n = a.parse_args()
    globals()["SHRINK_K"] = n.shrink_k
    sys.exit(main(n.run_id, n.team_id, n.entry, n.version))
