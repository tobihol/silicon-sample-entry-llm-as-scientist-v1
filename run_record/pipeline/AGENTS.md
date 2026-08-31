# AGENTS.md — the loop

**This file is mine.** The binding definitions — what I build, the words, the scoring
tables, the blinding rules, how to call a simulator — are in the system prompt, from
`.prime/agent/APPEND_SYSTEM.md`. That file is frozen and hash-checked. Nothing here restates
it; where I mean a scoring rule, I name its row.

## Where things are

| | |
|---|---|
| `.` (`/workspace/run`) | working directory — everything here is mine except the frozen file |
| `../benchmark/` | the official submission template, read-only: instrument, codebook, formats, validator |
| `../datasets/<name>/` | the public training datasets, read-only |
| `runs/<run-id>/` | everything a run produces |
| `.prime/agent/skills/` | the skills I write |
| `tools/` | scripts that rebuild an input from the mounted data, one that runs stage 3 end to end (`practice.py`), and one that rebuilds a whole dry run (`build_pool.py`, `build_baselines.py`, `extract_stimuli.py`, `extract_qsf_texts.py`, `measure_gap_transfer.py`, `measure_referent_fanout.py`, `measure_agency_anchor.py`, `validate_party_imputation.py`, `agency_sensitivity.py`, `fanout_sensitivity.py`, `prompt_budget.py`, `test_parse.py`, `test_gates.py`, `test_draw_frames.py`, `models_value.py`, `model_selection.py`, `verify_deposit.py`, `deposit_checklist.py`, `moderation_power.py`, `demographic_predictability.py`, `fill_registration.py`, `stage_raw_logs.py`, `length_bias.py`, `length_variants.py`, `length_experiment.py`, `length_robustness.py`, `build_tappin.py`, `build_hackenburg.py` (the two session-10 task inputs, each with its own red-path checks), `build_koetke.py` + `koetke_verdicts.py` (trust task #2 and its pre-registered verdicts), `build_altenmueller.py` + `altenmueller_verdicts.py` (trust task #3, a source-IDENTITY contrast, and its pre-registered verdicts), `build_orchinik.py` + `orchinik_verdicts.py` (trust task #4, the first in-family task on the target's own 0-100 slider format, its pre-registered verdicts and the permutation null that reads them), `vlasceanu_trust_anchor.py` (the card's trust levels/SDs against a US quota-panel climate-trust slider), `skill_decomposition.py` (does within-outcome skill track how different the arms are? - the pair analysis and the target projection), `identity_audit.py` (the 16 target stimuli read for explicit political-identity claims, plus the tilt arithmetic), `party_moderation.py` (identity-label vs message-strategy party interactions), `arm_power_projection.py` (does a candidate task DECIDE an open question?), `billing_factors.py`, `apply_slope_exclusions.py`, `dist_audit.py` (the Tier-1 distributional surface against real human rows, with the four-part compatibility rule, the human ceiling and the human floor), `synth_variants.py` (the pre-registered distributional improvement loop and its seed-noise floor), `build_target01b.py` (the PENDING-OPERATOR distributional variant of the deposit), `practice.py` (stages 0-3, `--variant` applies a length treatment), `target.py` (stages 4-9), `fake/claude` (the rehearsal stand-in), `dryrun.py`) |
| `DESIGN.md` | what the loop is and why it has this shape |
| `OPEN.md` | what I could not decide, and what would decide it |
| `RUNBOOK.md` | the exact sequence for a real practice run, with measured prompt sizes |
| `inputs/` | run inputs built once and reused: `stimuli.json`, `adapters/`, `texts/`, `pool/`, `format_params.json`, `baselines/` (human-anchored control levels + subgroup offsets), `measured/`, `prompt_budget.json` + `prompts/` (the exact stage-3/5 payloads) |
| `notes/DATA_*.md` | dataset reconnaissance: exact paths, columns, codings, caveats |
| `runs/_openexp24/` | the session-10 pre-registration that closed OPEN 24 |

Nothing else is mounted. If I cannot see it, it was withheld on purpose — ask the operator.

## The loop

One skill, `ssb`, holds all the machinery (`.prime/agent/skills/ssb/SKILL.md` is the API).
A **run** is a directory under `runs/<run-id>/` and a list of gates. Stages are plain code
except where marked. Nothing is a judgement call that isn't written down.

| # | stage | what it does | is it a model call? |
|---|---|---|---|
| 0 | `open` | `ssb.gates.new_run()`; record the frozen file's hash and the spec hash | no |
| 1 | `inputs` | build `inputs/`: stimuli, dataset adapters, the profile pool, heaping params | no |
| 2 | `carve` | `ssb.task.carve()` per training task → `brief/` (blind) + `sealed/` (never shown) | no |
| 3 | `practice` | predict each brief; score with `ssb.task.score_task`; `leak_audit` each transcript | **yes** — a panel of plain completions |
| 4 | `calibrate` | `ssb.predict.fit_calibration()` on the pooled (predicted, human) pairs | no |
| 5 | `predict` | the same predictor, same prompt shape, on `ssb.predict.target_brief()` | **yes** |
| 6 | `card` | assemble the card: calibrated ATEs, human-anchored baselines, responsiveness | no |
| 7 | `synthesise` | `ssb.synth.synthesize()` → Tier-1 rows; `fit_means` removes our own noise | no |
| 8 | `deposit` | `ssb.deposit.build()` → three submission repos, each run through `make check` | no |
| 9 | `close` | gates, `scoreboard_append`, update `OPEN.md`, write `runs/<id>/REPORT.md` | no |

Only stages 3 and 5 spend the budget. **Ask the operator before either.**

### What a training task is

An arm × outcome ATE table carved from one of the five multi-arm experiments, in percentage
points of scale range, computed locally and written to `sealed/`. The predictor is given
`brief/` — message texts, item wordings, sample description, arm sizes — and nothing else.
Ground truth is held out *structurally*: the predictor is a plain completion with `--tools ""`
and no filesystem, so it cannot read `sealed/` or the source dataset. `leak_audit` then greps
the transcript for the sealed path, the sealed hash, and echoed sealed values, and the verdict
goes on the scoreboard. A practice score with no leak verdict is not a score.

Training tasks are shaped exactly like the target task — same CSV schema, same metrics, same
prompt — so a practice number and a target number mean the same thing.

### What a run stops on

Every gate in `ssb.gates.GATES` green, or waived in `OPEN.md` with a reason:

    G1 frozen file intact          G5 `make check` PASS/PASS-WITH-WARNINGS on all three tiers
    G2 practice scored + audited   G6 analyses recomputed from Tier 1 reproduce the card
    G3 calibration fitted          G7 per-outcome SD ratio within tolerance of 1
    G4 card complete, no NA        G8 scoreboard row appended, OPEN.md reviewed

### How improvement is measured

`runs/scoreboard.csv`, one row per (run, task), carrying the Section-1 and Section-2 metrics,
the fitted slope, the margin over both scripted baselines, and the leak verdict. Improvement
is a query over that file. A run that does not beat the no-effect floor **and** the
all-positive baseline on the same task has demonstrated nothing, however good it looks.
**Filter the query.** Since session 7 the board also carries 23 rows from the length experiment
(`run_id` starting `20260815-lenexp-`), four of whose five arms are *deliberately degraded
prompts* — a "best rho per task" query that does not exclude them is reading an experiment as a
pipeline score. Every row records its treatment as `variant=<name>` in `note`; `variant=base` is
the only one that is the pipeline's own prompt, and it is a re-score of already-paid calls.

### Two arms on one mount (parallel safety)

Two sessions may run concurrently against this `runs/` directory. Three rules make that safe,
and each has a red path in `tools/test_gates.py`.

1. **Every scoreboard write goes through `ssb.gates.scoreboard_append`.** It holds an exclusive
   `fcntl.flock` on `runs/_locks/scoreboard.lock` for the whole read → duplicate-check → write
   cycle and replaces the file atomically (temp file in the same directory + `os.replace`).
   Nothing else may open `runs/scoreboard.csv` for writing. Measured on the old unlocked
   protocol: two writers making 30 identical `(run_id, task_id)` claims each produced **20–30
   duplicate rows on 3 of 3 trials** — the finding-46 refusal is simply not a refusal when two
   processes read the board before either writes — and two writers of 300,000-character rows
   produced **two headers and a torn row on 3 of 3 trials**. Under the lock: 40/40 rows, one
   header, no tear.
2. **The completions cache is content-keyed, so its layout is collision-safe by construction.**
   The filename is `sha256(prompt + model + every sampling parameter)`, so two processes can only
   ever target the same file when they are making the *identical* call, and then the two payloads
   are interchangeable. The hazard was never the key, it was the write: `tools/practice.py` now
   writes each entry through `ssb.gates._atomic_write`, so a concurrent reader can never see a
   truncated envelope and a crash cannot leave one on disk.
3. **`SSB_ARM` namespaces run ids.** `ssb.gates.new_run` suffixes the id with the arm
   (`20260822-practice` → `20260822-practice-b`), so the two arms cannot address the same run
   directory even when they ask for the same name; an id that already carries the suffix is left
   alone, so a resume finds its own directory. The one case a suffix cannot cover — an *unarmed*
   process walking into an armed run's id — is refused by a claim registry at
   `runs/_locks/run_ids.json`, written under the same lock.

`SSB_ARM` unset is the historical single-armed behaviour and stays the default: no existing run
id changes.

### Roles

- **Plain code** for everything reproducible: spec, card, synthesis, scoring, gates.
- **A plain completion** for prediction — never an `rlm()` child, so blinding is a property
  of the call and not a promise. Independent draws are aggregated by median.
- **`rlm()` children** only for harness work: dataset reconnaissance, code review, writing
  adapters. They may read the datasets; they may never produce a prediction.

### Model calls

Exactly the command in the frozen definitions, built by `ssb.predict.command()`. Cache on
`ssb.predict.cache_key()`, which covers the prompt and every sampling parameter. Ask the
operator before any batch; the deposit decision and the prediction lock are the operator's.

## Standing findings

Facts established by measurement, not taste. Change them only with new measurement.

1. **The precision floor is a minimum, not a target.** At 500/intervention and 1,000 control,
   an ATE recomputed from our own rows carries ~1.3 pp of sampling noise — larger than the
   effects being predicted. Deposit a larger pool and run `fit_means`.
2. **Heaping belongs at item level.** Heaping a composite produces a distribution no human
   sample has (Distributions rows: OVL, KS D, Wasserstein-1).
3. **An exaggerated prediction can lose to the no-effect floor on RMSE while ranking almost
   perfectly.** Ordering and magnitude are separate skills; only the second is transferable
   from practice, via the fitted slope.
4. **`distrust_post` moves opposite to every other outcome.** The all-positive baseline is
   wrong on 16 of 208 cells for free.
5. **The only randomised evidence on message effects on trust in scientists** (gligoric2025)
   is −0.22 to +0.83 pp, equivalence-bounded below d = 0.1, in conservatives only. Any
   predicted trust ATE materially above ~1–2 pp needs its warrant written down in the run report.
6. **The heaping *rate* transfers across item types; the midpoint spike does not.** Climate
   attitude sliders in a quota panel (voelkel2026, 95,437 control-arm PRE responses) heap like
   probability sliders — 41.2% on multiples of 5 against orchinik's 42.5% — but carry 5.2% at
   exactly 50, a third of sce's probability-item 16.8% and four times what smooth rounding gives.
   The education gradient is 0.09, not the 0.25 that sce implied. Fit format parameters by
   simulation against a measured distribution, never by algebra.
7. **A costly-act outcome is a spike distribution, not a bell.** goldwert2026's real \$0–10
   donation puts 82.3% of a control arm on three values (\$0 29.7%, \$5 28.9%, \$10 23.7%).
   A single 0/1 newsletter ask converts 24.7%; a second ask adds ~8 points, not 24.7 (r = 0.54).
8. **The predictor speaks percentage points; the card stores native units.** The conversion is
   invisible on the eleven 0–100 sliders and catastrophic on `donation_ams` and
   `newsletter_signup`. `ssb.predict.to_native` exists for this; `card.clipping_report()` is what
   catches it when it is forgotten.
9. **Sample match is not item match.** `policy_specific_mean` was anchored on the design twin
   (same panel, same slider format) and was wrong by 10 pp: the twin's four policy items are not the
   target's seven and carry a cost trade-off clause. The target's seven are near-verbatim
   vlasceanu2024 items in a less panel-like sample. Check the item wordings before trusting a level;
   post-stratification fixed only 0.9 pp of the difference.
10. **A rescaled coarse-Likert mean runs ~5 pp high against a slider.** Measured on five
   near-verbatim policy items asked of the same population on a 3-point scale (TISP) and a 0-100
   slider (vlasceanu2024): −4.0, −7.1, −2.9, −4.8, −5.8 pp. Subgroup *gaps* transfer better than
   levels but still shrink: ratio 0.63–0.93 (use 0.8). Every level imported from a Likert source
   needs both corrections, and the trust battery needs a third — the referent shift from
   "most scientists" to "most climate scientists" is −3.93 pp, measured within-person in TISP.
11. **An all-zero subgroup table is a prediction, not a neutral default** — the prediction that no
   demographic group differs from any other, which three Tier-1 scoring rows measure directly. On
   the mounted data it is wrong by up to 21 pp per cell (party x climate policy). `inputs/baselines/`
   now anchors **351 of 351 cells** (the last six, gender `Other` x trust, came from Pew W100+W114).
12. **Real subgroup offsets make G6 harder, and only rows fix it.** The Tier-2 moderator residual is
   `2.462 x sqrt(21,600 / n)` pp — sampling noise in thin cells (gender `Other` is ~12 respondents
   per condition), not raking error. 1.0 pp needs ~131,000 rows.
13. **An echo-based leak probe needs a null.** A predictor writing small effects onto the same 2-dp
   grid as the sealed truth collides with it 17–46% of the time by chance — measured on a scripted
   stub that read nothing. Score the excess over a shift-null, and keep a positive control (a
   transcript containing the sealed file) in the loop: the original probe scored that at 0.00
   because `truth.csv` stores full float precision.
14. **A gap transfers across scale formats; a level does not.** The 0.8 gap factor, borrowed from a
   3-point measurement, is now measured for the **4-point** case that the Pew anchor needs: slider
   offsets regressed on rescaled 4-point offsets, three constructs x four moderators (CCAM vs
   voelkel2026), slope **0.808, r 0.953, n = 36** (party+race 0.785; per-moderator 0.75–1.24). The
   same three construct pairs disagree on **level** by −1.6 to +12.6 pp, so no 4-point level bridge
   exists on the mounted data and none is claimed. Anchor orderings and gaps from a coarse item;
   never a level, a variance or a distribution.
15. **The climate referent does not lower trust — it fans it out by party.** Measured twice, with
   non-overlapping weaknesses, and they agree. Pew W42 (right cut, wrong referent): environmental
   research scientists score **+0.35 pp** against medical overall but **−6.58 among Republicans and
   +5.25 among Democrats**, an 11.83 pp interaction (SE 1.09) positive on all eleven items. TISP US
   (right referent, weaker cut): the same respondents on the same 5-point item shift **+1.79 pp**
   (least conservative) and **−8.61 pp** (most) when "scientists" becomes "scientists in your country
   who work on climate change" — a 10.40 pp fan-out (SE 1.16) whose weighted average is the −3.93 pp
   "level shift" the card already used. Pooled: **11.16 pp (SE 0.80)**. The **additive** form
   transfers and the multiplicative one does not: TISP's generic gap is 9.7 pp against Pew's 21.6, so
   a stretch fitted in one source (2.07) is meaningless in the other (1.55). A third leg agrees:
   in gligoric2025, where four of 35 scientist types are assigned at random, **climatologists have
   the largest ideology gap of all 35** (16.2 pp against a median type's 4.6), a DiD of 11.30 pp
   (SE 3.49). A trust baseline that moves the *level* for a climate referent and leaves the party
   gap alone has the correction the wrong way round — and the *level* is the half that is still
   unsettled (−3.93 pp within person in TISP against −10.1 pp exemplar-vs-exemplar in gligoric).
16. **Filtering on completion is not the cheapest fix for a zero-filled column — it is the most
   expensive.** Replacing goldwert2026's `Finished == 1` with per-outcome de-zero-filling gained
   2,651 rows, cut the Lee trim fraction 0.110 -> 0.094 and the bound width 12.54 -> 10.57 pp, and
   left the ATE ordering intact (r = 0.977). And the bounds are the point: 12.2 pp median width
   against 2.43 pp median |ATE| means that task's magnitudes are **not identified**, so it is flagged
   out of the calibration slope structurally (`in_slope`), not by a note.
17. **Practice prompts must live in the target's size band.** The target prompt is 9,892 tokens; the
   largest practice task was 44,935 before any policy. A prompt four or five times the target's size
   is a different task, so the budget is 24,000 tokens and the per-arm cap is 12,000 characters (just
   above the target's own longest arm, so the target is provably never truncated). Truncate one arm
   before splitting a task, split into balanced parts before anything else, and never summarise: a
   second model rewriting the stimulus changes the thing being predicted.
18. **A gate that passes on the seed is not a gate.** At 21,600 deposited rows the G6 Tier-2
   moderator residual is **2.487 ± 0.099 pp against a 2.50 tolerance and one seed in five fails**;
   runs 01-03 read single draws of 2.38-2.46 and called it margin. At 43,200 rows it is
   **1.702 ± 0.014**. Before trusting any gate whose statistic is computed from sampled rows, scan
   the seed: the spread, not the draw, is what says whether the tolerance means anything.
   **Confirmed out of sample on the first REAL card** (`20260815-target-01`): finding 12's formula
   `2.462 x sqrt(21,600/n)` predicts **1.741** at 43,200 rows against a measured **1.732** over five
   seeds, an error of 0.5% on a row count and a card it was not fitted on. But the seed SPREAD is
   **±0.038, nearly 3x the ±0.014** measured on a stub card - real subgroup structure varies more
   from seed to seed than scripted values do. The margin to the 2.50 tolerance is still 19 SDs, so
   nothing is at risk; the point is that a spread measured on a stub understates the real one, and it
   is the spread that the whole scan exists to read.
19. **A composite of five institutions is arithmetic, not a haircut.** `inst_trust_mean` had been
   science confidence minus a declared 5 pp. In the same GSS respondents on the same scale,
   confidence in education runs **−17.5 pp** and in the federal executive **−33.1 pp** against the
   scientific community (Pew agrees independently: elected officials 36.6 vs scientists 66.8), so
   even with EPA/NASA/NOAA rated *equal to* the scientific community the five-item mean is 10.1 pp
   below science trust. Compose a composite from its measured components and bracket the component
   nobody measured; do not fit a haircut to it.
20. **A negatively-worded item is not the opposite of a positively-worded one until you check.**
   TISP's distrust items correlate +0.68 with each other, −0.05 with the 12-item trust battery and
   **+0.22 with a positively worded item** — an acquiescence method factor. Anchoring `distrust_post`
   on them would have imported that method variance into a scored level, so it stays declared with
   the evidence attached. Check the correlation with the construct's positive pole before using a
   reverse-worded item as a level.
21. **A published topline can place what no microdata reaches — as a position, never a level.** Pew
   ATP W149's agency battery (Jul 2024, N = 9,424) has no microdata here and no party crosstab, but
   rescaled on the same 4-point map as Pew's own confidence items it puts **NASA at 67.0 — above
   confidence in scientists (66.9) — and EPA at 54.0**, against a same-half-sample DOJ/IRS/DHS cluster
   at 46.9. The three-agency mean is **θ = 0.319** of the way from science to government, bracket
   [0.067, 0.319] over wave × `not sure` treatment, and the midpoint 0.500 that `inst_trust_mean` had
   assumed **lies outside it** (level 50.0 → 52.9). Two bridges were available and the choice was
   forced by finding 14, not by taste: a *level* transfer across item families (favourability vs
   confidence) reads −6.4 pp, a *relative position inside one instrument* reads −10.6 pp, and only the
   second is a form that transfers. The favourability→confidence map itself stays declared because
   W149's 16 agencies and W100/W114's 9 referents **do not intersect** — there is nothing to fit on.
22. **A brief that names its own study cannot test recall — and some names cannot be removed.**
   Assembling the recognition probes found `Strengthening Democracy Challenge` and `BB-PRIME` sitting
   in two adapters' sample descriptions, including the task nominated as the cleanest recall control.
   Those are proper nouns and were deleted; `tools/practice.py` now aborts if an identity key appears
   in any assembled payload. But `voelkel2024`'s **outcome battery is its paper's title**
   (`antidemocratic attitudes`, `partisan animosity`), and that cannot be redacted without changing
   the task — so grading keys are split into `identity_keys` (graded) and `content_keys` (reported,
   never graded), and the clean controls are the two tasks whose briefs force no identifier at all.
23. **Price the batch before asking for it.** Stage 3 at 3 draws with the probe is **23 calls and
   363,443 tokens**; stage 5 adds 1 call and 9,892 input tokens per draw. Input counts are assembled
   payloads, measured; the only estimate is output at 12 tokens/cell. An approval request with a
   number in it is a different conversation from one without.
24. **A parser that has only seen the stub has been tested against the one input it will never
   get.** `ssb.predict.parse` passed every dry run because `stub_completion` emits perfect CSV.
   Built 14 realistic malformed completions from the target's own grid and **8 of them lost all 208
   cells** — a markdown table, a tab or semicolon delimiter, a `pp` or `%` suffix, a trailing
   comment column, sloppy case. `practice.py` aborts on an unparsed cell, which is right and would
   have arrived *after* the batch was paid for. Locating the **outcome** field first, then the
   condition before it and the first number after it, recovers all 14; seven negative controls
   (prose, a refusal, a sentence naming one cell, wrong names, a header alone) still parse to zero,
   and a stub dry run reproduces every scoreboard metric to 0.0. Test the tolerance in both
   directions or it is not tolerance, it is invention.
25. **The path that spends the money was the only one never executed.** Every dry run replaced the
   *predictor* and therefore skipped `subprocess` -> JSON envelope -> `result` -> cache entirely.
   `tools/fake/claude` is argv-compatible with `ssb.predict.command()`, refuses to run without
   `SSB_REHEARSAL=1`, and exits non-zero on a non-empty `--tools`; 40 calls through it establish
   that the frozen argv is accepted, the envelope parses, the cache key is stable across processes
   (a repeat run made **zero** new calls and scored identically), a rehearsal cannot contaminate the
   real cache or the scoreboard (`stub=True`, separate cache dir, the resolved binary hashed into
   `summary.json`), and **`anchor_spread` reads non-zero for the first time** (0.736 pp mean SD) once
   the draws genuinely disagree — its previous 0.00 measured the stub's determinism, not the split.
   Rehearse the call path against a fake before buying the real one.
26. **A validator that checks a field is present has not checked it is true.** `check.R` asserts
   `approach_family` and `models` are non-empty strings, so every deposit through run 07 passed with
   the template's own defaults — **"per-respondent simulation, single model"** and
   **"gpt-4o-mini-2024-07-18"** — describing a pipeline that is analysis-first and never generated a
   respondent, on a model it never called. `zenodo_citation.R` copies `approach_family` into the
   published citation, so it would have shipped. Those two are facts the harness knows and the
   operator does not, so the harness now writes them. Read every field a template hands you and ask
   whether it is true, not whether it passes.
27. **A gate that has never failed has not been shown to stop anything.** Every run to date was
   green, so the red path was untested code. `tools/test_gates.py` exercises seven of them: a failed
   gate and a missing gate both make `verdict.may_finish` False; `tools/target.py` now raises
   `RUN NOT CLOSEABLE` *after* writing every artefact, so evidence survives and the run does not
   close; an invented gate name and a scoreboard row with no `stub` flag are both refused; and the
   RUNBOOK's claim that only `primary|secondary-k` survives the filename check is now measured
   against `make check` (`secondary-2` PASS, `tertiary` FAIL, `primary2` FAIL) instead of asserted.

28. **A bill priced in the wrong tokenizer is not an estimate, it is a different number.** The first
   paid batch was approved at 401,282 tokens and billed **941,504** — 2.436x — and the guard that
   caught it was a human reading a total after the fact. Two multiplicative causes, both now measured
   on 12 real completions rather than assumed: `ssb.predict.n_tokens` is tiktoken cl100k, a proxy
   that reads **1.574x** low against Anthropic's tokenizer (range 1.513-1.598), and `claude -p` makes
   a **second billed pass** over the same prompt with `claude-haiku-4-5` worth **+73.2%** of context
   (range 71.0-76.2%), visible only in `payload.modelUsage` and invisible in `usage`. Output was 19
   tokens a cell, not 12. Re-priced, the same batch estimated **944,474** against an actual
   **941,504** — **0.3% error**. `tools/practice.py` now carries a ledger that adds each paid call's
   measured `modelUsage` total, counts cache hits as already-paid, and refuses to start the call that
   would cross `--max-billed-tokens`; `tools/target.py` imports the same factors, so the stage that
   makes the product cannot be priced in different units from the stage that was approved. Re-measure
   both factors when the model or the CLI version changes; both are recorded in `summary.json`.

29. **This predictor compresses; it does not exaggerate — and its error is bias, not variance.**
   The documented LLM failure mode is beta < 1. Measured on 1,101 cells over five tasks, **every task's
   beta is above 1** (1.11 to 1.90, pooled 1.42): human effects are 1.4-1.8x *larger* than predicted.
   Standing finding 3's structure holds — ordering and magnitude are separate skills — with its sign
   reversed. And the magnitude half is barely worth correcting: leave-one-task-out, the fitted
   multiplier buys **+0.008 pp of RMSE** over five folds (+0.136 pp climate-only, 3 wins of 4)
   against 2.6 pp of error, because lambda itself ranges 1.33-1.79 across folds. The depositable
   slope is **1.521**: the climate-only 1.790 readmits two structurally excluded tasks and is a
   diagnostic only, which surfaced only when a `--lambda-policy climate` was implemented and
   returned 1.5212 — respecting the exclusions, the only non-climate task is already out as
   RECOGNISED, so climate-only and pooled are the same 498 pairs. Meanwhile three
   independent draws disagree by **0.077-0.151 pp per cell** — twenty times smaller than the error.
   A panel cannot average away what is not noise: buy a *different* model before buying more draws.

30. **Naming a paper is not knowing its effect table.** Two of five practice tasks were recognised
   from the brief alone, by title and author list, at self-reported confidence 82 and 93. The pooled
   comparison says recall inflates everything (rho +0.807 recognised against +0.553) and the pooled
   comparison is confounded by pooling: **within task the two recalled tasks hold the lowest two
   Spearman values of the five**, and pooled they are *worse* on `pearson_r_within_outcomes`
   (0.388 vs 0.433) — the row defined to strip generic outcome knowledge — worse on RMSE and worse
   calibrated. `vlasceanu2024`'s 0.973 directional agreement is 93.3% of its human ATEs being
   positive, not recall: the all-positive baseline scores 0.933 on it. Whatever recall exists lives
   in the outcome fixed effects. Grade a recall probe against the *within-outcome* row, never the
   pooled one, and keep the pre-registered exclusion anyway — a rule reversed after seeing the result
   is not a rule.

31. **Never `pkill -f` a pattern that can appear in your own argv.** Stopping the first paid batch
   with `pkill -f "tools/practice.py"` sent SIGTERM to the agent itself, because this agent's command
   line contains the task brief and the brief names the tool. Record the batch PID at launch
   (`runs/_locks/practice.pid`) and kill that PID. A stop that also kills the thing doing the
   stopping is not a stop.

32. **A fallback that works is indistinguishable from a feature that works.** `fit_calibration(by=
   "family")` and `apply_calibration(family_of=FAMILY)` read as per-family calibration and were inert
   for every run to date: `pairs.csv`'s `family` column holds `practice_<task>`, so the lookup for
   `trust`/`policy`/`belief`/`behaviour` missed every time and all 208 cells quietly took `_pooled`.
   Nothing failed. Measured before fixing, against a family map frozen *before* any family slope was
   fitted (`inputs/outcome_families.json`): only **592 of 1,101 practice cells share a construct with
   any target family**, and a real per-family map is **worse than pooled on 3 of 4 held-out climate
   tasks (+0.197 pp RMSE)**. So the fallback was right and the silence was not: `target.py` now
   records `_applied_per_outcome` and prints it, and `tools/test_calibration.py` asserts the collapse
   is detectable, that a real family map *does* bite, that a null stays null, and that `in_slope` is
   respected with 200 contradictory rows present. When a lookup can miss, log which branch it took.

33. **The practice loop cannot calibrate the outcome the study is about, and the mounted data
   cannot fix it.** Zero of 1,101 scored practice cells fall in the target's `trust` family — four of
   its thirteen outcomes and the entire point of the megastudy. Every practice task measures belief,
   policy, behaviour or democracy. So any magnitude correction applied to a trust ATE is a
   cross-family extrapolation with no in-family evidence, which is the move findings 14 and 21
   already showed does not transfer for levels or for stretches. Both candidates for a sixth task
   were then checked and both are **NOT CARVABLE** (`notes/DATA_GLIGORIC.md`,
   `notes/DATA_GATEWAYBELIEF.md`): gligoric2025 has verbatim message texts and a trust battery but is
   a published null whose ATE table is indistinguishable from zero (finding 36), and its randomised
   sample is conservatives only — a QSF branch routes every liberal to control, so no ideology
   contrast is estimable at all; gatewaybelief has no trust outcome in any of its three studies
   (perceived scientific *consensus* is not trust — counting it would be the finding-9/20 error) and
   ships no stimulus texts on disk. So the extrapolation cannot be closed by measurement here, and
   admitting it in writing is the only honest option left. Taken, in OPEN item 18.

34. **The under-dispersion the frozen table warns about was in the predictions, not in the rows.**
   `beta = r * sd_human/sd_pred` is an identity, and it reproduces every fitted slope here exactly —
   so beta > 1 is not a second phenomenon, it IS under-dispersion. Measured: the predicted ATE spread
   is **0.23-0.46 of the human spread** (pooled **0.427**, a variance ratio of 0.18), because the
   predictor emits only **22-38 distinct values across 90-408 cells**, all on a 0.10 pp grid, with the
   modal value taking 8-14% of them. It ranks on a coarse ladder rather than estimating magnitudes.
   Three runs engineered the variance ratio to 0.992-1.006 **at the respondent level inside a cell**,
   which is where the Tier-1 row reads it, and nobody had looked at the dispersion of the predicted
   effects. Two multipliers are defensible and they differ: **2.34** matches the spread and makes RMSE
   worse; **1.42** (the fitted beta) minimises squared error and drives the Section-2 row to
   alpha = 0, beta = 1.05 while leaving the spread at 0.65 of human. The frozen table wants beta = 1
   in the REGRESSION sense, so the fitted slope is the target and matching the spread is not.
   **beta = 1 does not mean matched spread**; the missing 35% is r, and no scalar recovers it.

35. **A one-rule leak audit would have missed a verbatim copy of the sealed file.** First run on real
   transcripts rather than the stub: echo rates 0.033-0.085 against shift-nulls of 0.038-0.060, excess
   -0.016 to +0.027, z -1.17 to +2.09 — five CLEAN with two orders of magnitude of margin, and the
   null is doing exactly the job finding 13 built it for. But the positive control on `voelkel2026`,
   the smallest task, scores **z = 6.9 against a z > 8 rule** and is caught only by the excess > 0.25
   rule. On a small task the null's own spread is wide enough to hide a total leak from the z-test.
   Keep both rules, and keep the positive control that made the gap visible.

36. **Ask whether a task has any signal BEFORE carving it, not after paying to predict it.**
   `var(observed ATEs) = var(true effects) + mean(SE^2)`, so `var(true) = var(obs) - mean(SE^2)` is
   computable from `sealed/truth.csv` alone with no model call — and its square root over
   `sd(observed)` is **exactly the denominator the frozen `r_adj` row already divides by**, verified
   to 0.00000 on all five carved tasks. `tools/task_power.py` prints it. The five tasks in hand run
   `var_signal` 0.96-7.55 with a **ceiling on attainable r of 0.681-0.931**; gligoric2025's best
   40-cell table would have run **var_signal = -0.994**, a negative signal variance and a ceiling of
   zero. Every Section-1 metric on it would have had chance expectation however good the predictor
   was, and its 40 noise cells would have dragged `fit_calibration`'s pooled slope toward zero — the
   exact opposite of the correction finding 29 established. A task whose attainable-r ceiling is
   below the harness's own r is not a test of the harness.

37. **Two recon children answered in one pass what a batch would have answered for a million
   tokens.** `AGENTS.md` allows `rlm()` children for dataset reconnaissance and forbids them
   predictions; both rules earned their keep here. The children read 7,800 x 82 microdata, a 275-element
   QSF, five undocumented R scripts and 12 unlabelled columns, and came back with structural facts
   neither standing finding had: that gligoric2025 randomises **two** factors (message x referent),
   which is why findings 5 and 15 could both be right about it and appear to contradict; and that a
   branch in its instrument makes the randomised sample conservatives-only. Send a child at a
   dataset question; never at a prediction.

38. **The recognition probe was pointed at the training tasks and never at the target, where it is
   a different instrument.** On a practice task it measures recall and discounts a calibration slope
   (OPEN item 3). On the target the identical call is a **blinding check** against the frozen file's
   absolute rule — never ingest or infer from the target's human outcome data, its pilots or
   preprints, and if you encounter any, stop and tell the operator. Nothing in eight runs had ever
   asked the predictor whether it already knew the answer, because the probe was filed under recall
   rather than under blinding. `tools/target.py` now runs stage 5a before stage 5 and a
   `RESULTS_KNOWN: YES` raises `BLINDING EVENT` and aborts **before any prediction call**; the red
   path is asserted in `tools/test_gates.py` (abort after exactly 1 probe call and 0 prediction
   calls). It costs 27,463 billed tokens, 2.6% of a complete run. When the same instrument is
   pointed at a different target, ask what it measures there before assuming it measures nothing.

39. **A budget guard that stops after the ceiling has already been crossed is a report, not a
   guard.** The first version compared spend-so-far against the ceiling and let the next call run
   whatever its size: on `tools/fake/claude` a 60,000 ceiling ran to **74,574** before stopping. It
   now estimates the call it is about to make from the measured factors and refuses the one that
   would not fit, so the ceiling is never crossed rather than merely detected. Both properties -
   headroom reservation, and cache hits counting as already-paid money so the ceiling governs the
   BATCH and not the session - are red-path tested.

40. **A simulation is not evidence when the thing can be measured — and measuring it corrected two
   published claims.** `tools/forecast_target.py` estimates what a target score will look like given
   that the target is scored against ONE HALF of the human sample while every practice score was
   measured against a full sample. `tools/split_half.py` measures the same gap on real respondents:
   recompute each task's ATE table on two random halves (12 splits), score the already-paid
   predictions against half 1, score half 2 against half 1 for an empirical ceiling. Two corrections
   followed. (a) **Halving the reference is cheap**: dir -0.028, rho -0.073, RMSE +0.32 pp. The much
   larger drop the simulation predicted comes from ASSUMING smaller true effects on the target, which
   is a separate and unmeasured claim; the two must not be quoted as one. (b) **"A shrunk prediction
   beats a noisy replicate on RMSE" is conditional, not general** - it holds on 2 of 5 tasks, and
   `corr(noise/signal, our RMSE margin over the ceiling) = +0.861`. Where the human reference is
   precise the replicate wins and under-dispersion is a liability; where it is noisy, shrinkage wins.
   The target sits at the noisy end (`SE^2/tau_sd^2` = 11.1 at 0.5 pp effects, 0.36 at 2.76), so the
   conclusion survives there - because of the target's noise level, not as a property of the world.

41. **Do not fix the under-dispersion.** Finding 34 measured it (predicted ATE spread 0.427 of human)
   and argued from theory that correcting it would cost RMSE. Tested leave-one-task-out on the paid
   pairs, because "match the human distribution" is the obvious-looking improvement a later session
   re-invents: all rank-preserving transforms leave Spearman and directional agreement **identical**,
   so only RMSE moves, and matching the human SPREAD costs **+0.39 pp** while quantile-mapping onto
   the human SHAPE costs **+1.01 pp and loses on 5 of 5 folds**. Only the fitted OLS slope helps, by
   0.007 pp. Against a reference this noisy, under-dispersion IS the RMSE-optimal response to r < 1.
   `tools/calibration_variants.py` reruns it in a second. The Tier-1 variance-ratio row is about
   respondent-level spread inside a cell and is a different quantity; do not conflate them.

42. **The stopping rule was a comparison without an interval.** `AGENTS.md` stops a run on "beats
   the no-effect floor AND the all-positive baseline on the same task", and every number in that
   comparison was a point estimate over cells - finding 18's mistake in a second place, six runs
   later, because the lesson had been filed under gates rather than under statistics. `tools/margin_ci.py`
   bootstraps it, clustering on the **arm** and not the cell: a message's effects across 9-24 outcomes
   share whatever the predictor got right about that message, so a cell bootstrap reports intervals
   that are far too narrow. The verdict survives - every margin over the no-effect floor excludes
   zero on 5 of 5 tasks on both metrics, and the RMSE margin over the all-positive baseline excludes
   zero on 5 of 5 - and it survives with two honest qualifications the point estimates hid: the
   directional margin over all-positive is an **exact 0.000 in every resample** on the two tasks
   where the predictor itself predicted all-positive, and `vlasceanu2024`'s r-within-outcomes is
   +0.342 [+0.021, +0.662], the one row on the board that is barely distinguishable from nothing.
   Quote a margin with its interval or do not quote it as a win.

43. **The three-draw panel bought nothing, and it was 54% of the batch.** Finding 29 argued from a
   dispersion (draws disagree by 0.077-0.151 pp against 2.6 pp of error). `tools/draws_value.py`
   measures the thing itself, scoring every single draw the way the scoreboard scores the panel:
   one draw gives dir 0.7873 / rho +0.4503 / RMSE 2.4469, the deposited 3-draw median gives
   0.7871 / +0.4544 / **2.4482** - the median is fractionally WORSE on RMSE. The two extra draws cost
   **507,936 billed tokens**. The consequence is a better design at a lower price, not a saving:
   **two models at one draw each costs 873,074 against the 944,474 already spent on one model at
   three**, so a second panel member is not a purchase to justify, it is the cheaper option that also
   attacks bias instead of variance. Aggregate over models, not over draws of one model.

44. **The per-arm cap is 866 characters from silently rewriting the target's stimulus.** Finding 17
   set a 12,000-char cap and said it sits "just above the target's own longest arm, so the target is
   provably never truncated". True, and the margin is one edit wide: the longest target arm is
   **11,134 chars, 92.8% of the cap**. A re-extraction that adds whitespace would cross it and the
   only symptom would be a slightly better score against a stimulus no respondent saw. `target.py`
   now aborts on any truncated target arm and on any split of the target brief; the red path is
   forced and asserted in `tools/test_gates.py`. The cost of the policy on PRACTICE was also measured
   for the first time - 9 truncated arms score dir 0.644 / 1.676 pp against 34 untruncated at
   0.685 / 1.492 - but truncated arms are the longest arms and length predicts difficulty among
   untruncated arms too (corr +0.189 with absolute error), so at n = 9 the two are not separable and
   no separation is claimed. A policy that shapes every prompt should have its cost measured, and
   where it cannot be measured cleanly, that should be said.

45. **The run recorded the frozen file's hash and the spec's, and nothing about what the prompts
   were made of.** `inputs/` - 42 files, 6.6 MB of stimuli, adapters, texts, profile pool, baselines
   and format parameters - determines every prompt and every deposited baseline, and no run recorded
   its state. The cache gave partial cover, since a changed input changes the cache key, but the
   symptom of that is a silent extra CALL rather than a warning, and two scoreboard rows built from
   different inputs compared as if they were the same experiment. `tools/inputs_manifest.py` writes
   and verifies a per-file sha256 manifest plus one tree digest, exits non-zero on drift (proved by
   flipping one byte in `format_params.json`), and both spending tools now record the digest as
   `params.inputs_sha256`. Run 20260815-practice-01's digest was added retroactively and the addition
   is justified rather than assumed: reassembling all 23 payloads after the batch reproduced all 23
   cache keys, and a cache key covers the full prompt, so the inputs are provably the ones that built
   what was paid for.

46. **The file that measures improvement held numbers no artefact could reproduce.** `AGENTS.md`
   says "Improvement is a query over that file", and nothing had ever checked that a scoreboard row
   follows from the run's own `pairs.csv`. `tools/verify_scoreboard.py` recomputes all 13 metrics for
   every row from the stored pairs: **the five paid rows reproduce to 4.4e-16**, and 130 historical
   metrics on stub rows do not. The cause is not a scoring bug, it is that **`run_id` was never
   unique**: `new_run` does `mkdir(exist_ok=True)`, so re-executing into an existing id overwrites
   `stages/calibration/pairs.csv` while the scoreboard keeps the OLD rows.
   `20260815-rehearsal-03` carries ten rows for five tasks with disagreeing `in_slope` flags and one
   pairs.csv. `ssb.gates.scoreboard_append` now refuses a duplicate `(run_id, task_id)`; the
   historical rows are LEFT in place, because deleting another session's evidence is worse than
   carrying a documented defect, and the tool gates on `stub=False` rows only - a stub row is
   explicitly not a score. **This session resumed into an existing `run_id` on purpose** and it was
   safe only because the crashed session had appended nothing; that is luck, and it is now a guard.

47. **Deleting a run directory orphans its scoreboard row.** Nine rows from rehearsal runs created
   and removed while testing this session pointed at directories that no longer existed, so nothing
   could verify them. They were removed (all `stub=True`, verified before deleting, backup at
   `runs/scoreboard.csv.bak-preclean`) and `verify_scoreboard.py` now reports unverifiable rows as a
   category. Clean up a run and its row together, or leave both.

48. **Two frontier model lines given the same brief make the same errors, so a panel averages
   nothing.** Finding 43 said "aggregate over models, not over draws of one model" and priced a
   second model as the cheaper option that attacks bias. Bought: `claude-fable-5`, one draw of all
   five practice tasks plus its own probes, 453,231 billed. The two-model panel beats the better
   single model by **-0.0005 directional, +0.0038 rho, +0.0024 pp RMSE** - to three decimals the
   same nothing the two extra draws bought. The diagnostic that explains it must be read carefully:
   `corr(err1, err2) = +0.970` is an ARTEFACT, because `e = pred - human` for both and `var(human)`
   dominates, forcing the correlation toward 1 by construction. The honest number is
   `corr(pred_opus, pred_fable) = **+0.889**` (+0.690 to +0.934 by task). **The bias finding 29
   found lives in the task, not in the model.** Only `pearson_r_within_outcomes` moves, and only
   against the incumbent: panel - `claude-opus-5` is **+0.0376 [+0.0026, +0.0690]** (2,000-resample
   cluster bootstrap on the arm, excludes zero) while panel - `claude-fable-5`, the better member, is
   **+0.0114 [-0.0128, +0.0435]** (includes zero). That is not aggregation working; it is fable-5
   being better on that one row. **When a panel beats the incumbent but not its own best member, the
   indicated action is model SELECTION, not aggregation** - and it costs one draw instead of two.
   Correct finding 43's recommendation: buy neither. `tools/models_value.py` reruns all of it.
   And recognition is a property of the MODEL, not the brief - fable-5 recognised three tasks to
   opus-5's two.

49. **A scalar calibration policy cannot move four of the six Section-1 rows, which is most of what
   OPEN 18 was arguing about.** Both cards were built off the same four cached target calls (the
   comparison the operator approved, and it cost 0 tokens). A positive scalar multiple is rank- and
   sign-preserving, so Spearman between the unshrunk and x1.5212 cards is **1.000** and directional
   agreement, Spearman, Pearson r and Pearson r within outcomes are **numerically identical**. Lambda
   moves RMSE/RMSE_adj and the Section-2 slope, and nothing else. Two runs of argument treated it as
   governing the entry. Before agonising over a transform, check which scoring rows it is even
   capable of changing.

50. **The fitted slope was fitted where the predictor undershot; on trust it already overshoots.**
   Practice beta is 1.11-1.90 on five tasks, never below 1, so the correction says "multiply up". But
   the target's trust cells come out at +1.0 to +3.0 pp against finding 5's randomised band of
   -0.22 to +0.83 pp - already ~3x high unshrunk, and 32 of 64 trust cells above 2 pp before any
   multiplier. Applying 1.5212 takes that to 52 of 64 and a +4.56 pp maximum, and
   `tools/forecast_target.py` says it COSTS RMSE at those effect sizes (1.74 -> 1.84 at 0.5 pp).
   A correction fitted on families where the error has one sign must not be applied to a family
   where the evidence says it has the other - and finding 33 already established there is no
   in-family evidence to check against. The unshrunk card is the primary candidate; the shrunk one
   is retained, complete and gate-green, as the sensitivity.

51. **The estimator's first test on a model it was not measured on cost 3.8%.** The billed-token
   factors of finding 28 (tokenizer 1.574x, CLI second pass +73.2%, 19 output tokens/cell) were
   measured on `claude-opus-5`. Stage 5 on the same model landed at **+1.0%** (123,276 against
   122,061); the same estimator on `claude-fable-5` landed at **+3.8%** (453,231 against 436,538).
   The gap is answer length, not tokenization - a different model writes a slightly longer CSV.
   Carry a ceiling around 1.5x when pricing a model the factors were not measured on, and re-measure
   the output rate per model rather than per CLI version.

52. **A margin has two names in it and I only wrote one down.** Standing finding 42 established that
   a margin is quoted with an interval; this is the other half. The two-model bootstrap of finding 48
   was run as `panel - incumbent` and read against the point estimate of `panel - best member`
   (+0.0376 against +0.0114), and the 3x gap was written up as a *bias in the bootstrap*, complete
   with a plausible mechanism about `pearson_r_within_outcomes` demeaning by outcome and resampling
   arms disturbing it. The mechanism was invented to explain an artefact of my own bookkeeping: the
   bootstrap mean matches its point estimate to three decimals on all five contrasts. It surfaced
   only when the ad-hoc notebook calculation was rewritten as `tools/models_value.py` and the tool
   printed the contrast it was actually computing. Two rules follow. **Name both ends of every
   margin** - "panel - first model" is not "panel - best model", and against a two-member panel they
   differ by a factor of three. And **a plausible mechanism is not evidence**: before explaining a
   discrepancy, check that the two numbers are measuring the same thing. Every other standing finding
   here has a tool that reruns it in seconds; this one did not, for about an hour, and that is
   exactly how long the error lived.

53. **The card predicts zero treatment-effect moderation, and that is very close to the best
   available prediction — but the first two attempts to check it both gave the wrong answer.**
   Section 3 of the frozen table (Tiers 1-2) scores Section-1 metrics minus RMSE on condition x
   moderator interactions, and nothing had ever looked at what the harness submits there.
   `card/subgroup.csv` has **no condition column**: it holds 351 moderator x level x outcome LEVEL
   offsets (finding 11) and no interaction, so `submission_T2`'s 5,616 moderator cells reconstruct an
   interaction of **exactly 0.0000000000 pp** and Tier 1 carries only synthesis noise (SD 1.358 pp).
   The practice loop never tested it either: **0 of 1,101 scored cells were moderation cells**, the
   same structural blindness as finding 33's trust family but covering a whole scored section.
   Then the checking went wrong twice. Finding 36's analytic test
   (`var_true = var_obs - mean(SE^2)`) needs the noise variance of `ATE_level - ATE_overall`, whose
   two terms are CORRELATED; assuming independence says 3 of 21 task x moderator combinations are
   detectable, assuming an equal-weight decomposition says **18 of 21** at ceilings of 0.28-0.57, and
   neither weighting reproduces `ATE_overall` exactly because the level ATEs use level-specific
   controls. **A conclusion that flips on an unverified weighting assumption is not a measurement.**
   Finding 40's rule settles it: split-half replication on the respondents themselves. Interactions
   replicate at **r = +0.024** (range -0.157 to +0.210, 0 of 21 above 0.25) while MAIN EFFECTS on the
   very same splits, respondents and code replicate at **+0.596**. There is no moderation signal to
   predict at 4,000-20,000 respondents, so the exact zero is near-optimal, Section 3 is at chance for
   any entrant, and **no batch should be bought to predict moderation**. `tools/moderation_power.py`
   runs both the analytic trap and the empirical arbiter, side by side, on purpose.

54. **The subgroup offsets are each anchored on real data and their JOINT strength was never
   checked.** Finding 11 anchored 351 of 351 subgroup cells and that made every offset defensible
   one at a time; the frozen table's "Demographic predictability" row asks a different question -
   `R^2` of outcomes on moderators, "does the synthetic data exaggerate group differences relative to
   humans?" - and nothing had computed it. Pooled and uncontrolled it reads **0.191 synthetic against
   0.061 human, a 3.2x exaggeration**, and that number is meaningless: `R^2` rises mechanically with
   the number of dummies (the deposit carries 6 moderators, the datasets 2-5) and predictability is a
   property of the CONSTRUCT (climate attitudes are party-polarised, democracy and emotion outcomes
   are not). Matched moderator sets and adjusted `R^2`, per moderator:
   **party 0.1354 deposited against 0.1431 in the one climate dataset (0.95x) and 0.011-0.020 in the
   non-climate ones (6.7x)** - party IS the whole signal and the deposit sits at the climate level,
   which is the target's construct. gender 0.94x, race 0.84x, age_band 1.45x against the same climate
   reference. **The two exceptions are education (0.0213, 2.4-8.9x every human value) and income
   (0.0125, 3.2x), and neither has a climate reference anywhere in the mounted data** - the only
   datasets carrying them measure democracy, emotion and psychological distance. Both are anchored on
   real Pew W114 cuts, so this is an unresolved risk of exactly finding 33's shape and not a proven
   error; it is recorded in OPEN item 21 rather than fixed, because fixing it after seeing the target
   predictions would be choosing an input from an output. `tools/demographic_predictability.py`.
   The other two demographic rows pass on the same deposit and corroborate on different statistics:
   the **parity gap** (worst minus best group) sits at **0.79-1.15x** the climate reference on party,
   race, age and gender, and the **demographic baseline** reproduces card level + offset with a
   z-spread of **0.832** against the 1.0 that pure sampling noise gives, its RMSE falling 2.79 -> 0.77
   pp as cells grow - finding 12's thin-cell noise, measured on the real deposit rather than argued.

55. **"Operator-owned" was doing the same work "template default" did in finding 26.** `check.R`
   warns about `registration.md` and the harness had filed all of its ~39 items as the operator's,
   which is the same reflex that let `approach_family` and `models` sit at the template's false
   defaults through seven deposits. Read the form and **32 of 39 items are facts only the harness
   knows**, each with an artefact behind it: the exact model and the resolved binary's sha256, that
   sampling was provider-default with `MAX_THINKING_TOKENS=0`, that there is no fine-tuning, no
   retrieval, no web search, no tool use and no agent scaffold, that **no persona was ever verbalised
   to a model** because the approach is analysis-first, that the aggregation rule is a cell-wise
   median of 3 draws, that the fitted multiplier was 1.5212 on 498 in-slope pairs and under the
   deposited policy **was not applied**, that the blinding probe ran before any prediction call and
   returned CLEAN, and that the pipeline cost 1,064,780 billed tokens with a further 453,231 on
   selection experiments outside the submitted pipeline. Genuinely operator-owned: 7 - team,
   contact, competing interests, the signed blinding attestation, the contamination note, the repo
   DOI and the disclosure class. `tools/fill_registration.py` writes the filled draft to
   `runs/<id>/registration_draft.md`, cites a source file on every item, writes
   `OPERATOR - <what is needed>` where the harness does not know, and **never touches the deposit's
   own `registration.md`** - all three tiers still hash identical to the template, because copying
   it in is an operator act. Two rules generalise. **A form is an attestation: a plausible value
   invented to fill a blank is worse than the blank.** And when a template hands you a field, ask
   not only whether its default is true (finding 26) but whether you are the one who knows the
   answer.

56. **`make check` PASS WITH WARNINGS was hiding three more placeholders and one unaffirmed
   attestation.** The three standing warnings (`registration.md`, `code_repository`,
   `.zenodo.json` creators) had been treated as the complete list of what the operator still owed.
   Diffing the deposit's `metadata.json` against the benchmark template's finds **three more fields
   still at their template values that the validator passes GREEN**: `team_name` is
   `"Example Team (replace me)"`, `contact` is `"name@institution.edu"`, and `abstract` is empty and
   **not tested at all**. The cause is that `check.R` validates these inconsistently - `team_id` is
   checked against the example and `.zenodo.json` creators against `'Lastname, Firstname'`, but
   `team_name` and `contact` are only checked for PRESENCE, and presence is not identity.
   **The serious one is `blinding_attestation`.** It reads `true`, `check.R` asserts
   `blinding_attestation == true`, and it ships pre-set to `true` in the template - so the validator
   cannot distinguish an affirmation from a default, on the field carrying the study's absolute
   blinding rule. It is an assertion about **human** conduct ("no team member accessed... any human
   outcome data") and no harness has standing to make it, which is why the generated registration
   draft correctly marks I.3 `OPERATOR` - leaving the deposit asserting an attestation its own
   registration form leaves unsigned. Not flipped to `false` (the pipeline IS blinded, and the probe
   returned CLEAN before any prediction call); surfaced instead. `tools/verify_deposit.py` now
   reports every field still identical to the template as operator-pending, treats
   `blinding_attestation` explicitly, and separates two verdicts - **HARNESS-VERIFIED** (exit 0, the
   harness's own work is correct) from **DEPOSIT READY** (`--strict`, exit 1 while any operator item
   is outstanding). A validator's green is evidence about the validator, not about the field.

57. **Three tiers can silently submit three different predictions of the same 208 quantities, and
   nothing checked that they agree.** Each tier is scored separately, so a drift between them costs
   twice and is invisible to `check.R`, which validates each file's shape and never compares them.
   Measured: Tier 3's ATEs equal Tier 2's cell differences and the card to
   **0.0000000000 pp on all 208**, and the Tier-1 rows reproduce them to 0.0167 pp (the
   `newsletter_signup` 0/1 discretisation, 10 signups in 2,400 rows against a 0.004 target). The
   same pass checked the frozen file's **composite rule** - `trust_multidimensional` against its 12
   items, consistent to **0.000000 across all 43,200 rows**, with the items heaped and the composite
   not, which is finding 2 visible in the file. **Correction, made by reading `check.R` instead of
   assuming what it does:** the composite check was NOT a gap - the validator already runs it
   (`[ok] trust_multidimensional consistent with items`), so that half of this finding duplicated
   existing cover and was written up as novel before the report was read. What `check.R` genuinely
   does not do: compare files ACROSS tiers (it runs per repo), and **range-check the eleven 0-100
   sliders** - it bounds `donation_ams` to [0,10] and `newsletter_signup` to binary and leaves the
   sliders unbounded. The deposit is clean on all eleven (0 values outside [0,100]) and both checks
   are now in `tools/verify_deposit.py` with red paths (a composite pushed 3 pp off its items, a
   Tier-3 cell moved 0.4 pp off Tier 2, a slider pushed to 105 - all caught, exit 1). Two lessons:
   a rule in the scoring table that has never been tested against the artefact is not known to hold,
   however obviously it ought to - and **before claiming a validator misses something, read the
   validator**, because "nothing checks this" is itself a claim with a denominator (finding 52).

58. **The registration form requires the raw model logs to be DEPOSITED, and they were only ever
   saved.** K.2: "complete unprocessed model responses archived, hashed, time-stamped (required for
   Tiers 1-2, public or escrowed; oversized logs may be a separate linked Zenodo upload)". Every
   prompt, completion and provider envelope existed under `runs/<id>/stages/target/` and none of it
   was in the submission repo or in any depositable form. The tempting home is wrong too:
   `raw_data_deposit/` is the **Qualtrics-export path** for pipelines that produce a simulated
   survey export, so an analysis-first pipeline correctly leaves it empty and the shipped
   `example_raw_export.csv` is correctly deleted - the logs are not that.
   `tools/stage_raw_logs.py` assembles `runs/<id>/raw_model_logs/`: 4 prompts, 4 unprocessed
   completions, the 4 provider JSON envelopes (model id, billed usage, timing) keyed to
   `spend.json`'s own call keys, a `MANIFEST.sha256` that verifies under plain `sha256sum -c`, and a
   README. **And it replays**: parsing the three completions and taking the cell-wise median
   reproduces the deposited effect table to **0.0000000000 pp on all 208 cells**, then native units
   reproduce the card and the card reproduces all three tiers - so the chain
   `completions -> parse -> median -> native -> card -> Tier 1/2/3` is checkable end to end by a
   third party. **A log archive nobody can replay is an assertion, not evidence**, which is why the
   staging tool runs the replay itself and prints the residual. Staged, never deposited: the
   `make check`-verified submission directories are untouched, and K.2 explicitly allows either an
   in-repo copy or a separate linked Zenodo record - both operator acts.

59. **The deposited ranking of the 16 messages is substantially explained by how long each message
   is.** Section 1 scores Spearman rho on the ordering of the interventions, and nothing had ever
   asked what that ordering is made of. Measured on the deposited card: predicted mean effect
   against stimulus word count is **Spearman +0.726, 95% CI [+0.391, +0.884]** over arms, unchanged
   at +0.725 when the 1,628-word outlier is dropped, +0.599 as a Pearson on log(words). That is at
   the top of the predictor's own range - across the five practice tasks its length correlation
   averages **+0.294**. **But length is not automatically a bug**, because longer messages carry more
   arguments and humans may reward that too, so the test is the human side, which practice has:
   humans average **+0.106**, so the predictor over-weights length by **+0.188** and does so on
   **3 of 5** tasks. The two exceptions matter - on `voelkel2026` humans leaned on length MORE than
   the predictor (0.697 against 0.511) - and the human length-correlation ON THE TARGET is sealed
   and unknown, so this is a flag with an interval, not a defect. Recorded and NOT acted on: editing
   a deposited prediction because a harness diagnostic looked bad is choosing an output from a
   diagnostic, and RUNBOOK section 2a fixes the pipeline before the predictions are seen. The
   concrete experiment it suggests for a later session is a **length-controlled prompt** - the same
   arms padded or trimmed to a common length - which would separate "more argument" from "more
   text". `tools/length_bias.py`.

60. **The ordering's length dependence is in the messages, not in the prompt — and the only prompt
   that moved it moved it the wrong way.** Finding 59 flagged that the deposited card's ranking of
   the 16 messages tracks word count (Spearman +0.726) and named the experiment; it was
   pre-registered (`runs/_lenexp/PREREG.md`, written before any call) and run: five prompt variants,
   20 paid calls, **670,781 billed against a 669,143 estimate (0.25% error)**. The base arm is free
   and exactly matched — the identity transform reproduces `20260815-practice-01`'s draw-0 prompts
   **byte for byte**, so every base call is a cache hit — and the noise floor is measured rather
   than assumed: three already-paid draws of the SAME prompt move the pooled length gap by
   **SD 0.036**. Results. **Telling the model that length is only weakly related to effect size
   (rank correlation ~+0.1, the harness's own measured human value) does nothing**: Δgap
   **−0.027 [−0.155, +0.103]**, smaller than the untreated draw-to-draw SD, at Δρ +0.002.
   **Handing it each message's word count is worse than nothing**: Δgap −0.053 (CI crosses 0) bought
   with **Δρ −0.031 [−0.054, −0.012]** and ΔRMSE **+0.046 [+0.027, +0.063] pp**, both excluding zero
   at ~5 SD of the draw null — making length salient degrades the prediction. **Equalising the
   presented length does collapse the correlation** (L_pred +0.399 → +0.067) **but so does trimming
   the same total words proportionally** (+0.191), and the difference between them — the only
   contrast that isolates surface length, because both arms cut the same word budget in the same
   way — is **−0.124 [−0.328, +0.069]**, not distinguishable from zero, while both lose ρ (−0.091,
   −0.072) and r-within-outcomes (−0.136, −0.116). **Length correlation and predictive skill fall
   together when content is deleted**, which is the signature of length as a proxy for argument, not
   a surface cue. The target was therefore not touched — and could not have been by the trimming
   arms anyway, since its stimuli may never be trimmed (finding 44), which is why the only variant
   ever eligible to become a card was the instruction. What this is NOT: proof of no effect. The
   instruction arm's interval still admits a 0.155 reduction, the same order as the +0.165 gap to be
   removed. That interval is clustered on the **arm**, so it narrows with more ARMS — more carved
   tasks — and not with more draws; a second draw of the same five tasks would have bought almost
   nothing, which is finding 43 in a second place. `tools/length_variants.py` (the treatments),
   `tools/practice.py --variant` (the single seam: the brief is transformed before `plan_prompts`
   and nothing downstream changes), `tools/length_experiment.py` (the scoring and the verdict).
   Three post-hoc attacks on the null, all on already-paid data (`tools/length_robustness.py`), and
   the first is the one that settles the mechanism. **(a) The length correlation belongs to the
   messages, not to the model**: the second model line bought in session 6 (`claude-fable-5`) ranks
   the five tasks by length-dependence at **+0.985** against `claude-opus-5`, pooled gap +0.109
   against +0.165 — two independent models making the same length-dependence, which is finding 48's
   `corr(pred_opus, pred_fable) = +0.889` showing up in a second statistic. **(b)** The null is not
   an artefact of the pre-registered statistic: six alternative definitions (Pearson on log words,
   Kendall, drop-longest-arm, mean |ATE|, per-outcome averaging) leave the debias arms within
   [−0.068, +0.013] and the trimming arms large, with `eqlen` the bigger of the pair on all six.
   **(c)** The "more arms, not more draws" claim is now measured rather than asserted: bootstrap
   half-width = **1.10 x n^-0.506** over all 31 task subsets, so the arm IS the effective unit,
   81 arms buys ±0.128, **114 arms buys ±0.10** (one more mid-sized task) and ±0.05 needs ~447 and
   is out of reach. Finally, a bookkeeping fix in the same pass: the tool printed the bootstrap MEAN
   where the rule is stated on the POINT estimate, and for a correlation those differ (−0.020 vs
   −0.027 here). Both are now printed side by side and the rule reads the point estimate — finding
   52's "name both ends of every margin", applied to the same tool that was measuring it.

   **A second defect the experiment exposed, in a form nothing else would have.** `cache hits count
   as already-paid money` is right for a budget CEILING (finding 39) and wrong for a spend TOTAL.
   `tools/fill_registration.py` summed `billed_tokens + prior_billed_tokens` over every non-pipeline
   run to fill the registration form's J.1 line, and the length experiment's `base` arm is a pure
   cache replay of the PIPELINE's own practice calls — so the form charged the deposit **253,364
   tokens twice**, in an attestation, from inputs that were each individually correct. It now sums
   newly-billed tokens and reports the replayed total separately and by name (1,124,012 newly
   billed, 253,364 replayed). The general rule: **a ceiling and a total are different questions
   about the same ledger, and a cache hit answers them differently.** It surfaced only because the
   base arm of a controlled experiment is, by design, a replay of something already paid for.


61. **A deposit can carry an invented identity through eight builds, because the validator checks
   the template's example and not the truth.** `team_id` was `sodalab`, a placeholder this harness
   made up, and `check.R` passed it green every time — it rejects the id it shipped with and nothing
   else (finding 26 in a third place, now on the field that says *who is submitting*). The
   organisers' id is **`team_31`** and the deposit window is **Aug 28–31 only**. Both are now facts
   in the tooling rather than in a comment: `tools/verify_deposit.py` FAILS a deposit whose
   `team_id` or prediction filenames are not stamped `team_31` (red-path tested: `team_31` PASS,
   `sodalab` exit 1), and every build stamps `built_at`, `publication_window`,
   `not_for_publication_before` and a `publication_status` that today reads
   **NOT-FOR-PUBLICATION — built 2026-08-16, 12 days before the deposit window opens**, with
   `--strict` refusing to call a deposit ready outside the window. Two method points came out of
   doing it. **A submission directory is a derived artefact and must be re-BUILT, not edited**:
   `tools/restamp_deposit.py` re-runs stage 8 only, from the run's own `card/` and
   `stages/tier1.csv`, and re-records G5 against the new validator run. And **byte equality is the
   wrong test for "did the numbers change"**: the first version compared SHA-256 and reported a
   false alarm on the Tier-2 moderator file, which reproduces its own deposited values to
   **2.84e-14 pp** — the same prediction with different float accumulation. It now compares values
   with a tolerance and prints the worst change (target-01: exactly 0).

62. **The prereg's moderator ruling changes what Tier 1 SUBMITS without changing what the card
   PREDICTS — and Tier 1 and Tier 2 do not submit the same zero.** The finalized prereg (TASK_08)
   recomputes subgroup metrics from the individual rows via `run_moderator_model()` and scores an
   **interaction contrast against a reference level**, not a raw subgroup ATE. The card predicts
   `responsiveness.factor = 1`, so it says "no moderation" under either reading and no prediction
   changed. What did change is measurable and was not obvious (`tools/interaction_contrast.py`):
   under the raw reading our subgroup cells would have carried the **marginal ATE repeated in every
   group**, inheriting the Section-1 ranking; under the contrast reading they are an exact zero, so
   Section 3 is at chance — which costs nothing real, because finding 53 measured human interactions
   replicating at r = +0.024 against main effects at +0.596. And the two tiers differ: the Tier-2
   moderator FILE carries the contrast at **0.0000000000 pp**, while the same contrast recomputed
   from the 43,200 deposited Tier-1 rows is **0 ± 2.83 pp** (max 20.9, 49.40% positive) — the frozen
   table's guaranteed 0.5 directional for an exact zero becomes a per-cell coin flip with the same
   expectation. Section 3 excludes RMSE so the noise cannot cost magnitude credit, and removing it
   would need ~131,000 rows (finding 12). **When a scorer recomputes your prediction from your rows,
   your synthesis noise becomes part of your prediction.**

63. **The magnitude multiplier does not survive a family transfer, which is the only evidence that
   can speak to the trust family it will be applied to.** Finding 33 established that zero of 1,101
   practice cells are trust cells, so the deposited λ is a cross-family extrapolation; sessions 6–7
   argued about it from theory. `tools/family_transfer.py` measures the extrapolation error itself,
   at 0 tokens, on the families practice does cover. On the depositable (in-slope) pairs the family
   slopes span **1.135–1.578 (1.39×)** and a slope transferred INTO a held-out family is off by
   **0.74–1.37×**; the RMSE it buys on the held-out family is **+0.030 pp on average (worse), 2 of 3
   folds better, 0 of 3 intervals excluding zero**. The strict fold — held out on **neither the task
   nor the family**, the fold that actually resembles trust — wins 2 of 4 (mean +0.054 pp) in-slope
   and **4 of 11 (mean +0.135 pp, four intervals excluding zero, two of them losses of +1.10 and
   +0.21 pp)** on all pairs. So the multiplier is not merely small (finding 29: +0.008 pp
   leave-one-task-out); **transferred across families it is a coin flip with real downside**, and
   every fold that holds out the design twin `voelkel2026` shows it hurting (+0.195, +0.648,
   +0.167 pp). That is finding 50's conclusion arrived at from the other direction, and it is why
   `20260815-target-01` (unshrunk) remains the primary candidate.

64. **Draws saturate at one, and the curve — not the endpoints — is what says so.** Finding 43 read
   two points (one draw vs the 3-draw median) and found the median fractionally worse.
   `tools/draw_scaling.py` reads every point: all 3 singletons, all 3 pairs, the triple, and a
   fourth point that adds the paid `claude-fable-5` draw. Pooled over the five tasks the curve is
   **flat within its own noise** (dir 0.7558/0.7566/0.7552, ρ +0.6266/+0.6291/+0.6279, r-within
   0.4140/0.4190/0.4096 for k = 1/2/3) and the 3-draw median is **worse than a single draw on RMSE
   by +0.029 pp with an arm-clustered interval that EXCLUDES zero**, and on r-within by −0.026
   (interval includes zero), negative in 4 of 5 leave-one-study-out folds. The same run measures the
   **draw-to-draw noise floor** every prompt experiment needs — dir 0.0011, ρ 0.0046, **r-within
   0.0189**, RMSE 0.0321 — which is the reference band the session-8 pre-registration used.
   **One honest exception, and it is the design twin:** on `voelkel2026` alone the median beats a
   single draw (ρ +0.044, RMSE −0.026), so the campaign's design-twin rule blocks changing the
   deposited pipeline's `draws=3` on pooled evidence. Experiment arms are run at 1 draw (a third of
   the price for a difference of ≤0.03 pp); the pipeline default is left where it was.

65. **Letting the model reason before the table is the largest single-model gain ever measured
   here — and it does not replicate on a second model line.** Pre-registered in
   `runs/_promptexp/PREREG.md` before any call: four arms (two adoptable reasoning treatments, two
   ablations), 1 draw, five tasks, primary metric `pearson_r_within_outcomes`, verdict rules and an
   adoption rule fixed in advance, against the measured draw noise floor of finding 64. Cost
   **1,279,567 billed tokens** against a 1,012,019 estimate — and the gap is not estimator error
   (each arm landed at 0.96–1.07× its own estimate): **two arms were paid for twice** because a
   parse defect aborted them after the calls, which is finding 60's ceiling-versus-total lesson in a
   second place. Results, all against base draw 0 (byte-identical prompts, cache hits, 0 tokens):
   **`reason`** (write ≤2 sentences per message on mechanism and relative strength, then the CSV)
   moves r-within by **+0.0491** — 2.6× the draw SD, larger than the +0.0376 model selection bought
   (finding 48) — with LOSO positive in 4 of 5 folds and the design twin up (+0.060 r-within,
   +0.154 ρ), but its arm-clustered interval **[−0.022, +0.105] includes zero**, so the
   pre-registered rule says DO NOT ADOPT. Since that interval cannot be narrowed with money (finding
   60c: half-width falls only in the number of ARMS), the pre-registered follow-up was an
   independent replication on `claude-fable-5` — **and it came back −0.0337, the opposite sign, LOSO
   negative in 4 of 5**. Two model lines disagreeing in SIGN on the same treatment is what a false
   positive looks like; `reason` is not adopted and `ssb.predict.SYSTEM` is unchanged.
   **`reason_rank`** (rank the messages first, then the table) is *negative* on every metric
   (r-within −0.023, ρ −0.025, LOSO 5/5 negative): asking for the scored quantity directly is worse
   than asking for the cells. The two ablations answer "which inputs move within-outcome r" cleanly.
   **Arm titles carry nothing**: replacing every frame's name with `Message A…` moves r-within by
   **−0.005 (ns)** and ρ by +0.012 (ns) — the predictor is reading the stimulus text, not the label,
   which is the same conclusion the length experiment reached about content (finding 60).
   **Item wordings carry almost everything**: deleting the outcome questions and keeping only names
   and scales costs **ρ −0.408, r-within −0.273, RMSE +0.541, directional −0.045, every one DETECTED
   and LOSO 5/5** — by far the largest effect any prompt manipulation has produced here, and a
   warning that a task carved with thin item text is a much weaker task than its cell count
   suggests. **Two parser defects, both found by paying for them.** An ablation that renames arms
   `Message A` gets answered `A`, and the parser — correctly — refuses to invent a condition it was
   not given, so the arm aborted with 90 NaN cells; aliases are now declared by the variant and
   mapped back. And an arm whose real title contains a **typographic apostrophe**
   (`Outpartisans’ Experiences of Harm`) came back with a straight one and lost 9 cells: `_norm` now
   folds a fixed table of typographic characters to their ASCII forms, which cannot merge two
   genuinely different arms because they are the same character in two encodings, and
   `tools/test_parse.py` carries the red path. Both defects would have hit a paid TARGET batch the
   day a stimulus title acquired a curly quote.

66. **The `reason` prompt is dead, and the way it died is the point: a treatment effect that
   survives only at its own sample size is a sampling artefact.** Session 8 measured `reason` at
   **+0.049 r-within** on `claude-opus-5` over 66 arms — 2.6x the draw SD, LOSO 4/5 positive, the
   design twin up — with an interval that included zero and a cross-model replication that came
   back **−0.034**. Session 10 bought the only thing that could narrow it (121 more arms, from two
   newly mounted datasets) and re-ran the same tool under a pre-registration written before any
   call. At **187 arms and 1,354 cells the effect is −0.0023 [−0.0238, +0.0190] on opus and
   +0.0048 [−0.0265, +0.0341] on fable** — both null, both intervals half the width, and the two
   models have **swapped signs** relative to session 8. On opus the treatment is now DETECTED
   *worse* on RMSE (+0.206 pp [+0.118, +0.296]). OPEN 24 is closed as NULL and **FINAL**: no
   further `reason` arm is bought on any model line. Two consequences for method. **A point
   estimate that moves 0.055 when the pool grows was never an estimate of a treatment effect** —
   it was the pool. And **the pre-registered rule earned its keep twice**: it refused the treatment
   in session 8 when the point estimate was seductive, and it refused it again in session 10 when
   the sign flipped, without either refusal being a judgement call made after seeing a number.

67. **Power-gate the POOL, not the task — and the projection that matters is the one nobody had
   written.** `tools/task_power.py` (finding 36) asks whether a candidate task has signal;
   it says nothing about whether adding that task DECIDES an open question. The naive answer, and
   the one session 8's finding 60c invited, is "half-width falls as n^−0.5 in arms, so 48 more arms
   takes 0.066 to 0.053 and +0.049 becomes significant". That is wrong twice over, and
   `tools/arm_power_projection.py` measures both errors by augmenting the real 66-arm pool with
   pseudo-arms of the candidate's SHAPE: a task whose arms carry 2 cells against the existing arms'
   9-24 buys much less than n^−0.5 predicts (**0.0576, not 0.0531 — a coin flip against the point
   estimate**), because the pooled metric is computed over CELLS as well as clustered on arms; and
   an all-thin-arm projection (0.21) is far too pessimistic because the real pool is a MIXTURE. The
   gate's ruling — **tappin2023 alone would not have decided OPEN 24; tappin + a 73-arm,
   4-outcome hackenburg issue would** — is what turned a one-task session into a two-task one, and
   it was made before any call. Realised against projected: opus **0.0214 against 0.0456**
   (conservative by 2x), fable **0.0303 against 0.0236**. Project the pool, quote the projection,
   then report the realised interval against it.

68. **The billed-token estimator's "tokenizer factor" is a property of the TEXT, not of the model
   or the CLI.** Finding 28 measured `1.574` once, on the climate briefs, and both spending tools
   have carried it as a constant. The first batch on two new corpora landed at **0.77x its own
   estimate** — 333,200 billed against 431,123 quoted. Cause, measured by
   `tools/billing_factors.py` on the run's own `modelUsage`: `ssb.predict.n_tokens` has **no
   tiktoken installed in this environment and falls back to len/4**, so the "tokenizer factor" is
   really a characters-per-token ratio, and it reads **3.32 chars/token on the policy-message tasks
   against 2.5-2.9 on the climate briefs** (factor 1.206 against 1.40-1.57, consistent to ±0.003
   across all 11 calls of the run). The CLI's second pass is stable (+70.9% against +73.2%) and
   output ran 20.7 tokens/cell against the assumed 19. The constant is deliberately **left at the
   higher value**: over-pricing asks the operator for headroom, under-pricing spends money nobody
   approved. Re-measure on the first batch of any new corpus, and quote the estimate as an upper
   bound rather than a number.

69. **The first practice task whose calibration slope is BELOW 1 is the first whose outcome is not
   a slider.** Findings 29 and 34 established β = 1.11-1.90 on five tasks — human effects larger
   than predicted — and built the whole magnitude argument on it. Task 6 (tappin2023, a 7-point
   agreement item) comes in at **β = 0.865**: on a coarse Likert the predictor OVERSHOOTS the same
   pp scale it undershoots on sliders, which is what a compressed scale range should do and what
   the harness would have imported into a pooled slope without noticing. Three independent legs now
   say the same thing about coarse scales: no level transfers (finding 10), no level bridge exists
   (finding 14), and on ten near-verbatim policy issues measured 7-point vs 0-100 slider the level
   offset is **zero on average with ±14 pp of item scatter** while the party GAP runs **1.5x larger
   on the slider** — the opposite direction to finding 14's 0.808 gap factor, and confounded with
   panel. So the adapter carries a third structural exclusion, `exclude_from_slope`, declared in the
   adapter and honoured by `tools/practice.py` alongside `attrition_bounds` and `RECOGNISED`.
   Task 6 (scale format) and task 7 (LLM-authored stimuli) are both out of the slope and scored on
   every other row. **A magnitude is only poolable across tasks that share a measurement format.**

70. **Two more parse defects, one more paid-for lesson, and a rule about what an abort is for.**
   Task 7's 73 arms are titled `Message 01`..`Message 73` because their raw ids name the model that
   wrote each message. `claude-fable-5` answered every row as `message_01` and **lost all 292
   cells**; the parser was right to refuse a name it was not given, and being right cost a whole
   arm of a paid batch (recovered free from cache, but the money was already spent). `_numfold` now
   folds separators and leading zeros — `Message 01`, `message_01`, `Message-1` are one name in
   three encodings — and REFUSES the fold whenever two real arms would collide, with five numbered
   cases and the ambiguity red path in `tools/test_parse.py`. The second defect was not a parse
   defect at all: the same model **discussed arm `Message 68` in prose and omitted its four rows**,
   and `practice.py` aborted the arm over 1.4% of its cells. An abort exists to stop a SILENT
   mis-parse, not to discard a paid batch over an answer that is genuinely incomplete, so
   `--allow-missing-cells` is now available, bounded, off by default, recorded in `summary.json`,
   and paired with an intersection-of-cells rule in `tools/prompt_experiment.py` so no contrast is
   ever computed over two different grids. **Before hardening a parser, ask whether the model got
   the NAME wrong or the ANSWER wrong; only the first is yours to fix.**

71. **"Draws saturate at one" is a property of the tasks it was measured on.** Finding 64 measured
   the 3-draw median as fractionally worse than a single draw on five tasks. Re-run on the two new
   tasks (`tools/draw_scaling.py --tasks`, 0 tokens, the draws were already paid for), the median
   is **better on Spearman by +0.0127 with an arm-clustered interval that excludes zero**
   (+0.0016, +0.0280), neutral on r-within (+0.005) and directional (−0.004), and neutral on RMSE.
   The single-draw noise floor on these tasks is also 3-8x wider than on the original five
   (ρ SD 0.0142 against 0.0046), which is what a task with 48-73 arms and one or four outcomes
   should look like. The pipeline default of 3 draws stays; the general claim does not.

72. **The arm pool everything was measured on was 15 arms and 135 cells smaller than the pool it
   was named after, and nothing had ever checked it against the file the run wrote.** Every offline
   tool here re-derives a paid draw from its transcripts (`draws_value.draw_frames`), which is right
   — it is what lets a single draw be scored the way the panel was — and it did so by re-running
   `plan_prompts` and parsing part *i* against **today's** part-*i* arm list. `voelkel2024`'s
   arm→part split has changed since that batch was bought, so 7 of 13 arms in each part were looked
   for in the wrong transcript and **135 of its 234 cells reconstructed as NaN**, silently, because
   a `dropna` downstream merely made the task smaller. Session 10's "187 arms / 1,354 cells" was
   that shadow; the true base is **202 arms / 1,489 cells**, and 1,489 is the number the scoreboard
   had been printing all along. Fixed by parsing every part against the WHOLE brief and unioning
   the parts — and `kind="stable"` on the tie-break is load-bearing, because where two parts both
   answer a shared anchor arm the run kept the EARLIER part's number and a default (quicksort)
   sort picks the other one, which was exactly the 3-cell residual the test caught next.
   `tools/test_draw_frames.py` now checks every reconstruction against that run's own
   `prediction.csv`: 0.0 on 14 of 15 task x run pairs, with the red path (the old reconstruction
   must still show 135 NaN) asserted. **Nothing published changes sign** — OPEN 24's `reason` null
   re-measured on the corrected pool is −0.0031 [−0.0234, +0.0168] on opus against session 10's
   −0.0023 [−0.0238, +0.0190] — which is the point: the defect moved a POOL, not a conclusion, and
   a pool nobody recomputes is a number nobody owns. The 15th pair is a second lesson in the same
   place: `20260817-practice-t67`'s stored `hackenburg2025` prediction disagrees with today's
   parser on **23 of 292 cells**, because session 10 hardened `ssb.predict.parse` *after* that file
   was written. Re-running `tools/practice.py` on the same cached transcripts (0 new tokens,
   `runs/20260818-recheck-t67`) reproduces the new reconstruction exactly, which is what makes it a
   dated artefact rather than a defect. **A stored prediction is a parser version as much as a
   model answer.**

73. **Two more re-encodings, one abbreviation, and the line between them — drawn where finding 70
   said, and it cost 9 cells to hold it.** `claude-sonnet-5` answered `voelkel2024` in run-together
   CamelCase (`Outpartisans' Willingness to Learn` → `OutpartisansWillingnessToLearn`) and
   `hackenburg2025`'s 73 numbered arms as `msg01..msg73`, losing 18 and then **all 292** cells.
   Two folds were added and both refuse ambiguity: `_numfold` now drops punctuation inside a name
   along with the spaces, and `_digitfold_map` matches on the NUMBER alone — but only where every
   arm is numbered, the numbers are unique and the names share one stem, i.e. where the number IS
   the identity, and **conditions only**, because a bare number in an outcome position would let a
   value column masquerade as an outcome name (`integer_values` is a test case for exactly that).
   What was deliberately NOT folded: `Bipartisan Joint Trivia Quiz` answered as
   `BipartisanJointTrivia`. A dropped WORD is not an encoding, and a prefix rule would be the
   parser choosing which arm was meant, so those 9 cells stayed NaN under a bounded, recorded
   `--allow-missing-cells 0.04` (finding 70's rule, applied against my own convenience). A third
   defect in the same task was not a parse problem at all: `tools/practice.py` combined a split
   task's parts with `drop_duplicates(keep="first")`, so an unparsed part-1 cell **masked a
   perfectly good part-2 answer** for an arm both parts were shown. Six new red paths in
   `tools/test_parse.py`, three of them refusals.

74. **The third model line is decisively WORSE, and the pre-registered rule spent 584,048 tokens to
   say so in one direction instead of arguing about it in both.** `claude-sonnet-5`, one draw, all
   seven tasks, probes and leak audits CLEAN with positive controls firing, scored under
   `runs/_modelsel/PREREG.md` on the corrected 202-arm pool: `pearson_r_within_outcomes`
   **−0.0874 [−0.1584, −0.0205]** against `claude-opus-5` at one draw (DETECTED, 6x the draw SD),
   Spearman **−0.0570 [−0.0984, −0.0162]** (DETECTED), RMSE **+0.408 [+0.207, +0.592]** (DETECTED),
   directional −0.008 (ns), **LOSO negative in 7 of 7 folds**, and the design twin down on both
   twin rows. The legacy 187-arm subset agrees (−0.0873). **Verdict NULL under the selection rule;
   `claude-opus-5` stays.** Three things worth keeping. The loss is not uniform — sonnet-5 *beats*
   opus on `bbprime2025` r-within (0.593 against 0.495) and is level on directional — so "worse
   model" is a pooled statement about a pool that was chosen in advance, which is what
   pre-registration is for. The exploratory 3-line panel is **worse than opus alone** (r-within
   0.590 against 0.614), a third independent confirmation that aggregation buys nothing here
   (findings 43, 48, 64). And recognition is a property of the model: sonnet-5 recognised the same
   two tasks opus-5 does. Cost estimation on a line the factors were never measured on came in at
   **0.86x the quote** (584,048 against 680,332), with the CLI's second billed pass at **+66.9%**
   against the 73.2% constant and output at **20.96 tokens/cell** against the assumed 19 — the same
   direction as finding 68, over-priced rather than under-priced, which is the direction to be
   wrong in.

75. **A lookup keyed on the wrong thing dropped two tasks from an experiment and said nothing.**
   `tools/prompt_experiment.py` resolves the session-10 task runs from a dict keyed by MODEL LINE
   while the `--tag` argument names the RESULTS FILE, so `--tag opus_recheck` — a tag chosen so a
   re-check could not overwrite session 10's artefacts — silently scored **1,101 cells over 5
   tasks** instead of 1,489 over 7, printing the same table shape either way. It is finding 32's
   rule ("when a lookup can miss, log which branch it took") in a third place, and the fix is the
   same shape: resolve the line by prefix, and print a warning naming the tasks that are NOT
   included. The check it was blocking is the one that mattered this session — whether the
   corrected pool of finding 72 changes any published verdict — and the answer is no.

76. **The board was one parser version away from being one experiment, and the audit that made it
   so found the drift was 1 row, not 15.** Finding 72 established that a stored prediction is a
   parser version as much as a model answer. `tools/reparse_audit.py` re-derives every scoreboard
   row from the transcripts on disk through the parser that exists **today** — same brief
   (including a variant's transformed brief and its title aliases), same whole-brief part union,
   same median, same `ssb.task.score_task` — and then makes the board say which parser made each
   row. Of 172 rows, **127 re-derive** (45 have no transcripts on disk and are marked `unverified`
   rather than silently stamped). **One row moved**: `20260817-practice-t67`'s hackenburg2025, by
   +0.0014 directional, −0.0017 ρ, +0.014 pp RMSE and −0.080 on `cal_alpha` — and the re-derivation
   reproduces `20260818-recheck-t67` (the session-11 re-run on the same cached transcripts) to
   **1e-15 on all 13 metrics**, which is what makes it a parser drift rather than a scoring change.
   Five more rows differ and are **not** parser drift at all: they are finding 46's duplicate
   `run_id` defect, where the transcripts belong to the later execution, so they are labelled
   `unverified-duplicate-run-id` and their metrics are left exactly as they were — re-deriving them
   would overwrite the record of a documented defect with numbers from a different run. The four
   TARGET rows re-parse to **0.0000000000 pp on all 208 cells**, so no deposit is affected. What
   makes this durable is not the audit but the field: `ssb.predict.parser_version()` hashes the
   nine functions a parsed cell passes through (not the module file, which would change on any
   edit anywhere in it), `ssb.gates.scoreboard_append` writes it on every future row, and
   `tools/verify_scoreboard.py` exits non-zero on any PAID row whose version is neither today's nor
   `unverified`. A pairs.csv check could never have caught this: **the row and its pairs move
   together, so a stale parse reproduces perfectly and is still not comparable.** Old board kept at
   `runs/scoreboard.csv.pre-reparse`; red path in `tools/test_gates.py`.

77. **The first trust-family practice task can only be graded on magnitude, and graded that way it
   passes — while the model that recognised the paper had to be thrown out for passing.**
   Finding 33 said the gap could not be closed by measurement here, and
   `notes/DATA_GLIGORIC.md` ruled gligoric2025 NOT CARVABLE as a *scored* task. Both stand:
   `tools/task_power.py` reads **var_signal −1.00, attainable-r ceiling 0.000** on its 40-cell
   table, and the row on the board carries `r_adj = 1.0` and `rmse_adj = 0.0` because the
   disattenuation is dividing by a signal that is not there. What a null table CAN grade is
   magnitude, against a bound: the paper's own equivalence test (d < 0.1) is **Δ = 1.963 pp** of the
   1–7 range on the best-powered outcome, and the human table is **40 of 40 inside**.
   Pre-registered in `runs/_trusttask/PREREG.md` before any call: P1 = all 5 message arms inside Δ
   on `trust_overall`, P2 = ≥ 80% of 40 cells inside their own Δ, ranking rows explicitly not
   scored, `exclude_from_slope` declared in the adapter, and a **quarantine rule** because this
   paper *is* standing finding 5 — the harness's own trust prior comes from the study being
   predicted. Results, 37,227 billed tokens over three lines: **`claude-opus-5` P1 5/5, P2 1.000**
   (median |pred| 0.90 pp, max 1.20, all positive, probe UNRECOGNISED at self-confidence 3);
   **`claude-sonnet-5` P1 3/5 = FAIL, P2 0.800** (median 1.75 pp, max 2.60); and
   **`claude-fable-5` named Gligorić, van Kleef and Rutjens and self-reported `RESULTS_KNOWN: YES`
   at confidence 55**, so its 5/5 and 1.000 are **quarantined, not scored**
   (`tools/quarantine_row.py`, metrics NA on the board, everything else kept). That is the rule
   earning its keep in the hardest place: the quarantined line is the one whose numbers look best,
   and a null result is exactly what a recalling model would reproduce. **The trust-family slope is
   uninformative and was declared so before it was computed** — β 0.845 **[−0.869, +3.061]**,
   arm-clustered, an interval containing every slope any task has ever produced. And it carries a
   confound the mounted data cannot break: this is the harness's first TRUST task and only its
   second COARSE-LIKERT one, and the two Likert slopes (0.845 here, 0.865 on tappin2023) sit
   together below 1 while every slider task runs 1.11–2.31 — finding 69 predicts that from the
   scale format alone. `tools/build_gligoric.py` (7 red paths, including what forgetting the
   conservatives-only filter costs: every ATE moves −2.0 to −4.6 pp), `tools/trust_task.py`.

78. **The predictor is not writing large trust effects everywhere — it wrote small ones where the
   only randomised benchmark exists.** The card's 64 trust cells (4 trust outcomes × 16 arms) have
   median |ATE| **2.05 pp** and max 3.00, and **59% sit outside** gligoric2025's own equivalence
   bound; the same model, same prompt shape, on gligoric2025's real trust experiment wrote median
   **0.90 pp**, max 1.20, **100% inside**. Findings 50 and 63 argued from theory that the pooled
   multiplier must not be applied to trust; this is the first in-family measurement and it agrees
   from a third direction — ×1.5212 takes the card's trust cells to median 3.12 pp and 87.5%
   outside the bound, while the trust task's own β (0.845) would take them to 1.73 pp and 35.9%.
   Nothing was changed: TASK_12 item 3 is measurement only, RUNBOOK §2a forbids editing a
   prediction because a diagnostic looked bad, and the two magnitudes are not the same estimand —
   different messages, a general population against conservatives-only, and a slider against a
   7-point item. What is now on the record is that the gap is **2.3x**, measured rather than
   asserted, and that the deposited (unshrunk) card is the one of the two that sits closer to the
   only randomised trust evidence there is.

79. **A shared control mean makes an attainable-r ceiling read zero when it is 0.65.** Finding 36's
   `var_true = var(obs) − mean(SE²)` assumes independent cell errors, and every ATE table this
   harness carves differences several arms against **one** control mean inside each outcome, so the
   errors are positively correlated and the statistic is biased **down**. The covariance-aware form
   subtracts `trace(M V M)/(k−1)` with `V[i,j] = var_c/n_c` for cells sharing an outcome, and for a
   within-outcome metric it demeans inside the outcome first — which **removes the shared control
   noise entirely**. Measured on koetke2024 Study 5's 12 trust cells: naive **−0.543** (reads
   CHANCE), covariance-aware marginal −0.297 (still chance), **within-outcome +0.508, ceiling
   0.648** (real signal). So a table can be at chance on the marginal ranking and carry genuine
   signal in the contrasts the frozen table's `pearson_r_within_outcomes` row is defined on, and the
   two must be ruled on separately. The correction only ever moves a ceiling **up**, and it does not
   resurrect a dead table: re-checked at 0 tokens, gligoric2025 reads −0.925 covariance-aware and
   −0.306 within-outcome against −1.003 naive, so finding 77's ruling stands. `tools/build_koetke.py`
   carries the implementation; `tools/task_power.py` still carries the naive one and every task
   ruled on with it deserves a re-read.

80. **The predictor reproduces a published trust/belief dissociation and has no message-level skill
   on it — and the second half is the finding.** koetke2024 Study 5 (four arms of one interview
   vignette, 27 cells) was pre-registered before any call with three qualitative verdicts and they
   all **PASS on all three model lines**: trust UP and belief-in-research DOWN for both "limits"
   framings (4/4 signs), personal humility raising trust at no belief cost, and the exact human
   ordering of the dissociation index (chance 1/6). Then
   **`pearson_r_within_outcomes` = 0.059 against an attainable 0.644** — the lowest on a board where
   every other task runs 0.325–0.761 — with 0.124 and 0.111 on the other two lines, so it is a
   property of the task and not of a draw. Marginal r is 0.649 against a 0.850 ceiling: the
   predictor knows **which outcome** a humility cue moves and not **which framing** moves it most.
   The two tasks with high within-outcome r (tappin2023 0.761, hackenburg2025 0.680) have many arms
   differing in *content*; this one has three arms differing in a rhetorical move inside one
   paragraph. The target's 16 arms are framings of one topic, which is the koetke shape, not the
   tappin shape. `tools/koetke_verdicts.py` reruns all of it in a second.

81. **Polarized trust is a property of the SOURCE'S IDENTITY, not of the message — a 25x gradient,
   measured three ways.** The card predicts zero condition × moderator interaction and nothing had
   checked it against the polarization literature. Rule fixed before computing
   (`runs/_trusttask2/PREREG.md` §4), then `tools/party_moderation.py`: an institute explicitly
   labelled politically liberal vs conservative moves METI trust by **−46.45 pp between party halves
   (SE 5.48, z −8.5)**; the same manipulation done implicitly, as *discipline* (sociologists vs
   economists), moves it **−3.75 pp (z −1.4)**; and a **message strategy** — the target's shape —
   moves it by **at most 1.82 pp** with mean SE 3.15. Replication by finding 53's arbiter: the
   identity-label interactions replicate at **r = +0.647** (main effects +0.786), the
   message-strategy ones at **r = −0.507** (main effects +0.893). **VERDICT: CONSISTENT** — the
   card's zero is defensible for message interventions — with two bounds stated: koetke cannot rule
   out ±6.2 pp, and the target itself, at ~500 per party half, has SE(interaction) ≈ 1.94 pp and
   cannot resolve below ~4 pp. The one way this could be wrong is a target arm that makes an
   explicit political claim about climate scientists; reading the 16 stimuli with that question in
   mind is free and has not been done.

82. **A negative split-half r is not anti-replication — it is a signal-to-noise reading, and the
   identity is exact.** Complementary halves partition the sample, so for a mean-based estimator
   `mean_A + mean_B = 2·mean_full` and the halves' errors are exactly opposite. With S the
   across-cell signal variance and N the error variance, `vec_A = t + e`, `vec_B = t − e` and
   **`r = (S − N)/(S + N)`, i.e. `S/N = (1+r)/(1−r)`** — verified by simulation. So r = 0 is exactly
   S = N, r < 0 means noise exceeds signal, and the statistic is a ratio rather than a pass/fail.
   altenmueller Study 1's identity × party interactions read **S/N = 4.67**, koetke's message ×
   party interactions **0.33**, and finding 53's +0.024 on the target-shaped moderator vectors reads
   **1.05** — which sharpens finding 53 rather than changing its conclusion.

83. **The coarse-scale explanation of the sub-1 slopes has a counterexample; the confound does
   not.** OPEN 31 asked whether tappin2023's β = 0.865 and gligoric2025's 0.845 are a *trust-family*
   effect or a *coarse-scale* effect, and the operator's scouting closed the direct route (no
   randomised slider-format trust experiment with open microdata exists). koetke2024 is a third
   coarse-scale task — 7-point bipolar differentials, 5-point stereotype items, one binary item —
   and its slope is **1.47–1.91**, well above 1. "Coarse scale implies β < 1" is therefore not
   supported; between-task spread swamps scale format. The confound itself is **not** resolved (this
   is also a trust task), and no trust-family multiplier is fitted — the operator's session-13
   directive, and the adapter carries `exclude_from_slope` for the same reason tappin2023 does.

84. **The card's trust magnitudes are now BRACKETED by two randomised benchmarks, and the unshrunk
   card is the one inside the bracket.** The deposited card's 64 trust cells have median |ATE|
   **2.05 pp**. gligoric2025's human trust table has median **0.42 pp** (a published null,
   conservatives only); koetke2024's has **2.16 pp** (a general-population vignette with detectable
   effects). Finding 78 measured the card at 2.3x the first; against the second it is within 5%.
   Applying λ = 1.5212 takes it to 3.12 pp, **above both**. Same conclusion as findings 50, 63 and
   78, now from a fourth direction and for the first time against a trust task with signal:
   **keep the unshrunk card as the primary candidate.** Worth carrying alongside it: on this task
   the predictor's own trust cells are median **1.20 pp** against a human **2.16 pp** — it
   *under*-states trust magnitudes where the truth is non-null, which is the opposite sign to the
   gligoric comparison and is why a single-reference multiplier would have been fitted to the wrong
   thing.

85. **Arms that look alike make a study that cannot resolve them, not a predictor that cannot order
   them.** Session 13's `pearson_r_within_outcomes` = 0.059 on koetke2024 raised the fear that this
   predictor reads topic differences and not tone differences — a first-order worry for a target
   whose 16 arms are framings of one topic. Pre-registered in `runs/_decomp/PREREG.md` (distance
   measure, three regression specs, covariates, verdict rules and the target-projection rule, all
   fixed before any number) and run at 0 tokens by `tools/skill_decomposition.py`. The declared
   specs come back **UNRESOLVED**: the task-level Pearson of `r_within` on lexical spread is +0.744
   but the Spearman is only +0.333 (one outlier does the work), the arm-level slope with task fixed
   effects is −2.072 [−4.463, +0.529] and without them +0.168 [−1.674, +1.023]. The POST-HOC pair
   analysis is what explains it: over **21,931 within-outcome arm pairs**, only **27% are resolvable**
   (|Δh| > 2 SE — the shared control cancels in a contrast, so its SE is computable from truth.csv),
   accuracy on those runs **0.874 / 0.906 / 0.806 / 0.850** across lexical-distance quartiles (flat,
   coefficient −0.039 [−0.384, +0.157]), and over the ten tasks lexical spread correlates **+0.833**
   with the fraction of resolvable pairs and **+0.772** with the within-outcome ceiling but
   **−0.476** with accuracy on the pairs that are resolvable. koetke2024 has 3 resolvable pairs of
   27 and the predictor got **3 of 3** right. **The target is not koetke-shaped** — its arms sit at
   D = 0.894, above 5 of 8 live practice tasks — and the projected within-outcome r is
   **0.26 [0.19, 0.33] to 0.60 [0.43, 0.75]** as the target's true effect SD runs 0.5 → 2.76 pp.
   The free parameter is the target's own effect size, not the predictor.

86. **Three of the target's 16 stimuli make an explicit political-identity claim, one of them with
   the sign reversed — and a message's political vocabulary does not predict its party
   interaction.** Finding 81 left one escape open: if a target arm makes an explicit political claim
   about climate scientists, the card's zero condition x moderator interaction could be badly wrong.
   `tools/identity_audit.py` reads all 16 (mechanical lexicon scan, then a coded reading with the
   quote each rests on). **EXPLICIT: `Social justice`** ("scientists stand with us — the 90%"),
   **`Oil industry misinformation`** ("don't trust the oil companies, trust the climate scientists"),
   **`Former skeptics`** ("I am a registered Republican"; NRA, "the reddest states") — and the third
   is a **bridging** message whose expected gradient runs the OPPOSITE way, so a tilt applied by
   keyword count would get its sign backwards. One implicit cue (`Portrait Prof. Cherry`: Wyoming,
   football, no political noun) and three politically-coded actors. The like-for-like test that did
   not exist before: **70 real message arms** from the four carved tasks that ship a `__party`
   subgroup truth, correlating each arm's deconvolved party-interaction size with its political
   vocabulary, **within task** — +0.301, +0.080, −0.334, +0.507, **pooled +0.134**. The arithmetic
   settles the rest: the card's subgroup model is low rank, so a tilt is a MULTIPLE of a marginal
   ATE of 1–3 pp, and half of altenmueller's gradient on `Social justice` asserts **D+12.3 /
   R−10.9 pp** — the message driving Republican trust down 10.9 pp. It would move **156 of 5,616**
   interaction cells (±1.39% of one Section-3 row), leave Sections 1 and 2 untouched, and sit below
   the target's own resolution (SE(interaction) ≈ 1.94 pp). **Recommended: no tilt**, recorded as
   PENDING-OPERATOR; `card/tilt.csv` stays empty.

87. **The covariance-aware ceiling is now the default, and the number it added is the within-outcome
   one.** `tools/task_power.py` defaults to finding 79's statistic (`--naive` keeps finding 36's),
   reconstructing the control variance from `truth.csv` under homoskedasticity and **checking** that
   reconstruction against `build_koetke.py`'s exact individual-level computation (`--check`:
   marginal ceiling 0.850 vs 0.850, within-outcome 0.624 vs 0.644). Across all ten carved tasks
   **no carve verdict flips** — gligoric2025 stays dead at −0.925, the largest marginal move is
   tappin2023's 0.817 → 0.865 — but the new within-outcome column changes how three scored rows
   should be read. **The design twin `voelkel2026` scores r_within 0.487 against an attainable
   0.490**: read against the old marginal ceiling that was 72% of what was possible, and it is
   **99%**. koetke2024's within ceiling is 0.624 against a 0.850 marginal, and altenmueller2024's is
   exactly 0. A correlation quoted without its ceiling is not a score, and the ceiling that matters
   for the frozen table's message-level row is not the marginal one.

88. **A task whose arms are identity twins has a within-outcome ceiling of exactly zero, and its
   best-looking row is meaningless.** altenmueller2024 Study 4b is carved as trust task #3
   (`tools/build_altenmueller.py`, 15 checks including 5 red paths; `runs/_trusttask3/PREREG.md`
   before any call; 25,166 billed over three model lines). Its two preregistered arms are
   word-for-word twins apart from the discipline word, and the power gate — run BEFORE the carve was
   approved — reads marginal ceiling **0.783** and **within-outcome 0.000**. It came back with
   `pearson_r_within_outcomes` = **+0.914**, which would be the highest value on a board where every
   other task runs 0.06–0.76, and which is **at chance by construction**; the pre-registration says
   so in advance and the row is reported NOT INTERPRETED. All three lines were **UNRECOGNISED** (no
   quarantine, for the first time in three trust tasks) and the dissociation verdict **PASSES 3/3** —
   morality-based trust up, expertise-based trust not — with the same error in all three: they
   predict sociologists as **less competent** (−0.8 / −4.0 / −2.0 pp) where the humans show +0.37.
   The magnitude leg completes the pattern of findings 78 and 84: predicted trust medians are
   0.90 / 1.20 / 1.60 pp against human 0.42 / 2.16 / **4.33** — the predictor's trust magnitudes
   barely move while the human ones range over an order of magnitude. **The fold this task was
   carved to provide cannot exist**: the property that makes arms "differ only in a rhetorical move"
   is the same property that makes the human study unable to resolve them.

89. **A field with no stated referent gets quoted as if it had one.** The stage-3a recognition probe
   asks for `CONFIDENCE: <an integer 0-100>` and never says confidence in WHAT. `claude-opus-5`
   answered `STUDY: UNKNOWN` with **CONFIDENCE: 90** on altenmueller2024 and `UNKNOWN` with
   **CONFIDENCE: 4** on koetke2024; session 13's report quoted the 4 as "low confidence" as though it
   measured recognition. No verdict depends on it — the grade is the regex match and `RESULTS_KNOWN`
   — but the number has now been published twice with two incompatible readings. Recorded as OPEN 36
   and deliberately NOT fixed retroactively: changing the probe's system prompt changes its cache
   key and invalidates every probe result on disk, which is a larger cost than the defect.

90. **The projection everyone had been quoting was a function of a number nobody had computed — and
   computing it exposed a divisor error in three tools.** Session 14 projected the card's
   `pearson_r_within_outcomes` at "0.26-0.60 depending on tau" and left tau unpinned, so the whole
   width of the published expectation was one unmeasured quantity. tau - the SD of the TRUE
   within-outcome-demeaned effects across a study's message arms - is computable from any carved
   task's sealed truth with **no model call**, because inside one outcome the shared control mean
   cancels exactly under demeaning. Pre-registered in `runs/_tau/PREREG.md` (estimator, restriction
   rules, projection, and the rule for the range's centre) with arm codes frozen in
   `runs/_tau/arm_codes.json` before any number existed. **Primary stratum tau = 2.58 pp
   [0.79, 4.95]** over 34 climate x message x slider cells, **trust-family anchor 0.00**, so the
   pre-registered range is 0.5 - **1.14** - 2.58 pp and the expected score is **0.45 [0.31, 0.56]**,
   full range 0.25-0.59. Three post-hoc routes land on the same centre (leave-bbprime-out 1.04,
   median-over-tasks 1.28, koetke's trust outcomes 0.70) and the pooled number is one task:
   voelkel2026 0.60, vlasceanu2024 1.15, goldwert2026 1.40, **bbprime2025 6.51**, whose News
   Comments arms manipulate the relevance of the very headlines its `msg_*` outcomes ask about.
   **The methodological half is the bigger lesson.** A `--selftest` that recovers a KNOWN tau by
   simulation read **0.43 pp when the truth was 0.00**: `S` used divisor `k-1` and the noise term
   used the MEAN of the diagonal of `M V M`, i.e. divisor `k`, leaving `sigma^2/(n k)` of spread
   that was not there. The same inconsistency was live in `tools/task_power.py`'s WITHIN-outcome
   ceiling and in `tools/build_koetke.py`'s exact computation, so the two agreed with each other
   while both read slightly high (koetke 0.624 -> 0.605, voelkel2026 0.490 -> 0.481; **no carve or
   scoring verdict flips**). A reconstruction check that compares two implementations of the same
   convention cannot see the convention being wrong; only a known answer can. **Build the estimator,
   then make it recover a number you chose.**

91. **The predictor treats a four-dimension trust battery as one thing, and the target's PRIMARY
   outcome is exactly such a battery.** `trust_multidimensional` is the mean of competence,
   integrity, benevolence and openness, and the harness predicts the composite directly - so a
   dimension-specific distortion would never appear in any practice row. Measured on the only two
   carved tasks that ship the subscales (`tools/subscale_bias.py`, 0 tokens): with
   `b = e_competence - mean(e_moral)`, **b = +0.59 pp (koetke2024) and +2.94 pp (altenmueller2024),
   sign agreeing on both tasks and all three model lines**. The sign matters: it is not the feared
   stereotype trade-off (docking competence for admitted limits) but a **halo** - the predictor
   moves competence too much *with* the moral dimensions and **understates the human dissociation**
   (human moral-minus-competence gap +1.87 against predicted +1.28; +5.82 against +2.88). The bias
   an equal-weight four-dimension mean inherits is **+0.38 pp** (+0.76 pp if openness carries it
   too) against the target's own **SE(ATE) = 1.27 pp** on that outcome, so the pre-stated rule
   refuses a correction and none was written. Two rules generalise: **a composite hides the
   dimension its predictor is worst at**, and a correction smaller than the study's own resolution
   cannot be scored as an improvement, so measuring it is the whole deliverable.

92. **A field with no referent still correlates with the thing it was mistaken for, which is how it
   survived two sessions.** OPEN 36 flagged the probe's `CONFIDENCE` as uninterpretable. Audited
   over all 63 probe records on disk (`tools/confidence_audit.py`, 32 paid; the 31 rehearsal rows
   are the fake CLI's scripted 15): it separates the frozen verdict at **AUC 0.859**, point-biserial
   **+0.632** - so an aggregate reading of it looks fine, and a single value is unreadable, because
   `claude-opus-5` answered `STUDY: UNKNOWN` with **90, 75, 4 and 3** on four different tasks. The
   audit's load-bearing check is the other one: **every RECOGNISED verdict on disk is explained by
   an identity-key regex hit or by the model's own `RESULTS_KNOWN`**, so no verdict, quarantine or
   slope exclusion ever depended on it. Resolution at 0 tokens: **retired from interpretation**
   (`confidence_referent` stamped on every probe result; `trust_task.py`'s column renamed; and
   removed from **registration item I.3**, which is where it had actually leaked - into an
   attestation, finding 55's rule in a second place) and **defined for later** (`PROBE_SYSTEM_V2`,
   `--probe-version 2`, not the default because it makes every probe on disk a cache miss).
   **Before quoting a self-reported number, check what any conclusion would change if it were
   deleted** - here, nothing, which is why retiring it costs nothing and quoting it cost credibility.

93. **A low attainable-r ceiling caps what a perfect predictor could score and says nothing about
   what an arbitrary one does score — the second limit is a permutation null, and on this task it
   is enormous.** orchinik2024 (trust practice task #4) has the lowest non-zero marginal ceiling on
   the board, **0.534**, and the harness scored `spearman_rho` **+0.819** and
   `pearson_r_within_outcomes` **+0.510** against it — above the ceiling, which looked like a
   contradiction and is not one. Shuffling the arm labels across the 2,545 respondents and
   re-scoring the **same** prediction (`tools/orchinik_verdicts.py`, 1,000 shuffles) gives a null
   with **SD 0.34–0.42 on every correlation row**: ρ is real (p = 0.004), r = 0.658 is p = 0.059,
   and **r_within = 0.510 is p = 0.077 — not distinguishable from a structured prediction scored
   against noise.** The pre-registration had already ruled that row NOT INTERPRETED because its
   within-outcome ceiling is 0.000, and the three model lines confirm it from a second direction:
   their perception-stratum r_within spans **−0.349 to +0.470 while their predictions correlate
   +0.945 to +0.974 with each other.** A correlation on a small, noisy table needs BOTH limits
   quoted — the ceiling above it and the null beneath it — or it is not a score.

94. **The first trust-family task on the target's own measurement format says the magnitude
   multiplier is ~1, and the predictor's trust magnitudes still barely move.** Findings 69 and 83
   left trust-family and coarse-scale confounded because all three trust tasks were 1-5/1-7 scales.
   orchinik2024 is **0-100 sliders, message arms, a US quota panel, climate-scientist perception
   outcomes** — in family and in format — and its slope is **β = 1.117 / 0.929 / 0.954** on
   opus-5 / sonnet-5 / fable-5 (respondent-cluster bootstrap [−0.04, +2.23] on the primary line),
   i.e. centred on 1 and **below the pooled λ = 1.5212**, which is a fourth independent reason not
   to apply the pooled multiplier to trust (findings 50, 63, 78, 84). The magnitude series now runs
   over four trust tasks: **human median |ATE| 0.42 / 2.16 / 4.33 / 1.14 pp against predicted
   0.90 / 1.20 / 1.60 / 0.80 pp** — an order of magnitude of variation in the truth against a
   factor of two in the prediction. `exclude_from_slope` was set in the adapter before any call and
   no calibration changed. Two pre-registered verdicts passed on all three lines: the magnitude
   band (P1) and the study's own sign structure — perceived skill up for mainstream scientists and
   down for dissenting ones (P2, chance 1/4).

95. **When a study's outcomes are repeated measures, an interval that resamples cells is not an
   interval.** τ for orchinik2024's 20 perception outcomes reads **0.00 pp [0.00, 0.34]** when the
   per-outcome τ² readings are bootstrapped and **0.00 pp [0.00, 1.69]** when the RESPONDENTS are —
   a five-fold difference, because all 25 outcomes are answered by the same 2,545 people and the
   five consensus levels inside a family are near-copies. The respondent interval is the honest one
   and it is what `runs/_trusttask4/PREREG.md` rule M4 fixed in advance. Same lesson as finding 42's
   arm-clustering, in a place where the cluster is the person.

96. **`--probe-version 2` fixes the field finding 92 retired, and the fix is visible in one line.**
   Under v1, `claude-opus-5` answered `STUDY: UNKNOWN` with `CONFIDENCE: 90` on one task and `4` on
   another, and the number was unreadable because the prompt never said what the confidence was in.
   The first paid v2 batch (three model lines, this task) returns **`STUDY: UNKNOWN` with
   `CONFIDENCE: 0` on all three** — coherent, because v2 states the referent and says to answer 0
   when the study is unknown. Every probe result now carries `confidence_referent`, so a later
   reader can tell which instrument produced a number. **OPEN 36 is closed**; v2 is the version to
   use on any batch bought from here, and nothing on disk needs re-buying because no verdict ever
   depended on the field.

97. **A declared dependency that nothing in the session imports is not a dependency that works.**
   `openpyxl` is in `/workspace/pyproject.toml` and was absent from the project venv, so
   `ssb.task.carve("vlasceanu2024")` — one of the five original practice tasks, whose data is an
   `.xlsx` — raised `ImportError` on a full-loop run and nothing had noticed, because every session
   since the environment drifted carved only the tasks it was working on. Found by needing the file
   for an anchor check, fixed by installing the declared version, and verified by re-carving the
   task (165 cells). Re-carve one xlsx/sav task, not just the session's own, before trusting that
   the loop still runs end to end.

98. **A ceiling without a floor beneath it was half a reading, and putting the floor under all 84
   paid rows moved the primary metric on four tasks.** Finding 93 measured the permutation null on
   one task; `tools/null_audit.py` now measures it on every carved task at 0 tokens — shuffle the
   ARM LABEL across respondents (within `control_strata` where an adapter declares one), recompute
   the ATE table with the same `ssb.task.true_ates` the carve uses, re-score the **unchanged**
   prediction, 1,000 times, all of a task's rows sharing one set of shuffles so two models face the
   same null. On the first paid row of each task, **every task except gligoric2025 clears its null
   on Spearman ρ** (z +2.0 to +7.9; gligoric, the table with a zero ceiling, reads +1.12 — finding
   77 confirmed from a third direction). But `pearson_r_within_outcomes`, the row the campaign is
   about, is **within 2 SD of its own null on four tasks — gligoric2025 (+1.16), koetke2024
   (+0.17), orchinik2024 (+1.60), altenmueller2024 (+1.92) — which is every trust-family task on
   the board**, and the design twin `voelkel2026` clears it at only +2.55. The null SD is what
   drives this: 0.09 on a 73-arm task and 0.33–0.49 on a 2–3-arm one, so a small task cannot
   support a correlation however large it looks. **The RMSE row is a different statement and must
   not be read as a pass.** z is signed so positive always means better than a no-signal table, and
   on bbprime2025 (−2.36), hackenburg2025 (−3.23) and vlasceanu2024 (−2.27) the harness's RMSE is
   **worse** than what the same prediction earns against a table with no treatment in it — because
   a shuffled table's ATEs are pure noise and small, and so are ours. That is finding 34's
   under-dispersion appearing in a place nothing had looked, and it means the permutation null is
   not a floor for RMSE at all: a no-signal table is an *easier* target. Quote both limits, and say
   which question each answers. The self-test is the other half of the lesson: a "good predictor"
   built as *observed ATE + small noise* scores z = +3.4 against its own null when the true effect
   is zero, because it has copied the table's sampling noise — a prediction in a known-answer test
   must be built from the TRUTH, never from the realised table.

99. **The τ range's high end is a cap taken from a floor, and naming that is the whole
   sensitivity.** `tools/tau_sensitivity.py` maps τ → ceiling → expected score on a grid, inverts
   it, and prints the direction in which each input reading bounds τ. Two things fall out. **The
   inverse, in one line:** the published quote 0.25–0.53 is wrong only if the target's true τ is
   below **0.50 pp** or above **1.69 pp**, and the map is steepest exactly where the in-family
   evidence sits (+0.25 pp of τ buys +0.118 of expected r at τ = 0.25 and +0.017 at τ = 2.0), so
   the LOW end — a *substituted* 0.5 pp floor standing in for a trust anchor that reads 0.00 — is
   the fragile half. **The tension:** `runs/_trusttask4/PREREG.md` U3a uses orchinik2024's 95%
   upper bound (1.69) to cap the range's high end while U4 of the same document says that reading
   is a LOWER bound on the target's τ. A reading cannot cap a range it is a floor for; under U4
   alone the high end reverts to 2.58 pp and the quote becomes 0.25–0.59. The published quote is
   kept — it is narrower, lower-topped, and was fixed before the number existed — and the report
   now says what it is. Third result, free: at the centre τ the **skill normalisation contributes
   ±0.122 of the quote's width and τ over its whole published range contributes ±0.139**, so a
   session that pins τ further and leaves the 0.66 skill factor alone halves nothing. And the
   projection's arithmetic is now known-answer tested: simulating the target's own design (16 arms,
   n = 529 per arm) recovers `project`'s ceiling to ±0.008 at τ = 0.5, 1.14, 2.58 and 5.0 pp.

100. **Two brief-authoring defects cost 67,732 billed tokens, and neither was fixable in the
   parser.** Finding 70 drew the line — "before hardening a parser, ask whether the model got the
   NAME wrong or the ANSWER wrong; only the first is yours to fix" — and this is the third
   category: the BRIEF was wrong. (a) kim2024's adapter renamed the raw condition codes
   (`consensus`, `causal`) to readable titles and left the raw codes in the sample description's
   arm-size sentence, so the brief gave each arm two names; `claude-opus-5` answered with the raw
   code and the parser correctly refused a name it was not given, losing all 22 cells after the
   calls were paid for. (b) dablander2025's arm titles contained a **comma** and the answer format
   is `condition,outcome,ate`; `claude-opus-5` quoted the field and parsed, `claude-sonnet-5`
   dropped the comma so its row would still have three fields, and lost all 25 cells — two frontier
   lines diverging on a defect that is purely formatting. Both are refused at plan time now
   (`assert_one_name_per_arm`, `assert_csv_safe_names` in `tools/practice.py`, red paths in
   `tools/test_gates.py`), and both are fixed **structurally**: the derived file stores the title so
   the adapter's arms map is the identity and no raw code exists, and no arm title contains a
   delimiter. The narrowness matters — the one-name check scans only the harness-written parts of a
   brief and never the stimulus, because `voelkel2024`'s stimulus really does contain the Qualtrics
   block name `Misperception_Competition` and redacting a stimulus changes the task (finding 22).
   **The harness writes the brief; a name the harness chose is the harness's bug.**

101. **`SSB_ARM` was already in the environment, and the run id on the board was not the run id on
   disk.** The operator's harness exports `SSB_ARM=main`, so `ssb.gates.new_run` began namespacing
   run directories the moment namespacing was implemented — and the first paid batch appended
   scoreboard rows under the UN-namespaced id while writing artefacts to the namespaced directory,
   so four rows pointed at a directory that did not exist. `tools/practice.py` and `tools/target.py`
   now resolve `ssb.gates.namespaced(run_id)` **before** the duplicate check, so the id that is
   checked, the directory that is created and the row that is appended are one string. The four
   rows were deleted with a backup at `runs/scoreboard.csv.pre-session17` (finding 47: clean up a
   run and its row together). A namespacing scheme that renames the directory and not the record is
   worse than none: it converts a collision into an orphan.

102. **The two highest ceilings on the board belong to the two newest tasks, and that is a warning
   as much as a licence.** kim2024 reads marginal 0.966 / within-outcome 0.949 and dablander2025
   0.976 / 0.966, against 0.53–0.93 for the eleven tasks before them. Neither is a better test: the
   signal is carried by cells nobody could get wrong — kim's `consensus_perceived` moves +10.8 pp
   in the arm that states a consensus percentage (a manipulation check), dablander's
   `perceived_radicalness` moves +18 to +24 pp for a blockade with a hundred arrests. The
   pre-registration therefore graded neither task on its ranking rows and put the scored verdicts on
   magnitude and on sign structure instead. **A high attainable-r ceiling says the human table is
   precise, not that the task is hard.**

103. **The first randomised US general-population message → trust-in-climate-scientists ATE, and
   the predictor lands on it.** kim2024's two message arms move a 4-point trust item by **+0.75 pp
   (causal evidence) and +1.57 pp (97% consensus), median 1.16 pp**, neither individually
   significant. Pre-registered band [0.3, 2.5] pp: `claude-opus-5` predicts **1.00**,
   `claude-fable-5` **1.25**, both PASS; `claude-sonnet-5` predicts **0.06** and FAILS, the second
   time sonnet has failed a pre-registered trust-magnitude verdict (finding 77). dablander2025's
   registered-report null on general science credibility reads human median **1.17 pp** against
   predicted **0.50 / 1.00 / 0.50** — no line invents an effect where a registered report found
   none. The trust magnitude series over **six** tasks is now human **0.42 / 2.16 / 4.33 / 1.14 /
   1.16 / 1.17** against predicted **0.90 / 1.20 / 1.60 / 0.80 / 1.00 / 0.50** pp, and the shape is
   unchanged from finding 94: the truth ranges over an order of magnitude and the prediction over a
   factor of three. The card's own 64 trust cells sit at **2.05 pp**, above five of the six human
   readings — the deposited (unshrunk) card remains the one closer to the randomised evidence, and
   ×1.5212 would take it to 3.12 pp, above all six. kim2024's slope is **β = 2.21 [1.76, 3.24]**,
   the largest on the board and a fifth reason not to shrink toward a pooled λ of 1.52 in the trust
   family: this task says multiply UP, orchinik said 1.0, and the two disagree by more than the
   correction is worth. `exclude_from_slope` was set in both adapters before any call.


104. **The Tier-1 distributional surface is set by the card's `control_sd`, not by the synthesis
   code — and exactly one of the thirteen values was wrong.** Section 4 (variance ratio, OVL,
   KS D, Wasserstein-1, the same four within every group with n ≥ 30) had never been scored
   against real humans. `tools/dist_audit.py` does it at 0 tokens, on the one thing the target
   shares with data the harness may read: the RESPONSE FORMAT. The four-part compatibility rule
   is stated before any number — same format read off the raw data (0-100 integer slider / $0-10
   integer / binary), same item-count class (a composite of k heaped items is not an item,
   standing finding 2), same item family (attitude vs orchinik's probability items vs a costly
   donation slider are separate pools, findings 6 and 7), control arm only. The synthesis itself
   is clean: `sd_ratio` 0.990-1.007 over a five-seed scan, and against a **construct twin** —
   same construct AND same native format, so level and spread are matched by the card's own
   anchoring and OVL/KS/W1 read SHAPE — the variance ratios are `concern_mean` **1.000**,
   `behavior_mean` 0.989, `policy_general` 0.985, `policy_specific_mean` 1.077,
   `donation_ams` 0.989, `newsletter_signup` 1.000. **`belief_post` reads 0.734 / 0.704 / 0.625**
   against the twin's three single items, and the cause is mechanical: the target's `belief_post`
   is a SINGLE 0-100 item (`codebook.csv` section A) and the deposited SD of 22.27 is
   `voelkel2026 Belief_Pre`'s **three-item composite** SD, exact to four decimals, with the twin's
   own identity closing it — `22.27 = 26.96 × sqrt(0.524 + 0.476/3)` at the measured rho = 0.524.
   Every single-item climate-belief slider in the mount sits above the deposited value (26.13,
   26.68, 28.32 in the twin; 32.89-33.90 in vlasceanu2024; 36.07 in goldwert2026). Corrected to
   the twin's implied 26.96 in `runs/20260822-target-01b-main` (PENDING-OPERATOR): the marginal
   variance ratio moves 0.464 → 0.655, OVL 0.622 → 0.666, KS 0.212 → 0.170, W1 11.53 → 7.98, and
   **nothing else moves** — Tier 2 and Tier 3 reproduce target-01's payloads to 0.0. A construct
   match is not an ITEM-COUNT match, which is standing finding 9 in the second moment.

105. **A distributional number needs both limits, and against a wrong-construct reference it has
   almost none.** Finding 93 said a correlation needs its ceiling and its null; the same is true
   of an overlap. `tools/dist_audit.py` measures both on humans only: the CEILING is two
   independent draws from one human column's own empirical distribution at the two sample sizes
   actually being compared (what a *perfect* synthesis would score — OVL **0.874** for single
   items, **0.915** for composites), and the FLOOR is two DIFFERENT human columns of the same
   format and item class (OVL **0.714** and **0.614**). The deposited rows read 0.62-0.72 on
   single items and 0.65-0.73 on composites — i.e. **against a human distribution of another
   construct our synthetic rows are not distinguishable from a real human distribution of another
   construct**, which is the most that a format-compatible stand-in can say. It follows that the
   wide format pool can only detect a FORMAT defect and that every construct claim has to come
   from the twin table, where the ceiling is 0.85-0.97 and our numbers are 0.66-1.00. And six of
   the thirteen outcomes have **no construct twin anywhere in the mounted data** — the four
   trust-family outcomes, `funding_perceptions` and `policy_role_mean` — so their variance ratios
   are unmeasurable here. That is finding 33's blindness, in a second scored section.

106. **Coarsening a slider is a format constant, and it runs the opposite way to the fear.**
   `notes/DATA_baselines.md` §1.3 warned in writing that "TISP SD is not a usable estimate of the
   target slider SD… the single biggest misuse risk for TISP", and `trust_multidimensional`'s
   deposited SD is nevertheless TISP's 12-item battery SD × 25. The correction is now measured
   rather than feared: take 49 real 0-100 items from three studies, coarsen each onto K equal-width
   categories, rescale, and read `SD_slider / SD_rescaled_coarse` = **0.958 (K=5), 0.940 (K=4),
   0.867 (K=3)** at item level and **0.966 / 0.956 / 0.879** at composite level, with a spread of
   0.947-0.962 at K=5 across items whose floor mass ranges from 0.001 to 0.31. So a rescaled
   coarse SD reads about **3-4% HIGH**, not low: TISP's 20.60 becomes 19.90, and the deposited 20.6
   is if anything slightly generous. The same pass measured TISP's own within-battery item
   correlation at **rho = 0.613** against the synthesis's declared 0.600 — the one declared
   constant in `ssb.synth` that a measurement confirms. Three other card SDs check out the same
   way (`trust_post` 30.0 against 30.97, `policy_role_mean` 26.0 against 25.04), and
   `funding_perceptions` 27.0 against 29.8 does not, but its only reference is a different
   construct so nothing is changed. **Measure a format effect on the same respondents before
   arguing about it between samples.**

107. **The within-cell spread of a human 0-100 slider falls as p(1-p), the synthesis holds it
   constant, and the fix works and was refused anyway.** Regressing log(group SD) on log(p(1-p))
   over 65 control-arm demographic cells of the design twin, with outcome fixed effects:
   **humans gamma = 1.003 (SE 0.073, R² 0.889)**, the deposited rows **0.195 (SE 0.052)**. A
   constant SD is gamma = 0 and a Beta of constant precision is gamma = 0.5, so humans are past
   both. The cost is on a scored row: party × `policy_general` within-subgroup variance ratios
   read **2.099 / 0.821 / 0.798** for Democrat / Independent / Republican, because the card's party
   MEANS are right to ~2 pp and its spreads are flat. Implemented as `ssb.synth.spread_gamma`
   (0.0 = the deposited behaviour, exactly), gamma = 1.0 moves the synthetic gamma to **0.82**,
   the three party cells to **1.036 / 0.975 / 1.025**, the median |within-subgroup VR − 1| over 271
   twin cells from 0.188 to 0.161 (0.121 with the belief_post fix), pooled OVL 0.704 → 0.724,
   W1 7.97 → 7.38, and even G6's Tier-2 moderator residual 1.732 → 1.650. **It was not adopted**,
   because the pre-registered no-regression guard fails: it moves the MARGINAL variance ratio of
   `belief_post` by 5-9 seed SD and of `policy_general` by 3 SD. The cause is named and is a defect
   of its own — `_solve_scale` pins the SD of the WHOLE FILE while `control_sd` is a control-arm
   SD and the frozen row is stated per CELL, and `fit_means` then moves respondents by ±5 AFTER the
   solve. Targeting the control arm (`scale_on_control=True`) cuts the drift from +4.5% to +1.5%
   and still fails. The next session's move is to solve the scale after the residual mean fit, or
   to make that fit spread-neutral; the measurement, the flag and the pre-registration are all on
   disk (`runs/_dist/PREREG.md` amendments 1 and 2).

108. **The dependency check that exists is not the same as the dependency check that runs.**
   `openpyxl` AND `pyreadstat` — two of the four declared dependencies, and the two that
   `vlasceanu2024`, `voelkel2024` and every TISP/CCAM/GSS measurement need — were both absent from
   the run interpreter at the start of this session, again (finding 97, session 16, session 17).
   `tools/test_gates.py` has carried the preflight since session 17 and it is correct; it simply
   had not been run before the first tool call, so the first failure was still a stack trace inside
   a measurement. **Run `tools/test_gates.py` before the first tool of any session.** Two more
   things came out of the same pass. The deposited 43,200 × 33 Tier-1 rows now **re-synthesise from
   today's `ssb.synth`** as a red-path case, which is what stands between a synthesis edit and a
   deposit that has quietly stopped reproducing from its card — it caught all three of this
   session's new flags defaulting correctly. And it caught something else on the way: the
   comparison must carry a 1e-12 tolerance, not 0, because **`pandas.read_csv`'s float parser is
   not correctly rounded** and a deposited CSV differs from the in-memory values that wrote it by
   1 ULP (1.42e-14 on a 0-100 scale) on ~13% of the non-integer composite rows. Standing finding
   61's "byte equality is the wrong test" has a floating-point half.
