# The frozen definitions

Everything below is fixed for the duration of a run. You may not edit this file, restate it
in your own words elsewhere, or work around it locally. If something here is wrong or
missing, say so in `OPEN.md` and continue under it. A gate checks this file's hash before a
run may finish.

Everything *not* in this file — `AGENTS.md`, the skills you write, your harness state — is
yours to change.

## What you build

**An LLM scientist that predicts a sealed behavioral megastudy, analysis-first.** The target
study tests 16 message interventions (plus control) for increasing trust in climate
scientists on ~18,000 U.S. adults (census-based quotas on age, gender, race/ethnicity), and
is scored on 13 outcomes. Your product is (a) predictions of the target study's *analysis
results* — treatment effects, condition × outcome means, subgroup moderation, response
distributions — and (b) an individual-level synthetic dataset (Tier 1) generated **backwards
from those predictions**, such that running the benchmark's analyses on it reproduces them.

You improve by practicing: carve analysis tasks with held-out ground truth from the training
datasets, predict them blind, score yourself with the tables below, and refine what failed.

## Words

- **target study** — the sealed megastudy. Its instrument, codebook and validator are at
  `/workspace/benchmark`; its human results do not exist for you.
- **training task** — an analysis task carved from `/workspace/datasets/*` whose ground
  truth is computed locally and held out from the predictor.
- **entry** — one complete set of predictions for the target study at one tier.
- **analysis-first** — predictions are made at the level the benchmark scores, never as a
  side effect of item-by-item simulation.
- **backward synthesis** — generating individual rows to match predicted analysis results:
  cells, moderation, *and* distributions. A synthesis that matches means but not spread is
  a failed synthesis.
- **operator** — the human. Owns the budget, the model list, and the deposit decision.

Prefer a plain description over a coined term.

## The target study's scoring — binding

Predictions are scored against one half of the human sample ("Human 1"); the other half's
agreement with it is the replication ceiling. Two scripted baselines frame every metric: the
**no-effect floor** (every ATE zero; earns 50% directional credit) and the **all-positive
baseline** (every intervention helps). All effects are converted to **percentage points of
each outcome's scale range** before pooling (0–100 sliders → pp; $0–10 donation → pp, so
$0.30 = 3 pp; 0/1 signup → pp) across all 16 × 13 = 208 intervention × outcome effects.

### 1. ATE recovery (all tiers)

| Metric | The question |
|---|---|
| Directional agreement | Does each predicted effect have the human sign? (a zero prediction scores 0.5) |
| Spearman ρ | Do the interventions rank in the human order? |
| Pearson r | Are predicted effects proportional to human effects? |
| Pearson r within outcomes | Outcome fixed effects removed: message-level skill only, not generic outcome knowledge |
| RMSE (pp) | Absolute magnitude error |
| r_adj, RMSE_adj | The same, disattenuated for sampling noise in the human reference |

### 2. Calibration (all tiers)

Human ATEs regressed on predicted ATEs, pooled over all 208 effects: intercept **α = 0** and
slope **β = 1** is perfect calibration; β < 1 means systematic exaggeration.

### 3. Subgroup heterogeneity (Tiers 1–2)

Section-1 metrics minus RMSE, on condition × moderator interactions for six moderators:
gender, age band (18-29 / 30-44 / 45-59 / 60+), race/ethnicity, education, income, partisan
identity.

### 4. Distributions and demographic diagnostics (Tier 1; last two also Tier 2)

| Metric | The question |
|---|---|
| **Variance ratio** | Headline diagnostic. synthetic/human variance per cell; < 1 is the documented LLM failure mode (under-dispersion) |
| Overlap (OVL), KS D, Wasserstein-1 | Does the response *distribution* match, on fixed grids (0–100; $0–10)? |
| Within-subgroup distributions | The same four, within each demographic group with n ≥ 30 |
| Demographic baseline RMSE | Control-condition subgroup means per moderator |
| Demographic parity gap | Worst-served minus best-served demographic group |
| Demographic predictability | R² of outcomes on moderators: does the synthetic data exaggerate group differences relative to humans? |

| Rule | |
|---|---|
| Coverage | All 17 conditions and all 13 outcomes, every cell exactly once, no NA anywhere. Partial coverage does not exist. |
| Tier-1 floor | ≥ 500 respondents per intervention, ≥ 1,000 in control. Beyond precision, a larger pool buys nothing — only point estimates are scored. |
| Composites | Scored **as submitted**, never recomputed from items. A composite inconsistent with its items is scored on the deviant values. |
| Self-scoring | When you score a training task, use these metrics and no others. A metric invented to look better is not a score. |

## Blinding — absolute

- You never seek, ingest, or infer from human outcome data of the target study — including
  its pilots, preprints about it, or anything derived from them. If you encounter any,
  stop, record where, and tell the operator.
- Training ground truth comes from `/workspace/datasets/*` and published literature on
  *other* studies only.
- The pipeline is AI-based and fully automated end to end: no human edits a prediction.

## Calling a simulator

If any stage uses per-respondent generation, a simulator is a **plain completion**: fixed
system prompt, one user message, no tools, no retrieval, no filesystem, no agent wrapper.
Never an `rlm()` child — an agent runtime changes what the model says.

```bash
env -u ANTHROPIC_API_KEY -u ANTHROPIC_AUTH_TOKEN MAX_THINKING_TOKENS=0 \
  claude -p "<user text>" --system-prompt "<system text>" --tools "" \
  --settings '{"claudeMdExcludes":["**"]}' \
  --no-session-persistence --output-format json --model <model-id>
```

Every part of that line was earned (an exported API key silently bills the metered API;
thinking defaults on; print mode loads ancestor CLAUDE.md files). Use the provider's default
sampling; never tune it per task. Cache responses under a key covering the prompt **and**
every sampling parameter.

## Budget

Model calls come out of a Claude subscription window shared with other work. Ask the
operator before any batch. The target study's prediction lock is **August 31, 2026** — a
deposit the operator makes, never you.

## Refinement

When you refine this harness from your own trajectory, record what changed, what evidence
motivated it, and which scoring table row it was meant to move. Nothing here judges its own
output, so that record is the only thing that makes a refinement checkable later.
