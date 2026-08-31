---
name: ssb
description: Silicon Sample Benchmark harness - parse the benchmark spec, build and validate a prediction card, derive Tier-1/2/3 submission files, synthesise an individual-level dataset backwards from predicted analyses, score training tasks with the frozen metrics, carve held-out tasks with a leak audit, and run the gate list. Use for any work on the climate-trust megastudy prediction, the /workspace/benchmark submission format, backward synthesis, or the practice loop in /workspace/run/AGENTS.md.
---

# ssb - the Silicon Sample Benchmark harness

Import name `ssb`. Read `/workspace/run/DESIGN.md` for why the loop has this shape and
`/workspace/run/AGENTS.md` for the stage-by-stage loop. This file is the API contract.

    await ssb()                 # status: spec selftest + run inventory + scoreboard tail
    ssb.spec.selftest()         # confirm the parsed spec still matches the shipped example

## Modules

| module | what it owns |
|---|---|
| `ssb.spec` | the benchmark spec, parsed from `/workspace/benchmark` at call time. Nothing is hardcoded. `load()`, `tier1_columns()`, `to_pp()/from_pp()`, `composites()`, `stimuli()`, `intervention_text()`, `selftest()` |
| `ssb.card` | `Card`: the single prediction object. `skeleton()`, `from_inputs()` (assemble from `inputs/pool` + `inputs/baselines`), `load()/save()`, `validate()`, `tier3()`, `tier2_main()`, `tier2_moderator()`, `cell_means()`, `clipping_report()` |
| `ssb.predict` | the predictor as a plain tool-less completion. `target_brief()`, `build_prompt()`, `plan_prompts()` (the prompt-budget policy: whole -> truncate -> split), `n_tokens()`, `anchor_spread()` (what a split cost), `command()`, `cache_key()`, `parse()` (delimiter- and unit-tolerant; see below), `aggregate()`, `fit_calibration()` (honours an `in_slope` column), `apply_calibration()`, `to_native()` (pp -> native units, required before a card), `stub_completion()` (a scripted NON-predictor for dry runs) |
| `ssb.synth` | backward synthesis. `draw_profiles()`, `assign_conditions()`, `latent_means()`, `synthesize()`, `fit_means()`, `recompute()` |
| `ssb.score` | the frozen scoring tables and nothing else. One function per named row, plus `scorecard()` and `baselines()` |
| `ssb.task` | training tasks. `load_adapter()`, `carve()`, `true_ates()`, `attrition_bounds()` (Lee bounds when an adapter declares `attrition_bounds`), `score_task()`, `leak_audit()` |
| `ssb.deposit` | `build()` - three submission repos from one card, each validated by the benchmark's own `make check` |
| `ssb.gates` | `new_run()`, `record()`, `check_reconstruction()`, `verdict()`, `scoreboard_append()` |

## The card is the only prediction object

Tier 1, Tier 2 and Tier 3 are all *derived* from one `Card`, so they cannot disagree.

```python
crd = ssb.card.Card.load("runs/<id>/card")
assert crd.validate() == []          # gate G4
t1, diag = ssb.synth.synthesize(crd, joint)        # gate G7 = diag.sd_ratio
print(ssb.gates.check_reconstruction(crd, t1))     # gate G6
res = ssb.deposit.build("runs/<id>", crd, t1, meta)  # gate G5
```

Subgroup ATEs are low-rank: `ate[i,o,m,l] = ate[i,o] * r[m,l] * t[i,m,l] / Z[i,m]`, with `Z`
the share-weighted normaliser that makes subgroup ATEs average back to the marginal ATE.
Predicting "no moderation" is `responsiveness.factor = 1` everywhere - an honest, always-
available filling of the moderator grid, which the benchmark requires to be complete.

## Three rules that are easy to get wrong

1. **Heap items, never composites.** A human composite is the mean of k heaped items and is
   itself finely grained. `synth._round_human` is applied at item level only.
2. **Convert pp to native units before filling a card.** The predictor answers in percentage
   points of each outcome's scale range; `ssb.card` stores native units. Use `predict.to_native`.
   Silent on 0-100 sliders, catastrophic on `donation_ams` ($1 = 10 pp) and `newsletter_signup`.
3. **Do not deposit at the precision floor.** The floor is a minimum. At 500/1,000 the standard
   error of an ATE recomputed from your own rows is ~1.3 pp - larger than the effects. Use a
   bigger pool and `fit_means`; both are free. See DESIGN.md choice 2.

## Adapters

A training-task dataset is a declarative JSON file in `inputs/adapters/`, never code.
Copy `_TEMPLATE.json`, fill it, verify the codings on a small sample, then set
`status: VERIFIED`. `ssb.task.load_adapter` docstring lists the required keys.

Two keys exist for differential attrition, and they are a pair (OPEN item 11):
`outcomes.<name>.observed_if_any: [cols]` masks a column that stores **0** for people who
never reached the item (an attrition artefact) to NaN unless one of `cols` is present, and
`attrition_bounds: true` makes `carve` write `sealed/attrition_bounds.csv` and a summary into
the manifest. Do not "solve" a zero-filled column with a completion filter: that trades data
away for tighter post-treatment conditioning, measured at 2,651 rows and 2 pp of bound width.
Where the bounds are wider than the effects, tag the task's pairs `in_slope = False` so it is
scored but cannot inform the calibration slope.

## Prompt budget

`plan_prompts(brief, budget_tokens=24000, per_arm_char_cap=12000)` returns `{policy, parts,
briefs, ...}`. The order of remedies is fixed: send whole; truncate a single over-long arm at a
paragraph boundary **with a visible marker**; split arms into balanced parts that each carry the
control text and the same two anchor arms. Summarising is not offered - a second model rewriting
the stimulus changes the thing being predicted. After a split, `anchor_spread()` measures what
the split cost on the arms every part saw. Both numbers are set by measurement, not taste: the
target prompt is 9,892 tokens and its longest arm is 11,134 characters
(`inputs/prompt_budget.json`).

## Blinding

`ssb.predict` never touches the filesystem: the predictor is a plain completion with
`--tools ""`, so it cannot read a sealed truth or a source dataset. `ssb.task.leak_audit`
then checks the transcript anyway. Both are required; the audit result goes on the scoreboard.
The echo probe is scored as an EXCESS over a shift-null, because chance collisions on the 2-dp
grid run 17-46%; keep the two controls (a transcript containing the sealed file must score LEAK,
a scripted stub must score CLEAN) whenever that probe is touched.

## Parsing a real completion

`parse` locates the **outcome** as a whole field first, then the condition before it and the first
number after it. That one change makes a markdown table, a semicolon or tab delimiter, a trailing
comment column, a `pp`/`%` unit suffix, a `+` sign and sloppy case all parse identically — and it
keeps a missing cell as **NaN**, never 0, because a zero is scored as a deliberate null prediction.

The tolerance is bounded on both sides and the bounds are tested, not asserted:
`tools/test_parse.py` builds 14 malformed completions from the target's own grid and 7 negative
controls (prose, a refusal, a sentence naming one cell, wrong names, a header alone). Run it before
spending anything:

    /opt/kernel/venv/bin/python tools/test_parse.py    # 13 recovery modes at 208/208, 7 controls at 0

Before this existed the parser had only ever seen `stub_completion`'s perfect CSV, and **8 of the 14
modes lost every cell** — a markdown table, a tab, or `1.2 pp` would each have aborted a paid batch.

## Dry runs

`ssb.predict.stub_completion` scripts a CSV from cell names without calling a model, so the
plain-code stages can be exercised with no credential. `ssb.gates.scoreboard_append` REQUIRES an
explicit `stub` flag: a scripted number must never be confusable with a practice score.
