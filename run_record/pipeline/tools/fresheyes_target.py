#!/usr/bin/env python
"""Stage 5 for arm `fresheyes`: the target prediction, with this arm's own elicitation.

    /opt/kernel/venv/bin/python tools/fresheyes_target.py --model claude-opus-5 \
        --run-id 20260820-target-fresheyes --baseline runs/.../card_baseline.json     # plan only
    ... --execute --approved --max-billed-tokens N                                    # spend

Order of operations is PREREG.md section 6: probe -> abort on RESULTS_KNOWN: YES -> 3 draws ->
parse -> median -> pp->native -> card. Nothing here reads the other arm's target artefacts.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / "tools"))
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))

import practice            # noqa: E402  (the call path, the cache, the spend ledger)
import fresheyes_variant   # noqa: E402
import ssb                 # noqa: E402

N_TOTAL = 18000
N_COND = 17


def resolution_note(sd_pp: float) -> str:
    n_arm = N_TOTAL // N_COND
    se = sd_pp * np.sqrt(2.0 / n_arm)
    return ("RESOLUTION: about %d respondents read each text (%d conditions, ~%d respondents in "
            "all), so with a typical response spread the standard error of a single message x "
            "outcome effect is roughly %.1f percentage points. Effects smaller than that are not "
            "resolvable by this study, and effects larger than about 5 points are rare in "
            "message experiments of this kind." % (n_arm, N_COND, N_TOTAL, se))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--baseline", required=True, help="JSON: {outcome: {mean, sd, ...}} native units")
    ap.add_argument("--draws", type=int, default=3)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--approved", action="store_true")
    ap.add_argument("--rehearsal", action="store_true")
    ap.add_argument("--max-billed-tokens", type=int, default=None)
    a = ap.parse_args()

    if a.rehearsal:
        practice.CACHE_DIR = practice.REHEARSAL_CACHE
        import os
        os.environ["SSB_REHEARSAL"] = "1"
        a.approved = True
    if a.execute and not a.approved:
        raise SystemExit("--execute requires --approved")

    base = json.loads(Path(a.baseline).read_text())
    s = ssb.spec.load()
    run_id = ssb.gates.namespaced(a.run_id)
    d = RUN / "runs" / run_id
    d.mkdir(parents=True, exist_ok=True)
    st = d / "stages" / "target"
    st.mkdir(parents=True, exist_ok=True)
    practice.LEDGER["ceiling_tokens"] = a.max_billed_tokens
    practice.LEDGER["path"] = str(st / "spend.json")
    practice._ledger_flush()

    # ---- assemble the payload -----------------------------------------------------------------
    brief = ssb.predict.target_brief()
    levels = {o: float(base[o]["mean"]) for o in s["outcomes"] if o in base}
    sd_pp = float(np.median([float(base[o]["sd"]) * 100.0 / (s["ranges"][o][1] - s["ranges"][o][0])
                             for o in s["outcomes"] if o in base]))
    b, vmeta = fresheyes_variant.apply(
        brief, levels, resolution_note(sd_pp),
        level_note="estimated control-arm mean")
    if vmeta["levels_missing"]:
        raise SystemExit("baseline is incomplete: %d outcomes have no level" % vmeta["levels_missing"])
    plan = ssb.predict.plan_prompts(b, budget_tokens=24000, per_arm_char_cap=12000)
    parts = plan.pop("briefs")
    if len(parts) != 1 or plan.get("truncated"):
        raise SystemExit("TARGET ARM TRUNCATED OR SPLIT: %s" % plan)
    system, user = ssb.predict.build_prompt(parts[0])
    system = vmeta["system"] = fresheyes_variant.SYSTEM
    (st / "system.txt").write_text(system)
    (st / "user.txt").write_text(user)
    ps, pu = practice.probe_prompt(parts[0], 2)
    (st / "probe_system.txt").write_text(ps)
    (st / "probe_user.txt").write_text(pu)

    tk = ssb.predict.n_tokens(system) + ssb.predict.n_tokens(user)
    ptk = ssb.predict.n_tokens(ps) + ssb.predict.n_tokens(pu)
    est = round((tk * a.draws + ptk) * practice.BILLED_INPUT_FACTOR
                + (208 * a.draws * practice.OUT_TOKENS_PER_CELL + practice.PROBE_OUT_TOKENS)
                * practice.TOKENIZER_FACTOR)
    print("\nSTAGE 5 (fresheyes)  model=%s draws=%d" % (a.model, a.draws))
    print("  prompt %d tiktoken, probe %d, levels given %d/13" % (tk, ptk, vmeta["levels_given"]))
    print("  BILLED ESTIMATE %d tokens   ceiling %s" % (est, a.max_billed_tokens or "none"))
    (st / "cost.json").write_text(json.dumps({"model": a.model, "draws": a.draws,
                                              "prompt_tiktoken": tk, "probe_tiktoken": ptk,
                                              "billed_tokens_est": est, "variant": vmeta}, indent=1))
    if not a.execute:
        print("\nNO CALL WAS MADE (plan only).\n")
        return

    # ---- 5a. blinding probe, BEFORE any prediction ---------------------------------------------
    text, key, cached = practice.call(pu, ps, a.model, True, stage="probe", task="TARGET",
                                      variant="fresheyes")
    (st / "probe_completion.txt").write_text(text)
    self_known = "YES" in (text.upper().split("RESULTS_KNOWN:")[-1][:6] if "RESULTS_KNOWN" in text.upper() else "")
    (st / "probe_result.json").write_text(json.dumps(
        {"text": text, "results_known": self_known, "cache_key": key, "from_cache": cached,
         "probe_version": 2, "confidence_referent": "defined (v2)"}, indent=1))
    print("  PROBE: results_known=%s" % self_known)
    print("  " + text.strip().replace("\n", "\n  "))
    if self_known:
        raise SystemExit("BLINDING EVENT: the predictor reports it already knows this study's "
                         "results. Stopped before any prediction call. Tell the operator.")

    # ---- 5b. draws ------------------------------------------------------------------------------
    conds = [x["title"] for x in parts[0]["arms"]]
    outs = [o["name"] for o in parts[0]["outcomes"]]
    frames = []
    for dr in range(a.draws):
        t, k, c = practice.call(user, system, a.model, True, draw=dr, variant="fresheyes")
        (st / ("transcript_draw%d.txt" % dr)).write_text(t)
        f = ssb.predict.parse(t, conds, outs)
        n_bad = int(f.ate.isna().sum())
        print("  draw %d: %d/%d cells parsed%s" % (dr, len(f) - n_bad, len(f),
                                                   " (CACHED)" if c else ""))
        if n_bad:
            raise SystemExit("UNPARSED TARGET CELLS in draw %d: %d" % (dr, n_bad))
        frames.append(f)
    agg = ssb.predict.aggregate(frames)
    if agg.ate.isna().any():
        raise SystemExit("UNPARSED TARGET CELL after aggregation")
    agg.to_csv(st / "prediction_pp.csv", index=False)
    print("\n  median |ATE| = %.2f pp   max %.2f   draw-to-draw SD %.3f"
          % (agg.ate.abs().median(), agg.ate.abs().max(), agg.ate_sd_across_draws.mean()))
    print("  spend: %d billed this run, %d reused from cache"
          % (practice.LEDGER["billed_tokens"], practice.LEDGER["prior_billed_tokens"]))
    print("\nstage 5 complete -> %s" % st)


if __name__ == "__main__":
    main()
