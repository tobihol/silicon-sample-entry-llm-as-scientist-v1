#!/usr/bin/env python
"""tools/synth_variants.py - the pre-registered distributional improvement loop.

Stage 7 of the AGENTS.md loop, re-run under a named SYNTHESIS VARIANT, scored on the
construct-twin table of `tools/dist_audit.py`.  Nothing here touches the deposited run:
each variant writes to runs/_dist/<variant>/ and the deposit is rebuilt only by
tools/build_target01b.py, only for a variant the pre-registration adopted.

    /opt/kernel/venv/bin/python tools/synth_variants.py --variant base --seeds 0,1,2,3,4
    /opt/kernel/venv/bin/python tools/synth_variants.py --variant rho_measured
    /opt/kernel/venv/bin/python tools/synth_variants.py --compare base rho_measured

A variant is a pair (card SD overrides, per-outcome item-correlation map).  Both are
recorded in the variant's own JSON so a later reader can see exactly what produced a
number, and `base` is the deposited setting so every contrast has a matched control.

WHY THE SEED SCAN IS THE FIRST THING RUN.  Standing finding 18: a gate that passes on
one seed is not a gate.  Every metric here is computed from 43,200 sampled rows, so the
seed SPREAD - not the draw - is what says whether an improvement is real.  `--seeds`
prints it, and the pre-registration's DETECTED rule is stated in units of it.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RUN = Path("/workspace/run")
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(RUN / "tools"))

import ssb                                   # noqa: E402
import dist_audit as DA                      # noqa: E402

CARD = RUN / "runs/20260815-target-01/card"
OUT = RUN / "runs/_dist"
N_PER, N_CTRL = 2400, 4800                   # exactly the deposited pool (43,200 rows)

# Within-scale item correlation, measured on each target composite's own construct twin
# (control arm, native 0-100 sliders unless noted).  tools/dist_audit.py --rho prints
# the measurement; the numbers are quoted in runs/_dist/PREREG.md.
RHO_MEASURED = {
    "trust_multidimensional": 0.613,   # TISP US 12-item battery (5-point; rho is scale-free)
    "policy_role_mean": 0.594,         # TISP US NORMPERC x4 (5-point)
    "inst_trust_mean": 0.600,          # no twin - left at the historical default
    "concern_mean": 0.904,             # voelkel2026 Concern_Pre x3, control arm
    "policy_specific_mean": 0.584,     # vlasceanu2024 US control, the SEVEN target items
    "behavior_mean": 0.381,            # voelkel2026 IntentNp_Pre x6, control arm
}

# Card control_sd overrides.  belief_post is the one k-mismatch the audit found: the
# deposited 22.27 is voelkel2026 Belief_Pre's COMPOSITE SD (3 items) used for a target
# outcome that is a SINGLE item, and the same twin's implied single-item SD is 26.96.
SD_BELIEF = {"belief_post": 26.96}

# Mean-variance link exponent for the per-respondent latent SD; 0.0 is the deposited
# behaviour (one scalar SD for everybody), 1.003 +- 0.073 is what humans read.
GAMMA = 1.0

VARIANTS = {
    "base":          {"sd": {}, "rho": 0.6, "gamma": 0.0},
    "rho_measured":  {"sd": {}, "rho": RHO_MEASURED, "gamma": 0.0},
    "belief_sd":     {"sd": SD_BELIEF, "rho": 0.6, "gamma": 0.0},
    "both":          {"sd": SD_BELIEF, "rho": RHO_MEASURED, "gamma": 0.0},
    "hetero_sd":     {"sd": {}, "rho": 0.6, "gamma": GAMMA},
    "all":           {"sd": SD_BELIEF, "rho": RHO_MEASURED, "gamma": GAMMA},
    # the deposit candidate: only the changes the pre-registration adopted
    "adopted":       {"sd": SD_BELIEF, "rho": 0.6, "gamma": GAMMA},
    "hetero_sd_cell": {"sd": SD_BELIEF, "rho": 0.6, "gamma": GAMMA, "on_control": True},
}


def build(variant: str, seed: int = 0):
    v = VARIANTS[variant]
    crd = ssb.card.Card.load(CARD)
    if v["sd"]:
        crd.baseline = crd.baseline.copy()
        for o, sd in v["sd"].items():
            crd.baseline.loc[crd.baseline.outcome == o, "control_sd"] = sd
    joint = pd.read_csv(RUN / "inputs/pool/joint.csv")
    t1, diag = ssb.synth.synthesize(crd, joint, n_per_intervention=N_PER,
                                    n_control=N_CTRL, seed=seed, rho=v["rho"],
                                    spread_gamma=v.get("gamma", 0.0),
                                    scale_on_control=bool(v.get("on_control", False)))
    rec = ssb.gates.check_reconstruction(crd, t1)
    return crd, t1, diag, rec


def score_variant(t1: pd.DataFrame, href: pd.DataFrame) -> pd.DataFrame:
    tw = DA.audit_twins(t1, href)
    return tw[tw.status == "ok"].copy()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default=None)
    ap.add_argument("--seeds", default="0")
    ap.add_argument("--compare", nargs=2, default=None)
    a = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / "human_ref.csv.gz"
    href = pd.read_csv(cache) if cache.exists() else DA.human_reference()
    if not cache.exists():
        href.to_csv(cache, index=False)

    if a.compare:
        A = pd.read_csv(OUT / a.compare[0] / "twins_seed0.csv")
        B = pd.read_csv(OUT / a.compare[1] / "twins_seed0.csv")
        key = ["outcome", "twin"]
        m = A.merge(B, on=key, suffixes=("_a", "_b"))
        for col in ("variance_ratio", "ovl", "ks_d", "wasserstein1"):
            m["d_" + col] = m[col + "_b"] - m[col + "_a"]
        m["d_absVR"] = (m.variance_ratio_b - 1).abs() - (m.variance_ratio_a - 1).abs()
        cols = key + ["d_absVR", "d_ovl", "d_ks_d", "d_wasserstein1"]
        print(f"== {a.compare[1]} MINUS {a.compare[0]}  (negative d_absVR/d_ks/d_w1 and "
              f"positive d_ovl are improvements) ==")
        print(m[cols].to_string(index=False, float_format=lambda v: f"{v:8.4f}"))
        print("\nper-outcome totals:")
        g = m.groupby("outcome")[["d_absVR", "d_ovl", "d_ks_d", "d_wasserstein1"]].mean()
        print(g.to_string(float_format=lambda v: f"{v:8.4f}"))
        return 0

    variant = a.variant or "base"
    d = OUT / variant
    d.mkdir(parents=True, exist_ok=True)
    (d / "variant.json").write_text(json.dumps(
        {"variant": variant, **{k: v for k, v in VARIANTS[variant].items()},
         "n_per_intervention": N_PER, "n_control": N_CTRL, "card": str(CARD)}, indent=1))
    rows = []
    for seed in [int(s) for s in a.seeds.split(",")]:
        crd, t1, diag, rec = build(variant, seed)
        tw = score_variant(t1, href)
        tw.insert(0, "seed", seed)
        tw.to_csv(d / f"twins_seed{seed}.csv", index=False)
        gs = DA.audit_group_spread(t1, href)
        gam = DA.fit_gamma(gs, "synth")
        sub = DA.audit_twin_subgroup(t1, href)
        if seed == 0:
            gs.to_csv(d / "group_spread.csv", index=False)
            sub.to_csv(d / "twin_subgroup.csv", index=False)
        if seed == 0:
            t1.to_csv(d / "tier1.csv", index=False)
            diag.to_csv(d / "synth_diagnostics.csv", index=False)
        rows.append({"seed": seed, "sd_ratio_min": float(diag.sd_ratio.min()),
                     "sd_ratio_max": float(diag.sd_ratio.max()),
                     **{k: round(v, 4) for k, v in rec.items()},
                     "gamma": round(gam["gamma"], 4), "gamma_se": round(gam["se"], 4),
                     "sub_absVR1_med": float((sub.variance_ratio - 1).abs().median()),
                     "sub_ovl_med": float(sub.ovl.median()),
                     "VR_med": float(tw.variance_ratio.median()),
                     "OVL_med": float(tw.ovl.median()), "KS_med": float(tw.ks_d.median()),
                     "W1_med": float(tw.wasserstein1.median())})
        print(f"  seed {seed}: sd_ratio {rows[-1]['sd_ratio_min']:.4f}-{rows[-1]['sd_ratio_max']:.4f} "
              f"tier3 {rec['tier3_rmse_pp']:.4f} tier2mod {rec['tier2mod_rmse_pp']:.3f} "
              f"| VR {rows[-1]['VR_med']:.3f} OVL {rows[-1]['OVL_med']:.3f} "
              f"KS {rows[-1]['KS_med']:.3f} W1 {rows[-1]['W1_med']:.3f} "
              f"| gamma {gam['gamma']:.3f} sub|VR-1| {rows[-1]['sub_absVR1_med']:.3f} "
              f"sub_OVL {rows[-1]['sub_ovl_med']:.3f}")
    S = pd.DataFrame(rows)
    S.to_csv(d / "seed_scan.csv", index=False)
    if len(S) > 1:
        print("\n== SEED SPREAD (the unit every improvement claim is stated in) ==")
        print(S[["VR_med", "OVL_med", "KS_med", "W1_med", "gamma", "sub_absVR1_med",
                 "sub_ovl_med", "tier2mod_rmse_pp"]]
              .agg(["mean", "std", "min", "max"]).to_string(float_format=lambda v: f"{v:9.5f}"))
        # per-cell seed SD, which is what a per-outcome contrast has to beat
        allt = pd.concat([pd.read_csv(d / f"twins_seed{s}.csv") for s in S.seed])
        sd = allt.groupby(["outcome", "twin"])[["variance_ratio", "ovl", "ks_d",
                                                "wasserstein1"]].std()
        print("\nper-(outcome,twin) seed SD, median over pairs:")
        print(sd.median().to_string(float_format=lambda v: f"{v:9.5f}"))
        sd.to_csv(d / "seed_sd.csv")
    print(f"wrote {d}/")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
