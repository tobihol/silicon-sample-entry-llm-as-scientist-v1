#!/usr/bin/env python
"""Assemble the EXACT stage-3 and stage-5 prompt payloads and measure them.

    /opt/kernel/venv/bin/python tools/prompt_budget.py     # ~30 s, no model calls
    -> inputs/prompt_budget.json   (+ the assembled prompts under inputs/prompts/)

OPEN item 10's second half. Every number here is measured on the payload that
`ssb.predict.command()` would actually send: same brief, same `build_prompt`, same
system text. Nothing is estimated from file sizes.

THE POLICY, and why it has these two numbers:

  budget_tokens = 24,000    The TARGET prompt is 9,892 tokens. A practice prompt four or
                            five times that size is not the same task - context length
                            changes what a model attends to, and the fitted calibration
                            slope is supposed to transfer from practice to target. 24,000
                            keeps every practice prompt within ~2.4x of the target and
                            still leaves an 8x margin under a 200k context window, so
                            nothing is silently truncated by the provider instead of by us.

  per_arm_char_cap = 12,000 Just above the target study's own longest arm (11,134
                            characters), so the policy is guaranteed never to touch the
                            thing being predicted. Only two studies have arms above it.

Order of remedies is fixed in ssb.predict.plan_prompts: send whole; else truncate a single
over-long arm at a paragraph boundary with a visible marker; else split the arms across
parts that each carry the control text and the same two anchor arms. Summarising is not an
option - a second model rewriting the stimulus changes the thing being predicted.
"""
import json, shutil, sys, tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402

RUN = Path(__file__).resolve().parents[1]
TASKS = ["voelkel2026", "goldwert2026", "vlasceanu2024", "bbprime2025", "voelkel2024"]
BUDGET, CAP = 24000, 12000


def measure(brief, label):
    sysm, user = ssb.predict.build_prompt(brief)
    plan = ssb.predict.plan_prompts(brief, budget_tokens=BUDGET, per_arm_char_cap=CAP)
    briefs = plan.pop("briefs")
    outdir = RUN / "inputs" / "prompts" / label
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "system.txt").write_text(sysm)
    for i, b in enumerate(briefs, 1):
        (outdir / (f"user_part{i}.txt" if len(briefs) > 1 else "user.txt")).write_text(
            ssb.predict.build_prompt(b)[1])
    arms = {a["title"]: len(a.get("text") or "") for a in brief["arms"]}
    return {**plan, "label": label,
            "n_outcomes": len(brief["outcomes"]),
            "n_cells": len(brief["arms"]) * len(brief["outcomes"]),
            "system_tokens": ssb.predict.n_tokens(sysm),
            "user_chars_untruncated": len(user),
            "arm_chars": dict(sorted(arms.items(), key=lambda kv: -kv[1])),
            "arms_with_no_text": [t for t, n in arms.items() if n == 0],
            "prompt_files": sorted(p.name for p in outdir.iterdir())}


def main():
    out = {"policy": {"budget_tokens": BUDGET, "per_arm_char_cap": CAP,
                      "remedies_in_order": ["send whole", "truncate one over-long arm at a paragraph "
                                            "boundary with a visible marker", "split arms across parts "
                                            "sharing the control text and two anchor arms"],
                      "rejected": {"summarise": "a second model rewriting the stimulus changes the thing "
                                                "being predicted and the predictor would no longer have "
                                                "read the message it is predicting"},
                      "token_counter": "tiktoken cl100k_base as a proxy for the target tokenizer"},
           "tasks": {}}
    tmp = Path(tempfile.mkdtemp(prefix="ssb_prompt_budget_"))
    for t in TASKS:
        d = tmp / t                       # carve OUTSIDE runs/ - this is not a run
        ssb.task.carve(t, d)
        brief = json.loads((d / "brief" / "task.json").read_text())
        out["tasks"][t] = measure(brief, t)
    out["target"] = measure(ssb.predict.target_brief(), "target")
    prac = [v for k, v in out["tasks"].items()]
    out["totals"] = {
        "practice_prompt_tokens_one_draw": sum(sum(v.get("tokens_per_part") or [v["tokens_whole"]]) for v in prac),
        "target_prompt_tokens_one_draw": out["target"]["tokens_whole"],
        "n_calls_per_draw": sum(v["parts"] for v in prac) + out["target"]["parts"],
        "note": "multiply by the number of independent draws, and again by 2 if stage 3a's "
                "recognition probe reuses the same briefs",
    }
    (RUN / "inputs" / "prompt_budget.json").write_text(json.dumps(out, indent=1))
    shutil.rmtree(tmp, ignore_errors=True)
    for k, v in list(out["tasks"].items()) + [("target", out["target"])]:
        print("  %-14s %2d arms x %2d outcomes  whole %6d tok  policy=%-6s parts=%d %s"
              % (k, v["n_arms"], v["n_outcomes"], v["tokens_whole"], v["policy"], v["parts"],
                 ("truncated: " + ", ".join(v["truncated_arms"])) if v["truncated_arms"] else ""))
    print("  totals:", json.dumps(out["totals"]))


if __name__ == "__main__":
    main()
