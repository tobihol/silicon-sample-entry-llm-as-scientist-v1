#!/usr/bin/env python
"""Stages 4-9 of the AGENTS.md loop: calibrate, predict the TARGET, card, synthesise, deposit.

    # 1. plan only - assembles the target payload, makes NO call, prints the bill
    /opt/kernel/venv/bin/python tools/target.py --practice-run runs/<id> --model <model-id>

    # 2. rehearse the whole thing against tools/fake/claude, no credential, no spend
    PATH="/workspace/run/tools/fake:$PATH" /opt/kernel/venv/bin/python tools/target.py \
        --practice-run runs/<id> --model <model-id> --rehearsal

    # 3. spend, after the operator has approved the number printed by step 1
    /opt/kernel/venv/bin/python tools/target.py --practice-run runs/<id> --model <model-id> \
        --execute --approved

Stage 5 is the second and last stage that spends budget, and it is the one that produces the
actual product, so it stops being pseudocode in the RUNBOOK and becomes a script with the same
guard rails as stage 3: plan-by-default, `--execute` requires `--approved`, every call cached on
`ssb.predict.cache_key`, a rehearsal writes to a separate cache and flags itself.

Three things it refuses to do quietly, all of them from standing findings:
  - an unparsed target cell aborts (a NaN would be scored as a deliberate null prediction);
  - a non-empty `clipping_report()` aborts - that is finding 8, the pp -> native conversion, and
    it is silent on the eleven 0-100 sliders and catastrophic on donation_ams/newsletter_signup;
  - a gate that is computed from sampled rows is scanned over seeds, not read once (finding 18).
"""
import argparse, datetime as dt, hashlib, json, os, shutil, sys, time
from pathlib import Path

import numpy as np, pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ssb  # noqa: E402
from practice import call, CACHE, REHEARSAL_CACHE  # noqa: E402
import practice  # noqa: E402

RUN = Path(__file__).resolve().parents[1]
N_PER_INTERVENTION, N_CONTROL = 2400, 4800      # 43,200 rows - OPEN item 5, measured not chosen
# Identity and publication window, both facts from the organisers (TASK_08), not preferences.
# `team_31` replaces the placeholder `sodalab` this harness had invented; the deposit may not be
# published before Aug 28 and the lock is Aug 31, so every build stamps which side of the window
# it was made on. tools/restamp_deposit.py re-stamps a deposit built before this existed, and
# tools/verify_deposit.py --strict refuses a deposit carrying any other team id.
TEAM_ID = "team_31"
WINDOW_OPEN, WINDOW_CLOSE = dt.date(2026, 8, 28), dt.date(2026, 8, 31)
SEED_SCAN = (0, 1, 2, 3, 4)
# One estimator for both stages that spend. practice.py's factors are MEASURED on real completions
# (tiktoken->Anthropic 1.574x, plus the CLI's own per-call pass at +73.2%, plus 19 output tokens a
# cell); stage 5 is the stage that makes the product, so it must not be priced in different units
# from the stage that was approved against them.
OUT_TOKENS_PER_CELL = practice.OUT_TOKENS_PER_CELL
BILLED_INPUT_FACTOR = practice.BILLED_INPUT_FACTOR


def main(practice_run, model, draws=3, execute=False, approved=False, rehearsal=False,
         run_id=None, entry="primary", max_billed_tokens=None, probe=True,
         lambda_policy="pooled"):
    t0 = time.time()
    # Same live ledger as stage 3 (tools/practice.py): every paid call adds its MEASURED billed
    # tokens, cache hits count as already paid, and the run stops before the call that would cross
    # the ceiling. Stage 5 is the cheaper of the two stages that spend, and it is the one that makes
    # the product, so it gets the same guard rather than a weaker one.
    practice.LEDGER["ceiling_tokens"] = max_billed_tokens
    which = shutil.which("claude")
    binary = {"resolved": which,
              "sha256": (hashlib.sha256(Path(which).read_bytes()).hexdigest()[:16] if which else None)}
    if rehearsal:
        practice.CACHE_DIR = REHEARSAL_CACHE
        os.environ["SSB_REHEARSAL"] = "1"
        approved, execute = True, True
    else:
        practice.CACHE_DIR = CACHE
    if execute and not approved:
        raise SystemExit("--execute requires --approved: stage 5 spends the operator's budget.")

    # ---- stage 4: calibration, from the practice run's pairs ---------------------------------
    # `by="family"` groups on pairs.csv's `family` column, which practice.py fills with
    # "practice_<task>" - TASK names, not the target's four outcome families. So every target cell
    # falls back to `_pooled`, and it did so silently through every dry run and rehearsal: the
    # argument looked like per-family calibration and was inert (finding 26's shape exactly).
    #
    # Measured before deciding what to do about it (run 20260815-practice-01, the frozen map in
    # inputs/outcome_families.json): only 592 of 1,101 practice cells share a construct with any
    # target family, the trust family has ZERO, and a real per-family map fitted on the rest LOSES
    # to the pooled slope on 3 of 4 held-out climate tasks (-0.17, -0.55, -0.07 pp, +0.00 pp).
    # So pooled is the right map - but it must be pooled ON PURPOSE, and the run must record which
    # slope each outcome actually got.
    practice_run = Path(practice_run)
    pairs = pd.read_csv(practice_run / "stages" / "calibration" / "pairs.csv")
    lam = ssb.predict.fit_calibration(pairs, by="family")
    fam_keys = sorted(set(ssb.predict.FAMILY.values()))
    lam_used = {o: (str(f) if str(f) in lam else "_pooled") for o, f in ssb.predict.FAMILY.items()}
    lam["_applied_per_outcome"] = lam_used
    lam["_family_keys_available"] = [k for k in fam_keys if k in lam]
    lam["_note"] = (
        "Every outcome resolves to %s. The pooled slope is deliberate: a per-family map was fitted "
        "and tested by leave-one-task-out and lost to pooled on 3 of 4 held-out climate tasks "
        "(inputs/outcome_families.json, runs/20260815-practice-01/stages/calibration/family_slopes.csv). "
        "The target's trust family has no practice pairs at all, so its multiplier is an "
        "extrapolation from belief/policy/behaviour however it is fitted."
        % ("_pooled" if set(lam_used.values()) == {"_pooled"} else "a mix: %s" % lam_used))
    print("\nSTAGE 4 CALIBRATION  pooled lambda %.4f on %d in-slope pairs" % (lam["_pooled"], lam["_n"]))
    print("  slope applied per outcome: %s" % ("_pooled for all 13"
          if set(lam_used.values()) == {"_pooled"} else lam_used))

    run_id = run_id or time.strftime("%%Y%%m%%d-%starget-%%H%%M%%S" % ("rehearsal-" if rehearsal else ""))
    practice.assert_run_id_free(run_id)
    run_id = ssb.gates.namespaced(run_id)
    d = ssb.gates.new_run(run_id, stub_predictor=rehearsal,
                          inputs_sha256=practice._inputs_digest(),
                          note="%sstages 4-9 from %s, model=%s, draws=%d, claude=%s"
                               % ("REHEARSAL (scripted answers) - " if rehearsal else "",
                                  practice_run.name, model, draws, binary["resolved"]))
    ssb.gates.record(d, "G1_frozen_intact",
                     ssb.gates.frozen_hash() == json.loads((d / "run.json").read_text())["frozen_sha256"],
                     "APPEND_SYSTEM.md sha256 matches the value recorded at run start")
    ssb.gates.record(d, "G2_practice_scored", (practice_run / "stages" / "calibration" / "pairs.csv").exists(),
                     "inherited from %s: %d pairs, %d in slope" % (practice_run.name, len(pairs),
                                                                   int(pairs.in_slope.sum())))
    (d / "stages" / "calibration").mkdir(parents=True, exist_ok=True)
    pairs.to_csv(d / "stages" / "calibration" / "pairs.csv", index=False)
    (d / "stages" / "calibration" / "lambda.json").write_text(json.dumps(lam, indent=1))
    ssb.gates.record(d, "G3_calibration_fitted", "_pooled" in lam,
                     "pooled slope %.3f on %d pairs, inherited from %s"
                     % (lam["_pooled"], lam["_n"], practice_run.name))

    # ---- stage 5: the target, the SAME prompt shape ------------------------------------------
    brief = ssb.predict.target_brief()
    plan = ssb.predict.plan_prompts(brief, budget_tokens=24000, per_arm_char_cap=12000)
    briefs = plan.pop("briefs")
    # Truncating a PRACTICE arm is a considered trade (finding 17). Truncating the TARGET's own
    # stimulus changes the thing being predicted, and the margin is thinner than finding 17's
    # wording suggests: the longest target arm is 11,134 chars against a 12,000 cap - 92.8% of it,
    # 866 chars of headroom. A re-extraction that adds a little whitespace would cross it and the
    # only symptom would be a slightly better score on a different study. So it is asserted, not
    # assumed, on every run.
    if plan.get("truncated_arms"):
        raise SystemExit(
            "TARGET ARM TRUNCATED: %s. The per-arm cap (12,000 chars) exists so a practice prompt "
            "stays in the target's size band; it was never meant to bite on the target itself, and "
            "if it does, the deposit predicts a stimulus no respondent saw. Raise per_arm_char_cap "
            "and re-price, or fix the extraction - do not proceed."
            % {k: v for k, v in plan["truncated_arms"].items()})
    if plan["parts"] != 1:
        raise SystemExit("TARGET SPLIT into %d parts: the target has always fitted whole (9,892 "
                         "tokens against a 24,000 budget). A split here means the brief grew; "
                         "re-price before proceeding." % plan["parts"])
    st = d / "stages" / "target"
    st.mkdir(parents=True, exist_ok=True)
    practice.LEDGER["path"] = str(st / "spend.json")
    practice._ledger_flush()
    toks = 0
    for i, pb in enumerate(briefs):
        system, user = ssb.predict.build_prompt(pb)
        (st / ("user_part%d.txt" % (i + 1) if len(briefs) > 1 else "user.txt")).write_text(user)
        (st / "system.txt").write_text(system)
        toks += ssb.predict.n_tokens(system) + ssb.predict.n_tokens(user)
    # ---- stage 5a: the BLINDING probe -------------------------------------------------------
    # On a training task the recognition probe is a recall test (OPEN item 3). On the TARGET the
    # identical call is something else: a blinding check. The frozen file says "You never seek,
    # ingest, or infer from human outcome data of the target study - including its pilots,
    # preprints about it, or anything derived from them. If you encounter any, stop, record where,
    # and tell the operator." Nothing in this harness had ever ASKED the predictor whether it
    # already knows the answer. One call, ~28,000 billed tokens, before the prediction it would
    # contaminate - the same ordering that made stage 3a credible.
    probe_system, probe_user = practice.probe_prompt(briefs[0])
    (st / "probe_system.txt").write_text(probe_system)
    (st / "probe_user.txt").write_text(probe_user)
    probe_toks = ssb.predict.n_tokens(probe_system) + ssb.predict.n_tokens(probe_user)
    n_cells = len(brief["arms"]) * len(brief["outcomes"])
    cost = {"model": model, "draws": draws, "calls": plan["parts"] * draws + (1 if probe else 0),
            "input_tokens": toks * draws + (probe_toks if probe else 0),
            "output_tokens": n_cells * OUT_TOKENS_PER_CELL * draws
                             + (practice.PROBE_OUT_TOKENS if probe else 0),
            "probe": bool(probe), "probe_input_tokens": probe_toks if probe else 0,
            "policy": plan["policy"], "parts": plan["parts"], "n_cells": n_cells}
    cost["total_tokens"] = cost["input_tokens"] + cost["output_tokens"]
    cost["billed_tokens_est"] = round(cost["input_tokens"] * BILLED_INPUT_FACTOR
                                      + cost["output_tokens"])
    cost["billed_factors"] = {"tokenizer": practice.TOKENIZER_FACTOR,
                              "cli_overhead": practice.CLI_OVERHEAD_FACTOR,
                              "out_tokens_per_cell": OUT_TOKENS_PER_CELL,
                              "measured_on": practice.TOKENIZER_MEASURED_ON}
    (st / "cost.json").write_text(json.dumps(cost, indent=1))
    print("\nSTAGE 5 BILL  model=%s  draws=%d  ->  %d calls, %d input + %d est output = %d tiktoken"
          % (model, draws, cost["calls"], cost["input_tokens"], cost["output_tokens"],
             cost["total_tokens"]))
    print("              BILLED ESTIMATE (what the provider charges): %d tokens"
          % cost["billed_tokens_est"])
    if not execute:
        print("payload written to %s\nNO CALL WAS MADE (plan-only). Add --execute --approved to spend.\n" % st)
        return {"run": str(d), "cost": cost, "executed": False}

    blinding = None
    if probe:
        text, key, cached = practice.call(probe_user, probe_system, model, execute,
                                          stage="target_probe")
        (st / "probe_completion.txt").write_text(text)
        import re as _re
        known = _re.search(r"RESULTS_KNOWN:\s*(YES|NO)", text, _re.I)
        conf = _re.search(r"CONFIDENCE:\s*(\d+)", text)
        study = _re.search(r"STUDY:\s*(.+)", text)
        blinding = {"self_report_results_known": known.group(1).upper() if known else "UNPARSED",
                    "self_report_confidence": int(conf.group(1)) if conf else None,
                    # OPEN 36: no stated referent under probe v1 - recorded, never interpreted
                    "confidence_referent": "UNDEFINED - recorded, never interpreted (OPEN 36)",
                    "self_report_study": study.group(1).strip()[:200] if study else None,
                    "cache_key": key, "from_cache": cached}
        blinding["verdict"] = ("BLINDING EVENT" if blinding["self_report_results_known"] == "YES"
                               else "CLEAN")
        (st / "blinding_probe.json").write_text(json.dumps(blinding, indent=1))
        print("\nSTAGE 5a BLINDING PROBE  %s  (self=%s; raw CONFIDENCE=%s, referent UNDEFINED "
              "under probe v1 - not a measurement, OPEN 36)"
              % (blinding["verdict"], blinding["self_report_results_known"],
                 blinding["self_report_confidence"]))
        if blinding["verdict"] == "BLINDING EVENT" and not rehearsal:
            raise SystemExit(
                "BLINDING EVENT: the predictor reports it already knows this study's results "
                "(study %r; the raw CONFIDENCE field has no defined referent and is not part of "
                "this verdict - OPEN 36). The frozen file says: stop, record where, and tell the "
                "operator. The probe is recorded at %s and NO prediction call was made."
                % (blinding["self_report_study"], st / "blinding_probe.json"))

    frames = []
    for dr in range(draws):
        got = []
        for i, pb in enumerate(briefs):
            system, user = ssb.predict.build_prompt(pb)
            text, key, cached = call(user, system, model, True, draw=dr, stage="target")
            (st / ("transcript_draw%d_part%d.txt" % (dr, i + 1))).write_text(text)
            conds = [a["title"] for a in pb["arms"]]
            outs = [o["name"] for o in pb["outcomes"]]
            got.append(ssb.predict.parse(text, conds, outs))
        frames.append(pd.concat(got).drop_duplicates(["condition", "outcome"], keep="first"))
    agg = ssb.predict.aggregate(frames)
    if int(agg.ate.isna().sum()):
        raise SystemExit("target: %d unparsed cells - a NaN here would be deposited as a null "
                         "prediction. Run tools/test_parse.py and inspect %s"
                         % (int(agg.ate.isna().sum()), st))
    agg.to_csv(st / "ate_pp_raw.csv", index=False)

    # ---- stage 6: the card -------------------------------------------------------------------
    # WHICH multiplier, and it is the operator's call (OPEN item 18). Fixed here as an explicit
    # policy rather than an unmarked default, because run 20260815-practice-01 measured that the
    # choice is close to free and points the wrong way for trust:
    #   pooled  lambda 1.521 on the in-slope pairs  (the historical default)
    #   none    deposit unshrunk                     (recommendation (c) in OPEN item 18)
    # There is deliberately no third "climate" option. The 1.790 figure quoted as a climate slope is
    # fitted on all four climate tasks IGNORING the pre-registered exclusions - it includes
    # goldwert2026, whose magnitudes its own data does not identify (OPEN 11), and vlasceanu2024,
    # which the probe caught as RECOGNISED (OPEN 3). Respecting both exclusions, the only non-climate
    # task (voelkel2024) is ALREADY out as RECOGNISED, so a climate-only slope is the same 498 pairs
    # and the same 1.5212. 1.790 is a diagnostic, never a depositable multiplier.
    # Leave-one-task-out the multiplier is worth +0.008 pp of RMSE over five folds; and at the
    # effect sizes finding 5 implies for trust (~0.5 pp) tools/forecast_target.py says it makes RMSE
    # WORSE, 1.74 -> 1.84. Whichever is chosen, the run records it.
    lam_applied = dict(lam)
    if lambda_policy == "none":
        lam_applied = {**lam, "_pooled": 1.0}
    print("  lambda policy %-8s -> multiplier %.4f applied to all %d cells"
          % (lambda_policy, lam_applied["_pooled"], len(agg)))
    lam["_policy"] = lambda_policy
    lam["_multiplier_applied"] = lam_applied["_pooled"]
    (d / "stages" / "calibration" / "lambda.json").write_text(json.dumps(lam, indent=1))
    ate_pp = agg[["condition", "outcome", "ate"]]
    ate = ssb.predict.to_native(ssb.predict.apply_calibration(ate_pp, lam_applied,
                                                              family_of=ssb.predict.FAMILY))
    today = dt.date.today()
    meta = {"run_id": run_id, "stub": bool(rehearsal), "model": model, "team_id": TEAM_ID,
            "practice_run": practice_run.name, "calibration_slope": lam_applied["_pooled"],
            "lambda_policy": lambda_policy, "fitted_slope": lam["_pooled"],
            "built_at": today.isoformat(),
            "publication_window": f"{WINDOW_OPEN} .. {WINDOW_CLOSE}",
            "not_for_publication_before": WINDOW_OPEN.isoformat(),
            "publication_status": (
                f"NOT-FOR-PUBLICATION - built {today}, {(WINDOW_OPEN - today).days} days before "
                f"the deposit window opens on {WINDOW_OPEN}" if today < WINDOW_OPEN else
                ("in-window" if today <= WINDOW_CLOSE else
                 "AFTER THE PREDICTION LOCK - do not deposit")),
            "note": ("REHEARSAL - scripted ATEs, NOT a prediction" if rehearsal else
                     "calibrated prediction of the target megastudy")}
    crd = ssb.card.from_inputs(ate, meta=meta)
    crd.save(d / "card")
    problems, clipped = crd.validate(), crd.clipping_report()
    if len(clipped):
        raise SystemExit("card clips %d cells - this is standing finding 8 (pp -> native units), "
                         "silent on the sliders and catastrophic on donation_ams/newsletter_signup:\n%s"
                         % (len(clipped), clipped))
    ssb.gates.record(d, "G4_card_complete", not problems and len(clipped) == 0,
                     "%d validation problems, %d clipped cells" % (len(problems), len(clipped)))

    # ---- stage 7: backward synthesis, with the seed scan finding 18 demands ------------------
    scan = []
    for s in SEED_SCAN:
        t1s, diags = ssb.synth.synthesize(crd, pd.read_csv(RUN / "inputs" / "pool" / "joint.csv"),
                                          n_per_intervention=N_PER_INTERVENTION,
                                          n_control=N_CONTROL, seed=s)
        r = ssb.gates.check_reconstruction(crd, t1s)
        scan.append({"seed": s, **{k: round(v, 4) for k, v in r.items()},
                     "sd_min": float(diags.sd_ratio.min()), "sd_max": float(diags.sd_ratio.max())})
        if s == SEED_SCAN[0]:
            t1, diag, rec = t1s, diags, r
    sc = pd.DataFrame(scan)
    sc.to_csv(d / "stages" / "g6_seed_scan.csv", index=False)
    t1.to_csv(d / "stages" / "tier1.csv", index=False)
    diag.to_csv(d / "stages" / "synth_diagnostics.csv", index=False)
    tol = ssb.gates.TOL["G6_tier2mod_rmse_pp"]
    worst = float(sc.tier2mod_rmse_pp.max())
    ssb.gates.record(d, "G6_reconstruction",
                     bool(worst < tol and sc.tier3_rmse_pp.max() < ssb.gates.TOL["G6_tier3_rmse_pp"]),
                     "seed scan over %d seeds: tier2mod %.3f-%.3f (tol %.2f), tier3 max %.4f"
                     % (len(scan), sc.tier2mod_rmse_pp.min(), worst, tol, sc.tier3_rmse_pp.max()))
    sdr = (float(sc.sd_min.min()), float(sc.sd_max.max()))
    ssb.gates.record(d, "G7_dispersion", abs(np.log(sdr[0])) < 0.1 and abs(np.log(sdr[1])) < 0.1,
                     "sd_ratio %.3f-%.3f over the seed scan" % sdr)

    # ---- stage 8: deposit --------------------------------------------------------------------
    res = ssb.deposit.build(d, crd, t1, meta, entry=entry)
    verdicts = {k: v["verdict"] for k, v in res.items()}
    ssb.gates.record(d, "G5_validator_pass", all("FAIL" not in v for v in verdicts.values()),
                     json.dumps(verdicts))

    # ---- stage 9: close ----------------------------------------------------------------------
    ssb.gates.scoreboard_append({"run_id": run_id, "stage": "rehearsal-target" if rehearsal else "target",
                                 "stub": bool(rehearsal), "task_id": "TARGET", "n_cells": n_cells,
                                 "leak_verdict": "n/a (no sealed truth exists for the target)",
                                 "cal_beta": lam["_pooled"],
                                 "note": "%smodel=%s; draws=%d; from %s; G6 worst seed %.3f"
                                         % ("REHEARSAL scripted - NOT a prediction; " if rehearsal else "",
                                            model, draws, practice_run.name, worst)})
    ssb.gates.record(d, "G8_recorded", True, "scoreboard row appended; REPORT.md written by hand")
    v = ssb.gates.verdict(d)
    spent = practice.LEDGER["billed_tokens"] + practice.LEDGER["prior_billed_tokens"]
    out = {"run": str(d), "verdict": v, "cost": cost, "rehearsal": bool(rehearsal), "binary": binary,
           "calibration": lam, "reconstruction": rec, "seed_scan": scan, "validator": verdicts,
           "blinding_probe": blinding,
           "spend": {**{k: val for k, val in practice.LEDGER.items() if k != "calls"},
                     "batch_billed_tokens": spent,
                     "estimate_billed_tokens": cost["billed_tokens_est"],
                     "actual_over_estimate": (round(spent / cost["billed_tokens_est"], 3)
                                              if cost["billed_tokens_est"] else None)},
           "cache_dir": str(practice.CACHE_DIR), "seconds": round(time.time() - t0, 1)}
    (d / "stages" / "summary.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: out[k] for k in ("run", "verdict", "validator", "seconds")}, indent=1))
    print("G6 seed scan:\n" + sc.to_string(index=False))
    # A gate that reports is not a gate. Everything above is already on disk, so the evidence
    # survives; what must not happen is a run CLOSING green while a gate is red.
    if not v["may_finish"]:
        raise SystemExit("\n*** RUN NOT CLOSEABLE ***\nfailed: %s\nmissing: %s\nEverything is "
                         "written to %s. Fix the gate or waive it in OPEN.md with a reason "
                         "(AGENTS.md, 'What a run stops on'). The deposit under %s must not be "
                         "sent while this is red." % (v["failed"], v["missing"], d, d))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--practice-run", required=True, help="a run directory with stages/calibration/pairs.csv")
    ap.add_argument("--model", required=True)
    ap.add_argument("--draws", type=int, default=3)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--entry", default="primary", help="primary or secondary-k")
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--approved", action="store_true")
    ap.add_argument("--rehearsal", action="store_true",
                    help="run the full path against tools/fake/claude: no credential, separate "
                         "cache, scoreboard row flagged stub=True")
    ap.add_argument("--lambda-policy", choices=("pooled", "none"), default="pooled",
                    help="which magnitude multiplier the card applies (OPEN item 18): pooled = the "
                         "fitted in-slope slope (1.521); none = deposit unshrunk, which is the "
                         "recommendation in OPEN item 18. Recorded on the card either way. There is "
                         "no climate-only option: respecting the pre-registered exclusions it is the "
                         "same 498 pairs and the same number.")
    ap.add_argument("--no-probe", dest="probe", action="store_false",
                    help="skip stage 5a, the blinding probe. Do not.")
    ap.add_argument("--max-billed-tokens", type=int, default=None,
                    help="hard ceiling on tokens the provider actually bills (cache hits count as "
                         "already paid). Stops before the call that would cross it; every completed "
                         "call is cached, so resuming is free.")
    a = ap.parse_args()
    main(a.practice_run, a.model, a.draws, a.execute, a.approved, a.rehearsal, a.run_id, a.entry,
         a.max_billed_tokens, a.probe, a.lambda_policy)
