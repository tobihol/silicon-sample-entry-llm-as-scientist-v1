# RUNBOOK.md — the real practice run, when the simulator credential lands

Everything in this file is built and verified. The **only** missing ingredient is an authenticated
`claude -p`; stages 3 and 5 are the only ones that spend budget, and the operator approves the batch.
Gate definitions, the stopping rule and the roles are in `AGENTS.md`; this is the sequence.

## 0. Preconditions (all currently true)

```bash
cd /workspace/run
PY=/opt/kernel/venv/bin/python                # there is no `python`/`python3` on PATH in a shell
$PY -c "import ssb; print(ssb.gates.list_runs())"     # spec selftest + run inventory + scoreboard
$PY -c "import pyreadstat, openpyxl, tiktoken"        # the three optional deps the tools need
env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN claude -p hi --tools "" --model <id>   # must NOT 401
```

If that third line fails, the venv was rebuilt between sessions and lost them (it happened at the
start of run 06). Restore, then re-check — nothing else in this file works without them:

```bash
uv pip install --python /opt/kernel/venv/bin/python pyreadstat openpyxl tiktoken
```

Inputs are built and reusable; rebuild only if a dataset changes:

```bash
$PY tools/build_pool.py            # 21 s  -> inputs/pool/joint.csv (+ marginal-exact variant)
$PY tools/measure_referent_fanout.py #  20 s -> inputs/measured/referent_fanout.json (read by the next line)
$PY tools/build_baselines.py       #  8 s  -> inputs/baselines/{control_levels,subgroup_offsets,provenance}
$PY tools/measure_gap_transfer.py  # 15 s  -> inputs/measured/gap_transfer_4point.json (GAP4)
$PY tools/extract_qsf_texts.py     # 40 s  -> inputs/texts/{vlasceanu2024,bbprime2025}_arms.json
$PY tools/extract_stimuli.py       #        -> inputs/stimuli.json (only if questionnaire.txt changes)
$PY tools/prompt_budget.py         # 30 s  -> inputs/prompt_budget.json + inputs/prompts/
$PY tools/measure_agency_anchor.py #   1 s -> inputs/measured/agency_trust_anchor.json (read by build_baselines)
$PY tools/validate_party_imputation.py # 40 s -> inputs/measured/party_imputation_validation.json (a check, not an input)
```

**Before any spend**, and it takes a second — the parser is the only thing between a paid batch and
a `SystemExit`:

```bash
$PY tools/test_parse.py            # 13 recovery modes at 208/208, 7 negative controls at 0
$PY tools/test_gates.py            # 7 RED-path cases: a gate that has never failed is not a gate
$PY tools/test_calibration.py      # 6 cases: a map that silently falls back is not a map (finding 32)
```

And two things that cost nothing and change what a batch is worth paying for:

```bash
$PY tools/task_power.py            # does each carved task HAVE signal? var(true)=var(obs)-mean(SE^2),
                                   #   and its sqrt/sd(obs) IS the r_adj denominator (finding 36)
$PY tools/forecast_target.py       # what we should expect to SCORE on the target, and the ceiling
$PY tools/split_half.py            # the same question MEASURED on real respondents, not simulated
                                   #   (~8 min; it recomputes 5 ATE tables x 12 random half-splits)
$PY tools/margin_ci.py             # does the margin over the two baselines exclude zero? (finding 42)
$PY tools/calibration_variants.py  # do NOT "fix" the under-dispersion: 0/5 folds (finding 41)
$PY tools/draws_value.py           # what did 3 draws buy? nothing, for 54% of the batch (finding 43)
$PY tools/models_value.py --bootstrap 2000   # what did a second MODEL buy? ~nothing either (finding 48);
                                   #   name BOTH ends of every margin it prints (finding 52)
$PY tools/verify_deposit.py --strict  # do the deposited ROWS reproduce the card, independently of the
                                   #   tool that built them? + coverage, floors, NA, finding-26 fields,
                                   #   and every field still at a template placeholder (finding 56)
$PY tools/moderation_power.py      # is there ANY predictable Section-3 moderation? no: interactions
                                   #   split-half at r=0.02 vs main effects at 0.60 (finding 53)
$PY tools/demographic_predictability.py  # does the synthesis exaggerate group differences? party sits
                                   #   at 0.95x the climate reference; education/income unchecked (54)
$PY tools/fill_registration.py runs/<id>  # fill the registration form from artefacts: 32 of 39 items
                                   #   are facts only the harness knows (finding 55). Draft only.
$PY tools/length_bias.py runs/<id>        # what is the predicted RANKING made of? message length
                                   #   explains rho +0.726 of it on the target card (finding 59)
$PY tools/stage_raw_logs.py runs/<id>     # assemble the K.2 raw-log bundle: prompts, unprocessed
                                   #   completions, provider envelopes, sha256 manifest, and a
                                   #   replay that reparses to the deposited table (finding 58)
$PY tools/inputs_manifest.py       # has inputs/ drifted since the last run? exit 1 on any change
$PY tools/verify_scoreboard.py     # does every PAID row recompute from its pairs.csv? (finding 46)
                                   #   + which PARSER made each row; stale PAID row -> exit 1 (76)
$PY tools/reparse_audit.py         # re-derive every row through today's parser; --write makes the
                                   #   board one version and keeps scoreboard.csv.pre-reparse (76)
$PY tools/trust_task.py            # the trust-family task's pre-registered verdicts, its slope's
                                   #   (uninformative) interval, and the card's trust cells (77, 78)
```

**Never re-use a `run_id`.** `new_run` does `mkdir(exist_ok=True)`, so re-executing into an existing
id overwrites that run's `pairs.csv` while the scoreboard keeps the old rows — the defect behind
standing finding 46. Both spending tools now refuse at start, and `scoreboard_append` refuses the
duplicate row as a backstop. Every completed call is cached, so a fresh id costs nothing.

`inputs_manifest.py --write` re-baselines it after a deliberate rebuild. Every run now records the
tree digest as `params.inputs_sha256` in `run.json`, so two scoreboard rows can be told apart when
they were built from different inputs — which nothing could do before.

And the whole loop, with the scripted stub in place of the predictor, is one command — run it before
spending any budget, because it exercises every plain-code stage and all eight gates in 86 s:

```bash
$PY tools/dryrun.py 20260815-dryrun-04
```

## 0b. The task list (session 10)

The five original tasks are the default of `tools/practice.py`. **Tasks 6 and 7 are opt-in** and
must be named, because they are not part of the pipeline's own practice pool - they exist to widen
the ARM base for prompt/model experiments (`runs/_openexp24/PREREG.md`):

```bash
PY=/opt/kernel/venv/bin/python
$PY tools/build_tappin.py --check          # arm derivation red paths + derived file digest
$PY tools/build_hackenburg.py              # rebuild task 7's input (73 arms, one issue)
$PY tools/practice.py --model claude-opus-5 --tasks tappin2023 hackenburg2025 --draws 3
```

Measured sizes and prices, so a later session does not re-derive them:

| task | arms | cells | prompt | parts | billed, 3 draws + probe |
|---|---|---|---|---|---|
| `tappin2023` | 48 | 96 | 15,141 (len/4) | 1, nothing truncated | ~170k |
| `hackenburg2025` | 73 | 292 | 24,089 whole | **2** (12.6k each) | ~165k |

Both are `in_slope = False` by adapter declaration (`exclude_from_slope`): a 7-point Likert outcome
and LLM-authored stimuli respectively. They are scored on every Section-1 row and inform no
magnitude. Price a new corpus with `tools/billing_factors.py` after its first batch: the len/4
factor is 1.206 here against 1.40-1.57 on the climate briefs (finding 68).

**Task 8 (session 12) is opt-in and is not a scored task in the ordinary sense.** `gligoric2025` is
the harness's only TRUST-family experiment and its ATE table has negative signal variance
(`tools/task_power.py`: ceiling on attainable r = 0.000), so it is carved to grade MAGNITUDE against
the paper's published equivalence bound and nothing else:

```bash
$PY tools/build_gligoric.py                # rebuild the input, 7 red paths
$PY tools/practice.py --model claude-opus-5 --tasks gligoric2025 --draws 3   # ~20k billed
$PY tools/practice.py --model claude-opus-5 --tasks orchinik2024 --draws 3 --probe-version 2
                                                                            # ~80k billed, task 10
$PY tools/trust_task.py                    # the pre-registered verdicts + the card sensitivity
```

| task | arms | cells | prompt | parts | billed, 3 draws + probe |
|---|---|---|---|---|---|
| `gligoric2025` | 5 | 40 | 1,618 (len/4) | 1, nothing truncated | ~19k |

Rules that travel with it, all declared in `runs/_trusttask/PREREG.md` before its first call: its
ranking rows are **at chance by construction and may not be read as skill**; it is
`exclude_from_slope` (conservatives-only subgroup, unidentified magnitudes); it is **not** appended
to the 202-arm pool that prompt and model experiments use; and a `RECOGNISED` probe **quarantines**
the row (`tools/quarantine_row.py`) rather than scoring it - which is what happened to
`claude-fable-5`, so read the board's fable row as evidence about recall, not about prediction.

## 1. Stages 0-3, in one command

Stage 3 is one of the two stages that spend budget, so it has its own entrypoint and its own
default of spending nothing. `tools/practice.py` carves the tasks, assembles the recognition
probes **and** the prediction prompts through the real `ssb.predict` path, writes every payload to
disk, prints the bill, and stops:

```bash
PY=/opt/kernel/venv/bin/python
$PY tools/practice.py --model <model-id> --probe-version 2                       # plan only. NO call.
$PY tools/practice.py --model <model-id> --probe-version 2 --execute --approved  # spend, after yes
```

`--execute` without `--approved` is refused by the script.

**Rehearse it first — it costs nothing and it is not the same test as the dry run.** `tools/dryrun.py`
exercises the plain-code stages with the predictor replaced; the rehearsal exercises the *call* path
itself, which no dry run touches:

```bash
PATH="/workspace/run/tools/fake:$PATH" $PY tools/practice.py --model <id> --draws 3 --rehearsal
```

`tools/fake/claude` is argv-compatible with `ssb.predict.command()`, refuses to run without
`SSB_REHEARSAL=1`, and exits non-zero if `--tools` is not empty. A rehearsal writes to a **separate
cache** (`runs/_cache/rehearsal/`) so a scripted answer can never satisfy a later paid call, and its
scoreboard rows carry `stub=True` and `stage=rehearsal`. Every run — rehearsal or real — records the
resolved `claude` path and its sha256 in `stages/practice/summary.json`.

One `--execute` run does, in this order:

| | |
|---|---|
| 0 | `ssb.task.carve` every task -> `brief/` + `sealed/`; nothing that touches a prompt reads `sealed/` |
| 3a | **the recognition probe (OPEN item 3), before any prediction — use `--probe-version 2`, whose `CONFIDENCE` field states its referent (finding 96); v1 is the default only so that probes already on disk stay cache hits** — one call per task, graded against `inputs/recognition_keys.json`, a regex list frozen before the call |
| 3b | n independent draws per task through `plan_prompts`' whole/truncate/split policy, every call cached on `ssb.predict.cache_key` under `runs/_cache/completions/` |
| 3c | median aggregate, `score_task`, `leak_audit` of every transcript **with its positive control**, one scoreboard row per task with `stub=False` |
| 3d | `stages/calibration/pairs.csv` (what stage 4 needs), `stages/practice/cost.json`, `stages/practice/summary.json` |

Three things it refuses to do quietly, all of them lessons from earlier runs:

- **an unparsed cell aborts the run.** A NaN that reached `aggregate` would be scored as a null
  prediction and earn 0.5 directional credit for a broken call.
- **a payload that names its own study aborts the run.** Assembling the probes found two adapters
  whose `sample_description` named the study (`Strengthening Democracy Challenge`, `BB-PRIME`);
  both are redacted and the check runs every time (`--allow-identified` to override, loudly).
- **a leak verdict is required for every transcript**, and the positive control must still fire.

Because every call is cached on the prompt and every sampling parameter, a crash mid-batch costs
nothing to resume: rerun the same command.

## 2. Stages 4-9, in one command

Stage 5 is the second and last stage that spends budget, and it is the one that makes the product,
so it is a script with the same guard rails as stage 3 rather than pseudocode to be run by hand:

```bash
$PY tools/target.py --practice-run runs/<id> --model <model-id>                       # plan only
PATH="/workspace/run/tools/fake:$PATH" \
  $PY tools/target.py --practice-run runs/<id> --model <model-id> --rehearsal          # free rehearsal
$PY tools/target.py --practice-run runs/<id> --model <model-id> --execute --approved   # spend
```

It takes the practice run's `stages/calibration/pairs.csv`, fits the calibration (stage 4), calls
the target through the same cached `ssb.predict.command()` path (stage 5), converts pp → native
units and builds the card (stage 6), synthesises 43,200 rows **over five seeds** (stage 7), deposits
all three tiers through the benchmark's own `make check` (stage 8) and records the gates and the
scoreboard row (stage 9).

**Stage 5 costs 4 calls and 52,357 tiktoken = 122,061 BILLED tokens at 3 draws** — 3 prediction
draws plus **stage 5a, the blinding probe** (27,463 billed), which asks the predictor whether it
already knows the target study's results and **aborts before any prediction call** if it says yes
(`stages/target/cost.json`). Price in billed tokens, always: tiktoken cl100k undercounts Anthropic's
tokenizer by 1.574x and `claude -p` makes a second billed pass over the same prompt worth +73.2% of
context, so the naive number is 2.44x low (finding 28). Stage 3 at 3 draws with the probe is
**23 calls and 944,474 billed tokens** — measured against an actual 941,504, an error of 0.3%.
`tools/practice.py --max-billed-tokens N` stops before the call that would cross the ceiling, and
counts already-paid cache hits against it so the ceiling governs the batch and not the session.

Three aborts, each one a standing finding made structural:

- an **unparsed target cell** aborts — a NaN would be deposited as a null prediction;
- a **non-empty `clipping_report()`** aborts — finding 8, the pp → native conversion, silent on the
  eleven 0-100 sliders and catastrophic on `donation_ams` and `newsletter_signup`;
- **G6 is a five-seed scan, not one draw** — finding 18. The gate detail records the range, and the
  worst seed is what has to clear the tolerance.

Rehearsed end to end on `20260815-rehearsal-target-01`: all eight gates green, `make check`
PASS WITH WARNINGS ×3, G6 1.665-1.770 over five seeds against a 2.50 tolerance.

`tools/dryrun.py` still runs the same sequence with `stub_completion` in place of the predictor and
no subprocess at all; it is the faster plumbing check.

## 2a. Stage-5 decision rules — fixed before any target prediction exists

Written while stage 5 is unapproved and unrun, for the same reason the recognition probe's discount
policy was written before the first probe call: a rule chosen after seeing the output is not a rule.
Anything below that is changed later must be changed **in this file, with a reason, before** the run
that uses it.

**Order of operations.** Stage 5a (blinding probe) → abort on `RESULTS_KNOWN: YES` → 3 prediction
draws → parse → median aggregate → calibration policy → card → deposit. The probe runs first so that
a blinding event costs one call and no prediction exists to be discarded.

**Draws = 3, and not more.** Measured: cell-level SD across three draws is 0.077–0.151 pp against an
RMSE of 2.6 pp (finding 29). A fourth draw averages a quantity that is not the error.

**The magnitude multiplier is the operator's ruling (OPEN item 18), and there are exactly two
options** — `--lambda-policy pooled` (1.521, the exclusion-respecting fitted slope) and `none`
(unshrunk). There is no climate-only option; respecting the pre-registered exclusions it is the same
498 pairs and the same number. **If stage 5 is approved without a ruling on item 18**, build both
cards, deposit neither, and take both to the operator — the deposit decision is theirs under the
frozen file, and building both costs nothing because the predictions are cached.

**Four aborts, all structural, none of them a judgement call at run time:**

| abort | why |
|---|---|
| `BLINDING EVENT` | the frozen file's absolute rule; stops before any prediction call |
| an unparsed target cell | a NaN would be deposited as a null prediction and earn 0.5 directional credit |
| a non-empty `clipping_report()` | finding 8: pp → native, silent on the eleven sliders, catastrophic on `donation_ams` and `newsletter_signup` |
| `--max-billed-tokens` exceeded | the guard reserves headroom, so the ceiling is never crossed |

**G6 is a five-seed scan and the worst seed is what has to clear the tolerance** (finding 18). A
single draw of 2.38–2.46 against a 2.50 tolerance is not margin.

**Two things the harness must write into the deposit because the template's defaults are false**
(finding 26): `approach_family` is analysis-first and never generated a respondent, and `models` is
the model actually called. `check.R` asserts they are non-empty, not that they are true.

**One warrant rule.** Any trust ATE in the final card above 2 pp needs its justification written into
the run report, naming finding 5 (the only randomised evidence on the target's own construct is
−0.22 to +0.83 pp, equivalence-bounded below d = 0.1). This is a reporting requirement, not a cap:
the number is not to be edited to avoid writing the paragraph.

**Three things that must not change after the target predictions are seen**, because each was fitted
or frozen on evidence that predates them: the `in_slope` exclusions, `inputs/outcome_families.json`,
and the λ policy chosen above.

## 3. Costs, measured (`inputs/prompt_budget.json`, rebuilt by `tools/prompt_budget.py`)

Tokens are the payload `ssb.predict.command()` would actually send, counted with tiktoken cl100k as
a proxy. The policy is `ssb.predict.plan_prompts(brief, budget_tokens=24000, per_arm_char_cap=12000)`
and it is applied in stage 3 and stage 5 alike — see OPEN item 10 for why those two numbers.

| prompt | arms x outcomes | tokens | policy |
|---|---|---|---|
| vlasceanu2024 | 11 x 15 | 5,880 | whole (texts now on disk, from the QSF) |
| voelkel2026 | 10 x 9 | 7,626 | whole |
| goldwert2026 | 17 x 12 | 17,036 | whole |
| bbprime2025 | 17 x 24 | 17,447 | whole, 2 arms truncated at 12k chars |
| voelkel2024 | 26 x 9 | 34,303 | **split into 2 parts** (18,076 / 18,066), 2 anchor arms in both, 7 arms truncated |
| **target** | **16 x 13** | **9,892** | whole, never truncated by construction |

One draw of the practice set is **84,136 tokens over 7 calls**; the target is 9,892 over 1. Times the
number of independent draws, plus the probe.

### The batch the operator is asked to approve

Printed by `tools/practice.py --model <id>` (plan mode) and written to
`runs/<id>/stages/practice/cost.json`. At the default **3 draws with the probe on**:

| task | policy | calls | probe in | predict in | est. out | total |
|---|---|---|---|---|---|---|
| voelkel2026 | whole | 4 | 7,763 | 23,553 | 3,360 | 34,676 |
| goldwert2026 | whole | 4 | 17,172 | 51,783 | 7,464 | 76,419 |
| vlasceanu2024 | whole | 4 | 6,017 | 18,315 | 6,060 | 30,392 |
| bbprime2025 | whole | 4 | 17,579 | 53,001 | 14,808 | 85,388 |
| voelkel2024 | **split** | 7 | 18,218 | 109,806 | 8,544 | 136,568 |
| **stage 3 total** | | **23** | **66,749** | **256,458** | **40,236** | **363,443** |

Stage 5 adds **1 call and 9,892 input tokens per draw** on the target (3 draws: 3 calls, ~31,500
tokens with output). **A full first real run is therefore ~26 calls and ~395,000 tokens.** Input
counts are the assembled payloads, measured; output is the one estimate (12 tokens/cell, 120/probe)
and is flagged as such in `cost.json`. Halving the draws roughly halves everything except the probe,
which is one call per task whatever `--draws` says.

After a split, `ssb.predict.anchor_spread(frames, anchors)` reports how much splitting changed the
answer on the arms both parts saw. Record it: it is the only measurement of what the split cost.

## 4. What must be true before deposit

- All eight gates green (`ssb.gates.verdict`), or waived in `OPEN.md` with a reason. For G6 and G7,
  which are computed from sampled rows, check the seed scan (`tools/dryrun.py` writes one) rather
  than a single draw: at the 21,600-row floor G6's margin is smaller than its seed noise.
- Every practice task leak-audited **CLEAN**, with the positive control still firing
  (a transcript containing the sealed file must score LEAK).
- `make check` PASS or PASS WITH WARNINGS on all three tiers. Its three standing warnings are
  operator-owned (`registration.md`'s 37 checklist items, `code_repository`, `.zenodo.json`
  creators) — but they are **not the whole list**. `tools/verify_deposit.py --strict` is the gate:
  it also catches `team_name`, `contact` and `abstract`, which `check.R` passes green on template
  placeholders, and `blinding_attestation`, which ships pre-set to `true` (finding 56). Of
  `registration.md`'s items, 32 of 39 are harness facts and are generated by
  `tools/fill_registration.py`; only 7 are genuinely the operator's (finding 55).
- `entry` is `primary` or `secondary-k` - anything else fails the filename check.
- Any predicted trust ATE materially above ~1-2 pp has its warrant written into the run report
  (AGENTS.md standing finding 5).
- The deposit decision and the prediction lock (**August 31, 2026**) are the operator's, never mine.
