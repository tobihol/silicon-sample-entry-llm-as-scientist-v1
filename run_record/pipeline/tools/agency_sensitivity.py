#!/usr/bin/env python
"""OPEN item 14: what does WHERE the agencies sit actually change on a scored row?

    /opt/kernel/venv/bin/python tools/agency_sensitivity.py runs/<run-id>
    -> runs/<run-id>/stages/agency_sensitivity.json

`inst_trust_mean` is one of thirteen outcomes and its level is a composition; the last free
parameter in that composition is theta, where EPA/NASA/NOAA sit on the span from the scientific
community (0) to the federal government (1). Run 05 assumed 0.500; the W149 topline measures
0.319 with a bracket of [0.067, 0.319] (tools/measure_agency_anchor.py).

This script rebuilds the baselines at each theta from the SAME predicted ATEs, synthesises with
the SAME seed, and reports the rows the choice can move - demographic baseline RMSE (variant
against variant), parity gap, predictability R^2 - plus the two gates it could break. It reuses
tools/fanout_sensitivity.py's helpers so the two sensitivities are computed identically.
"""
import json, subprocess, sys, tempfile
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ssb  # noqa: E402
from fanout_sensitivity import parity_gap, predictability  # noqa: E402

RUN = Path(__file__).resolve().parents[1]
PY = "/opt/kernel/venv/bin/python"


def main(run_dir):
    run_dir = Path(run_dir)
    anchor = json.loads((RUN / "inputs" / "measured" / "agency_trust_anchor.json").read_text())
    lo, hi = anchor["adopted"]["theta_bracket_over_wave_x_notsure"]
    adopted = anchor["adopted"]["theta_agencies"]
    variants = {"theta_science_end_%.3f" % lo: lo,
                "theta_ADOPTED_%.3f" % adopted: adopted,
                "theta_prior_midpoint_0.500": 0.5,
                "theta_government_end_1.000": 1.0}

    ate = pd.read_csv(run_dir / "card" / "ate.csv")
    joint = pd.read_csv(RUN / "inputs" / "pool" / "joint.csv")
    tmp = Path(tempfile.mkdtemp(prefix="agency_sens_"))
    res, cards, levels = {}, {}, {}
    for name, th in variants.items():
        out = tmp / name
        subprocess.run([PY, str(RUN / "tools" / "build_baselines.py"),
                        "--agency-theta", str(th), "--out", str(out / "baselines")],
                       check=True, capture_output=True)
        for sub in ("pool", "measured", "texts", "adapters", "prompts"):     # the rest of inputs/
            src = RUN / "inputs" / sub
            if src.exists() and not (out / sub).exists():
                (out / sub).symlink_to(src)
        for f in ("format_params.json", "stimuli.json", "prompt_budget.json"):
            if (RUN / "inputs" / f).exists() and not (out / f).exists():
                (out / f).symlink_to(RUN / "inputs" / f)
        crd = ssb.card.from_inputs(ate, meta={"variant": name}, inputs=out)
        t1, diag = ssb.synth.synthesize(crd, joint, n_per_intervention=2400, n_control=4800, seed=0)
        cards[name] = crd
        lv = pd.read_csv(out / "baselines" / "control_levels.csv").set_index("outcome")
        levels[name] = float(lv.loc["inst_trust_mean", "control_mean"])
        rec = ssb.gates.check_reconstruction(crd, t1)
        res[name] = {"theta": th, "inst_trust_mean_level": levels[name],
                     "gate_G6": {k: round(v, 4) for k, v in rec.items()},
                     "gate_G7_sd_ratio": [float(diag.sd_ratio.min()), float(diag.sd_ratio.max())],
                     "parity_gap_pp_inst_trust_mean": round(parity_gap(crd)["inst_trust_mean"], 2),
                     "predictability_r2_inst_trust_mean": round(predictability(t1)["inst_trust_mean"], 4)}
        print("  %-28s theta %.3f  level %5.1f  G6 tier2mod %.3f  parity %5.2f  R2 %.4f"
              % (name, th, levels[name], rec["tier2mod_rmse_pp"],
                 res[name]["parity_gap_pp_inst_trust_mean"],
                 res[name]["predictability_r2_inst_trust_mean"]))

    # every pair as a prediction of every other: the size of the judgement call, in the units of
    # the row it lands on (demographic baseline RMSE over the Tier-2 moderator grid)
    keys = list(variants)
    dist = {}
    for i, a_ in enumerate(keys):
        for b_ in keys[i + 1:]:
            a = cards[a_].tier2_moderator().merge(
                cards[b_].tier2_moderator(),
                on=["condition", "moderator", "moderator_level", "outcome"], suffixes=("_a", "_b"))
            a["d"] = [ssb.spec.to_pp(r.mean_a - r.mean_b, r.outcome) for r in a.itertuples()]
            dist["%s vs %s" % (a_, b_)] = {
                "demographic_baseline_rmse_pp_all_outcomes": round(float(np.sqrt((a.d ** 2).mean())), 4),
                "rmse_pp_inst_trust_mean_only":
                    round(float(np.sqrt((a[a.outcome == "inst_trust_mean"].d ** 2).mean())), 3),
                "max_abs_pp": round(float(a.d.abs().max()), 3),
                "cells_moved": int((a.d.abs() > 1e-9).sum()), "cells_total": int(len(a))}
    res["variant_distance"] = dist
    res["_reading"] = (
        "theta moves ONE of thirteen outcomes' level, so its footprint on the pooled demographic "
        "baseline RMSE is the per-outcome move divided by sqrt(13). The adopted-vs-prior distance is "
        "the number that matters: it is what run 05 would have deposited and run 06 does not.")
    p = run_dir / "stages" / "agency_sensitivity.json"
    p.write_text(json.dumps(res, indent=1))
    print("\n" + json.dumps(dist, indent=1))
    return res


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "runs/20260815-dryrun-06")
