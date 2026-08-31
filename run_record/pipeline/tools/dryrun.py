#!/usr/bin/env python
"""Run a full STUB dry run of the AGENTS.md loop, stages 0-9, with no model calls.

    /opt/kernel/venv/bin/python tools/dryrun.py 20260815-dryrun-03

Everything except the predictor is the real code path: the same carves, the same
prompts (assembled through ssb.predict.plan_prompts, so the split policy is exercised
end to end), the same scoring, the same card, the same synthesis, the same validator,
the same gates. The predictor is `ssb.predict.stub_completion`, a scripted function of
cell NAMES that has read nothing - so every number produced here is a plumbing check
and is written to the scoreboard with stub=True.

Previous dry runs existed only as notebook state; this script is what makes dry run 03
repeatable by a later session.
"""
import hashlib, json, sys, time
from pathlib import Path
import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402

RUN = Path(__file__).resolve().parents[1]
TASKS = ["voelkel2026", "goldwert2026", "vlasceanu2024", "bbprime2025", "voelkel2024"]
MODEL = ssb.predict.STUB_MODEL
N_DRAWS = 3


def stub_draws(brief, seed0):
    """One task -> a complete (condition, outcome, ate) table, through the real prompt
    path including plan_prompts' truncate/split policy."""
    plan = ssb.predict.plan_prompts(brief, budget_tokens=24000, per_arm_char_cap=12000)
    briefs = plan.pop("briefs")
    frames, per_part = [], {}
    for d in range(N_DRAWS):
        parts = []
        for i, b in enumerate(briefs):
            system, user = ssb.predict.build_prompt(b)
            key = ssb.predict.cache_key(user, system, MODEL, draw=d)          # real cache key
            text = ssb.predict.stub_completion(user, system, seed=seed0 + d)
            conds = [a["title"] for a in b["arms"]]
            outs = ([o["name"] for o in b["outcomes"]] if isinstance(b["outcomes"], list)
                    else list(b["outcomes"]))
            f = ssb.predict.parse(text, conds, outs)
            per_part.setdefault(f"part{i + 1}", []).append(f)
            parts.append(f)
        frames.append(pd.concat(parts).drop_duplicates(["condition", "outcome"], keep="first"))
    agg = ssb.predict.aggregate(frames)
    spread = None
    if plan["policy"] == "split" and plan["anchors"]:
        merged = {k: ssb.predict.aggregate(v) for k, v in per_part.items()}
        spread = ssb.predict.anchor_spread(merged, plan["anchors"])
    return agg, plan, spread


def main(run_id):
    t0 = time.time()
    d = ssb.gates.new_run(run_id, stub_predictor=True,
                          note="Pew-anchored baselines (351/351 cells), QSF texts in every arm, "
                               "goldwert2026 attrition mitigation, measured prompt-budget policy")
    ssb.gates.record(d, "G1_frozen_intact",
                     ssb.gates.frozen_hash() == json.loads((d / "run.json").read_text())["frozen_sha256"],
                     "APPEND_SYSTEM.md sha256 matches the value recorded at run start")

    joint = pd.read_csv(RUN / "inputs" / "pool" / "joint.csv")

    # ---- stages 2-3: carve, predict (stub), score, leak-audit -------------------------
    pairs, board, plans = [], [], {}
    for t in TASKS:
        task_dir = d / "tasks" / t
        carve = ssb.task.carve(t, task_dir)
        brief = json.loads((task_dir / "brief" / "task.json").read_text())
        # a STABLE seed: Python's hash() is salted per process, which would make a dry run
        # unreproducible between sessions for no reason at all
        seed0 = int(hashlib.sha256(t.encode()).hexdigest()[:6], 16) % 1000
        agg, plan, spread = stub_draws(brief, seed0=seed0)
        plans[t] = {k: v for k, v in plan.items() if k != "briefs"}
        pred_csv = task_dir / "prediction_stub.csv"
        agg[["condition", "outcome", "ate"]].to_csv(pred_csv, index=False)
        if spread is not None:
            spread.to_csv(task_dir / "anchor_spread.csv", index=False)
            plans[t]["anchor_spread_pp"] = {"mean_sd": float(spread["std"].mean()),
                                            "max_range": float((spread["max"] - spread["min"]).max())}
        sc = ssb.task.score_task(task_dir, pred_csv)
        transcript = task_dir / "transcript_stub.txt"
        transcript.write_text(pred_csv.read_text())
        audit = ssb.task.leak_audit(task_dir, [transcript])
        # the probe's positive control, run every time: a transcript that literally contains
        # the sealed file must score LEAK, or a CLEAN verdict on the line above means nothing
        pos = task_dir / "transcript_positive_control.txt"
        pos.write_text((task_dir / "sealed" / "truth.csv").read_text())
        audit_pos = ssb.task.leak_audit(task_dir, [pos])
        truth = pd.read_csv(task_dir / "sealed" / "truth.csv")
        ad = ssb.task.load_adapter(t)
        in_slope = not ad.get("attrition_bounds")           # OPEN item 11: bounded magnitudes stay out
        p = truth.merge(agg[["condition", "outcome", "ate"]].rename(columns={"ate": "pred"}),
                        on=["condition", "outcome"]).rename(columns={"ate": "human"})
        p["task"] = t
        p["family"] = "practice_" + t
        p["in_slope"] = in_slope
        pairs.append(p)
        row = {"run_id": run_id, "stage": "dryrun-stub", "stub": True, "task_id": t,
               "n_cells": len(p), "leak_verdict": audit["verdict"],
               "note": f"{plan['policy']}, {plan['parts']} part(s), "
                       f"{plan['tokens_whole']} tok; in_slope={in_slope}; "
                       f"positive_control={audit_pos['verdict']}",
               **{k: v for k, v in sc.items() if k in
                  {"directional_agreement", "spearman_rho", "pearson_r", "pearson_r_within_outcomes",
                   "rmse_pp", "r_adj", "rmse_adj", "cal_alpha", "cal_beta", "shrinkage_factor",
                   "vs_no_effect_floor_directional", "vs_no_effect_floor_rmse",
                   "vs_all_positive_directional", "vs_all_positive_rmse"}}}
        row["_positive_control"] = audit_pos["verdict"]
        board.append(row)
        print("  %-14s cells %4d  dir %.3f  rho %+.3f  rmse %5.2f  leak %s  %s"
              % (t, len(p), sc["directional_agreement"], sc["spearman_rho"], sc["rmse_pp"],
                 audit["verdict"], plans[t]["policy"]))
    pairs = pd.concat(pairs, ignore_index=True)
    (d / "stages" / "calibration").mkdir(parents=True, exist_ok=True)
    pairs.to_csv(d / "stages" / "calibration" / "pairs.csv", index=False)
    (d / "stages" / "prompt_plans.json").write_text(json.dumps(plans, indent=1))
    ssb.gates.record(d, "G2_practice_scored",
                     all(r["leak_verdict"] == "CLEAN" for r in board)
                     and all(r["_positive_control"] == "LEAK" for r in board),
                     f"{len(pairs)} cells over {len(TASKS)} tasks, all leak-audited "
                     f"({', '.join(sorted({r['leak_verdict'] for r in board}))}); "
                     f"positive control fires on every task "
                     f"({', '.join(sorted({r['_positive_control'] for r in board}))}); STUB predictor")

    # ---- stage 4: calibration --------------------------------------------------------
    lam = ssb.predict.fit_calibration(pairs, by="family")
    (d / "stages" / "calibration" / "lambda.json").write_text(json.dumps(lam, indent=1))
    ssb.gates.record(d, "G3_calibration_fitted", "_pooled" in lam,
                     f"pooled stub slope {lam['_pooled']:.3f} on {lam['_n']} pairs "
                     f"(goldwert2026 excluded by in_slope=False, OPEN item 11)")

    # ---- stage 5: the target, same prompt shape --------------------------------------
    brief = ssb.predict.target_brief()
    agg, plan, _ = stub_draws(brief, seed0=7)
    plans["target"] = {k: v for k, v in plan.items() if k != "briefs"}
    (d / "stages" / "prompt_plans.json").write_text(json.dumps(plans, indent=1))
    ate_pp = agg[["condition", "outcome", "ate"]]
    ate = ssb.predict.to_native(ssb.predict.apply_calibration(ate_pp, lam, family_of=ssb.predict.FAMILY))

    # ---- stage 6: the card -----------------------------------------------------------
    meta = {"run_id": run_id, "stub": True, "model": MODEL, "team_id": "sodalab",
            "note": "SCRIPTED STUB ATEs - not a prediction"}
    crd = ssb.card.from_inputs(ate, meta=meta)
    crd.save(d / "card")
    problems, clipped = crd.validate(), crd.clipping_report()
    ssb.gates.record(d, "G4_card_complete", not problems and len(clipped) == 0,
                     f"ssb.card.from_inputs from disk; {len(clipped)} clipped cells; "
                     f"{len(problems)} validation problems")

    # ---- stage 7: backward synthesis -------------------------------------------------
    # 43,200 rows, not the 21,600 of runs 01-03. MEASURED (stages/g6_seed_scan.csv, run 04): at
    # 21,600 the Tier-2 moderator residual is 2.487 +/- 0.099 pp against a 2.50 tolerance and one
    # seed in five FAILS the gate. At 43,200 it is 1.702 +/- 0.014. A gate that passes on the seed
    # is not a gate. The deposit size itself remains the operator's call (OPEN item 5).
    t1, diag = ssb.synth.synthesize(crd, joint, n_per_intervention=2400, n_control=4800)
    t1.to_csv(d / "stages" / "tier1.csv", index=False)
    diag.to_csv(d / "stages" / "synth_diagnostics.csv", index=False)
    sdr = (float(diag.sd_ratio.min()), float(diag.sd_ratio.max()))
    ssb.gates.record(d, "G7_dispersion", abs(np.log(sdr[0])) < 0.1 and abs(np.log(sdr[1])) < 0.1,
                     "sd_ratio %.3f-%.3f" % sdr)
    rec = ssb.gates.check_reconstruction(crd, t1)
    ssb.gates.record(d, "G6_reconstruction",
                     rec["tier3_rmse_pp"] < ssb.gates.TOL["G6_tier3_rmse_pp"]
                     and rec["tier2mod_rmse_pp"] < ssb.gates.TOL["G6_tier2mod_rmse_pp"],
                     json.dumps({k: round(v, 4) for k, v in rec.items()}))

    # ---- stage 8: deposit ------------------------------------------------------------
    res = ssb.deposit.build(d, crd, t1, meta, entry="primary")
    verdicts = {k: v["verdict"] for k, v in res.items()}
    ssb.gates.record(d, "G5_validator_pass",
                     all("FAIL" not in v for v in verdicts.values()),
                     json.dumps(verdicts))

    # ---- stage 9: close --------------------------------------------------------------
    for row in board:
        ssb.gates.scoreboard_append(row)
    ssb.gates.record(d, "G8_recorded", True,
                     "scoreboard rows appended with stub=True; OPEN.md and REPORT.md updated by hand")
    v = ssb.gates.verdict(d)
    summary = {"run_id": run_id, "verdict": v, "reconstruction": rec, "sd_ratio": sdr,
               "validator": verdicts, "calibration": lam,
               "prompt_plans": {k: {kk: vv for kk, vv in p.items()
                                    if kk in ("policy", "parts", "tokens_whole", "tokens_per_part",
                                              "anchor_spread_pp")} for k, p in plans.items()},
               "seconds": round(time.time() - t0, 1)}
    (d / "stages" / "summary.json").write_text(json.dumps(summary, indent=1))
    print(json.dumps(summary, indent=1))
    return summary


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else time.strftime("%Y%m%d-%H%M%S"))
