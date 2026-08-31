# DATA_format.md — profile pool + response-format / distribution evidence

Scope: `/workspace/datasets/{acs,ces,gatewaybelief,orchinik2024,sce}`.
Authoring/recon only: no full-file computation, no model calls. Everything below is either
(a) quoted from a file I read, or (b) computed on a header / first-N-rows slice, which is
labelled as such. UNVERIFIED = stated but not checked against data by me.

Target-side facts used here come from `/workspace/benchmark/codebook.csv` (63 rows x 5 cols:
`section,qualtrics_label,target_label,question_text,response_options`) and
`/workspace/benchmark/raw_data_deposit/example_raw_export.csv` — both are instrument/format
files, no human results.

---

## 0. Target moderator levels — verbatim from `/workspace/benchmark/codebook.csv`

| target_label | `response_options` (verbatim, section A "Measured items") |
|---|---|
| `gender` | `Exact submission levels: Male \| Female \| Other (raw Qualtrics codes 1 \| 2 \| 3)` |
| `year_birth` | `Free numeric` — "Year of birth (used to derive age and age_band)" |
| `race` | `Exact submission levels: White / Caucasian \| Black / African American \| Hispanic / Latino \| Asian / Asian American \| Other (raw Qualtrics codes 1–5; the survey's on-screen labels hyphenate slightly differently — clean.R accepts both, but score files must carry these exact strings)` |
| `education` | `Exact submission levels: Less than high school \| High school diploma / GED \| Some college or Associate's degree \| Bachelor's degree \| Master's degree / Professional degree \| Doctorate degree / Ph.D. (raw Qualtrics codes 1–6)` |
| `income` | `Exact submission levels: Less than $30,000 \| $30,000 to $55,999 \| $56,000 to $99,999 \| $100,000 to $167,999 \| $168,000 or more (raw Qualtrics codes 1–5)` — question_text: **"Household income"** |
| `party` | `Exact submission levels: Republican \| Democrat \| Independent \| Other (raw EXPORTED Qualtrics codes: 1=Republican, 2=Democrat, 3=Independent, 4=Other — the on-screen choice order is Rep/Ind/Dem/Other, but Qualtrics recodes on export)` |
| `age_band` (section B, constructed) | `Exact submission levels: 18-29 \| 30-44 \| 45-59 \| 60+`; question_text: `Age band, cut from age = 2026 − year_birth` |

Two format facts that constrain everything below, from the same codebook:
- `donation_ams`: `$0–$10 in whole-dollar choices ($1 increments; integers only). **All 0–100 slider items are also integers.**`
- Composites (`section B. Constructed during cleaning`, 13 rows) are means of items:
  `trust_multidimensional` = mean of the four subscales, each = mean of 3 items (12 items);
  `policy_role_mean` = mean of `policy_role_1..4`; `inst_trust_mean` = mean of 5 `inst_trust_*`;
  `concern_mean` = mean of `concern_1..3`; `policy_specific_mean` = mean of 7 items;
  `behavior_mean` = mean of 6 items; `funding_perceptions` = `100 − funding_5`.
  Tier-1 deposit is a **raw item-level Qualtrics export** (`example_raw_export.csv`, 1,022 rows ×
  69 cols; row 0 = question labels, row 1 = `{"ImportId":...}` JSON, data from row 2; item columns
  `trust_competent_1 … individual_donate_1`, `donation` integer 0–10, `newsletter` raw 1=Yes/2=No),
  so composites are re-derived from items → **the generator must emit items, not composites.**

---

## 1. ACS — `/workspace/datasets/acs`

### 1.1 Files, format, size (verified)
- Person file, two parts, SAS7BDAT (**not** CSV):
  - `/workspace/datasets/acs/downloads/unix_pus/psam_pusa.sas7bdat` — **1,648,512 rows × 286 cols**
  - `/workspace/datasets/acs/downloads/unix_pus/psam_pusb.sas7bdat` — **1,566,027 rows × 286 cols**
  - identical column lists (verified: `names_a == names_b` → True). **Total 3,214,539 person records.**
  - read via `pandas.read_sas(path, format='sas7bdat', chunksize=...)`; header read costs ~5 ms.
    Character variables come back as **bytes** (`b'01'`), numerics as float64 (verified on a
    500-row chunk).
- Codebook: `/workspace/datasets/acs/downloads/PUMS_Data_Dictionary_2018.pdf` (132 pages; all code
  values below are extracted verbatim from it).
- Manifest `/workspace/datasets/acs/dataset_acs.json` lists exactly the two `.sas7bdat` files as
  `data_files`/`primary`.

### 1.2 The variables needed, with dictionary text
| PUMS var | dict entry (verbatim, abbreviated) |
|---|---|
| `PWGTP` | `PWGTP Numeric 5 / Person's weight / 1..9999 .Integer weight of person` — **the person weight**. `PWGTP1..PWGTP80` are the 80 replicate weights (present, for SEs only). |
| `AGEP` | `AGEP Numeric 2 / Age / 0 .Under 1 year / 1..99 .1 to 99 years (Top-coded)` |
| `SEX` | `SEX Character 1 / Sex / 1 .Male / 2 .Female` |
| `RAC1P` | `Recoded detailed race code / 1 White alone / 2 Black or African American alone / 3 American Indian alone / 4 Alaska Native alone / 5 AI/AN tribes specified... / 6 Asian alone / 7 Native Hawaiian and Other Pacific Islander alone / 8 Some Other Race alone / 9 Two or More Races` |
| `HISP` | `Recoded detailed Hispanic origin / 01 .Not Spanish/Hispanic/Latino / 02 Mexican / 03 Puerto Rican / ... / 24 All Other Spanish/Hispanic/Latino` (24 levels) |
| `SCHL` | `Educational attainment / bb N/A (<3 yrs) / 01 No schooling completed / ... / 15 12th grade - no diploma / 16 Regular high school diploma / 17 GED or alternative credential / 18 Some college, but less than 1 year / 19 1 or more years of college credit, no degree / 20 Associate's degree / 21 Bachelor's degree / 22 Master's degree / 23 Professional degree beyond a bachelor's degree / 24 Doctorate degree` |
| `PINCP` | `Total person's income (signed, use ADJINC to adjust) / bbbbbbb N/A (less than 15 years old) / 0 None / -19998 .Loss of $19998 or more / -19997..-1 / 1..4209995 (Rounded & top-coded)` |
| `ADJINC` | `Adjustment factor for income and earnings dollar amounts (6 implied decimal places) / 1013097 .2018 factor (1.013097)` — constant in this file (verified: all sampled rows `b'1013097'`). |
| `SERIALNO`,`SPORDER`,`RELP` | household id / person number within household / relationship to reference person — needed for the household-income workaround in §1.4. |
| `POVPIP` | income-to-poverty ratio (present; NA for GQ residents — verified NaN on GQ rows in the first chunk). |

### 1.3 Recode table — PUMS → EXACT target strings

**Filter first:** `AGEP >= 18` (target = U.S. adults). Optionally drop group-quarters records
(`SERIALNO` beginning `2018GQ`) — an online survey panel does not sample GQ. UNVERIFIED whether
the target sample excludes GQ; recommend dropping (institutionalized population is unreachable).

`age_band` (from `AGEP`; note ACS is a 2018 file, target age is 2026 − year_birth — see §1.5):
| AGEP | level |
|---|---|
| 18–29 | `18-29` |
| 30–44 | `30-44` |
| 45–59 | `45-59` |
| 60–99 (top-coded) | `60+` |

`gender` (from `SEX`):
| SEX | level |
|---|---|
| `1` | `Male` |
| `2` | `Female` |
| — | `Other` — **ACS cannot produce this level.** ACS 2018 has no non-binary/other category. Must be injected exogenously; the CES 2024 rate is the natural donor: `gender4` = Non-binary 448 + Other 106 out of 60,000 = **0.92%** (CES guide p. 28–29). AMBIGUOUS: whether the target's "Other" also absorbs "prefer not to say". |

`race` (from `HISP` + `RAC1P`, **Hispanic takes precedence**):
| condition | level |
|---|---|
| `HISP != '01'` (any of codes 02–24) | `Hispanic / Latino` |
| else `RAC1P == '1'` | `White / Caucasian` |
| else `RAC1P == '2'` | `Black / African American` |
| else `RAC1P == '6'` | `Asian / Asian American` |
| else `RAC1P in {3,4,5,7,8,9}` | `Other` |

AMBIGUITIES (flagged):
- **Hispanic precedence is a choice, not a fact.** The target instrument is a single-choice
  race/ethnicity item with Hispanic as one of 5 options (codebook `raw Qualtrics codes 1–5`), i.e.
  respondents self-sort; ACS asks race and Hispanic origin separately. Precedence (Hispanic wins)
  reproduces the "bridged" convention and is what a single-choice item approximates, but a
  Hispanic White respondent choosing "White / Caucasian" is possible in the target and impossible
  under this rule. Sensitivity: `RAC1P == 8` ("Some Other Race alone") is overwhelmingly Hispanic
  write-ins; after precedence, residual code-8 lands in `Other`.
- `RAC1P == 7` (NHPI) and `9` (Two or More Races) both fall in `Other`; the target has no
  multiracial option, so a multiracial respondent's actual choice is unknowable. UNVERIFIED.
- ACS "Asian alone" (`6`) excludes Middle Eastern (coded White in ACS); the target's `Other`
  probably absorbs MENA. Cross-check: CES has an explicit `Middle Eastern` code (§2).

`education` (from `SCHL`) — this mapping is clean, no straddles:
| SCHL | level |
|---|---|
| `bb`,`01`–`15` (through "12th grade - no diploma") | `Less than high school` |
| `16` (regular HS diploma), `17` (GED) | `High school diploma / GED` |
| `18`,`19` (some college), `20` (Associate's) | `Some college or Associate's degree` |
| `21` | `Bachelor's degree` |
| `22` (Master's), `23` (Professional beyond bachelor's) | `Master's degree / Professional degree` |
| `24` | `Doctorate degree / Ph.D.` |

`income` — **BLOCKED. The vendored ACS is the PERSON file only.**
- Verified from the 286-column list: `PINCP` (person total income), `PERNP`, `WAGP`, `SEMP`,
  `INTP`, `RETP`, `SSP`, `SSIP`, `PAP`, `OIP`, `POVPIP` are present; **`HINCP` and `FINCP` are
  NOT** (they exist in the data dictionary — `HINCP Numeric 7 / Household income (past 12 months...)`
  — but only on the HOUSING record, and `unix_hus.zip` / `psam_hus*.sas7bdat` is not mounted;
  `ls /workspace/datasets/acs/downloads/unix_pus/` = `psam_pusa.sas7bdat, psam_pusb.sas7bdat,
  ACS2018_PUMS_README.pdf` only).
- The target asks **"Household income"** (codebook). Using `PINCP` instead is a construct swap
  and would badly bias the low bands (every non-earning spouse/student lands in `Less than $30,000`).
- Three options, in order of preference:
  1. **Reconstruct household income from the person file**: `HH_INC ≈ Σ PINCP within SERIALNO`
     (× `ADJINC`/1e6 = 1.013097). Requires one full pass (group-by on 3.2M rows) — cheap, but a
     *computation*, so deferred out of this recon task. Caveats: PINCP is top-coded/rounded per
     person; GQ serials are single-person; ACS "household income" (HINCP) is defined as the sum of
     person incomes of household members 15+, so this reconstruction is close to exact by
     definition — UNVERIFIED against HINCP because the housing file is absent.
  2. **Take income from CES `faminc_new`** (family income, 16 bands) — see §2.4.
  3. Ask the operator for `unix_hus.zip`.
- **Band-edge ambiguity regardless of source**: the target bands cut at **$30,000 / $56,000 /
  $100,000 / $168,000**. $56,000 and $168,000 are not standard survey band edges and fall *inside*
  CES bands 6 (`$50,000 - $59,999`) and 12 (`$150,000 - $199,999`). Continuous ACS income has no
  such problem; CES needs a within-band split rule (§2.4).
- Second ambiguity: **inflation base year.** ACS is 2018 dollars (`ADJINC` 2018 factor), CES asks
  about 2023/24 income, the target fields in 2026. A 2018-dollar pool put into 2026 bands
  understates the top bands by ~25–30% cumulative CPI. Must deflate/inflate explicitly; UNVERIFIED
  which base the target's respondents will implicitly use (they self-report nominal 2025/26 income).
- **No party variable exists in ACS at all** (verified against the 286-column list). This is the
  decisive fact in §2.5.

### 1.4 Weights
`PWGTP` is the person weight; sum over adults gives the U.S. 18+ population. Use it (a) to draw the
profile pool with probability ∝ `PWGTP`, or (b) to compute the raking targets. Replicate weights
`PWGTP1..80` are only needed for standard errors — the benchmark scores point estimates
(AGENTS.md/system prompt: "only point estimates are scored"), so skip them.

### 1.5 Vintage problem (both pools)
ACS is **2018**, CES is **2024**, the target study fields in **2026** with `age = 2026 − year_birth`.
Do **not** shift a respondent's birth year forward (that empties the 18–19 cell: the youngest CES
respondent in the sampled block is `birthyr` 2006 → age 20 in 2026). Instead treat the pool as a
joint distribution over `(age_band, gender, race, education, income, party)`, **rake it to 2026
quota marginals**, then generate `year_birth = 2026 − U{band bounds}` (with `60+` drawn from an
ACS-shaped age tail, not uniform).

---

## 2. CES — `/workspace/datasets/ces`

### 2.1 Files (verified)
- `/workspace/datasets/ces/downloads/CCES24_Common_OUTPUT_vv_topost_final.csv` — **694 columns**
  (verified by reading the header); README states **60,000 rows**; the Guide's per-item tables all
  total `N 60000` (e.g. gender4 27454+31992+448+106 = 60000, verified arithmetically). 177 MB.
- `/workspace/datasets/ces/downloads/cumulative_2006-2025.feather` — 718,955 × 109 (README; not opened).
- Codebooks: `CES_2024_GUIDE_vv.pdf` (95 pp) and the questionnaire `CCES24_Common_pre.docx`
  (the **docx gives the numeric codes explicitly**; the Guide gives only labels + N, and its
  label/N alignment is off by one line in the PDF text layer — verified by summing).

### 2.2 Columns and codings (codes verified from `CCES24_Common_pre.docx`; frequencies cross-checked
against the Guide and against the first 2,000 rows of the CSV — "sample" below = those 2,000 rows,
**not** a random sample)

| column | dtype | codes (verbatim from the questionnaire docx) | Guide N (of 60,000) |
|---|---|---|---|
| `birthyr` | int64 | free numeric; sampled min 1934, max 2006 | — |
| `gender4` | int64 | `1 Man, 2 Woman, 3 Non-binary, 4 Other` | 27454 / 31992 / 448 / 106 |
| `educ` | int64 | `1 Did not graduate from high school, 2 High school graduate, 3 Some college, but no degree (yet), 4 2-year college degree, 5 4-year college degree, 6 Postgraduate degree (MA, MBA, MD, JD, PhD, etc.), 8 Skipped, 9 Not Asked` | 2133 / 15983 / 13961 / 6666 / 13297 / 7960 |
| `race` | int64 | `1 White, 2 Black or African-American, 3 Hispanic or Latino, 4 Asian or Asian-American, 5 Native American, 8 Middle Eastern, 6 Two or more races, 7 Other (open race_other), 98 Skipped, 99 Not Asked` — **note the non-monotone order: 8 = Middle Eastern sits between 5 and 6** | White 41443, Black 7728, Hispanic 5150, Asian 1949, Native American 582, Middle Eastern 166, Two or more 1947, Other 1035 (sums to 60000) |
| `hispanic` | int64 | `1 Yes, 2 No` (asked only if `race != 3`) | 7647 / 52352 (N 59999) |
| `pid3` | int64 | `1 Democrat, 2 Republican, 3 Independent, 4 Other, 5 Not sure` | 22982 / 15913 / 16292 / 2371 / 2442 |
| `pid7` | int64 | `1 Strong Dem, 2 Not very strong Dem, 3 Lean Dem, 4 Independent, 5 Lean Rep, 6 Not very strong Rep, 7 Strong Rep, 8 Not sure` (standard order; confirmed by matching sample shares to Guide N: Strong Dem 28.2% vs 27.6%, code 7 18.2% vs Strong Rep 18.0%, code 4 14.6% vs Independent 13.2%, code 8 1.9% vs Not sure 2.1%) | 16576 / 6406 / 6504 / 7891 / 5448 / 5087 / 10826 / 1262 |
| `faminc_new` | int64 | `1 Less than $10,000, 2 $10,000-$19,999, 3 $20,000-$29,999, 4 $30,000-$39,999, 5 $40,000-$49,999, 6 $50,000-$59,999, 7 $60,000-$69,999, 8 $70,000-$79,999, 9 $80,000-$99,999, 10 $100,000-$119,999, 11 $120,000-$149,999, 12 $150,000-$199,999, 13 $200,000-$249,999, 14 $250,000-$349,999, 15 $350,000-$499,999, 16 $500,000 or more, 97 Prefer not to say, 998 Skipped, 999 Not Asked` — code 97 verified present in the sample (177/2000 = 8.9%) | 3259, 4373, 5849, 5236, 4764, 4817, 3679, 4058, 4853, 3929, 4083, 3037, 1366, 912, 375, 268; Prefer-not 5119; N 59977 |
| `ideo5` | int64 | 1–5 + 6 ("Not sure"); useful auxiliary, not a target moderator | — |
| `inputstate`, `region` | int64 | FIPS / 1–4 | — |
| `commonweight` | float64 | **the weight to use** | — |

Wording of the income item (docx): *"Thinking back over the last year, what was your family's
annual income?"* → **family**, not household. Target says "Household income". Near-equivalent for
most respondents; flag as a construct mismatch (roommates, adult children).

### 2.3 Weights (Guide, "Using Weights", verbatim)
`commonweight` — All respondents — target population **Adults**;
`commonpostweight` — answered both waves — Adults;
`vvweight` / `vvweight_post` — validated registered voters. Guide: *"We recommend the use of
'commonweight' any time researchers wish to characterize the opinions and behaviors of adult
Americans."* → **use `commonweight`**. Sampled mean 1.035, median 0.660, max 13.78 (first 2,000 rows).

### 2.4 CES → EXACT target strings
- `gender`: `1 → Male`, `2 → Female`, `3,4 → Other`. (Exact match to the target's 3 levels.)
- `age_band`: `age = 2024 − birthyr` → cut 18-29 / 30-44 / 45-59 / 60+ (see the vintage caveat §1.5).
- `race`: `1 → White / Caucasian`; `2 → Black / African American`; `3 → Hispanic / Latino`;
  `4 → Asian / Asian American`; `5,6,7,8 → Other`. Optional Hispanic-precedence overlay:
  `hispanic == 1 → Hispanic / Latino` (this moves ~2,400 self-identified-other Hispanics;
  Guide `multrace - Hispanic` = 2,395). Choose ONE rule and state it. AMBIGUOUS.
- `education`: `1 → Less than high school`; `2 → High school diploma / GED`;
  `3,4 → Some college or Associate's degree`; `5 → Bachelor's degree`; **`6 → ???`**.
  **This is the worst mapping problem in CES.** CES collapses all postgraduate degrees into one
  code (7,960 respondents), while the target splits `Master's degree / Professional degree` from
  `Doctorate degree / Ph.D.`. A split is needed; ACS `SCHL` gives the exact split ratio among
  postgrads (`22`+`23` vs `24`) and should be used to allocate CES code 6 stochastically.
  UNVERIFIED ratio (needs the full-pass ACS tabulation; ~1 in 8–9 U.S. postgrad degrees is a
  doctorate, order-of-magnitude only).
- `income` (`faminc_new` → 5 target bands). Exact where possible, split where the target edge
  falls inside a CES band:
  | target band | CES codes | note |
  |---|---|---|
  | `Less than $30,000` | 1,2,3 | exact ($0–29,999) |
  | `$30,000 to $55,999` | 4,5 + **0.6 of code 6** | code 6 = $50,000–59,999 straddles $56,000; uniform-within-band → 6/10 of it is below $56,000 |
  | `$56,000 to $99,999` | **0.4 of code 6** + 7,8,9 | |
  | `$100,000 to $167,999` | 10,11 + **0.36 of code 12** | code 12 = $150,000–199,999 straddles $168,000; uniform → 18/50 = 0.36 below |
  | `$168,000 or more` | **0.64 of code 12** + 13,14,15,16 | |
  | (drop / impute) | 97 "Prefer not to say" (5,119 = 8.5%) | must be imputed, the target has no such level |
  The straddle splits above assume a **uniform** density within the CES band. A log-normal /
  Pareto-tail density puts slightly more mass low in band 6 and low in band 12; the difference is
  ~1–2 pp of the population in each band. Flag as a modelling choice; recommend fitting a
  log-normal to the 16 CES band boundaries (weighted by `commonweight`) and integrating.
- `party`: `pid3`: `1 → Democrat`, `2 → Republican`, `3 → Independent`, `4 → Other`,
  **`5 "Not sure" (2,442 = 4.1%) → ???`**. The target has no "Not sure" — force to `Independent`
  (defensible: a forced-choice 4-option item pushes not-sures to Independent) or to `Other`.
  AMBIGUOUS; recommend `Independent` and record the choice. Note the target's on-screen order is
  Rep/Ind/Dem/Other (codebook), which mildly favours Republican via primacy — irrelevant for a
  synthetic pool, relevant if we ever calibrate party shares to a published crosstab.

### 2.5 Judgement: which pool?
**Neither alone. Use CES as the pool of record, raked to ACS marginals.** Reasons:
1. `party` is a required moderator (13 outcomes × 4 party levels enter the Section-3 subgroup
   metrics) and **ACS has no party variable** — verified against the 286-column list. Imputing
   party into ACS requires a donor model estimated from CES anyway, and that model can only use
   variables the two share (age, gender, race, education, income, state) — which is exactly the
   conditional distribution `P(party | X)` that CES already carries jointly, with the true
   party×education×race correlations intact. Drawing from CES preserves the joint; imputing into
   ACS destroys it (adds a conditional-independence assumption).
2. CES is a 2024 opt-in online panel (YouGov, matched + weighted) — the *same population and mode*
   as a 2026 online megastudy with census quotas. ACS is an address-based mandatory survey; its
   composition is right, its response style is irrelevant here (we only take demographics).
3. ACS wins on: exact continuous income (if the household file is obtained or reconstructed), the
   postgrad split (`SCHL` 22/23 vs 24), true 18–19 coverage, and its person weights are the
   accepted population benchmark.

**Concrete joint approach (asset "D1"):**
1. Build `ACS_ADULT` = both `.sas7bdat` parts, `AGEP >= 18`, non-GQ, columns
   `SERIALNO, SPORDER, PWGTP, AGEP, SEX, RAC1P, HISP, SCHL, PINCP, ADJINC` → recode §1.3 →
   weighted marginals and the 3-way `age_band × gender × race` table (this is the census quota the
   target study says it used) plus `education` and `income` marginals. One full pass, once,
   cached to parquet.
2. Build `CES_ADULT` = 60,000 rows, columns `commonweight, birthyr, gender4, educ, race, hispanic,
   pid3, pid7, faminc_new, inputstate` → recode §2.4, imputing `faminc_new == 97` and splitting
   `educ == 6` with ACS ratios.
3. **Rake** (IPF) `commonweight` to the ACS targets on: `age_band × gender × race` (the stated
   quota, so match it exactly), and marginally on `education` and `income`. Leave `party` free —
   it is then implied by the ACS-consistent demographics + the CES joint, which is the honest
   prediction of the target sample's partisan composition.
4. Draw the N synthetic respondents (≥ 500 per intervention, ≥ 1,000 control → ≥ 9,000 minimum;
   ~18,000 to mirror the target) **with replacement, ∝ raked weight**, then jitter `year_birth`
   within `age_band`.
5. Emit the exact strings of §0 (and the raw Qualtrics integer codes for the Tier-1 deposit:
   gender 1/2/3, race 1–5, education 1–6, income 1–5, party 1=Rep 2=Dem 3=Ind 4=Other — note the
   party code order is **not** alphabetical and **not** the on-screen order).

Cross-check available for free: the Guide's per-item `N` table is a published marginal of the CES
itself; `pums_estimates_18.csv` in `/workspace/datasets/acs/publications/` is the Census Bureau's
published per-state estimates + SEs "to reproduce" (README) — use it to validate the ACS pass.

---

## 3. GATEWAYBELIEF — the 0–100 slider ↔ 1–7 Likert bridge

Path: `/workspace/datasets/gatewaybelief/downloads/`. No codebook; the `.R` scripts are the
documentation (README). Three files, all read as CSV with pandas (shapes verified):

### 3.1 Experiment 1 — Maertens, Anseel & van der Linden 2020 — **the cleanest bridge**
`Experiment 1 data Maertens et al 2020.csv` — **479 × 58**, self-documenting column names.
Paired within-person, at three timepoints (T1 pre, T2 post-message, T3 post-misinfo):

| construct | column | scale (verified on first 400 rows) |
|---|---|---|
| perceived scientific consensus | `PSC.T1`, `PSC.T2`, `PSC.T3` | **0–100 integer slider** (T1: min 1, max 100, 60 distinct values; T3: min 0, max 100, 53 distinct) |
| belief in climate change | `Belief.T1/.T2/.T3` | **1–7 integer** (7 distinct) |
| human causation | `HumanCausation.T1/.T2/.T3` | 1–7 integer |
| worry | `Worry.T1/.T2/.T3` | 1–7 integer |
| support for action | `SupportForAction.T1/.T2/.T3` | 1–7 integer |
Also: `Condition` (Control/Consensus/Inoculation/Balanced), `Consensus`/`Inoculation`/`Misinfo`
dummies, `Age`, `Age_Category`, `Sex`, `Education` (1–5), `Education_Category`, `PoliticalParty`,
`Ideology` (1–7), `Ideology_Category`, and pre-computed difference scores `*_Diff_T2T1` etc.
n complete at T3 = 345 of the first 400 rows (attrition).

### 3.2 Experiment 2 — van der Linden et al. 2017
`Experiment 2 data van der Linden et al 2017.csv` — **2,197 × 33**, Qualtrics Q-numbers. Map from
`Experiment 2 analysis.R` (verbatim renames):
- `Q8_1 → psc.T1`, `Q36_1 → psc.T2` — **0–100 slider** (first 400 rows: T1 min 5 max 100, 68
  distinct values, mean 74.5; T2 min 0 max 100, 69 distinct, mean 77.4)
- `Q10_1 → worry.T1`, `Q38_1 → worry.T2` — **1–7 integer** (7 distinct, mean 4.8 / 5.0)
- `Q11_1 → action.T1`, `Q39_1 → action.T2` — **1–7 integer** (7 distinct, mean 5.8 / 5.8)
- belief and human-causation are **5-point recodes** built in R from branching items
  (`Q3_1,Q5_1,Q31_1,Q33_1` → `belief.T1/T2` 1–5; `Q6_1,Q7_1,Q34_1,Q35_1` → `hcaused.T1/T2` 1–5)
- demographics (from the script's own comments): `Q49` gender `2 = male, 3 = female`;
  `Q50` age `1 = 18-24, 2 = 25-44, 3 = 45-64, 4 = 65+`; `Q51` education
  `1 = Some high school or less, 2 = High school graduate, 4 = College graduate,
  5 = Graduate School Degree, 6 = Some College / Associates / Vocational`;
  `Q53` party `1 = Republican, 2 = Democrat, 3 = Indep`; `Q54_1` ideology
  `8 = very liberal ... 1 = very conservative`; condition in `FL_32_DO`.
- README: "pre-PSC × pre-worry r ≈ 0.47 on N = 2,173" — a within-person slider↔Likert correlation
  usable directly as ρ in §5.4.

### 3.3 Supplemental study — Maertens et al. 2025
`Supplemental study data Maertens et al 2025.csv` — **1,825 × 384**. `PSC.Pre/.T1/.T2/.T3` are
0–100 integer sliders (first 400 rows: Pre min 6 max 100, 55 distinct); `BeliefInCC.*`,
`HumanCausation.*`, `Worry.*`, `SupportForAction.*` are **continuous 1–7 sliders** (37–48 distinct
values in 400 rows), i.e. NOT a Likert bridge — but they are the one source here for what a
*continuous* attitude slider's shape looks like. `Group` (Control/Inoc/InocInoc) × `Measurement`
(T1/T2/T3), `Gender` (string: Female/Male/Other:/Non-binary/Transgender), `PoliticalParty`
(string: Republican/Independent/Democrat), `Education` 1–5, `Ideology` 1–7, `Age_Year` (birth year).

### 3.4 What can be estimated from it (the bridge we actually need)
The target study has NO Likert items — everything is a 0–100 slider. The bridge is needed in the
**other** direction: published priors on climate/science attitudes (TISP, GSS, Pew) are 1–5 / 1–7
Likert distributions, and we must turn "mean 3.9 on a 1–5 scale, SD 1.0" into "mean 68 on 0–100,
SD 24" to anchor `belief_post`, `concern_mean`, `inst_trust_mean`, `trust_post`, etc.
Estimable here, all within-person and all on climate constructs:
1. **Location map** `E[slider | Likert = k]`, k = 1..7, per construct (worry, support for action,
   belief) — 4 constructs × up to 3 timepoints in Exp 1 (n = 479) and 2 constructs × 2 timepoints
   in Exp 2 (n = 2,197). Pooled n for the (PSC-slider, worry-Likert) pair alone ≈ 2,600 persons.
   The naive map (`(k−1)/6 × 100`) is almost certainly wrong: Likert categories are unequally
   spaced on the latent scale and the slider carries endpoint bunching the Likert cannot show.
2. **Dispersion map** `SD[slider | Likert = k]` — the *within-Likert-category* slider SD, which is
   exactly the variance a Likert-anchored prior throws away and the quantity the Tier-1 variance
   ratio punishes us for missing.
3. **Rank/copula link**: with both scales on the same people, fit an ordered-probit /
   normal-copula: latent z ~ N(0,1), Likert = cut(z), slider = F⁻¹_slider(Φ(z)). Then any published
   Likert marginal maps to a slider marginal by matching quantiles. (README gives r ≈ 0.47 between
   PSC-slider and worry-Likert — different constructs, so treat that as a lower bound on the
   same-construct link; the same-construct link is what Exp 1's Belief-vs-PSC and the T1/T2/T3
   repeats let you estimate.)
4. **Effect-size proxy**: all three studies randomize a consensus/inoculation message, so
   Δslider(PSC) per arm is an ATE on a 0–100 climate slider from a real experiment — directly in
   the benchmark's pp units. (Use for prior width on our 16 interventions, not for the bridge.)

CAVEAT: every 0–100 item here is *perceived scientific consensus* — a **percentage** quantity
("what % of scientists agree"), the same family as SCE's "percent chance". The target's sliders are
**attitude/agreement** sliders with verbal anchors (`0 = Very uneager … 100 = Very eager`). Heaping
and endpoint behaviour on percentage items is an upper bound for attitude items. UNVERIFIED.

---

## 4. ORCHINIK2024 and SCE — the heaping evidence

### 4.1 Orchinik et al. 2024 (Bovitz quota-matched U.S. sample)
Path `/workspace/datasets/orchinik2024/downloads/data/final_clean.csv` — **3,478 rows × 68 cols**
(README; header verified = 68 columns); analysis sample = `drop == FALSE` → **n = 2,545** (README).
0–100 slider columns (verified numeric, range 0–100, 75–78 distinct values in the first 400 rows):
`prior_cc_occur`, `prior_consensus_num`, `prior_cc_occur_conf`, `prior_consensus_num_conf`,
`prior_sci_always_E_yes`, `prior_sci_always_E_no`, `prior_sci_unbiased`,
`P_E_yes_given_cc_unbiased`, `P_E_no_given_no_cc_unbiased`, and the 25 within-subject conditional
items `P_{cc,pro_bias,anti_bias,pro_skill,anti_skill}_given_cons{50,75,90,97,99}`.
Non-slider moderators: `age` (free numeric, junk values 0.1/1111 exist per README), `gender`
(1 Male, 2 Female, 5 Non-Binary, 6 Not listed, 7 Prefer not to answer — from `Bovitz qualtrics.docx`),
`race` (**multi-select, stored as comma-joined codes**, e.g. `'1,14'`, `'4,10,11'`; options
`4 White/Caucasian, 3 Black or African American, 1 American Indian or Alaska Native,
10 Native Hawaiian or other Pacific Islander, 11 Hispanic/Latino, 12 Indian, 13 Middle Eastern,
14 Chinese, 15 Other`), `edu` (`1 Less than a high school degree, 2 High School Diploma,
3 Vocational Training, 4 Attended College, 5 Bachelor's Degree, 6 Graduate Degree, 7 Unknown`),
`income` (`1 Less than $20,000, 2 $20,000-$39,999, 3 $40,000-$59,999, 4 $60,000-$79,999,
5 $80,000-$99,999, 6 $100,000-$149,999, 7 $150,000 or more` — "your entire household income in
(previous year) before taxes"), `party` (`1 Democrat, 2 Republican, 3 Independent, 4 Other`),
`politics` 1–7, `god` 0–7, `gov.trust`/`pol.party.trust`/`uni.science.trust`/`priv.science.trust`
(4-point, 1–4 = "None at all" … "A great deal of confidence"; the derived `uni_sci_trust` /
`priv_sci_trust` columns are all-NA — README), `condition` (control/skill/trust).
Instrument evidence (`qualtrics/Bovitz qualtrics.docx`): the 0–100 items are **visual sliders with
tick labels every 10** (the rendered scale prints `0 10 20 30 40 50 60 70 80 90 100`), and the
attention check reads verbatim *"Please drag the slider between 20 and 30 for each of the questions
below."* → drag-slider UI with decade tick marks; that UI is the mechanical cause of the heaping.

**Heaping facts, verbatim from `/workspace/datasets/orchinik2024/README.md` ("Why it is here"):**
> "Verified heaping on the raw 0–100 belief items (9 items pooled, analysis sample, 22,905
> responses): 1.8% at 0, 3.2% at 50, 13.7% at 100 (15.5% at either endpoint), 42.5% on multiples
> of 5, 32.3% on multiples of 10. The top endpoint dominates: e.g. `prior_cc_occur` has 22.6% of
> responses at exactly 100 (full-sample), and `P_cc_given_cons99` 24.6%."

Also verbatim (README, Contents): the endpoint recode on the `*_adj` variables is
`0 → 0.497462, 100 → 99.50254`, "used to keep log-odds transforms finite" — evidence that endpoint
mass is large enough to break transforms.
Caveats verbatim: *"use the Bovitz sample only for slider response shape (Lucid used a different
−50…+50 slider); the main DVs are within-subject conditional beliefs ... and the trust items are
4-point categories, not sliders."*

### 4.2 SCE (FRBNY Survey of Consumer Expectations)
Paths (verified sizes on disk):
`downloads/frbny-sce-public-microdata-complete-13-16.xlsx` (56,444 × 220),
`...-complete-17-19.xlsx` (47,681 × 220), `...-20-24.xlsx` (71,976 populated × 229),
`...-latest.xlsx` (10,559 × 229 — verified via openpyxl read_only: single sheet `Data`,
`max_row` 10,561, `max_column` 229; **row 1 = the FRBNY source/disclaimer string, row 2 = the
variable header**, so `pandas.read_excel(..., skiprows=1)`). ~186k person-months pooled.
Header verified to contain: `date, userid, tenure, weight, Q1, Q1a, Q1apart2, Q2, Q3, **Q4new,
Q5new, Q6new**, Q8v2, Q9_bin1..Q9_bin10, ... Q10_1, Q10_2, **Q13new, Q14new, Q22new**, Q32, Q33,
Q34, Q36, Q47, `_AGE_CAT`, `_EDU_CAT`, `_HH_INC_CAT`, `_NUM_CAT`, `_REGION_CAT`,
`_COMMUTING_ZONE`, `_STATE``.
Derived categorical levels seen in the first 10 data rows: `_AGE_CAT` ∈ {Under 40, 40 to 60,
Over 60}; `_EDU_CAT` ∈ {High School, Some College, College}; `_HH_INC_CAT` ∈ {Under 50k,
50k to 100k, Over 100k}; `_NUM_CAT` ∈ {Low, High}; `_REGION_CAT` ∈ {Northeast, Midwest, South, West}.
Weight column: `weight`.
Instrument (`frbny-sce-survey-core-module-public-questionnaire.pdf`), verbatim:
> `Q3intro` — "In some of the following questions, we will ask you to think about the percent
> chance of something happening in the future. Your answers can range from 0 to 100, where 0 means
> there is absolutely no chance, and 100 means that it is absolutely certain. For example, numbers
> like: 2 and 5 percent may indicate 'almost no chance' / 18 percent or so may mean 'not much
> chance' / 47 or 52 percent chance may be a 'pretty even chance' / 83 percent or so may mean a
> 'very good chance' / 95 or 98 percent chance may be 'almost certain'"
> `Q4new` — "What do you think is the percent chance that 12 months from now the unemployment rate
> in the U.S. will be higher than it is now? Instruction H2. **Ruler & box**. If no response: error E1"
(`Ruler & box` = slider ruler + numeric entry box; `error E1` = forced response, hence no missing.)
Note the intro *explicitly discourages* round numbers by example, and respondents heap anyway.

**Heaping facts, verbatim from `/workspace/datasets/sce/README.md` ("Why it is here"):**
> "Verified on `Q4new` pooled across all files (n = 186,302; 100% integer-valued): 75.3% of
> responses are multiples of 5, 61.2% multiples of 10, 16.8% exactly 50, 1.7% at 0, 1.3% at 100 —
> and heaping declines with education (non-multiple-of-5 share: 28.9% high school, 25.6% some
> college, 23.2% college)."
Visible in the first 10 rows of the latest file (`Q4new`): 0, 9, 50, 50, 100, 100, 100, 40, 40 —
consistent.

### 4.3 Side-by-side (the two anchors for the generator)
| statistic | Orchinik 2024 (9 belief sliders, n = 22,905 responses) | SCE `Q4new` (n = 186,302) |
|---|---|---|
| multiples of 10 | 32.3% | 61.2% |
| multiples of 5 (incl. 10s) | 42.5% | 75.3% |
| ends in 5 (5,15,25,…) | 10.2% (42.5 − 32.3) | 14.1% (75.3 − 61.2) |
| not a multiple of 5 | 57.5% | 24.7% |
| exactly 0 | 1.8% | 1.7% |
| exactly 50 | 3.2% | 16.8% |
| exactly 100 | 13.7% | 1.3% |
| item type | belief/probability, drag-slider w/ decade ticks | percent-chance, ruler + numeric box |
The gap is large and is the main uncertainty in §5. Orchinik is the closer analogue (drag slider,
attitude/belief content, quota-matched opt-in U.S. panel, 2023-vintage) and its 50-mass is small;
SCE's huge 50-mass is the "epistemic 50/50" of probability items and should **not** be copied onto
attitude sliders. Recommend Orchinik as default, SCE as the education-gradient donor and as a
sensitivity bound. UNVERIFIED for verbal-anchor attitude sliders — no dataset in this scope has one.

---

## 5. Specification: a human-like 0–100 slider response generator

Inputs per cell: outcome o, condition c, target mean `m` and SD `s` (on the 0–100 scale), plus a
respondent's moderator vector (only `education` is used below). Output: **integers 0–100 at the
ITEM level** (composites are means of items; see §0 — never generate a composite directly, or its
granularity and its variance will both be wrong).

### 5.1 Latent draw (shape)
1. Feasibility: a distribution on [0,100] with mean m has max variance `m(100−m)`. Require
   `s² < m(100−m)`; if violated, only an atoms-at-endpoints mixture can do it.
2. Default family: **scaled Beta**, `x = 100·B(α,β)` with method-of-moments
   `ν = m(100−m)/s² − 1`, `α = ν·m/100`, `β = ν·(1−m/100)`. Beta handles the boundedness and the
   left/right skew that any high-mean attitude item has (target trust means will sit well above
   50, so the distribution must be left-skewed with a ceiling — a Normal would be badly wrong).
   Alternative if a heavier interior mode is wanted: logit-normal.
   *Justified by*: shape of `PSC.T1/T2` in gatewaybelief (mean 74.5, min 5, max 100, mass at 100)
   and `prior_cc_occur` in orchinik2024 — both strongly left-skewed with a ceiling spike.
3. **Endpoint atoms** (applied before rounding; they are not produced by any smooth family):
   `P(0) = π₀`, `P(100) = π₁₀₀`, remaining `1 − π₀ − π₁₀₀` from the Beta refitted to the residual
   mean/variance so the **overall** mean and SD still hit `m`, `s`.
   Defaults from orchinik2024 (README, §4.1): pooled `π₀ = 0.018`, `π₁₀₀ = 0.137`; and the item-level
   evidence that the top endpoint scales with the item mean (`prior_cc_occur` mean-high → 22.6% at
   100; `P_cc_given_cons99` → 24.6%). Implement as a monotone rule rather than a constant, e.g.
   `π₁₀₀ = 0.14·((m−50)/50)⁺^1.0` calibrated so the pooled value is recovered at the pooled mean;
   symmetric rule for `π₀`. Mark the functional form UNVERIFIED (fittable: regress per-item
   endpoint share on per-item mean across the 9 orchinik items + the 3 gatewaybelief PSC items).
   Reverse-coded outcomes (`distrust_post`, `funding_5` before the `100 − x` flip) will have low
   means → their endpoint mass sits at 0 instead; the rule must be mean-driven, not hard-coded.
4. Optional **midpoint atom** `π₅₀`: orchinik 3.2%, SCE 16.8%. Use `π₅₀ ≈ 0.03` for attitude
   sliders; do **not** import SCE's 16.8%.

### 5.2 Heaping (rounding) operator — calibrated, derivable
Apply to each latent value `x`, independently: with probability `a` round to the nearest 10, with
`b` to the nearest 5, with `c = 1 − a − b` to the nearest integer. Then, exactly,
```
P(multiple of 10) = a + 0.5·b + 0.1·c
P(ends in 5)      =     0.5·b + 0.1·c
P(not mult. of 5) =             0.8·c
```
Inverting against the two verified datasets (my arithmetic, from the README figures in §4.3):

| calibration | a (round-to-10) | b (round-to-5) | c (integer) | reproduces |
|---|---|---|---|---|
| **Orchinik (recommended default)** | **0.221** | **0.060** | **0.719** | 32.3% mult-10, 10.2% ends-in-5, 57.5% non-mult-5 ✓ |
| SCE (upper bound, probability items) | 0.471 | 0.220 | 0.309 | 61.2% / 14.1% / 24.7% ✓ |

**Education gradient** (SCE README, verbatim numbers): non-multiple-of-5 share 28.9% / 25.6% /
23.2% for high school / some college / college → implied `c = 0.361 / 0.320 / 0.290` against a
pooled `c = 0.309`, i.e. multipliers **1.17 / 1.04 / 0.94** on `c` (renormalise `a`,`b`
proportionally). Apply the same *relative* multipliers to the Orchinik default `c = 0.719`, mapped
onto the target's 6 education levels as: `Less than high school` & `High school diploma / GED` →
1.17; `Some college or Associate's degree` → 1.04; `Bachelor's`, `Master's/Professional`,
`Doctorate` → 0.94. (SCE also carries `_NUM_CAT` numeracy, which the target does not measure.)
Order of operations: **atoms → Beta draw → rounding → clip to [0,100] → cast int**. Rounding is
mean-preserving to first order and *increases* variance slightly (a coarse-rounding variance of
≈ a·(100/12)·... ) — refit `s` after rounding, or shrink the pre-rounding Beta SD by the
analytically-known rounding variance `a·8.33 + b·2.08 + c·0.083` (variance of a uniform rounding
error with widths 10, 5, 1). Verify by simulation, not by assumption.

### 5.3 Why this matters for the score
The headline Tier-1 diagnostic is **variance ratio (synthetic/human), where < 1 is the documented
LLM failure mode**. Two structural traps:
- Generating a composite directly gives it the *item* SD instead of the (much smaller) composite
  SD, or a smooth continuum instead of the /3, /4, /12 granularity that OVL and KS-D on a fixed
  grid will see. Generate items.
- Generating without atoms and heaping gives a smooth interior distribution: KS-D against a human
  distribution with 13.7% at 100 and 32% on decades is large *even when the mean is exactly right*.

### 5.4 Item-level correlation → composite SD
For a k-item composite with equal item SD `σ_i` and average inter-item correlation ρ:
`SD_composite = σ_i · sqrt((1 + (k−1)ρ)/k)`. Solve for `σ_i` given the target composite SD.
k = 12 (`trust_multidimensional`, via 4 subscales of 3), 4 (`policy_role_mean`),
5 (`inst_trust_mean`), 3 (`concern_mean`), 7 (`policy_specific_mean`), 6 (`behavior_mean`).
ρ must be assumed: multi-item trust subscales typically α ≈ 0.85–0.95 → ρ ≈ 0.6–0.8 within
subscale, lower across subscales. **UNVERIFIED — no dataset in my scope has a multi-item 0–100
trust battery.** The nearest empirical anchor in scope is the cross-construct
slider↔Likert r ≈ 0.47 (gatewaybelief README) — a lower bound. Implement `trust_multidimensional`
as a two-level model (respondent effect + subscale effect + item noise) so the four subscales
correlate ~0.6–0.7 and items within a subscale ~0.75.

### 5.5 `donation_ams` ($0–10, whole dollars)
Codebook: *"Of the $10 bonus, how much would you like to donate to the American Meteorological
Society (AMS)?"*, `$0–$10 in whole-dollar choices ($1 increments; integers only)`. Raw export
column `donation` (integers seen in the example file, e.g. 1, 0, 5 — but that file is a
**fabricated example**, not evidence).
**Evidence in my five datasets: NONE.** No donation/dictator item exists in acs, ces,
gatewaybelief, orchinik2024 or sce (verified against their column lists). The expectation of spikes
at $0, $5 and $10 is a dictator-game regularity (modal 0, focal "half", secondary "all") — plausible
but **UNVERIFIED here**; do not cite it as data. `/workspace/datasets/` also contains
`bbprime2025, ccam, gligoric2025, goldwert2026, gss, tisp, vlasceanu2024, voelkel2024, voelkel2026`
— out of my scope; whoever profiles those should be asked specifically for a $0–$10 / dictator /
donation item, since it is the only outcome whose distribution we would otherwise be inventing.
Proposed parametric form until evidence arrives — an explicit 11-point pmf, not a rounded continuum:
`p = (π₀, π₁, …, π₁₀)` with free atoms at 0, 5, 10 and a smooth (e.g. Beta-binomial on 0–10) body
between them; fit `p` to the cell's target mean and SD subject to `π₀ ≥ π₁, π₅ > π₄, π₅ > π₆,
π₁₀ > π₉`. Scoring note: donation is converted at **$0.30 = 3 pp** (system prompt), i.e. 1 dollar
= 10 pp, so a $0.10 error in a cell mean is 1 pp — donation is 1 of the 13 outcomes and therefore
1/13 of the pooled RMSE; its *distribution* also enters the Tier-1 OVL/KS/W1 on the "$0–10 grid".

### 5.6 `newsletter_signup` (0/1)
Codebook: raw Qualtrics `1 = Yes, 2 = No`, recoded to 1/0 in cleaning; the raw export column is
`newsletter` and it "Refers to an earlier newsletter-offer page; see questionnaire.txt for the
cross-page dependency". Generation is a per-cell Bernoulli(p_{c,o}) — nothing to shape. The ATE in
pp of scale range is `100·(p_treat − p_control)`. Variance is determined by the mean
(`p(1−p)`), so the variance-ratio metric on this outcome is automatically satisfied **iff** the
rate is right — the only 1 of 13 outcomes where mean accuracy alone buys distributional accuracy.
Watch the cross-page dependency: the raw deposit must be internally consistent with whatever
earlier page the questionnaire defines (`/workspace/benchmark/survey/questionnaire.txt`).

---

## 6. Open items for the operator / other agents
1. **ACS housing file is missing** (`unix_hus`/`psam_hus*.sas7bdat`) → no `HINCP`. Either request
   it, or accept the `Σ PINCP within SERIALNO` reconstruction (§1.4 option 1), or take income from
   CES. Decide before the pool is built; it changes the `income` moderator for all 18,000 rows.
2. **Postgrad split ratio** (`Master's/Professional` vs `Doctorate`) must come from ACS `SCHL`
   22/23 vs 24 — needs the one-time full pass.
3. **`pid3 == 5` ("Not sure", 4.1%) and `faminc_new == 97` ("Prefer not to say", 8.5%)** have no
   target level. Imputation rule must be recorded.
4. **No attitude-slider heaping dataset in scope.** Both heaping anchors (orchinik, SCE) are
   percentage/probability items; the target's sliders are verbally-anchored attitude sliders. If
   any of `ccam, gss, tisp, vlasceanu2024, voelkel2024/2026, goldwert2026, gligoric2025,
   bbprime2025` contains a 0–100 *attitude* slider with raw individual responses, that dataset —
   not SCE — should set `a, b, c, π₀, π₅₀, π₁₀₀`.
5. **No donation-item evidence in scope** (§5.5).
6. Nothing resembling target-study results was encountered. No web access was used.
