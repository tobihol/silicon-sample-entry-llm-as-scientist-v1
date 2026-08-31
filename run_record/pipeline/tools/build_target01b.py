#!/usr/bin/env python
"""tools/build_target01b.py - the PENDING-OPERATOR distributional variant of the deposit.

Session 18's audit found exactly one card value with a mechanical proof behind it
(`runs/_dist/PREREG.md` V2): the target's `belief_post` is a SINGLE 0-100 item and the
deposited `control_sd` of 22.27 is the design twin's THREE-item composite SD, so the
deposit is under-dispersed on that outcome by construction. This tool rebuilds stages 7
and 8 from `runs/20260815-target-01`'s own card with that one number corrected, into a
NEW run directory. It makes NO model call and it never touches target-01.

    /opt/kernel/venv/bin/python tools/build_target01b.py            # plan + build
    /opt/kernel/venv/bin/python tools/build_target01b.py --run-id 20260822-target-01b

Three things it refuses to do, each asserted rather than promised:

  * A5 - it re-derives Tier 2 main, Tier 2 moderator and Tier 3 from the card and requires
    them to equal target-01's deposited payloads to 1e-9. A `control_sd` may move Section
    4 and nothing else; if any Section-1/2/3 number moves, the build aborts.
  * it copies the card rather than editing it, and asserts that `ate.csv`,
    `subgroup.csv` and `responsiveness.csv` are byte-identical to target-01's.
  * it stamps `publication_status` from the deposit window like every other build
    (standing finding 61) and marks the entry PENDING-OPERATOR in the metadata note.
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
import ssb  # noqa: E402

SRC = RUN / "runs/20260815-target-01"
SEED_SCAN = [0, 1, 2, 3, 4]
N_PER, N_CTRL = 2400, 4800
BELIEF_SD = 26.96          # runs/_dist/PREREG.md V2; 22.27 = 26.96 * sqrt(0.524 + 0.476/3)
WINDOW_OPEN, WINDOW_CLOSE = dt.date(2026, 8, 28), dt.date(2026, 8, 31)


def main(run_id: str, team_id: str, entry: str, version: int) -> int:
    d = ssb.gates.new_run(run_id, source=str(SRC), change="belief_post control_sd 22.27 -> %.2f"
                          % BELIEF_SD, prereg="runs/_dist/PREREG.md V2")
    print(f"run dir: {d}")
    ssb.gates.record(d, "G1_frozen_intact", ssb.gates.frozen_hash() ==
                     json.loads((d / "run.json").read_text())["frozen_sha256"],
                     "APPEND_SYSTEM.md sha256 matches the value recorded at run start")
    src_gates = json.loads((SRC / "gates.json").read_text())
    for g in ("G2_practice_scored", "G3_calibration_fitted"):
        ssb.gates.record(d, g, src_gates[g]["passed"],
                         src_gates[g]["detail"] + " (inherited from %s; no model call)" % SRC.name)

    # ---- the card: copied, then ONE number changed -------------------------------------------
    shutil.copytree(SRC / "card", d / "card")
    b = pd.read_csv(d / "card" / "baseline.csv")
    old = float(b.loc[b.outcome == "belief_post", "control_sd"].iloc[0])
    b.loc[b.outcome == "belief_post", "control_sd"] = BELIEF_SD
    b.to_csv(d / "card" / "baseline.csv", index=False)
    for f in ("ate.csv", "subgroup.csv", "responsiveness.csv", "tilt.csv"):
        assert (d / "card" / f).read_bytes() == (SRC / "card" / f).read_bytes(), f
    print(f"card: belief_post control_sd {old} -> {BELIEF_SD}; ate/subgroup/responsiveness/tilt "
          f"byte-identical to {SRC.name}")

    crd = ssb.card.Card.load(d / "card")
    problems = crd.validate()
    clipped = crd.clipping_report()
    ssb.gates.record(d, "G4_card_complete", not problems and len(clipped) == 0,
                     "%d validation problems, %d clipped cells" % (len(problems), len(clipped)))
    assert not problems and len(clipped) == 0, (problems, clipped)

    # ---- A5: Sections 1-3 must be untouched --------------------------------------------------
    src_crd = ssb.card.Card.load(SRC / "card")
    worst = 0.0
    for name, a, bb in (("tier3", src_crd.tier3(), crd.tier3()),
                        ("tier2_main", src_crd.tier2_main(), crd.tier2_main()),
                        ("tier2_moderator", src_crd.tier2_moderator(), crd.tier2_moderator())):
        assert list(a.columns) == list(bb.columns) and len(a) == len(bb), name
        num = [c for c in a.columns if pd.api.types.is_numeric_dtype(a[c])]
        w = max(float((a[c].astype(float) - bb[c].astype(float)).abs().max()) for c in num)
        worst = max(worst, w)
        assert w < 1e-9, f"A5 violated: {name} moved by {w:g} pp"
    print(f"A5: Tier 2 main, Tier 2 moderator and Tier 3 identical to {SRC.name} "
          f"(max |diff| {worst:.3g})")

    # ---- stage 7 -----------------------------------------------------------------------------
    joint = pd.read_csv(RUN / "inputs/pool/joint.csv")
    scan = []
    for s in SEED_SCAN:
        t1s, diags = ssb.synth.synthesize(crd, joint, n_per_intervention=N_PER,
                                          n_control=N_CTRL, seed=s)
        r = ssb.gates.check_reconstruction(crd, t1s)
        scan.append({"seed": s, **{k: round(v, 4) for k, v in r.items()},
                     "sd_min": float(diags.sd_ratio.min()), "sd_max": float(diags.sd_ratio.max())})
        print("  seed %d: tier3 %.4f tier2mod %.3f sd_ratio %.4f-%.4f"
              % (s, r["tier3_rmse_pp"], r["tier2mod_rmse_pp"], scan[-1]["sd_min"], scan[-1]["sd_max"]))
        if s == SEED_SCAN[0]:
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
                     "PENDING-OPERATOR distributional variant of %s. Identical predictions in "
                     "Sections 1-3 (Tier 2 and Tier 3 payloads are equal to %s's to 1e-9); the "
                     "only change is card.baseline.control_sd for belief_post, 22.27 -> %.2f, "
                     "which moves ONLY the Tier-1 response distribution. Evidence and adoption "
                     "rule: runs/_dist/PREREG.md V2." % (SRC.name, SRC.name, BELIEF_SD))})
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
        "note": ("PENDING-OPERATOR distributional variant of %s: belief_post control_sd "
                 "22.27 -> %.2f (runs/_dist/PREREG.md V2). Sections 1-3 identical to 1e-9; "
                 "no model call; G6 worst seed %.3f" % (SRC.name, BELIEF_SD, worst6))})
    ssb.gates.record(d, "G8_recorded", True, "scoreboard row appended through the locked path")
    v = ssb.gates.verdict(d)
    print("\ngates:", json.dumps(v))
    (d / "stages" / "summary.json").write_text(json.dumps(
        {"run": str(d), "source": str(SRC), "change": {"belief_post.control_sd": [old, BELIEF_SD]},
         "verdict": v, "validator": verdicts, "seed_scan": scan,
         "a5_max_abs_diff_sections_1_3": worst, "model_calls": 0}, indent=1))
    return 0 if v["may_finish"] else 1


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--run-id", default="20260822-target-01b")
    a.add_argument("--team-id", default="team_31")
    a.add_argument("--entry", default="primary")
    a.add_argument("--version", type=int, default=1)
    n = a.parse_args()
    sys.exit(main(n.run_id, n.team_id, n.entry, n.version))
