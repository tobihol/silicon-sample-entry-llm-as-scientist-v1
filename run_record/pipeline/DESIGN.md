# DESIGN.md

## What the loop is

One prediction object — a **card** — and a pipeline that practises against held-out ground
truth before filling it in.

The card holds every number the harness predicts: 13 control-condition means and SDs, 27×13
subgroup offsets, 208 intervention × outcome ATEs, 27 responsiveness factors and a sparse
tilt table. Tier 3, Tier 2 (main and moderator) and Tier 1 are all *derived* from it. The
three deposited entries therefore cannot contradict each other, and "does the synthetic
dataset reproduce the predicted analyses" becomes a measurement (gate G6) rather than a hope.

The loop: build inputs once → carve training tasks with sealed ground truth → predict each
blind → score with the frozen metrics → fit a calibration slope on the (predicted, human)
pairs → predict the target with the same prompt → apply the slope → assemble the card →
synthesise Tier-1 rows backwards from it → run the benchmark's own R validator → record.
Stages, gates and the stopping rule are in `AGENTS.md`; the API is in `ssb/SKILL.md`.

## The three most consequential choices

**1. The predictor supplies ordering; a fitted slope supplies magnitude.**
Practice cannot teach a model what the trust effects are — no dataset randomises messages onto
trust outcomes. What practice *can* estimate is how much this predictor exaggerates, and that
transfers. On a synthetic demonstration with a predictor whose ranking was near-perfect
(Spearman ρ = 0.95, Pearson r = 0.96) but whose slope was β = 0.42, RMSE was **1.98 pp —
worse than the no-effect floor's 1.51 pp**. Multiplying by the fitted through-origin slope
took RMSE to 0.40 pp and β to 0.98, with the ranking untouched. So the loop separates the two
skills and only claims transfer for the second.
*Rejected:* trusting the predictor's absolute percentage points. It is the documented failure
mode, it is what the Calibration row is built to catch, and it loses to a script that predicts
nothing.

**2. Backward synthesis from a parametric card, deposited well above the precision floor.**
Rows are drawn to hit predicted means, predicted moderation *and* human-anchored spread; the
per-cell SD comes from human data and the generator bisects on the latent SD until the SD
*after* rounding and heaping matches it. Measured SD ratios are 0.99–1.01 across all 13
outcomes, so the headline variance-ratio row is engineered rather than hoped for. The
measurement that changed the design: at the preregistered floor, the ATEs recomputed from our
own rows correlated only **0.67** with the card (RMSE 1.13 pp) — the deposit would have been
scored on our sampling noise. Raising the pool and adding a residual mean fit took that to
r = 1.000, RMSE 0.006 pp. The floor buys nothing beyond precision, but precision is exactly
what a Tier-1 deposit needs, because the scored point estimate is computed from our rows.
*Rejected:* per-respondent LLM simulation aggregated into analyses. It costs ~10⁵ calls,
inverts the required direction (analysis-first), and walks straight into under-dispersion,
which is the one failure the Tier-1 table names as the headline diagnostic.

**3. The predictor is a plain, tool-less completion — not an `rlm()` child.**
Blinding then holds by construction: a process with no filesystem and no retrieval cannot read
the sealed truth beside its brief, cannot look up the source study, and cannot go hunting for
the target study. `rlm()` children do the harness work (reconnaissance, adapters, review) and
never produce a prediction. `leak_audit` still greps every transcript for the sealed path,
hash and values, and the verdict is a scoreboard column.
*Rejected:* an agentic predictor that reads `brief/` from disk. It predicts better on paper —
and its practice scores would be uninterpretable, because on a *published* training study the
one thing an agent can always do is find the answer.

---

# Below the fold

## Why moderation is low-rank

The moderator grid has 5,967 cells and the benchmark refuses NAs. Eliciting 5,616 subgroup
ATEs from a language model would produce noise that no scoring row rewards. The card instead
carries 27 responsiveness factors (how much a group moves at all) plus a sparse tilt table for
the few condition × group beliefs worth stating — e.g. a social-justice framing landing
differently on Republicans. A share-weighted normaliser forces subgroup ATEs to average back
to the marginal ATE, so the Tier-2 moderator file can never contradict the Tier-2 main file.
Setting every factor to 1 is the honest floor: it predicts "this works the same for everyone",
fills the grid completely, and is what the benchmark's FAQ recommends when you have no belief.

## Why composites are built from items

`policy_specific_mean` is the mean of seven 0–100 slider items. Humans heap on multiples of 5
at the *item* level (orchinik2024: 42.5% multiples of 5, 32.3% multiples of 10, 13.7% at the
top endpoint); the mean of seven such items is finely grained and barely heaped. Generating
the composite directly and heaping it produces a distribution no human sample has, which the
OVL / KS D / Wasserstein-1 rows would see immediately. The harness therefore draws k latent
items per composite, heaps each, and averages — after solving for the item SD that yields the
target composite SD. Realised: single items 44–50% on multiples of 5, composites 5–17%, and
`trust_multidimensional` (12 items) 2,305 distinct values in 21,600 rows.
`trust_multidimensional` is computed from the 12 shipped items exactly as `codebook.csv`
defines it, so the composite and its items can never disagree — the frozen Composites rule
scores it as submitted, and the validator warns when they diverge.

## What the training datasets can and cannot do

The honest asymmetry, recorded as a finding. **None of the five multi-arm experiments
randomises messages onto trust in scientists.** `voelkel2026` is a genuine design twin —
same delivery mode, same 0–100 sliders, same quota panel, all six moderators, and its
`Concern_*`, `Policies_Post_3` and `IntentNp_*` items are *verbatim* five of the target's
outcomes; its three control texts are the *same three filler texts* the target uses. But it
has zero trust outcomes. `vlasceanu2024` supplies `belief_post` and seven `policy_specific_*`
items verbatim, but ships no message texts, so it can train levels and not ranking.
`goldwert2026` is the only source for donation in dollars and a 0/1 newsletter signup.
`bbprime2025` and `voelkel2024` are process practice.

So the calibration slope is fitted on non-trust outcomes and *transferred* to trust outcomes.
That is the single largest inferential leap in the design, and it is why the trust-outcome
prior is set separately, from `gligoric2025`: five randomised trust-raising messages,
**−0.22 to +0.83 pp**, all equivalence-bounded below d = 0.1 — in conservatives only, on a
one-sentence dose, against a control mean already at 69 pp of the scale. That null does not
license "trust ATEs are zero" for a general-population sample reading a 200–1,600 word text.
It does license a hard prior that they are *small*, and a standing rule that any predicted
trust ATE materially above 1–2 pp must have its warrant written into the run report.

The observational baselines anchor levels, not effects. `tisp` is decisive for levels: the
target's 12 trust items are the TISP items reworded from "most scientists" to "most climate
scientists" (11 of 12 verbatim, per `codebook.csv`), and its `policy_role_*` and five
`policy_specific_*` items are verbatim TISP too. But TISP has **no race and no party**, which
are two of the six moderators. `pew_atp` (mounted for run 03) closes that: W100+W114 carry a
trust-in-scientists item with party, race and gender in one probability panel, so all 351
subgroup-offset cells are now anchored — **but on a 4-point verbal scale**, which anchors
orderings and gaps and cannot anchor a level (the gap transfer was measured at 0.808; the level
bridge was not measurable at all). Levels stay on TISP; gaps come from Pew. `ccam` has race and
party on climate content but no trust item.

A second asymmetry, learned from `goldwert2026`: **a training task can be sound for ordering and
useless for magnitude, and the pipeline has to be able to say so.** Its differential attrition
(observation rates 0.675–0.867 by arm) leaves Lee bounds ~10.6 pp wide around effects of ~2.4 pp.
The task is still carved and scored; it is simply flagged out of the fitted magnitude map. Any
future task with a bounded estimand joins it there rather than being dropped or trusted.

## Structure of the instrument that the prediction has to respect

- `belief_post` and `trust_post` are **re-asked**: the same respondent answered `belief_pre`
  and `trust_pre` minutes earlier. Own-answer anchoring should compress effects on these two
  relative to the never-before-asked composite.
- `distrust_post` is reverse-valenced. A message that raises trust lowers it. The all-positive
  scripted baseline is therefore wrong on 16 of the 208 cells by construction.
- `funding_perceptions` is already reversed in cleaning (`100 − funding_5`), so it points the
  same way as the rest.
- `newsletter_signup` requires leaving the survey tab; `donation_ams` gives away real money.
  Both are costly acts with low base rates and correspondingly small pp movements.
- Dose varies 94 to 1,628 words across the 16 texts. Length is confounded with content — in
  `voelkel2026` too, which is the one place that confound could be measured.

## Cost shape

Prediction is `n_draws` completions of ~12k input tokens each, per task and for the target.
Synthesis, scoring, derivation and validation are free local compute. The expensive thing the
design deliberately does not do is generate 200,000 respondents with a language model.
