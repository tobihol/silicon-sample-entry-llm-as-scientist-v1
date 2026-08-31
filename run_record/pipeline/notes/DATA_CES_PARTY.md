# DATA_CES_PARTY — validating the party-imputation route (OPEN.md item 9)

Script: `tools/validate_party_imputation.py` (deterministic, SEED 20260815, split seed 20260901, ~40 s).
Numbers: `inputs/measured/party_imputation_validation.json`. Every figure below is a field of that file.
Nothing here touches the pool files; this is measurement only.

## What is measured, and why in this shape

The route (`tools/build_pool.py`) is: ACS 2018 adult cells over (age_band, gender, race, education,
income) x a hierarchical CES donor `P(party | X)` x IPF onto census/panel demographic margins **and
five party x moderator two-way margins taken from CES's own conditionals**. Because those five
two-ways are raking targets, any residual measured on a two-way is near-vacuous by construction —
the fixed point of the rake is the target. So the informative surfaces are the three-ways that
nothing constrains, and every table below carries them: `party x race x education`,
`party x race x age_band`, `party x education x income`, `party x gender x age_band`.

All figures are **L1 (sum of absolute cell differences) in percentage points of the sample**;
total variation is half of it; `max_cell_pp` is in the JSON alongside.

CES: `/workspace/datasets/ces/downloads/CCES24_Common_OUTPUT_vv_topost_final.csv`, 60,000 rows,
54,858 complete on the six variables, weight `commonweight`.

## A/B — smoothing/fallback cost, isolated (split-half, n = 27,429 / 27,429, 1,098 demographic cells)

Four columns, because a naive split-half number is mostly noise:

- **null**: half 1's *real* joint against half 2's *real* joint. Pure sampling noise, no imputation.
- **A cross-half**: donor fitted on half 1, applied to half 2's cell table (the route). = fallback
  cost + donor sampling noise.
- **B raked**: the same, then IPF onto half 1's five party x moderator conditionals.
- **A/B self-donor**: donor fitted on half 2 and applied to half 2. Cells resolved at the full
  5-key then reproduce the truth exactly, so what is left is **only** the fallback/smoothing error.
  This is the isolated number the task asks for.

Half weights are rescaled to the full file's total so the 30-weighted-unit fallback threshold bites
where it bites in production; the `*_raw_scale` variant in the JSON brackets that choice
(fallback share 0.157 rescaled vs 0.254 raw), and moves no conclusion.

| surface | null (two real halves) | A cross-half | B raked | A self-donor (pure) | B self-donor raked |
|---|---|---|---|---|---|
| `party__gender` | 1.94 | 2.40 | 2.06 | 0.90 | 0.00 |
| `party__age_band` | 3.00 | 3.26 | 2.56 | 0.99 | 0.00 |
| `party__race` | 3.54 | 2.73 | 2.54 | 0.99 | 0.00 |
| `party__education` | 3.65 | 3.74 | 2.74 | 1.14 | 0.00 |
| `party__income` | 3.58 | 3.56 | 3.23 | 1.28 | 0.00 |
| `party__race__education` | 8.94 | 7.43 | 7.41 | 1.85 | 1.61 |
| `party__race__age_band` | 6.87 | 5.91 | 5.54 | 1.60 | 1.39 |
| `party__education__income` | 9.22 | 7.85 | 7.46 | 2.21 | 2.16 |
| `party__gender__age_band` | 5.20 | 4.81 | 4.69 | 1.26 | 0.64 |

Reading:

1. **Cross-half A and B sit at or below the sampling null on every surface.** At half-sample size
   the imputation error is not separable from noise. Any "measured error" of this route that does
   not carry a null is mostly measuring the reference.
2. **The isolated fallback cost is small**: 1.28 pp L1 at worst on a two-way
   (`party x income`), 2.21 pp on a three-way (`party x education x income`);
   max single cell 0.25 pp. It comes entirely from the
   15.7% of weight that cannot use the full 5-key.
3. **The two-way raking is exactly vacuous on the two-ways**: self-donor B is **0.00 pp on all five**,
   to machine precision, as construction predicts.
4. **On the three-ways it buys little**: 1.85 -> 1.61 (race x educ),
   1.60 -> 1.39 (race x age),
   2.21 -> 2.16 (educ x income, -2%),
   1.26 -> 0.64 (gender x age, -50%).
   It removes the two-way error it is aimed at and leaves 87-98% of the three-way error alone on
   three of the four surfaces.

## C — the deposited pool against CES's real joint

`inputs/pool/joint.csv` vs the real weighted CES six-way joint, with the difference split by

    p(party,s) - q(party,s) = [p(s)-q(s)] p(party|s) + q(s) [p(party|s)-q(party|s)]

into a **demographic frame** part and a **party-conditional** part. The last column of the table is a
bootstrap noise floor: the same statistic between a bootstrap replicate of CES and CES itself
(B = 16), i.e. how much of any residual is CES's own sampling error.

| surface | frame L1 | party-cond. L1 | CES noise floor (cond.) | max cell | dominant |
|---|---|---|---|---|---|
| `party__gender` | 1.63 | 0.00 | 1.29 | 0.29 | frame |
| `party__age_band` | 12.38 | 1.35 | 1.80 | 2.14 | frame |
| `party__race` | 7.63 | 0.63 | 1.88 | 0.86 | frame |
| `party__education` | 15.21 | 0.68 | 2.14 | 2.59 | frame |
| `party__income` | 0.23 | 0.16 | 1.98 | 0.05 | frame |
| `party__race__education` | 18.24 | 3.35 | 4.15 | 1.95 | frame |
| `party__race__age_band` | 17.12 | 2.33 | 3.62 | 1.86 | frame |
| `party__education__income` | 19.36 | 3.37 | 4.50 | 1.39 | frame |
| `party__gender__age_band` | 12.75 | 1.56 | 2.61 | 1.12 | frame |

Party-conditional L1 across the three pool variants:

| surface | joint.csv | joint_marginal_exact.csv | plain imputation (no raking) |
|---|---|---|---|
| `party__gender` | 0.00 | 1.00 | 3.16 |
| `party__age_band` | 1.35 | 1.88 | 1.88 |
| `party__race` | 0.63 | 2.28 | 3.10 |
| `party__education` | 0.68 | 1.84 | 1.63 |
| `party__income` | 0.16 | 3.93 | 5.31 |
| `party__race__education` | 3.35 | 3.90 | 2.67 |
| `party__race__age_band` | 2.33 | 3.13 | 3.27 |
| `party__education__income` | 3.37 | 4.63 | 4.92 |
| `party__gender__age_band` | 1.56 | 2.20 | 2.69 |

Reading:

1. **The frame dominates on all nine surfaces for the pool of record** (and on 8/9 for the
   marginal-exact variant; the exception is `party x income`, 3.93 pp conditional against a
   0.00 frame, which is exactly the association the two-way rake exists to fix — it falls to
   0.16 pp in `joint.csv`). The pool is *deliberately* not CES's demographics: age band
   13.4 pp, education 15.2 pp (raked to the design twin), race 7.6 pp (census quota).
2. **The party-conditional residual of `joint.csv` is at or below CES's own noise floor on every
   surface** (3.35 vs 4.15 on race x educ; 3.37 vs 4.50 on educ x income).
   This is a bound on the *machinery*, not evidence that the fine party structure is right: the
   pool's conditionals **are** CES's, so this comparison cannot detect CES-to-target transfer error.
   That question is D's, and it is not settled by any mounted file.
3. The raking fix improves the conditional part on all nine surfaces against the marginal-exact
   variant, and the party marginal itself goes from 2.26 pp L1 (plain imputation, no raking —
   ACS demographics propagating through P(party|X)) to 0.14 pp.

## D — CES opt-in composition against the ACS census base

CES `commonweight` is entropy-balanced to the **2023 ACS citizen** frame on age, gender, race,
Hispanic origin and education *and their interactions*, then post-stratified on registration and
2020/2024 presidential vote (CES_2024_GUIDE_vv.pdf, "Weighting"). The pool of record is **all**
non-GQ ACS 2018 adults. So the comparison has three legs:

| margin | ACS all adults vs CES | ACS citizens vs CES | ACS all vs ACS citizens |
|---|---|---|---|
| `age_band` | 13.43 | 13.04 | 2.77 |
| `gender` | 2.07 | 2.41 | 0.34 |
| `race` | 8.51 | 5.14 | 9.78 |
| `education` | 8.87 | 7.47 | 4.10 |
| `income` | 19.48 | 20.92 | 1.44 |
| `age_band__race` | 18.09 | 14.72 | 9.78 |
| `race__education` | 12.31 | 10.94 | 9.79 |
| `race__income` | 23.96 | 22.29 | 9.78 |
| `education__income` | 31.09 | 30.51 | 4.28 |
| `age_band__income` | 27.24 | 27.09 | 3.73 |

- **Citizenship is the largest single explanation on race.** Restricting ACS to citizens (`CIT != 5`,
  8.1% of weighted adults) cuts the race L1 8.51 -> 5.14 pp, gender x race
  9.19 -> 6.18, age x race 18.09 -> 14.72. Worst region:
  **Hispanic x less than high school is 49.7% non-citizen** and 4.56% of ACS adults,
  against 1.82% of weighted CES. Asian x less than high school has the thinnest CES
  coverage of any race x education block: 0.15% of CES against 0.69% of ACS
  (ratio 0.21, **n = 19** unweighted).
- **Income is instrument, not frame**: the citizen restriction makes it *worse*
  (19.48 -> 20.92 pp). ACS is true household dollars (2018), CES is a self-reported
  family-income band; the largest gap is `Less than $30,000` ACS 17.3% vs CES 24.7%.
  This is the difference OPEN item 1 already rakes away.
- **Age is neither**: 13.43 -> 13.04 pp under the citizen cut. CES is 60+ 35.7% against
  ACS 2018's 29.0%; part is the 2018 vs 2023 vintage, the rest is the vote-choice
  post-stratification. The pool rakes age to the census, so this enters only through P(party | X).

**Does it matter for this use?** The donor is asked to speak in exactly those regions:

- 21.1% of ACS weight lands in a cell too thin for the full 5-key
  (age+gender+race+educ+income 78.9%, age+gender+race+educ 19.4%, age+race+educ 0.8%, race+educ 0.9%),
  over 1,199 occupied ACS cells; 1.05% of ACS weight sits in cells with **zero**
  CES respondents.
- The biggest single fallback cell is `30-44, Male, Hispanic / Latino, Less than high school, $56,000 to $99,999`
  — 0.22% of ACS adults, **n = 5** CES respondents
  (26.9 weighted units against the 30-unit threshold); it borrows P(party | X) with income dropped.
  Seven of the ten largest fallback cells are Hispanic (six of those at HS-or-less); the other
  three are white, high-school-educated, household income $168,000+ (CES n = 48, 16, 35).
- **What dropping income costs**: over the 147 CES cells where both the 5-key and the 4-key
  conditional are well estimated (>= 100 weighted units, 57.0% of ACS weight), the two
  conditionals differ by **6.09 pp mean total variation** (p90 11.62 pp). That is the per-cell
  price paid on the 19.4% of weight that falls back one level — and it is measured only
  where CES is *thick*, so it is a floor.

## Coding checks against the CES codebook (`CCES24_Common_pre.docx`, `CES_2024_GUIDE_vv.pdf`)

Verified correct: `educ` 1-6 (build_pool folds 3,4 -> "Some college or Associate's degree", splits
code 6 into MA/PhD at 11.431% from ACS); `gender4` 1 Man / 2 Woman / 3 Non-binary / 4 Other (3,4 ->
"Other"); `race` 1-8 with **8 = Middle Eastern** (166 rows) folded into "Other" alongside 5/6/7;
`faminc_new` band edges — code 6 ($50,000-59,999) split 60/40 at $56,000 and code 12
($150,000-199,999) split 36/64 at $168,000 are both the uniform-within-band answer.

Two deviations worth naming:

1. **`pid3 == 5` is "Not sure", not "Independent".** build_pool maps it to Independent.
   2,442 rows, **6.98% of CES weight**. It moves the Independent share from
   29.30% to 34.24% — and 34.24% is precisely the party marginal
   `inputs/pool/provenance.json` deposits and rakes onto. If the target's item has no "not sure"
   option, this is the right fold only if "not sure" respondents behave like Independents; if it has
   one, the pool has no cell for them. Recorded, not changed.
2. **`faminc_new == 97` ("Prefer not to say") is dropped**, 5,119 rows = 9.23% of CES weight
   (+23 missing). They are dropped from the income margin *and* from the donor's income
   conditionals, i.e. treated as missing-at-random within the other four demographics.

## Bottom line for OPEN item 9

The machinery is not the problem. Fallback/smoothing costs 2.21 pp L1 at worst on an
unconstrained three-way; the two-way rake removes the two-way error by construction and 2-50% of
the three-way error; the deposited pool's party-conditional distance from CES is inside CES's own
sampling noise on all nine surfaces. What is unmeasured, and unmeasurable from what is mounted, is
whether CES's `P(party | X)` is the target panel's — and D shows the donor is being borrowed hardest
exactly where the CES frame is weakest (non-citizen-heavy Hispanic and Asian low-education cells,
1.05% of ACS weight with no CES respondent at all).
