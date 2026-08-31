# Silicon Sample Benchmark — method registration form

Fill in every item before the prediction lock; this file ships inside your repo's Zenodo release
(see the README's *Deposit* step). This form covers **one entry** (one repo / one Zenodo release,
`primary` or `secondary-k` — see the README's *What counts as a submission*); if you submit several
entries, fill one form per entry. Items marked **★**
must be disclosed **fully publicly** (never escrowed or withheld). Items marked **†** must be at
minimum escrowed — they may be sealed from the public, but never withheld from the core team. Items
not applicable to your approach: write `N/A`. When several models serve different pipeline stages, complete the model
sections (B) once per model. See the call's *Disclosure policy* for escrow rules.

---

## 0 · Approach identity and output
- **0.1 Team ★** — team_31. Registered members: Tobias Holtdirk (LMU Munich, corresponding contact: tobias.holtdirk@lmu.de) and Bolei Ma (LMU Munich). Contributor, not a registered member: Haiwen Huang (MPI-IS).
- **0.2 Plain-language summary ★** — Dataset acquisition → agent loop → derivation of individual-level rows. The predictions are analysis-first: the study's published analysis table is predicted directly and the individual-level rows are synthesized backwards from it, so that re-running the benchmark's analyses on the rows reproduces it. The loop has a prescribed strategy and self-administered testing. The start state fixes the strategy and the materials: predict analysis-first, improve by practicing on tasks built from published data, and build the entry from nothing but that data plus plain model completions (fixed prompts, no tools, no agent runtime, thinking off). The deposited entry is therefore independent of the building agent's own reasoning: it reproduces from code, data, and a handful of cached completions. Testing was self-administered: practice ground truth sat in the loop's own filesystem, held out only by its own discipline, with no external rules. Outcome: the model states the 16 × 13 effect table in one prompt (three completions, cell-wise median), with control levels and subgroup offsets anchored on public surveys. Same family as the team's primary entry (LLM as scientist): here the strategy is prescribed and the prediction path restricted to plain model completions, while the primary leaves the path free and restricts information instead.
- **0.3 Submission tier & approach family ★** — Tier 1. Family: direct forecasting (analysis-level effect forecast; no per-respondent simulation, no survey walk-through); single model; zero-shot for the effects (one fixed prompt), literature-conditioned for control levels and subgroup offsets (published survey aggregates).
- **0.4 Pipeline diagram** — dataset acquisition → prime-agent loop → derivation of individual-level rows → `predictions/team_31_T1_secondary-1_v1.csv`.
- **0.5 Coverage ★** — 208 predicted cells = 16 interventions × 13 outcomes, all 17 conditions present, every cell exactly once, no NA.

## A · Scope of LLM use
- **A.1 Purpose** — N/A
- **A.2 Degree of automation ★** — Fully automated; no human in the loop at prediction time.

## B · Model / system details (once per model)
- **B.1 Model name(s)** — `claude-opus-5` (Anthropic), in two roles. Agent: the loop that designed and ran the pipeline, via Prime Agent 0.7.2 (release pinned in `utils/prime/Dockerfile`) over the Claude Code CLI. Predictor: the plain completions the pipeline calls, `claude -p` over Claude Code CLI 2.1.220.
- **B.2 Access & context mode** — Agent: subscription login, agentic chat sessions in a Docker container with the repository mounted, 2026-08-15 → 2026-08-20 (24 launched sessions; ledger: `run_record/pipeline/progress-ledger.md`). Predictor: stateless `claude -p` (`--no-session-persistence`), one user message per call, no chat history, no tools; target calls 2026-08-15 (run `20260815-target-01`, whose completions this entry reuses).
- **B.3 Configuration** — Provider-default sampling in both roles. Agent: per-session wall/turn/token budgets. Predictor: thinking disabled (`MAX_THINKING_TOKENS=0`), no overrides, 3 completions per prompt, one prompt covering all 208 cells.
- **B.4 Customization** — No fine-tuning. Agent: tool use inside its container sandbox (filesystem, Python) on published data only; scaffold: Prime Agent with the frozen `APPEND_SYSTEM.md`. Predictor: no tools, no retrieval, no web access — the frozen definitions require a plain completion with no agent runtime.
- **B.5 Persistent memory** — Agent: durable state only through its own files in the mounted run tree. Predictor: none (stateless calls).
- **B.6 Inference stack** — N/A (hosted model).
- **B.7 Ensembles** — No multi-model ensemble. The predictor's 3 completions of the identical prompt are aggregated cell-wise by median (F.2).

## C · Prompts
- **C.1 Exact prompts** — Agent: the frozen system append and the first session brief are deposited in `code_repository` (`llm-as-scientist-v1/run/.prime/agent/APPEND_SYSTEM.md`, `llm-as-scientist-v1/run/TASK_01.md`). Predictor: deposited verbatim — `run_record/prompts/system.txt`, `run_record/prompts/user.txt` (verbatim message texts, item wordings, sample description, arm sizes; asks for an arm × outcome effect table in percentage points) and the blinding probe (`probe_system.txt` / `probe_user.txt`).
- **C.2 System-wide instructions** — Agent: `APPEND_SYSTEM.md` (code repository). Predictor: `run_record/prompts/system.txt`.
- **C.3 Prompt-design rationale** — Agent append: fixes the strategy and the materials (analysis-first, practice on published data, plain completions only) and leaves the pipeline design to the agent. Predictor prompts: practice and target share one shape and one size band so a practice score and a target score mean the same thing; effects are asked in a common unit (pp of scale range) so calibration can be fitted across studies.

## D · Persona / profile construction (Tiers 1–2)
- **D.1 Profile source** — Public survey microdata (ACS/CES) used to build a joint demographic pool (`run_record/pipeline/tools/build_pool.py`); condition assignment by the harness. Control levels and subgroup offsets anchored on Pew ATP, GSS, TISP, CCAM aggregates (`run_record/pipeline/inputs/baselines/provenance.json`).
- **D.2 Profile verbalization** — N/A.
- **D.3 Assignment & weighting** — 43,200 synthetic respondents over all 17 conditions, 2,400 per intervention and 4,800 in control, drawn from the joint pool to the census quotas; no reuse across conditions.

## E · Stimulus and survey administration
- **E.1 Stimulus presentation** — Verbatim in the prediction prompt.
- **E.2 Survey walk-through** — N/A.
- **E.3 Response elicitation** — Constrained structured output: a CSV of condition, outcome and effect in percentage points, parsed by `ssb.predict.parse`.

## F · Stochasticity and aggregation
- **F.1 Runs & seeds** — 3 completions per prompt at provider-default sampling; the API exposes no seed, so completions are not bit-reproducible, but each is cached and deposited verbatim (`raw_model_logs/`, `MANIFEST.sha256`). Backward synthesis is seeded and its recovery gate was scanned over 5 seeds (`run_record/gates.json`, G6).
- **F.2 Aggregation rule** — Cell-wise median across the 3 draws.

## G · Validation & post-processing
- **G.1 Human validation** — None. No human reviewed, edited or selected any prediction.
- **G.2 Post-processing** — Parser tolerant to delimiter/format variation; unparsed cell aborts; no exclusions; no refusals encountered. Percentage points converted to each outcome's native unit (sliders 0–100; `donation_ams` dollars; `newsletter_signup` proportion) with a clipping report that aborts if non-empty. Effective N: 2,400 per intervention, 4,800 control.
- **G.3 Calibration corrections** — None.

## H · Learning and conditioning components
- **H.1 Fine-tuning data** — N/A.
- **H.2 Context & retrieval corpora** — Material in the agent's working context: the benchmark materials, the published experiments and survey sources listed under I.2 (mounted in its container), and the pipeline's own inputs and notes (`run_record/pipeline/`). The datasets are documented with licences and fetch scripts in `code_repository/data/README.md`. The predictor's context is only the deposited prompt (C.1); no retrieval.

## I · Data inputs, blinding, and competing interests
- **I.1 Competing interests ★** — no relationship with LLM-vendor entities beyond being customers.
- **I.2 External human data †** — Published experiments carved into practice tasks for the calibration fit and the design-space search (13 studies: altenmueller2024, bbprime2025, beall2017, bokemper2022 (E1/E2, referee only), dablander2025, gligoric2025, goldwert2026, hackenburg2025, kerwer2025, kim2024, koetke2024, orchinik2024, tappin2023, vlasceanu2024, voelkel2024, voelkel2026); public survey sources for control levels and subgroup offsets (Pew ATP waves, GSS 2016–2024, TISP, CCAM, ACS/CES pool). All documented with licences in `code_repository/data/README.md`; no restricted respondent-level data is deposited.
- **I.3 Blinding attestation ★** — "Signed for team_31 by Tobias Holtdirk, 2026-08-31; covers both registered members (Tobias Holtdirk, Bolei Ma) and the contributor Haiwen Huang."
- **I.4 Contamination note †** — claude-opus-5; training-data and reliable-knowledge cutoff **May 2026** (Anthropic models documentation, checked 2026-08-31).

## J · Internal selection procedure
- **J.1 Design-space search †** — The pipeline's own design choices were validated on practice tasks built from published experiments (`run_record/pipeline/runs/scoreboard.csv`). Selection between the team's candidate methods used held-out published studies (bbprime2025, bokemper2022): this entry was designated secondary-1 after the primary cleared a pre-registered bar there.

## K · Reproducibility & frozen artifacts
- **K.1 Code & materials** — `code_repository`: https://github.com/tobihol/silicon-sample-submission (directory `llm-as-scientist-v1/` — holding the campaign environment and start state.) Snapshot DOI: [10.5281/zenodo.22214502](https://doi.org/10.5281/zenodo.22214502) (`metadata.json.code_doi`). run records and the completed pipeline (code, `ssb` package, inputs, dataset notes, harness definitions) duplicated in this deposit under `run_record/` and `run_record/pipeline/`.
- **K.2 Raw output logs †** — `raw_model_logs/`: 4 prompts, 4 unprocessed completions (3 prediction draws + 1 blinding probe), 4 provider JSON envelopes (model id, billed usage, timing), `MANIFEST.sha256` (verifies under `sha256sum -c`). These are the complete model outputs behind this entry's effect table (this run made zero model calls of its own; see `raw_model_logs/README_target-04.md`). The building agent's own session transcripts are not part of this deposit: the entry reproduces from the deposited completions, data and code alone.
- **K.3 Computational resources** — Agent loop: ≈ 463 M tokens (`run_record/pipeline/progress-ledger.md`). Predictor: ≈ 4.5 M billed tokens, of which ≈ 1.06 M are the deposited pipeline's practice and target calls (`run_record/prompts/cost.json` / `spend.json`).

## L · Disclosure class
**A · Open.** Every item is public in this deposit or in `code_repository`; nothing is escrowed or withheld.

★ items must always be public (never escrowed or withheld); † items must be at minimum escrowed. Full
policy: <https://janpfander.github.io/llm_predictions_megastudy/#disclosure>
