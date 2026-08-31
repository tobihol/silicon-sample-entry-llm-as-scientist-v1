#!/usr/bin/env python
"""OPEN item 13: what does the Pew climate-referent fan-out actually change?

    /opt/kernel/venv/bin/python tools/build_baselines.py --fanout 0 --out /tmp/nofanout/baselines
    /opt/kernel/venv/bin/python tools/fanout_sensitivity.py runs/<run-id> /tmp/nofanout
    -> runs/<run-id>/stages/fanout_sensitivity.json

The card applies a x1.55 stretch to the PARTY contrast on the climate-scientist trust outcomes,
because W42 measures an 11.83 pp partisan fan-out when the referent moves from medical to
environmental research scientists. That is the largest judgement call in the baselines, so it
gets measured rather than argued: this script builds both cards from the SAME predicted ATEs,
synthesises both with the SAME seed, and reports the three Tier-1 rows the choice can move -
demographic baseline RMSE (variant against variant), demographic parity gap, and demographic
predictability R^2 - plus the two gates it could break.
"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402

RUN = Path(__file__).resolve().parents[1]
MODS = list(ssb.spec.load()["moderators"])
OUTS = ssb.spec.load()["outcomes"]


def predictability(t1: pd.DataFrame) -> dict:
    """R^2 of each outcome on the six moderators (additive dummies, OLS, control arm only).
    The frozen table asks whether the synthetic data EXAGGERATES group differences, so this is
    computed the same way for both variants and compared, never reported as an absolute truth."""
    d = t1[t1.condition == "control"] if "control" in set(t1.condition) else t1
    X = pd.get_dummies(d[MODS], drop_first=True).to_numpy(float)
    X = np.column_stack([np.ones(len(X)), X])
    out = {}
    for o in OUTS:
        y = pd.to_numeric(d[o], errors="coerce").to_numpy(float)
        m = np.isfinite(y)
        beta, *_ = np.linalg.lstsq(X[m], y[m], rcond=None)
        resid = y[m] - X[m] @ beta
        out[o] = float(1 - resid.var() / y[m].var())
    return out


def parity_gap(crd) -> dict:
    """Worst-served minus best-served demographic group, per outcome, in the control condition."""
    ctrl = crd.tier2_moderator()
    ctrl = ctrl[ctrl.condition.str.lower().str.contains("control")]
    g = ctrl.groupby("outcome")["mean"]
    return {o: float(ssb.spec.to_pp(g.max()[o] - g.min()[o], o)) for o in g.max().index}


def main(run_dir, alt_inputs):
    run_dir, alt_inputs = Path(run_dir), Path(alt_inputs)
    ate = pd.read_csv(run_dir / "card" / "ate.csv")
    joint = pd.read_csv(RUN / "inputs" / "pool" / "joint.csv")
    res = {}
    cards, tier1s = {}, {}
    for name, inputs in [("with_fanout", RUN / "inputs"), ("no_fanout", alt_inputs)]:
        crd = ssb.card.from_inputs(ate, meta={"variant": name}, inputs=inputs)
        # same size as the deposit (43,200 rows): at the 21,600 floor the G6 statistic below is
        # noise-dominated (2.487 +/- 0.099) and could not distinguish the two variants at all
        t1, diag = ssb.synth.synthesize(crd, joint, n_per_intervention=2400, n_control=4800, seed=0)
        cards[name], tier1s[name] = crd, t1
        rec = ssb.gates.check_reconstruction(crd, t1)
        res[name] = {"gate_G6": {k: round(v, 4) for k, v in rec.items()},
                     "gate_G7_sd_ratio": [float(diag.sd_ratio.min()), float(diag.sd_ratio.max())],
                     "parity_gap_pp": {k: round(v, 2) for k, v in parity_gap(crd).items()},
                     "predictability_r2": {k: round(v, 4) for k, v in predictability(t1).items()}}
    # the two variants as predictions OF EACH OTHER: this is the size of the judgement call
    a = cards["with_fanout"].tier2_moderator().merge(
        cards["no_fanout"].tier2_moderator(),
        on=["condition", "moderator", "moderator_level", "outcome"], suffixes=("_a", "_b"))
    a["d"] = [ssb.spec.to_pp(r.mean_a - r.mean_b, r.outcome) for r in a.itertuples()]
    res["variant_distance"] = {
        "demographic_baseline_rmse_pp": float(np.sqrt((a.d ** 2).mean())),
        "max_abs_pp": float(a.d.abs().max()),
        "cells_moved": int((a.d.abs() > 1e-9).sum()), "cells_total": int(len(a)),
        "worst": a.reindex(a.d.abs().sort_values(ascending=False).index).head(4)[
            ["moderator", "moderator_level", "outcome", "d"]].round(2).to_dict("records")}
    p = run_dir / "stages" / "fanout_sensitivity.json"
    p.write_text(json.dumps(res, indent=1))
    print(json.dumps(res["variant_distance"], indent=1))
    for k in res:
        if k != "variant_distance":
            print(k, "G6", res[k]["gate_G6"], "G7", [round(x, 3) for x in res[k]["gate_G7_sd_ratio"]])
    return res


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
