# DATA_GLIGORIC — can gligoric2025 carry a sixth practice task (a TRUST-family ATE table)?

Recon session, harness child. Read-only pass over `/workspace/datasets/gligoric2025`.
Nothing in `/workspace/run` was modified except this file. No adapter JSON was written.
No prediction of the target study appears anywhere below.

**VERDICT (in full at the bottom): NOT CARVABLE as a sixth *scored* practice task.**
Every adapter field but three can be filled and all six arm texts exist verbatim — the blocker
is not plumbing, it is that the ATE table this dataset yields is statistically indistinguishable
from zero and would be scored as noise.

---

## 1. Exact paths

| what | path |
|---|---|
| microdata | `/workspace/datasets/gligoric2025/downloads/Main Study/Analyses (data and codes)/dataMainStudy.csv` (7,800 x 82) |
| de-facto codebook | `.../Analyses (data and codes)/R Code Main Study.R` (434 lines), `R-Code-Markdown.html`, `R Code Markdown.Rmd` |
| instrument (message texts) | `/workspace/datasets/gligoric2025/downloads/Main Study/Materials/Qualtrics file.qsf` (275 SurveyElements) and `Materials (word exported from Qualtrics).docx` |
| manipulation pre-test | `/workspace/datasets/gligoric2025/downloads/Pilot Study 2/Pre-test_ideology_and_trust_manipulations.docx` (+ `Pilot Study 2 data.csv`, 201 x 21) |
| occupation pilot | `/workspace/datasets/gligoric2025/downloads/Pilot Study 1/IdeologyTrust data.csv` (3,509 x 1,271) |

Fielded **2024-05-28 to 2024-06-14** (`RecordedDate`), US online river panel (the QSF's end-of-survey
redirects go to `samplicio.us` and `notch.insight...`), median `Duration` 151 s. Ideology quota:
the authors' own comment requires at least 10% in each of conservatives (6-10) and liberals (1-5).
Sample is 50.3% Man / 49.5% Woman / 0.2% Other. `Age` min is **16**, so "US adults" is not exact
(13 rows under 18).

## 2. What is actually randomised — TWO independent factors, and the harness's two standing
findings describe different ones

The standing findings are not in conflict; they describe the two factors of one design.

**Factor A — the MESSAGE (`Condition`), between subjects.** QSF flow `FL_53` is a
`BlockRandomizer`, `SubSet: 1`, `EvenPresentation: true`, over exactly **6 groups**, each of which
sets the embedded field `Condition` and then shows its own block. This is standing finding 5's
factor ("message effects on trust in scientists").

**Factor B — the SCIENTIST TYPE (referent), within subjects.** Each condition block contains
36 elements: the message (fixed first) plus **35 occupation-rating questions from which Qualtrics
draws `TotalRandSubset: 4`** (`Randomization.Advanced`, identical in all six blocks). So every
respondent rates **exactly 4 of 35 occupations, randomly chosen** — verified in the data:
`trust.notna().sum(axis=1)` is 4 for all 7,800 rows; 31,200 = 7,800 x 4 ratings total.
This is standing finding 15's factor (climatologists' ideology gap against a median type).

Both findings are correct. Finding 5 reads Factor A; finding 15 reads Factor B.

**The decisive structural fact: only conservatives were randomised.** QSF branch `FL_57` sends
anyone answering `Ideology` in 1-5 (Extremely/Very/…/Slightly liberal) straight to a block that
hard-sets `Condition = "Control"`. Confirmed in the data: the crosstab `Ideology x Condition` has
**zero** liberals in any of the five message arms.

    Ideology <= 5 (liberals) : Control 1,110 ; every other arm 0
    Ideology >  5 (conservatives) : Control 1,138 ; five message arms 1,095-1,116

So the experimental sample is **6,690 self-identified conservatives** (Ideology 6-10), not 7,800.
The 1,110 liberals are an observational comparison group, never a randomised one.

## 3. Condition column, arm levels, n

Column: **`Condition`** (string, no NA). Author factor order in `R Code Main Study.R`:
`Control, Co-Benefit, ConservativeScientists, Norms, RespectableConservatives, ValueBased`.

| arm | n (whole file) | n (randomised sample, Ideology > 5) |
|---|---|---|
| Control | 2,248 | **1,138** (the other 1,110 are the non-randomised liberals) |
| Norms | 1,116 | 1,116 |
| ConservativeScientists | 1,116 | 1,116 |
| RespectableConservatives | 1,114 | 1,114 |
| ValueBased | 1,111 | 1,111 |
| Co-Benefit | 1,095 | 1,095 |

## 4. Message texts — YES, verbatim, and short

All six arm texts are in the QSF as `DB` (descriptive-text) questions, one per condition block.
Cleaned of HTML they are:

- **Control** (`QID225`, 144 chars): "We ask you to evaluate the scientific occupations below on two attributes. We are interested in your view - there are no right or wrong answers."
- **Norms** (`QID189`, 433 chars): "Recent research shows that scientists are among the most trusted professions in the US. Various surveys with representative samples in the US found that a majority of conservative respondents (over 70%) reported high levels of confidence in scientists. This particularly applies to the scientific occupations below, …"
- **ConservativeScientists** (`QID153`, 392 chars): "Although there are ideological differences among scientists, many scientists in fact consider themselves conservatives. Currently, there are approximately 400 000 conservative scientists working in the US alone. …"
- **RespectableConservatives** (`QID261`, 549 chars): "Over the course of the last 75 years, various respected conservatives have publicly signaled their trust in scientists. For example, conservative politicians such as `${e://Field/Politician}` relied heavily on scientists' input on various issues, whereas many scientists and intellectuals such as `${e://Field/Intellectual}` were conservatives themselves. …"
- **ValueBased** (`QID2`, 411 chars): "Many scientists work to preserve the world we live in and protect it against various natural and societal threats. They actively engage to conserve the order of the communities we love, giving us a sense of security and stability. …"
- **Co-Benefit** (`QID117`, 427 chars): "Many scientists work to develop new jobs and promote technological innovation, actively contributing to the economy. In certain countries, it is estimated that scientists directly contribute as much as 11% to the Gross Domestic Product each year. …"

**Caveat on RespectableConservatives:** two piped fields are themselves randomised in the flow —
`Politician` in {Henry Kissinger, George W. Bush}, `Intellectual` in {William F. Buckley, Ayn Rand}
(flow IDs FL_35/FL_42 and FL_44/FL_45). **Neither is recorded in `dataMainStudy.csv`**, so that arm
is a 4-way mixture we cannot condition on and cannot reproduce exactly in a brief. The Pilot-2 docx
shows the pre-test used a wider set (Kissinger, Reagan, George W. Bush, John McCain).

**Prompt size:** the six texts total **428 cl100k tokens (~674 by the 1.574x Anthropic factor of
standing finding 28)**. With item wording and sample description a whole brief lands near
**1,000-1,500 tokens against the target's 9,892**. Standing finding 17 fixed the *upper* edge of the
band; this task would sit ~7x *below* it — a different kind of size mismatch, worth naming.

## 5. Trust outcome — column names, scale, construction

70 columns, `<occupation>_1` and `<occupation>_2` for 35 occupations, in the file's column order
(cols 9-78; data column names are lowercase plural and include two truncations,
`environmental scient` and `hydrologist`). Both are **7-point bipolar matrix items, 1-7**:

- `_1` = "not credible : credible"
- `_2` = "untrustworthy : trustworthy"

Stem: *"Please rate how you view `<occupation>` using the following attributes"*.
Authors' construction (`R Code Main Study.R`, the `for (i in 1:35)` loop): **per-occupation trust =
rowMeans of the two items**; then melt to long and model `Trust ~ (1|id) + (1|Occupation) + Condition`
on conservatives (H3), with `Condition*PolIdentification` for H4. **Scale range = 6 (1 to 7)**, so
1 raw point = 16.67 pp.

Control-arm conservative mean trust = **5.14** (median 5.25); the non-randomised liberals average 5.47.

Manipulation check `BelievabilityExper_1..3` (1-7; item 3 reverse-scored, `8 - x`) exists **only in
the five message arms — all three columns are 100% missing in Control**, so it cannot be an outcome
in an arm x outcome table.

## 6. Moderators present

| target moderator | gligoric column | status |
|---|---|---|
| gender | `Gender` 1=Man 2=Woman 3=Other (+`Gender_3_TEXT`) | present, but **`Other` = 13 respondents across 6 arms** (0-5 per arm) → fails the >=3-per-cell rule exactly as voelkel2024/bbprime2025 do |
| age_band | `Age` integer 16-99 | present; bands 18-29/30-44/45-59/60+ give 200-382 per arm-band |
| education | `Education` 1-6 | **6 levels but not the target's 6.** 1=Less than HS, 2=Completed HS, 3=Currently studying undergrad, 4=Completed undergrad, 5=Currently studying postgrad, 6=Completed graduate degree (MSc, MA, **PhD**). Level 6 merges Master's/Professional with Doctorate — the target's last two levels are **not recoverable**; level 5 is ambiguous |
| race | — | **ABSENT** (not asked) |
| income | — | **ABSENT** (not asked) |
| party | — | **ABSENT.** Only `Ideology` (1-10, "Extremely liberal" 1 … "Extremely conservative" 10; QSF choice ids 1,2,4,5,…,11 recoded to 1-10) and `PolIdentification` (1-7, "I identify with my political group"). And within the randomised sample **Ideology is 6-10 by construction** (6: 1,368; 7: 1,172; 8: 2,223; 9: 926; 10: 1,001) — so **no party or liberal-vs-conservative contrast is estimable from randomised data at all** |

Also present: `Duration`, `RecordedDate`. No respondent id, no weights. Attention checks
(`QID76` experimental / `QID79` control) are **not** in the data file — exclusions were applied
upstream; N is exactly the preregistered 7,800.

## 7. The blocking measurement: the ATE table is noise

Recomputed here as plain difference-in-means on conservatives, converted to pp of the 1-7 range
(divide by 6, x100). Outcomes tried: overall trust (mean of the 4 rated occupations), the two items
separately, and five thematic occupation clusters (climate/environment, life+medical, physical,
social, quantitative/tech).

Best-powered outcome, **overall trust**, n ~1,100 per arm:

| arm | ATE (pp) | SE (pp) |
|---|---|---|
| Norms | +0.79 | 0.83 |
| ValueBased | +0.36 | 0.83 |
| ConservativeScientists | +0.27 | 0.83 |
| RespectableConservatives | +0.21 | 0.83 |
| Co-Benefit | -0.19 | 0.83 |

(That range, -0.19 to +0.79 pp, reproduces standing finding 5's -0.22 to +0.83 pp to within the
difference between difference-in-means and the authors' `emmeans` on the mixed model.)

- One-way ANOVA on overall trust across the 6 conservative arms: **F = 0.319, p = 0.902**.
- Sum of z^2 over the 5 overall-trust cells: **1.30 on 5 df, p = 0.935**.
- Over the full 55-cell table tried here (11 outcome definitions x 5 arms): **chi2 = 24.5 on 55 df**.
- **Variance decomposition, 8-outcome x 5-arm core table (40 cells): observed var(ATE) = 0.520 pp^2
  (SD 0.72 pp); variance expected from sampling alone = 1.514 pp^2 (SD 1.23 pp). Implied signal
  variance is NEGATIVE.** There is no measurable between-arm signal to predict.
- Median |ATE| **0.65 pp** against median SE **1.45 pp**. Compare the existing five tasks:
  vlasceanu2024 median |ATE| 3.9 pp, bbprime2025 range -4.53..+15.93 pp, goldwert2026 median 2.43 pp.
- Cutting finer makes it worse, not better: per-occupation cells have ~125 per arm and SE ~3.5 pp
  (e.g. climatologists x RespectableConservatives reads +4.26 pp, SE 3.57 — that is the largest
  number in the whole table and it is one sigma of nothing).
- No-effect-floor RMSE on the 40-cell core table = **0.810 pp**; 67.5% of cells are positive, so the
  all-positive baseline scores 0.675 directional. A predictor can only beat the floor by predicting
  the *sampling noise* of 6,690 people.

This is exactly the situation standing finding 16 named for goldwert2026 ("magnitudes are not
identified"), except here it applies to the point estimates themselves rather than to attrition
bounds, and there is no `in_slope`-style rescue: the whole table would have to be excluded.
Feeding it to `fit_calibration` would drag the pooled slope toward zero by adding 40+ cells whose
human values are pure noise — the opposite of the correction standing finding 29 measured.

Note this is not a defect of the dataset. It is the *published result*: five preregistered messages,
all null, equivalence-bounded below d = 0.1. That null is the finding, and the harness already
carries it as standing finding 5.

## 8. Where the real signal in this file is (and why it is a different shape)

Factor B has plenty of signal. In the control arm (n = 2,248, including liberals), the per-occupation
OLS slope of trust on `Ideology` runs from **-3.27 pp per ideology point (environmental scientists)**
and **-2.71 (climatologists, rank 2 of 35)** to **-0.07 (geneticists)**. That is the measurement
standing finding 15 rests on. But its "arms" are *referent labels inside an item stem*, not messages
a respondent reads, and its estimand is an ideology x referent interaction, not an ATE — so it is not
a task shaped like the existing five, and the harness already extracted its value.

## 9. Adapter template field-by-field (`inputs/adapters/_TEMPLATE.json`)

| field | could it be filled? |
|---|---|
| `dataset` / `file` / `reader` | yes — `csv`, the path in §1 |
| `sample_description` | yes — but must say "US self-identified conservatives (1-10 ideology, 6-10), May-June 2024 river panel", which is not the target's census-quota general population |
| `condition_col` | yes — `Condition` |
| `arms` (6) | yes, identity map |
| `control_arms` | yes — `["Control"]`, **with a filter to `Ideology > 5`**, else the control arm silently mixes in 1,110 never-randomised liberals and every ATE is biased downward |
| `outcomes` | **only by construction.** There is no outcome column in the file; every outcome must be built from the 70 item columns. lo/hi = 1/7 for all. And the "outcomes" would be nested subsets of one 35-item battery, not 13 distinct constructs — the Section-1 row *"Pearson r within outcomes"* would have almost nothing left to measure |
| `moderators` | partial: `gender` (Other n=13, breaks), `age_band` (fine), `education` (5 of 6 target levels, no Doctorate split) |
| `moderators_unavailable` | `race`, `income`, `party` — all three absent; party structurally impossible |
| `filters` | **required, not optional**: `Ideology > 5` |
| `weight_col` | `null` |
| `message_texts_file` | yes — six texts, extractable from the QSF exactly as `tools/extract_qsf_texts.py` does elsewhere |
| `provenance.caveats` | 4 of 35 occupations per respondent (missing-at-random by design, ~125 per arm per occupation); RespectableConservatives is an unrecorded 4-way pipe mixture; `BelievabilityExper_*` all-NA in Control; Age min 16; no respondent id, no weights; **arm-level ATEs statistically indistinguishable from zero** |

## 10. VERDICT

**NOT CARVABLE** as a sixth practice task shaped like the existing five.

It is *mechanically* buildable — the arms are real randomised message arms, all six texts exist
verbatim, the outcome is genuinely trust in scientists, and every template field except `race`,
`income` and `party` can be filled. The disqualifier is measurement, not plumbing:

1. **No signal.** Across the best 40-cell table the observed ATE variance (0.520 pp^2) is *below*
   the variance sampling noise alone predicts (1.514 pp^2); ANOVA p = 0.902. Scoring a prediction
   against it measures a predictor's ability to guess the noise of 6,690 respondents, and every
   Section-1 metric (directional, Spearman, Pearson, within-outcome Pearson) has expectation at
   chance regardless of how good the predictor is. Adding those cells to `fit_calibration` would
   bias the pooled slope toward zero.
2. **The randomised sample is conservatives only**, so the moderator that matters most for the
   target's trust construct — party/ideology — cannot be estimated from randomised data here at
   all, and `race`/`income` were never asked.
3. **The "outcomes" are not distinct outcomes**, only overlapping subsets of one 35-item, two-item
   battery; the outcome-fixed-effects-removed row would be near-empty.
4. Prompt would be ~1,000-1,500 tokens against the target's 9,892 — out of the size band that
   standing finding 17 requires, on the low side.

**What it should be used for instead** (no change to the harness proposed here, this is the finding):
gligoric2025 remains the harness's *declared null prior* on message-to-trust ATEs (standing finding 5)
and its referent fan-out evidence (standing finding 15). Both already extracted. It does **not**
close the gap standing finding 33 names — zero practice cells in the `trust` family — because a
practice task needs a *measurable* effect table and this study's headline result is that there
isn't one. OPEN item 18's honest admission of the cross-family extrapolation stands; if the gap is
to be closed by measurement rather than by writing, the source has to be a trust experiment with
detectable effects, and it is not in this dataset.
