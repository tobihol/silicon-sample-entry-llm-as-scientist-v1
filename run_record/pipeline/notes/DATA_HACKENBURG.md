# DATA_HACKENBURG — can hackenburg2025 carry a high-arm-count practice task, and does it have signal?

Recon session, harness child. Read-only pass over `/workspace/datasets/hackenburg2025` (plus a
bridge pass over `tappin2023`). Nothing in `/workspace/run` was modified except this file and
`runs/_scratch/hackenburg_power.csv`. No adapter JSON was written. No model call of any kind was
made. **No prediction of any study's effects appears anywhere below** — every number here is a
description of human data already on disk.

**VERDICT (in full at the bottom): CARVABLE — exactly ONE issue, `solitary_confinement`.**
73 arms, verbatim texts, one shared control, `var_signal = 92.1` and an attainable-r ceiling of
**0.824** (empirical split-half `r = 0.590`, the highest of any table this harness has measured).
`veteran healthcare` is a defensible second (ceiling 0.623). **The other eight issues fail
`tools/task_power.py`**: six have ceilings 0.16–0.48 and two have *negative* signal variance.
Two structural costs, both real: the brief is ~2.4x the target's prompt size and must be split,
and the arms are LLM-generated messages of wildly varying quality, so a large share of the signal
is "is this message coherent and on the right side" rather than "which good argument works".

---

## 1. Exact paths

| what | path | shape |
|---|---|---|
| **canonical microdata** | `downloads/main_study/code/analysis/final_data_with_metrics.csv` | 25,982 x 113 |
| raw Qualtrics export | `downloads/main_study/code/analysis/raw_data_final.csv` | 35,858 x 67 (+1 header row) |
| **item wordings (verbatim)** | row 2 of `raw_data_final.csv` (the Qualtrics label row) | 40 item texts |
| prompt templates | `downloads/main_study/code/analysis/prompts.csv` | 30 x 8 |
| de-facto codebook | `1_prepare_data.R`, `2_fit_models.R`, `3_make_plots.R`, `4_is_this_AI_analysis.R`, `5_nonlinear_comparisons.R` | |
| SI | `downloads/SI_Appendix.pdf` | 927 KB |

All paths relative to `/workspace/datasets/hackenburg2025/`. US Prolific sample; `age` 18–100
(mean 38.7), 56.8% Female, 20.8%/26.6% Strong/Moderate Democrat against 7.1%/12.9%
Strong/Moderate Republican — **a young, Democrat-leaning convenience panel, not a census quota**.

`final_data_with_metrics.csv` is *already cleaned*: `attention_check` has exactly one level
(`On-line sources only`, i.e. only passers survive) and 35,858 raw rows become 25,982. **The
script that performs that reduction is not in the mirror** — `1_prepare_data.R` reads the cleaned
file. So the exclusion rule is inferred (attention check + `Finished` + assigned-condition
non-missing: raw has 9,687 rows with a null `condition`), not read. Caveat, not a blocker: a
carve would use the authors' own analysis file, which is what their paper reports.

## 2. Arm structure — how the 730 messages are encoded

| column | what it is |
|---|---|
| `condition` | `AI` 19,529 / `control` 5,163 / `human` 1,290 |
| `treatment_message_id` | **the arm.** 730 levels, `<issue_short>_<model>_<prompt_variant>` e.g. `ban_solitary_confinement_juveniles_claude-3-opus-20240229_2`; NaN in control |
| `treatment_message` | **the verbatim message text.** Confirmed 1:1 with `treatment_message_id` (730 distinct texts <-> 730 ids, both directions), full prose, not an id |
| `message_id` | numeric twin of `treatment_message_id` (730 levels) |
| `issue` | 10 levels; every arm id belongs to exactly one issue (checked: `nunique(issue) == 1` per id) |
| `model`, `model_family`, `parameters`, `pretraining_tokens` | generation provenance: 24 LLMs in 7 families + `human` |
| `prompt_variant_number` (1–3), `prompt_variant_template`, `prompt_full_text` | the 3 prompt phrasings, all "~200 words, persuasive, respond with only the message" |
| `condition_assignment` | 0–100 randomisation **slot**, not an arm: 76 AI slots, 20 control slots, 5 human slots. A slot spans all 10 issues and 23–24 models (big models were deliberately over-sampled), so it is a design artefact and an adapter should ignore it |
| `treatment_message_word_count`, `flesch`, `moral_nonmoral_ratio`, `emotion_proportion`, `type_token_ratio`, `gpt_legibility`, `gpt_on_topic`, `gpt_valence`, `valence_correct`, `task_completion` | message-level text metrics, constant within arm |

**72 + 1 arms per issue.** 24 models x 3 prompt variants = 72 LLM messages, plus 1 expert-written
human message = **73 arms per issue on all 10 issues**, and a per-issue control group.

**Control is identified by `condition == "control"`** — 5,163 rows, `treatment_message` null on
every one of them. Control respondents ARE assigned an issue (471–557 per issue) and answer only
that issue's items, so each issue has its own control group of ~500.

**Per-arm n is the weak point.** Within an issue: min 3, 25th pct 11, **median 16**, 75th pct
~30, max 158 (the human arm and the frontier models). That is what drives the median SE of
5.3–7.7 pp in §3.

Balance is clean at the condition level (control vs AI vs human differ by <0.05 on
`political_party`, `age`, `political_knowledge`, %Female, %grad). Across the 73 arms of
`solitary_confinement` the sd of arm-mean `political_party` is 0.354 against 0.308 expected under
pure random assignment (variance ratio 1.32, 72 df, p ~= 0.06) — consistent with chance, worth
one line in a run report and no more.

## 3. Per-issue ATE tables and power

Method, per issue: **arms** = the 73 `treatment_message_id` levels; **control** = the same
`condition == "control"` rows for that issue; ATE = treated mean − control mean; SE = unpooled
two-sample. Outcomes are already 0–100 sliders, so pp of scale range = raw units.
`var_signal = var(observed ATE) − mean(SE^2)` and `max r` are from
`tools/task_power.py`'s `power(ate, se)`, unmodified.

### Primary DV = `<issue>_mean` (= `dv_response_mean`, verified identical to 0.0), 73 cells

| issue | arms | cells | med \|ATE\| | med SE | var_obs | var_noise | var_signal | max r |
|---|---|---|---|---|---|---|---|---|
| `solitary_confinement` | 73 | 73 | 8.96 | 5.70 | 135.7 | 43.6 | 92.1 | **0.824** |
| `veteran healthcare` | 73 | 73 | 11.82 | 7.51 | 103.6 | 63.4 | 40.2 | **0.623** |
| `electoral_college` | 73 | 73 | 7.11 | 7.45 | 78.5 | 60.8 | 17.7 | **0.475** |
| `felons_voting` | 73 | 73 | 6.88 | 5.83 | 46.6 | 40.6 | 6.0 | **0.359** |
| `medicaid` | 73 | 73 | 8.32 | 7.24 | 71.6 | 66.0 | 5.6 | **0.280** |
| `foreign_aid` | 73 | 73 | 8.15 | 5.26 | 39.9 | 36.2 | 3.8 | **0.307** |
| `assisted suicide` | 73 | 73 | 6.81 | 6.52 | 54.9 | 53.0 | 1.8 | **0.183** |
| `affirmative_action` | 73 | 73 | 4.70 | 6.53 | 54.0 | 52.7 | 1.3 | **0.157** |
| `border_restrictions` | 73 | 73 | 5.13 | 7.27 | 69.5 | 69.6 | **−0.1** | 0.000 |
| `worker_pensions` | 73 | 73 | 10.03 | 5.99 | 45.7 | 49.1 | **−3.4** | 0.000 |

### Four items as separate outcomes (`-1`, `-2-reversed`, `-3`, `-4`), 292 cells

| issue | arms | cells | med \|ATE\| | med SE | var_obs | var_noise | var_signal | max r |
|---|---|---|---|---|---|---|---|---|
| `solitary_confinement` | 73 | 292 | 11.37 | 7.48 | 184.3 | 77.1 | 107.2 | **0.763** |
| `veteran healthcare` | 73 | 292 | 12.28 | 7.74 | 110.2 | 70.7 | 39.5 | **0.599** |
| `electoral_college` | 73 | 292 | 6.97 | 7.63 | 84.7 | 67.9 | 16.9 | **0.446** |
| `foreign_aid` | 73 | 292 | 8.93 | 7.07 | 68.8 | 58.8 | 9.9 | **0.380** |
| `felons_voting` | 73 | 292 | 8.33 | 7.76 | 78.3 | 71.5 | 6.8 | **0.294** |
| `medicaid` | 73 | 292 | 7.68 | 7.70 | 79.4 | 74.8 | 4.7 | **0.242** |
| `assisted suicide` | 73 | 292 | 6.54 | 7.35 | 63.9 | 60.5 | 3.5 | **0.232** |
| `affirmative_action` | 73 | 292 | 5.06 | 7.52 | 72.0 | 70.8 | 1.3 | **0.132** |
| `border_restrictions` | 73 | 292 | 5.59 | 7.47 | 74.4 | 75.0 | **−0.6** | 0.000 |
| `worker_pensions` | 73 | 292 | 9.53 | 6.46 | 52.2 | 55.1 | **−2.9** | 0.000 |

The ranking is **identical** under both outcome definitions, and the top two are separated from
the field by a factor of 2–5 in `var_signal`. Reference scale: the five carved practice tasks run
`var_signal` 0.96–7.55 at ceilings 0.681–0.931 (standing finding 36), so
`solitary_confinement` sits **above the best carved task on ceiling** and an order of magnitude
above all five on signal variance.

### Two corrections to the analytic number, both run

**(a) `mean(SE^2)` over-states the cross-arm noise, because all 73 arms share ONE control group.**
A shared control mean shifts every ATE by the same amount, so it contributes nothing to the
variance ACROSS arms, but `SE^2` contains it. Adding it back
(`var(control mean) = 1.4–2.2 pp^2`) raises the ceilings slightly and flips `border_restrictions`
from −0.1 to +1.4 (ceiling 0.137). It does not change the ranking or the verdict, and
`worker_pensions` stays negative (−1.5). Reported for honesty, not used: the uncorrected
`power()` is the harness's own frozen statistic and it is the conservative direction.

**(b) The empirical arbiter agrees with the analytic one** (standing finding 40's rule: split the
respondents, do not trust a formula alone). 12 random half-splits per issue, ATE tables recomputed
on each half and correlated:

| issue | split-half r (12 splits) | Spearman-Brown implied ceiling | analytic ceiling |
|---|---|---|---|
| `solitary_confinement` | **+0.590** (sd 0.041) | 0.862 | 0.824 |
| `veteran healthcare` | +0.258 (sd 0.104) | 0.640 | 0.623 |
| `electoral_college` | +0.149 (sd 0.103) | 0.509 | 0.475 |
| `foreign_aid` | +0.098 | 0.423 | 0.307 |
| `felons_voting` | +0.084 | 0.394 | 0.359 |
| `affirmative_action` | +0.071 | 0.365 | 0.157 |
| `medicaid` | +0.047 | 0.300 | 0.280 |
| `border_restrictions` | +0.042 | 0.283 | 0.000 |
| `assisted suicide` | +0.030 | 0.242 | 0.183 |
| `worker_pensions` | **−0.042** | 0.000 | 0.000 |

`solitary_confinement`'s +0.590 is essentially the +0.596 that finding 53 measured for main
effects on the carved tasks. Eight of ten issues replicate at r <= 0.15 — **an eight-issue,
584-arm "task" would be almost entirely noise**, which is exactly the trap finding 36 was built
to catch, and it is invisible from the arm count alone.

### What the signal IS — read this before believing the ceiling

The heterogeneity is largely a model-quality gradient, because 24 of the 72 LLM arms per issue are
Pythia models that produce short, off-topic, or wrong-side text. On `solitary_confinement`, mean
ATE by family: **claude +19.5, gpt +18.9, human +19.5, Llama +11.5, Yi +6.0, Qwen1.5 +5.5,
falcon +4.9, pythia −1.2**. Message-level: `corr(ATE, valence_correct) = +0.591`,
`corr(ATE, task_completion) = +0.503`; arms whose message argues the WRONG side average
**−3.55** against **+10.61** for the right side.

It is not ONLY that. Dropping all 24 Pythia arms leaves 49 arms with `var_obs 133.6`,
`noise 40.3`, **`var_signal 93.3`, ceiling 0.836** — the signal survives the removal of the
gibberish. (For `veteran healthcare` it does not: non-Pythia ceiling falls 0.623 -> 0.366, which
is a second reason to prefer `solitary_confinement`.) Still, a practice task built here measures
**"can you tell a good persuasive message from a broken one"** at least as much as **"which of 16
professionally-written messages moves an attitude most"**, and those are not the same skill as the
target's. Say so in any run report that scores it.

## 4. Message lengths and prompt cost

730 messages overall: word count min 14, **median 208**, max 519 (the ~200-word instruction bites).

| issue | arms | words min/med/max | chars min/med/max | TOTAL chars, all arms | est. cl100k tokens (chars/4) |
|---|---|---|---|---|---|
| `solitary_confinement` | 73 | 14 / 202 / 354 | 83 / 1,324 / 2,457 | **93,285** | **~23,300** |
| `veteran healthcare` | 73 | 15 / 211 / 482 | 89 / 1,446 / 3,052 | 99,514 | ~24,900 |
| `electoral_college` | 73 | 27 / 208 / 494 | 173 / 1,334 / 3,196 | 98,976 | ~24,700 |

`tiktoken` is not installed in `/opt/kernel/venv`, so these use the same `chars/4` fallback
`ssb.predict.n_tokens` itself falls back to; treat them as +-10%.

**Consequences for standing finding 17.** No single arm comes near the 12,000-character per-arm
cap (max 3,196 = 27% of it), so **nothing is ever truncated** — the finding-44 risk is absent
here. But the *stimulus text alone* is ~23,300 tokens against a 24,000-token whole-prompt budget,
and the target's whole prompt is 9,892. So a 73-arm brief **must be split**, into 2 parts
(~12–13k each, still above the target) or preferably **4 balanced parts of 18–19 arms
(~6k each, comfortably inside the target's band)**. Splitting is the policy's own first move
("split into balanced parts before anything else"), it costs `anchor_spread`, and it turns one
task into 4 paid calls per draw. Rough cost, priced by finding 28's factors
(cl100k x1.574 tokenizer, +73.2% CLI second pass, ~19 output tokens/cell): a 4-part,
1-draw pass over `solitary_confinement`'s 73 arms x 4 items is on the order of **~110k billed
tokens** including the shared fixed text repeated in each part. That is a fifth of a stage-3 batch
for **73 arms** — the cheapest arms-per-token in the repo by a wide margin, which matters because
finding 60c measured the bootstrap half-width falling only in the number of ARMS
(`1.10 x n^-0.506`): 73 new arms roughly doubles the board's arm count.

## 5. Moderators available

| target moderator | available? | column | coding |
|---|---|---|---|
| gender | **yes** | `gender` | `Female` 14,747 / `Male` 10,537 / `Non-binary / third gender` 600 / `Prefer not to say` 98 |
| age band | **yes, derive** | `age` (int, 18–100) | cut to 18-29 (7,424) / 30-44 (10,836) / 45-59 (5,574) / 60+ (2,148). **Skewed young**: only 8.3% are 60+ |
| education | **yes** | `education` | 6 levels: `Did not graduate high school` 194 / `High school diploma` 6,049 / `Technical certification or trade school` 1,460 / `2-year college` 3,138 / `4-year college` 10,258 / `Graduate degree` 4,883 |
| partisan identity | **yes** | `party_affiliation` (6) + `political_party` (0–4) | `Strong Democrat` 0 (5,446) / `Moderate Democrat` 1 (6,865) / `Independent` **and** `Other (Libertarian, Green, etc.)` both 2 (7,412 + 1,118) / `Moderate Republican` 3 (3,435) / `Strong Republican` 4 (1,706). **`political_party == 2` merges Independent with Other** — use the string column if that matters |
| race/ethnicity | **NO** | — | no race, ethnicity or Hispanic column in either the final or the raw file |
| income | **NO** | — | no income column in either file |

Extra, not in the target's six: `ideo_affiliation` (6 levels) + `political_ideology` (0–4),
`political_knowledge` (0–3 from three items), `authorship` ("who wrote this?", 7 levels,
post-treatment — never a moderator), `attention_check` (single-valued after cleaning).

**Two of the target's six moderators are simply absent.** Any subgroup work carved here covers
gender / age / education / party only. Given finding 53 (human condition x moderator interactions
replicate at r = +0.024) that is a small loss, but it should not be described as a full moderator
set. Cell sizes for a single issue are thin: on `solitary_confinement`, `Strong Republican` is
**32 control / 139 treated across 73 arms**, i.e. ~2 per arm.

## 6. Does a clean single-issue carve exist? Yes.

Every arm of one issue is compared to **the same control group**, and the adapter needs exactly
this:

1. read `final_data_with_metrics.csv`;
2. `df = df[df.issue == "solitary_confinement"]` (2,589 rows);
3. **control** = `df[df.condition == "control"]` (524 rows, `treatment_message` all null);
4. **arms** = `groupby("treatment_message_id")` over `df[df.condition != "control"]` (73 groups,
   n 4–119, median 16) — includes the one `condition == "human"` arm, which should be labelled as
   the expert-written benchmark message rather than hidden among the LLM arms;
5. **arm text** = `treatment_message` (first value per group; constant within group);
6. **outcomes** = `confinement-1`, `confinement-2-reversed`, `confinement-3`, `confinement-4`
   (0–100 sliders, all four already oriented so that higher = agrees with the issue stance;
   verified: `corr(-1, -2-reversed) = +0.67`) and/or the composite `confinement_mean`
   (= `dv_response_mean`, verified identical);
7. ATE in pp = treated mean − control mean, no rescaling needed;
8. moderators as in §5.

No other filter is required — no completion filter (already applied upstream), no de-zero-filling
(items are NaN, not 0, for non-assigned issues), no weights (none supplied).

Per-issue stem map (the item column prefix is NOT the `issue` value):
`medicaid`->`medicaid`, `veteran healthcare`->`veterans`, `worker_pensions`->`pensions`,
`foreign_aid`->`foreign_aid`, `solitary_confinement`->`confinement`,
`assisted suicide`->`suicide`, `border_restrictions`->`border`, `felons_voting`->`felon_voting`,
`affirmative_action`->`affirmative_action`, `electoral_college`->`electoral_college`.

### Verbatim item wordings (from `raw_data_final.csv` row 2) — `solitary_confinement`

- `confinement-1` — "The U.S. should not ban the use of solitary confinement for juveniles in prison. [0=Strongly disagree; 100=Strongly agree]"
- `confinement-2` — "Banning the use of solitary confinement for juveniles in prison is a good idea. [0=Strongly disagree; 100=Strongly agree]" (**reverse-scored** into `confinement-2-reversed`)
- `confinement-3` — "Banning the use of solitary confinement for juveniles in prison would have bad consequences. [0=Strongly disagree; 100=Strongly agree]"
- `confinement-4` — "Do you support or oppose banning the use of solitary confinement for juveniles in prison? [0=Strongly support; 100=Strongly oppose]. Note that for this question, the scales are flipped"

The issue stance argued by every message (`issue_full`) is "The U.S. should not ban the use of
solitary confinement for juveniles in prison", and control-arm level is 35.4 pp — i.e. the
messages argue the **unpopular** side, which is part of why the ATEs are large (+11.2 pp for AI
messages overall, +19.5 for the human message).

---

## 7. BRIDGE CHECK — tappin2023 (7-point agreement) vs hackenburg2025 (0–100 slider)

**All ten hackenburg issues appear in tappin2023**, eight of them in near-verbatim wording — the
two studies share an author (Tappin) and hackenburg's issues were drawn from tappin's 24-item
bank. This is the cleanest coarse-Likert-to-slider comparison available on the mounted data:
the *same policy propositions*, one asked on a 1–7 agreement scale and one on a 0–100 slider.

Method. tappin control arm = `condition == "Control"` (no cue, no message) AND `item_seen` AND
`likertAgree` non-null, from `runs/_scratch/tappin_RM.csv` (240–302 respondents per item);
rescaled `(likertAgree − 1) / 6 * 100`. hackenburg control arm = `condition == "control"` within
issue (471–557 respondents). Where the two instruments state the policy in opposite polarity
(4 of 10) the tappin value is flipped to `100 − x` and its party gap negated (`flip` column).
Party gap = Republican-identifying mean − Democrat-identifying mean (tappin: all six `party7`
levels, which include leaners; hackenburg: `political_party in {3,4}` minus `{0,1}`, i.e.
Independents and `Other` excluded because `political_party == 2` merges them).

| hackenburg issue | tappin item | flip | tappin level (pp) | hack level (pp) | level diff | tappin gap (pp) | hack gap (pp) | gap ratio |
|---|---|---|---|---|---|---|---|---|
| `medicaid` | 9 Require work for Medicaid | no | 50.00 | 32.38 | **−17.62** | +15.33 | +29.33 | 1.91 |
| `veteran healthcare` | 21 Privatization of veterans' healthcare | no | 57.29 | 44.05 | **−13.24** | +9.37 | +22.10 | 2.36 |
| `worker_pensions` | 24 Private pensions for public workers | no | 51.88 | 45.56 | −6.32 | +1.32 | +15.81 | 12.0 |
| `foreign_aid` | 20 Decrease foreign aid | yes | 34.56 | 45.85 | **+11.29** | −12.14 | −16.88 | 1.39 |
| `solitary_confinement` | 13 Ban juvenile solitary confinement | yes | 36.46 | 35.43 | −1.03 | +9.30 | +23.74 | 2.55 |
| `assisted suicide` | 10 Allow assisted suicide | no | 55.74 | 65.42 | **+9.68** | −5.14 | −23.69 | 4.61 |
| `border_restrictions` | 8 More restrictions at U.S. border | no | 67.27 | 55.97 | **−11.31** | +19.63 | +42.02 | 2.14 |
| `felons_voting` | 12 Deny criminals the vote | yes | 45.46 | 57.35 | **+11.89** | −17.73 | −20.86 | 1.18 |
| `affirmative_action` | 16 Allow affirmative action | yes | 45.20 | 44.97 | −0.23 | +23.42 | +30.91 | 1.32 |
| `electoral_college` | 3 Abolish electoral college | no | 52.29 | 64.05 | **+11.76** | −26.58 | −34.18 | 1.29 |

(hackenburg outcome above = the 4-item composite `<issue>_mean`. Using only item `-1`, the single
item whose wording is closest to tappin's, gives the same picture: level diff mean −0.57,
range [−19.18, +16.32], level r = 0.388; gap r = 0.948, through-origin slope 1.682.)

**Two findings, and they point opposite ways.**

**(a) The LEVEL does not transfer, and the mean offset is ~zero.** Mean level difference
(slider − rescaled 7-point) is **−0.51 pp**, median −0.63 — but the per-item spread is
**−17.6 to +11.9 pp** and the cross-item correlation of the two instruments' levels is only
**r = 0.426** (0.388 on item `-1`). Ten near-verbatim propositions, and knowing the 7-point level
tells you almost nothing about the slider level. This is standing finding 14's rule confirmed on a
**7-point** scale ("anchor orderings and gaps from a coarse item; never a level"), and it is a
**correction in direction to standing finding 10**, which measured a 3-point Likert running ~5 pp
HIGH against a slider on five items: on a 7-point scale, across ten items, the systematic offset
is not +5 pp, it is **0 pp with +-14 pp of item-level scatter**. A single scalar haircut for
"coarse Likert" is not supported here.

**(b) The GAP transfers in ordering, but the slider gap is ~1.6x LARGER**, which is the opposite
sign of finding 14's 0.808. Party-gap correlation across the ten items is **r = +0.948**
(Spearman +0.939); the fitted slope is **1.568** (through-origin 1.596, intercept +4.20). Checked
against the obvious confound — tappin's partisan definition includes leaners, hackenburg's
excludes Independents — and the slope is stable:

| cut | r | through-origin slope | OLS slope |
|---|---|---|---|
| tappin all partisans (incl. leaners) vs hack Moderate+Strong | 0.948 | 1.596 | 1.568 |
| tappin excluding leaners vs hack Moderate+Strong | 0.923 | 1.469 | 1.442 |
| tappin Strong only vs hack Strong only | 0.881 | 1.624 | 1.594 |
| tappin all partisans vs hack Strong only | 0.945 | 2.179 | 2.143 |

**This is a measurement of two instruments in two different samples, and it cannot separate them.**
tappin is Lucid, quota-matched, partisans-only, mean age 47, 41% BA, fielded Sep 2021; hackenburg
is Prolific, no quotas, Democrat-skewed, mean age 39, fielded 2024. Prolific samples are known to
be more politically sorted, and a real difference in polarisation is fully confounded with the
7-point-vs-slider difference. Two further caveats: tappin's control responses are *within*-subject
(each respondent saw 5 items in a 2x2 cue x info design, so a "control" item can follow a treated
item), and 4 of 10 comparisons required a polarity flip, which assumes symmetric use of the scale.

**What may honestly be taken from this:** the finding-14 rule survives on a third scale format
(gaps transfer, levels do not, r = 0.95 vs 0.43); the **magnitude** of the gap slope is
sample-confounded and **should not be adopted as a bridge constant** the way 0.808 was, unless a
same-sample 7-point/slider comparison turns up. If it is ever quoted, quote it as
"1.44–1.62 across strength-matched cuts, confounded with panel", never as "1.6".

---

## VERDICT

**CARVABLE: `solitary_confinement`, and only it (with `veteran healthcare` as a second choice).**

What is unambiguously good:
- **73 arms with verbatim texts** and one shared 524-person control, the largest arm count in the
  repo by a factor of three, and the arm is the effective unit for every interval this harness
  quotes (finding 60c).
- **Real signal**: `var_signal = 92.1`, analytic ceiling **0.824**, empirical split-half
  **+0.590** — above every carved task, and it survives dropping the 24 Pythia arms (ceiling 0.836).
- **No truncation risk**: the longest arm is 2,457 chars against a 12,000 cap.
- A clean adapter: three filters, no completion rule, no de-zero-filling, no weights.

What it costs, and what must be written down if it is used:
1. **The brief must be split** — ~23,300 tokens of stimulus against a 24,000 whole-prompt budget.
   4 balanced parts of 18–19 arms puts each part near the target's own 9,892 and pays
   `anchor_spread`; 2 parts stays over the target's band.
2. **The stimuli are LLM-generated persuasion messages, half of them from deliberately weak
   models.** A large part of the predictable variance is message quality
   (`corr(ATE, valence_correct) = +0.591`), not argument selection among competent messages. That
   is a *different* skill from the target's 16 professionally written climate messages, and a
   calibration slope fitted here would be fitted partly on "can you spot broken text".
3. **`in_slope` should be considered off, or at least argued.** Finding 63 measured the magnitude
   multiplier failing to transfer across families; this task's family is single-issue US policy
   attitude, its arms are machine-written, and its median |ATE| (9.0 pp) is 3–4x the target's
   likely scale. Carve it for **ordering and within-outcome r**, which is where 73 arms buy the
   most, and decide `in_slope` explicitly rather than by default.
4. **Two of the target's six moderators (race, income) do not exist here**, and party cells are
   thin (32 control Strong Republicans on the chosen issue).
5. **Do NOT carve the other eight issues.** Six have ceilings 0.16–0.48 and two are negative;
   pooling them to reach "584 arms" would put ~500 pure-noise cells into `fit_calibration` — the
   exact failure finding 36 exists to prevent. If a second table is wanted, take
   `veteran healthcare` (ceiling 0.623, split-half +0.258) and note that its signal is mostly the
   Pythia contrast (non-Pythia ceiling 0.366).

**Recognition risk** (finding 30/38): this is a 2025 PNAS paper with a memorable design
("scaling LLM size yields diminishing returns for persuasion"). A brief that lists 24 model names
would name the study outright. An adapter should present arms **anonymously** — no `model`,
`model_family`, `parameters`, or `prompt_variant` fields, and arm labels like `Message 07` — which
is also the finding-65 result that arm titles carry nothing. The message texts themselves cannot
be redacted and are the task; a recognition probe should be run and reported either way.

**Artefact written:** `runs/_scratch/hackenburg_power.csv` — the chosen issue's 73-arm ATE table
on the primary DV (`issue, arm, n_treat, n_control, ate_pp, se_pp`), sorted by `ate_pp`.
