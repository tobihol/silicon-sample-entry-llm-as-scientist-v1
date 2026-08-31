# Idea 01 — LLM-scientist harness with analysis-first prediction

> **Location note (deposit, 2026-08-31).** This file was the arm's design README in the
> team's working repository. In this deposit the pipeline lives at `run_record/pipeline/`:
> paths of the form `run/<x>` map to `<x>` in this directory (e.g. `run/tools/` → `tools/`,
> `run/.prime/…` → `.prime/…`). References to `../utils/` (the container launcher and
> shared infrastructure), the first session brief, and the frozen-definitions signature
> point to the code repository (registration K.1); `../idea_02/` and
> `docs/self-improvement-loop.md` refer to an internal predecessor arm and a working note,
> described narratively in registration J.1 and not deposited.

## Core idea

Use the **prime-agent harness** to frame the benchmark as an **LLM-as-scientist problem**:
instead of hand-designing a persona-simulation pipeline, the harness runs an agentic
scientist that reasons about the study, forms hypotheses about how the interventions will
move each outcome, and **self-improves on the benchmark's own analysis tasks** — trained
and validated on **our existing survey datasets**, where ground truth is known.

## Analysis-first, individuals second

The benchmark's preferred tier (Tier 1) asks for individual-level synthetic respondents.
Rather than simulating ~9,000 respondents item by item, invert the problem:

1. **Predict at the analysis level.** The LLM scientist works directly on the quantities
   the benchmark scores — treatment effects, condition × outcome means, subgroup
   moderation, and response distributions.
2. **Generate individuals backwards.** Synthesize the individual-level response data such
   that it reproduces those predicted analysis results when run through the scoring
   pipeline.

This gets the best of both worlds: the reasoning happens where the signal is (effects and
distributions, which the model can ground in literature and our training surveys), while
the submission still qualifies as Tier 1 and enters every analysis section.

## Self-improvement loop

Our survey datasets serve as training data: the harness repeatedly runs its
predict-then-synthesize pipeline against studies whose human results we hold, scores
itself with the benchmark's preregistered metrics (ATE recovery, calibration slope,
variance ratio, distributional overlap, demographic diagnostics), and iterates on its own
strategy — prompts, aggregation rules, distributional assumptions — before being run once,
blind, on the actual benchmark survey.

## Where the agent stops and the predictor begins (clarified 2026-08-24)

The description above can be read as "the agent predicts the study". As built, that is
true of everything **except the 208 effect sizes**, and the difference matters:

| level | who / what | sees | produces |
|---|---|---|---|
| **Outer loop** — the LLM scientist | Prime Agent session (claude-opus-5, IPython kernel, file system, budgets, gates, auto-refine) | everything mounted: benchmark materials, all 22 datasets incl. the practice studies' human outcomes, the literature it vendored, its own findings | the pipeline, the validation tasks, the calibration rules, baselines from survey microdata, subgroup offsets and their shrinkage, distribution shapes, the synthesis, every defect fix — and the *decision* how to treat the effect sizes |
| **Inner step** — the predictor | `ssb.predict`: a plain completion of the **same model**, fixed prompt, `--tools ""`, no session context | the target study's design materials only: preamble, verbatim message texts, outcome items and ranges (md5 of the prompt is identical across all deposited runs) | the raw 208 intervention × outcome effects (4 completions) |

So the agent does not write the effect sizes down itself; it asks a **blind instance of
itself** and then treats the answer as raw material. Nothing the agent learned during the
campaign — the 13 practice studies, the trust-literature anchors, the survey microdata —
is in the prompt of that call (the `fresheyes` arm tested appending three dataset-derived
scalars; no variant beat the plain prompt). The agent's knowledge enters the deposited
card only through the layers *around* the call: the refusal to scale magnitudes, the
baseline and offset layers, the distribution model, and the synthesis.

Two decisions produced this, and both are documented:

1. **Operator-set:** the frozen definitions (`run/.prime/agent/APPEND_SYSTEM.md`,
   "Calling a simulator") require any per-respondent simulator to be a plain completion,
   never an agent child — so that an agent runtime cannot change what the model says.
2. **Agent-set:** `run/DESIGN.md`, choice 3, extended that rule from simulators to the
   predictor itself, for a reason specific to this benchmark: the only ground truth the
   agent can validate against are *published* experiments, and "on a published training
   study the one thing an agent can always do is find the answer". A tool-less completion
   can be scored honestly on held-out studies and the same function is then applied to the
   target; blinding on the target holds by construction rather than by good behaviour.

**Consequence.** The ARC-AGI-3 analogy (`docs/self-improvement-loop.md`) is therefore
partial. In ARC-AGI-3 the agent plays the game itself and the environment scores it. Here
the agent builds and calibrates a fixed predictor, and the "game" — the held-out practice
score — is only honest for a function that cannot look things up. The direct version, in
which the agent *is* the predictor and validation outcomes are sealed outside the
container so that the score stays honest, is `../idea_02/`.

## Implementation

**Runtime: Prime Agent.** The harness follows the `gssim_prime` pattern (shared
infrastructure in `../utils/`, launcher `../utils/prime/run.sh`):

| | |
|---|---|
| `run/` | everything the container sees as its working directory |
| `run/.prime/agent/APPEND_SYSTEM.md` | **frozen**: the binding definitions — the target study's scoring tables, the blinding rules, the simulator call. Signed in `frozen.sha256`; re-sign after deliberate edits with `../utils/sign-frozen.sh idea_01` |
| `run/TASK_01.md` | the first (authoring-only) session task: design the loop |
| `run/AGENTS.md` | the agent's own file — the loop, once it designs it |
| `run/runs/<run-id>/` | run products |

First session:

```bash
docker build -t ssb-prime:latest utils/prime/     # once
SSB_IDEA=idea_01 SSB_ARM=fresh ./utils/prime/run.sh \
    --mode json --autonomous "$(cat idea_01/run/TASK_01.md)"
```

In-container the session sees the submission template read-only at `/workspace/benchmark`
and the public training data (GSS, ACS) read-only at `/workspace/datasets` — and nothing
else. See `../utils/README.md` for logins, arms, and snapshots.

## Constraints to respect

- The backward-generation step must target predicted **distributions** (per condition and
  subgroup), not just means — Tier 1 is scored on variance ratio, overlap/KS/Wasserstein,
  and demographic predictability, where naive synthesis would fail.
- The pipeline must remain **fully automated and AI-based**, with no access to human
  outcome data from the benchmark study itself; our training data must be external
  datasets only.
- The full loop (harness, prompts, training setup, synthesis code) gets documented in the
  registration form.
