# DATA_experiments.md — the five multi-arm experiments (ATE practice substrate)

Recon only. Nothing here was produced by a full-file computation over microdata: row counts are
`wc -l`, columns are CSV/XLSX headers, value codings come from the first 300–1500 rows plus the
authors' own codebooks/scripts/questionnaires. Claims taken from a dataset `README.md` that I did
not independently recompute are marked **[README]**. Anything I could not verify is **UNVERIFIED**.

Cross-cutting note used throughout section 9: `/workspace/benchmark/codebook.csv` (63 rows) shows
that several *target* items are **verbatim or near-verbatim** items from these datasets. That is the
single most useful fact in this document and is spelled out per dataset.

---

## 1. voelkel2026 — Climate-Messages Megastudy (CCC)

### 1.1 Files

| path | format | bytes | rows (incl. header) | cols |
|---|---|---|---|---|
| `/workspace/datasets/voelkel2026/downloads/CCC - Data - Recoded.csv` | CSV | 11,704,158 | 13,822 (**13,821 data rows**) | **139** |
| `/workspace/datasets/voelkel2026/downloads/CCC - Data - Deidentified.csv` | CSV | 8,853,122 | 13,822 | **164** |
| `/workspace/datasets/voelkel2026/downloads/CCC - Script - Step 2 - Preparation.R` | R, 21,271 chars | — | — | the de-facto codebook |
| `/workspace/datasets/voelkel2026/downloads/CCC - Questionnaire.pdf` | PDF, 31 pp | — | — | item wordings + scales |
| `/workspace/datasets/voelkel2026/downloads/CCC - Questionnaire - Qualtrics.pdf` | PDF, 72 pp | — | — | **contains all 13 treatment texts** |
| `/workspace/datasets/voelkel2026/downloads/Interventions.csv` | CSV | 77,122 | 157 | citation-screening table of candidate studies, *not* messages |

Analysis-ready file = `CCC - Data - Recoded.csv`. There is **no respondent ID column** and **no
weights column** (header verified: only `StartDate`,`EndDate` identify a row).

### 1.2 Condition variable

- `Condition` — 13 exact labels: `Binding Framing`, `Consensus Framing 1`, `Consensus Framing 2`,
  `Control Baseball`, `Control Dances`, `Control Neckties`, `Dire But Solvable Framing`,
  `Free Market Framing`, `Gains Framing`, `High Social Distance Framing`, `Purity Framing`,
  `System Preservation Framing`, `Warmth Framing`.
- `ConditionR` — the analysis variable: the three `Control *` arms pooled to the single string
  `Control` (10 treatments + `Control`); `Control` is the reference level (`relevel(..., ref="Control")`
  in the prep script).
- `ConditionB` — `Control` / `Treatment`.
- Arm sizes ~1,057–1,069 each [README]; therefore the pooled control is ~3,180.

### 1.3 Outcomes

All post-treatment outcomes are **0–100 sliders** (101-point, `Questionnaire.pdf` §Part J/K).
Composites are **pre-computed** in the recoded file by the prep script:

| composite (Pre and Post) | items | prep-script recodes |
|---|---|---|
| `Belief_Pre` / `Belief_Post` | mean of `Belief_*_1_1`,`_2_1`,`_3_1` | item 3 reversed: `100 - Belief_*_3_1` |
| `Concern_Pre/Post` | mean of `Concern_*_1_1.._3_1` | none |
| `Policies_Pre/Post` | mean of `Policies_*_1.._3` | none |
| `Intent_Pre/Post` | mean of `Intent_*_1.._4` (political intentions) | none |
| `PoliciesSp_Pre/Post` | mean of `PoliciesSp_*_1_1.._4_1` | item 3 reversed |
| `Candidate_Pre/Post` | mean of `Candidate_*_1_1.._4_1` | **all four items reversed** |
| `Companies_Pre/Post` | mean of `Companies_*_1.._3` | none |
| `IntentNp_Pre/Post` | mean of `IntentNp_*_1.._6` (non-political intentions) | none |
| `Donation` (post-only) | `Donation_1+..+Donation_5` | allocation of **100 cents ($1)**; `Donation_6` = kept for self; so `Donation` ∈ 0–100 |

Nine outcome families → 9 post-treatment DVs. Sample-of-800 sanity: `Belief_Post` mean ≈ 63.8,
`Concern_Post` ≈ 58.0, `Intent_Post` ≈ 33.9, `Donation` ≈ 52.5 (SD 46.9, strongly bimodal at 0/100).
Nine manipulation checks (`Check_Relevant_1` … `Check_Community_1`) are also 0–100.

### 1.4 Moderators vs. the target's six

| target moderator | voelkel2026 column | recode note |
|---|---|---|
| gender (Male/Female/Other) | `Gender` | **exact match**; prep script maps 1→Male, 2→Female, 3→Other, backfilled from `Gender_B` |
| age_band (18-29/30-44/45-59/60+) | `Age` (=2024−`YOB`), `AgeCategory` | `AgeCategory` uses 18-24/25-34/35-44/45-54/55-64/65+ — **does not nest** in the target bands; re-cut from `Age` instead |
| race (5 target levels) | **`Race`** in `CCC - Data - Deidentified.csv` (codes 1–5) | survey wording (`Qualtrics.pdf` p.9): 1 White / Caucasian, 2 Black / African-American, 3 Latino / Hispanic, 4 Asian / Asian-American, 5 Other → **1-to-1 with the target's five levels** modulo hyphenation. The *recoded* file drops `Race` in favour of eight non-exclusive `RaceEthnicity_*` string dummies built from the panel's `Ethnicity_B`/`Hispanic_B` (Hispanic, White, Black, Asian, NHPI, AIAN, Other, NA) — use the deidentified `Race` for a clean single-select mapping |
| education (6 target levels) | `Education` | raw survey codes 1–5 (`Less than high school`, `High school diploma / GED`, `Some college or Associate's degree`, `Bachelor's degree`, `Postgraduate (Master's/Ph.D./Professional)`); the recoded file collapses to 3 strings `HS or less` / `Some college` / `Bachelor or Postgraduate`. **Target's 6 levels split Master's vs Doctorate — not recoverable**; use the raw 1–5 from the deidentified file and treat target levels 5+6 as one |
| income (5 target bands) | `Income_B` (panel-supplied) | codes **1–11 plus 99** in-sample. **No label table anywhere on disk** — the Qualtrics instrument never asks income. Band boundaries **UNVERIFIED**; a crosswalk to the target's 5 bands cannot be built from this repo alone |
| party (Rep/Dem/Ind/Other) | `Party_N` (1–8), `PartyC8`, `PartyC3` | ANES branching: `PartyC3` = Democrat / Republican / **Neither** (leaners folded into Dem/Rep; `Party_N==8` "Other" falls into "Neither"). Target keeps Independent and Other apart → use `Party_N`: 1–2 Democrat, 6–7 Republican, 3–5 Independent, 8 Other |

Extras not in the target: `Region` (4 census regions), `Ideology_B`, `Ideology_Economic_B`,
`Ideology_Social_B`, `Position_Abortion/Guns/Immigration/Taxes`.

### 1.5 Weights / clustering / country

None. No weights column, no clusters (single-shot individual randomization), 100% U.S. panel — no
country filter needed.

### 1.6 ATE recipe (percentage points of scale range)

1. Load `CCC - Data - Recoded.csv`. Set `ConditionR` reference = `Control` (pools the three
   innocuous-text controls, exactly as the authors do).
2. For each of the 9 post outcomes `Y ∈ {Belief_Post, Concern_Post, Policies_Post, Intent_Post,
   PoliciesSp_Post, Candidate_Post, Companies_Post, IntentNp_Post, Donation}`:
   `ATE_k = mean(Y | ConditionR = k) − mean(Y | ConditionR = Control)`, complete cases on `Y`.
3. **pp conversion**: every one of these is already on a 0–100 range, so 1 raw unit = 1 pp.
   (`Donation` is 0–100 *cents*, range 100 → also 1:1.)
4. Optional ANCOVA (the authors' design intent): regress `Y_Post` on `ConditionR` + `Y_Pre`. This
   changes precision, not the target estimand; use the raw difference for a like-for-like ATE table.
5. Exclusions the README names: attention-check failures were screened **before** the file was
   delivered (the deidentified file retains no `Attention1`/`Attention2` response columns, only their
   timers, which the prep script then deletes). 13,546 of 13,821 rows have ≥1 post-treatment outcome;
   paper analysis N ≈ 13,544 [README]. No further preregistered exclusion is documented on disk.

### 1.7 Message texts — **YES, verbatim, on disk**

`CCC - Questionnaire - Qualtrics.pdf` contains a `Start of Block:` section with the **full text** for
all 13 arms: `History of Neckties`, `Rules of Baseball`, `Different Types of Dances`,
`Binding Framing`, `Consensus Framing I`, `Consensus Framing II`, `Dire But Solvable Framing`,
`Free Market Framing`, `Gains Framing`, `High Social Distance Framing`, `Purity Framing`,
`System Preservation Framing`, `Warmth Framing`. (Verified: e.g. the ~2,000-char necktie control text
and the ~1,800-char baseball control text extract cleanly with `pypdf`.)
The *other* PDF, `CCC - Questionnaire.pdf`, only lists condition **names** and says "The text for all
conditions are the revised interventions listed in the SI" — the SI was deliberately not downloaded.
So: use the Qualtrics PDF, not the questionnaire PDF.

### 1.8 Gotchas

- **Pre/post priming.** Every outcome family is measured pre *and* post. Control-arm *post* values are
  primed by the pre-measures; the dataset README explicitly says to use control-arm **PRE**
  distributions as unprimed baselines. This matters for Tier-1 distribution work but *not* for ATEs
  (the priming is common to all arms).
- **Reverse-scoring is already applied** in the recoded file (Belief item 3, PoliciesSp item 3, all
  four Candidate items). Do not reverse twice.
- Treatments differ in length: `Free Market Framing` is 11 pages, `System Preservation` 6, `Dire But
  Solvable` 4, `Warmth` 2, the rest 1 page. Dose is confounded with content.
- **Zero trust outcomes.** No item about scientists at all.
- `Income_B` has no label table (see 1.4).
- No respondent ID; rows cannot be joined to anything.

### 1.9 What a good held-out task looks like / distance to the target

Design-twin claim, **verified in detail**:
- same delivery mode (short single-exposure text vignette in a survey),
- same response format (0–100 integer sliders, 101 points),
- same population (census-quota US opt-in panel),
- same arm count order of magnitude (10+3 vs 16+1) and same arm size (~1,050 vs ≥500),
- **all six target moderators present at the individual level** (with the education/income caveats
  in 1.4 — that part of the twin claim is weaker than the README implies),
- **item-level overlap with the target instrument**: `Concern_*_1..3` are *verbatim* the target's
  `concern_1..3`; `Policies_Post_3` ("The U.S. government should do more to reduce global warming") is
  *verbatim* the target's `policy_general`; `IntentNp_Post_1/2/4` (eat less meat / walk-bike-carpool-
  public-transport / less non-business air travel) are *verbatim* the target's
  `behavior_meat`/`behavior_transport`/`behavior_fly`; `Intent_Post_4` ("Give money to an
  environmental group") ≈ `behavior_donate`. That is the real reason it is the twin.
- Not shared: trust in scientists (13 → 0 of the target's trust family), institutional trust, funding
  perceptions, the scientists' policy-role battery.

Carve: hold out the 10 × 9 ATE matrix (in pp), predict blind from the 13 verbatim message texts +
the questionnaire item wordings, then score with the section-1/2 metrics of the frozen table
(directional, Spearman, Pearson, Pearson-within-outcome, RMSE, α/β). Second carve: the 10 × 9 × 6
moderator interaction table (section 3). Third: control-arm PRE response distributions per outcome
for the Tier-1 distribution metrics — this is the best on-disk source of *real 0–100 slider shape*
in a climate-message context.
Expected ATE distribution: same family as the target — small, mostly-positive, heavily
outcome-dependent effects on 0–100 sliders. This is the dataset whose ATE magnitudes should be
trusted most as a prior for the target's magnitude scale.

---

## 2. goldwert2026 — Climate Advocacy Megastudy

### 2.1 Files

| path | format | bytes | rows | cols |
|---|---|---|---|---|
| `/workspace/datasets/goldwert2026/downloads/advocacy_data.csv` | CSV | 23,269,542 | 31,325 (**31,324 data rows**) | **113** |
| `/workspace/datasets/goldwert2026/downloads/codebook_advocacy.pdf` | PDF, 11 pp | 133,993 | — | data dictionary |
| `/workspace/datasets/goldwert2026/downloads/Advocacy_Cleaning_main.ipynb` | Jupyter | 134,678 | — | exclusions + composite formulas |
| `/workspace/datasets/goldwert2026/downloads/intervention_docx/*.docx` | 18 files | — | — | intervention materials |
| `/workspace/datasets/goldwert2026/downloads/intervention_qsfs/*.qsf` | 18 files | — | — | Qualtrics blocks |
| `/workspace/datasets/goldwert2026/downloads/readme.txt` | text | 3,287 | — | file manifest |

`advocacy_data.csv` is the cleaned analysis file (exclusions applied, timers dropped,
intervention-specific columns dropped).

### 2.2 Condition variable

`cond` (0–17, float in file) ↔ `condName`. Exact pairs (verified from the data):

| cond | condName | | cond | condName |
|---|---|---|---|---|
| 0 | **Control** | | 9 | IndStructuralChange |
| 1 | ClimatePolicyLiteracy | | 10 | BindingMorals |
| 2 | MispCorrectionRisks | | 11 | CollEfficacyEmoBenefit |
| 3 | CoBenefits | | 12 | HopeAngerNarratives |
| 4 | GlobalHealthThreat | | 13 | ThreatInjustEfficacy |
| 5 | GuiltCollResponsibility | | 14 | DynamicAngerNorm |
| 6 | SystemJustification | | 15 | BipartisanEliteCues |
| 7 | EcologicalDisruptions | | 16 | ActivistPerspective |
| 8 | ShiftFocusIndColl | | 17 | LetterFuture |

Control = `cond == 0` / `condName == "Control"` (a neutral video). ~1,733–1,745 per arm [README].
Note the cleaning notebook's `rename_dict`: `PolicyLiteracy→ClimatePolicyLiteracy`,
`MisperceptionCorrection→MispCorrectionRisks`, `CallToAction→CoBenefits`,
`HealthFrame→GlobalHealthThreat`, `CollectiveResponsibility→GuiltCollResponsibility`,
`MoralIdentity→EcologicalDisruptions`, `ExternalLOC→ShiftFocusIndColl`,
`PositiveEmotion→CollEfficacyEmoBenefit`, `NatHopeAnger→HopeAngerNarratives`,
`FearCollectiveAct→ThreatInjustEfficacy`, `AngerConsDynNorm→DynamicAngerNorm`,
`PartisanCues→BipartisanEliteCues` — the .docx/.qsf filenames use the *display* names, so match on
the renamed labels.

### 2.3 Outcomes (all post-only; no pre-measures)

| column | scale | note |
|---|---|---|
| `belief_1` | 0–100 slider | **not in the codebook**; per `DV_order` it is the "BeliefandPolicySupport" block. ~24% missing overall, 16.5%–35% by arm [README] |
| `policy_1` | 0–100 slider | same block, same missingness |
| `pol_campaign`, `pol_candidate`, `march`, `conversation`, `flyless`, `lessbeef`, `bank_raw` | 0–100 sliders | commitment items; `pol_candidate` NaN = not eligible to vote; `flyless`/`lessbeef` heavily conditional (972 / 1,356 of my first 1,500 rows) |
| `bank` | 0–100 | `bank_raw` with NaN for anyone whose `bankscore` was already "good"/"great" |
| `petition`, `newsletter1`, `newsletter2`, `newsletter`, `video` | **0/1** | real behaviours. `newsletter = newsletter1 OR newsletter2`. `video` = willing to share on social media, "no social media" → NaN |
| `donation` | **0–10 (whole $)** | donation to an environmental org; `donation_keep` = 10 − donation; `donation_bin` = donation>0 |
| `Pefficacy`, `Cefficacy`, 9 emotions | 0–100 | mediators |
| `public_awareness`, `political_advocacy`, `financial_advocacy`, `lifestyle_changes` | **0–1** | pre-computed composites of 0–1-normalised items (formulas below) |
| `pos_emo`, `neg_emo` | 0–1 | means of /100-normalised emotion items |

Composite formulas (from `Advocacy_Cleaning_main.ipynb`, exact):
```
marchN=march/100; conversationN=conversation/100; pol_campaignN=pol_campaign/100
pol_candidateN=pol_candidate/100; bankN=bank/100; flylessN=flyless/100
lessbeefN=lessbeef/100; donationN=donation/10
public_awareness   = (newsletter + video + marchN + conversationN)/4
political_advocacy = (petition + letter + pol_campaignN + pol_candidateN)/4
financial_advocacy = (donationN + bankN)/2
lifestyle_changes  = (flylessN + lessbeefN)/2
pos_emo = (Hope+Pride+Joy)/100/3 ; neg_emo = (Anger+Sadness+Fear+Guilt+Disappointment+Anxiety+Disgust)/100/7
```
`letter` = letter-completion coded by the GPT API and manually checked (0/1).

### 2.4 Moderators vs. the target's six

Two demographic sources are stapled together in the file: the survey's own items (`Gender`,`Age`,
`Edu`,`Income`,`Party`,`MacArthur_SES`,`Politics_*`) and the panel provider's columns
(`Education`,`Sex`,`Race`,`Household Income`,`Party_connect`,`Ethnicity_connect`,`Hispanic`,`Region`,
`State`,`City`, `Age_connect`, `Age_prime`, `GENDER(2)`,`HISPANIC(3)`,`ETHNICITY(4)`,`ZIP(5)`,
`REGION(6)`).

| target moderator | best column | recode note |
|---|---|---|
| gender | `Gender` (string) | in-sample values `Male`,`Female` only (codebook: 1 Male, 2 Female, 3 prefer-not→NaN, 4 non-binary/other). Target's `Other` is thin here |
| age_band | `Age` (numeric, 18–86 in sample) | cut to 18-29/30-44/45-59/60+ directly. Sample skews young (mean ≈ 38.9 in first 1,500 rows) |
| race | provider `Race` (fine-grained strings: `White`, `Black or African American`, `Chinese`, `Vietnamese`, `Korean`, `Asian Indian`, `Japanese`, `Filipino`, `American Indian or Alaska Native`, `An ethnicity not listed here`, …) | must be collapsed by hand: Asian-detail → `Asian / Asian American`; Hispanic identity lives in a separate `Hispanic` column (empty in my 1,500-row sample — **UNVERIFIED** whether populated later in the file) |
| education | `Edu` (1–4) **or** provider `Education` (10 strings) | `Edu` is years-based (1 ≤grade school, 2 ≤high school, 3 college/undergrad/cert, 4 >17 years, 5 prefer-not→NaN) — too coarse. Provider `Education` strings (`No formal education`, `Less than a high school diploma`, `High school graduate…GED`, `Some college, but no degree`, `Associate degree`, `Bachelor's degree`, `Master's degree`, `Professional degree`, `Doctorate degree`, `Prefer not to say`) **map cleanly onto the target's 6 levels** (Master's+Professional → target level 5; Doctorate → level 6) |
| income | `Income` (1–8) or provider `Household Income` (18 bands, e.g. `Less than $10,000` … `$150,000-$174,999`) | `Income` codebook: 1 <10k, 2 10–14.9k, 3 15–24.9k, 4 25–49.9k, 5 50–99.9k, 6 100–149.9k, 7 150–199.9k, 8 ≥200k, 9 prefer-not→NaN. **Boundaries do not line up with the target's** (30k / 56k / 100k / 168k); the provider's 18 narrow bands come closer but still cross 56k and 168k |
| party | `Party` (`Democrat`/`Republican`/`Other`) | **3 levels only — no Independent**. Target's Rep/Dem/Ind/Other is *not* recoverable from `Party`; provider `Party_connect` exists but its levels are **UNVERIFIED**. Continuous alternatives: `ide`, `Politics_Soc`, `Politics_Econ` (all 0–100, higher = more conservative), `ide_ms` (median-split binary) |

### 2.5 Weights / clustering / country

No weights, no clusters. `Country Of Residence` == `United States` for every sampled row — the study
is US-only, so no filter needed (but the column exists if you want to assert it).

### 2.6 ATE recipe (pp)

1. Load `advocacy_data.csv` (already the post-exclusion file).
2. Reference arm `condName == "Control"`.
3. `ATE_k(Y) = mean(Y | k) − mean(Y | Control)`, complete cases per outcome.
4. **pp conversion**: 0–100 sliders → ×1. `donation` (0–10) → **×10**. Binary `petition`,
   `newsletter*`, `video`, `letter`, `donation_bin` → **×100**. The 0–1 composites
   (`public_awareness` etc.) → **×100**.
5. Preregistered exclusions (already applied in this file, per `readme.txt` +
   `Advocacy_Cleaning_main.ipynb`): test cases by `ResponseId`; rows with blank `aid`; duplicate
   `aid` (keep first); `AttentionCheck_purp != 4` (the "select purple" check). The notebook prints
   each count; the counts themselves are not stored on disk.
6. The authors' own models are mixed-effects with FDR correction (`Advocacy_Main.Rmd`, not
   downloaded). A raw difference-in-means table is a legitimate but not identical estimand.

### 2.7 Message texts — **partly**

`intervention_docx/` has 18 .docx (17 interventions + `Neutral_Control_Condition.docx`) and
`intervention_qsfs/` the 18 matching .qsf. Caveat: `python-docx` returns 0 paragraphs (the content
sits in tables/textboxes and one file has a broken content-type entry); extract by reading
`word/document.xml` from the zip and concatenating `w:t` nodes. Extracted lengths (chars):

```
Linking_Individual_and_Structural_Change 11681   Hope_and_Anger_Narratives 9364
Misperception_Correction_Risks 7609             Connecting_to_Ecological_Disruptions 7548
Collective_Efficacy_and_Emotional_Benefit 7379  Dynamic_Anger_Norm 4859
Binding_Moral_Foundations 4526                  System_Justification 3911
Threat-Injustice-and-Efficacy 3714              Global_Health_Threat 3028
Co-Benefits 2847                                Letter_to_Future_Generations 2503
Bipartisan_Elite_Cues 2352                      Shifting_Focus_from_Individual_to_Collective 1398
Guilt-Based_Collective_Responsibility 1337      Climate_Activist_Perspective_Taking 1163
Climate_Policy_Literacy 970                     Neutral_Control_Condition 281
```
**Six arms are video-based** — `Climate_Policy_Literacy` (970 chars, all of it "watch the video" +
comprehension items), `Neutral_Control_Condition` (281 chars, a bare video placeholder),
`Shifting_Focus_from_Individual_to_Collective_Action`, `Collective_Efficacy_and_Emotional_Benefit`,
`Global_Health_Threat`, `Climate_Activist_Perspective_Taking`, plus `Bipartisan_Elite_Cues`
(2 mentions of "video"). The **video content is not on disk**. Several other arms are writing tasks,
where the .docx gives the prompt but the stimulus a participant produced is theirs.
Net: a predictor can read a full stimulus for roughly 11–12 of 17 arms; for the video arms it has a
title and a comprehension quiz only.

### 2.8 Gotchas

- `belief_1`/`policy_1` are **undocumented in the codebook** and ~24% missing with arm-varying
  missingness (16.5%–35%) [README] — differential attrition, so an unadjusted ATE on these two is
  the most fragile number in the file. (My first-1,500-row sample shows only 6 missing, i.e.
  missingness is **not uniform down the file** — do not estimate missingness from a head sample.)
- `flyless`/`lessbeef` are conditional on relevance; `pol_candidate` conditional on voter
  eligibility; `video` conditional on having social media; `bank` conditional on `bankscore`.
- Dose is wildly unequal (a 970-char video prompt vs an 11,681-char multi-part writing task).
- Video/writing interventions ≠ the target's short read-a-message format. README's own advice:
  use for **ranking**, not magnitudes.
- No trust items at all.

### 2.9 What a good held-out task looks like / distance to the target

Structurally the closest on *arm count* (16 crowdsourced + benchmark + control ≈ the target's 16+1)
and it is the **only** dataset here carrying both of the target's non-slider outcomes in the
target's own units: `donation` is **$0–10 whole dollars**, exactly `donation_ams`; `newsletter1`,
`newsletter2` are **0/1 newsletter signups**, exactly `newsletter_signup`. Those two columns are the
best available prior for the *level* and *spread* of the target's two behavioural outcomes.
Carve: 17 × {belief_1, policy_1, donation, newsletter, petition, pol_campaign, march, conversation}
ATE table in pp, predicted from the 11–12 readable intervention texts; score on directional
agreement and Spearman only (magnitudes are not transferable because the modality differs).

---

## 3. vlasceanu2024 — Global Climate Intervention Tournament (63 countries)

### 3.1 Files

| path | format | bytes | rows | cols |
|---|---|---|---|---|
| `/workspace/datasets/vlasceanu2024/downloads/data63.xlsx` | XLSX (sheets `data4joe (1)`, `Sheet1`) | 9,447,198 | 59,441 incl. header (**59,440 data rows**) | **28** |
| `/workspace/datasets/vlasceanu2024/downloads/data_notimers.csv` | CSV, latin-1 | 66,355,376 | 74,814 lines (embedded newlines in open-text; **59,508 records** [README]) | **196** |
| `/workspace/datasets/vlasceanu2024/downloads/codebook.xlsx` | XLSX | 56,284 | **1,108 rows** (1,107 variables) | 7 (`Variable`,`Position`,`Label`,`Question Type`,`Values`,`Notes`) |
| `/workspace/datasets/vlasceanu2024/downloads/OSF_READme.txt` | text | 2,513 | — | file inventory of the *full* OSF project |

Analysis-ready file = `data63.xlsx`, sheet `data4joe (1)`.
Columns: `ResponseId, Country, cond, condName, Belief1-4, Policy1-9, Gender, Age, Politics2_1,
Politics2_9, Edu, Income, MacArthur_SES, Intro_Timer, condition_time_total, SHAREcc, WEPTcc`.

### 3.2 Condition variable

`condName` (with numeric `cond`), 12 levels: **`Control`** plus `BindingMoral`, `CollectAction`,
`DynamicNorm`, `FutureSelfCont`, `LetterFutureGen`, `NegativeEmotions`, `PluralIgnorance`,
`PsychDistance`, `SciConsens`, `SystemJust`, `WorkTogetherNorm` (11 interventions).
Control = `condName == "Control"`.

### 3.3 Outcomes

| column(s) | scale | source item (codebook) |
|---|---|---|
| `Belief1..Belief4` | 0–100 sliders | `Belief.in.CC_1/2/4/5`: "How accurate do you think these statements are?" — (1) *Human activities are causing climate change*, (2) *Climate change poses a serious threat to humanity*, (4) *Taking action to fight climate change is necessary to avoid a global catastrophe*, (5) *Climate change is a global emergency* |
| `Policy1..Policy9` | 0–100 sliders | `CC_policy_1,2,3,5,6,7,8,9,10`: "I support… " — carbon taxes on gas/fossil fuels/coal; expanding public-transport infrastructure; more EV charging stations; sustainable energy (wind/solar); taxes on airline companies; protecting forested and land areas; green jobs and businesses; laws to keep waterways and oceans clean; taxes on carbon-intense foods |
| `SHAREcc` | **0/1** | `Share`: willing to share a climate message on social media (raw had `[2] I do not use social media`, dropped) |
| `WEPTcc` | **0–8 integer** | WEPT: number of tedious number-screens completed for tree-planting (`WEPT1..8`) |

**Composites are NOT pre-computed** in `data63.xlsx` — you must build belief and policy means
yourself (`Belief1-4` mean; `Policy1-9` mean). The paper's own indices are **UNVERIFIED** here
(analysis code lives on GitHub, not on disk).

### 3.4 Moderators vs. the target's six

| target moderator | column | note |
|---|---|---|
| gender | `Gender` | 1 Male, 2 Female, 3 Prefer not to say, 4 Non-binary/third gender/other → collapse 3+4 into `Other` (or 3→NA) |
| age_band | `Age` (free numeric) | cut directly |
| race / ethnicity | **ABSENT** | no race or ethnicity item anywhere in the 1,107-variable codebook |
| education | `Edu` (=`Education.2`) | 1 = 0–6 yrs, 2 = 7–12 yrs, 3 = 13–16 yrs, 4 = >17 yrs, 5 = prefer not to answer. Four usable levels vs. the target's six → **coarse, lossy** |
| income | `Income` | 1 <\$10,000; 2 \$10,000–14,999; 3 \$15,000–24,999; 4 \$25,000–49,999; 5 \$50,000–99,999; 6 \$100,000–149,999; 7 \$150,000–199,999; 8 ≥\$200,000; 9 prefer not to respond. **Boundaries cross the target's** (30k/56k/100k/168k) — only the 100k cut aligns |
| party | **ABSENT** | no party-ID item. Proxies: `Politics2_1` (social ideology 0–100) and `Politics2_9` (economic ideology 0–100), 0 = extremely liberal / 100 = extremely conservative. Also `MacArthur_SES` (1–10 ladder) |

### 3.5 Weights / clustering / country

- **Country filter**: `Country == "Usa"` in `data63.xlsx` (US n = 8,253 [README]); `country` in
  `data_notimers.csv`.
- **Clustering**: 63 countries — outside the US subset, country is the natural cluster and the
  interventions were translated/adapted per country. For target-relevant work, **subset to `Usa`**
  and there is no residual clustering.
- No weights column.

### 3.6 ATE recipe (pp)

1. Read sheet `data4joe (1)` of `data63.xlsx`; the file uses the literal string `"NA"` for missing —
   convert before any numeric cast.
2. Filter `Country == "Usa"` (n ≈ 8,253) so the estimand is a US ATE.
3. Build `BeliefMean = mean(Belief1..4)`, `PolicyMean = mean(Policy1..9)` (or keep the 13 items
   separately, which gives a 11 × 13 table with roughly the target's shape).
4. `ATE_k = mean(Y|k) − mean(Y|Control)`.
5. **pp conversion**: `Belief*`, `Policy*` 0–100 → ×1; `SHAREcc` 0/1 → **×100**; `WEPTcc` 0–8 →
   **×12.5** (=100/8).
6. Exclusions: the OSF README documents the cleaning script (`datapaper_cleaning.R`) but that script
   is **not on disk**; `data63.xlsx` is the already-cleaned paper analysis file, so apply none.
   `AttentionCheck_purp` (select "purple") and `AttentionCheck60` exist in `data_notimers.csv` if you
   want to re-derive exclusions on the full release. Preregistered exclusion rules themselves are
   **UNVERIFIED** from on-disk material.

### 3.7 Message texts — **NO**

Only 4 files were downloaded. The intervention texts live in the OSF folders
`ClimateManylabs_CollaboratorResources` (`master_survey.pdf`, `intervention_adaptation_manual.pdf`)
and `ClimateManylabs_QSF`, per `OSF_READme.txt` — **none of which is on disk**. A predictor gets
only the 11 short condition names (`SciConsens`, `DynamicNorm`, `SystemJust`, …). This is the
single biggest limitation of this dataset for our purpose.

### 3.8 Gotchas

- `"NA"` string literals throughout `data63.xlsx`.
- 63-country pooling: any global ATE mixes translation/adaptation quality (the OSF project ships an
  `intervention_translation_and_adaptation_overview.xlsx`, not downloaded).
- `data_notimers.csv` has 74,814 *lines* for 59,508 records (open-text fields carry newlines) —
  never infer n from `wc -l` for this file.
- Two overlapping releases (Zenodo analysis file vs OSF full release) with different n
  (59,440 vs 59,508) and different variable names (`Belief1` vs `Belief.in.CC_1`,
  `Edu` vs `Education.2`).
- Sharing item had an "I do not use social media" option folded away.

### 3.9 What a good held-out task looks like / distance to the target

Item-level overlap with the target is **the strongest of any dataset here on the two policy/belief
outcomes**: the target's `belief_post` ("How accurate do you think this statement is? 'Human
activities are causing climate change.'") is *verbatim* `Belief.in.CC_1`; and **seven of the
target's `policy_specific_1..7`** are near-verbatim `CC_policy` items (fossil-fuel taxes; public
transport; sustainable energy; protecting forested and land areas; carbon-intensive food taxes;
green jobs; laws to keep waterways and oceans clean). So the *baseline levels and dispersion* of the
target's `policy_specific_*` and `belief_post` can be anchored on the US subsample here.
Carve: US-only, 11 × 13 item-level ATE table in pp + the SHAREcc/WEPTcc pair. But because the
message texts are missing, this is a **weak ATE-prediction task** (the predictor must guess from
names) and a **strong distribution/baseline task**. Use it mainly for Tier-1 distribution anchoring
and for the demographic-baseline RMSE row, not for message ranking.

---

## 4. bbprime2025 — BB-PRIME Phase II Climate Intervention Tournament

### 4.1 Files (all **long format**, one row per participant × scale × item; join key `SID`)

| path | bytes | rows (incl. header) | cols | header |
|---|---|---|---|---|
| `messages_data.csv` | 77,598,063 | 266,788 | 11 | `survey_name, group, SID, scale_name, item, value, main_headline, snippet, clicks, action, exclude_item` |
| `petitions_data.csv` | 117,304,376 | 106,170 | 8 | `survey_name, group, SID, scale_name, item, value, petition_link, petition_text` |
| `actions_data.csv` | 55,134,625 | 517,215 | 9 | `survey_name, group, SID, scale_name, category, item, value, maxed_out, value_z` |
| `emotions_data.csv` | 5,191,784 | 60,992 | 6 | `survey_name, group, SID, scale_name, item, value` |
| `other_dvs_data.csv` | 6,421,426 | 84,039 | 7 | `+ n_missing` |
| `demographics_data.csv` | 5,873,428 | 85,450 | 5 | `group, SID, scale_name, item, value` |
| `indiv_diffs_data_few_excl.csv` | 2,235,593 | 28,659 | 7 | `+ n_missing` |
| `actions_data_notmaxed_few_excl.csv` | 42,379,655 | 459,271 | 9 | |
| `other_dvs_data_few_excl.csv` | 5,283,949 | 62,137 | 7 | |
| `demographics_data_few_excl.csv` | 5,227,977 | 87,064 | 5 | |
| `tournament_analysis_OSF.Rmd` | 20,287 | — | — | main analysis |
| `tournament_analysis_moderators.Rmd` | 11,293 | — | — | moderator analysis |
| `SOP_and_measures.docx` | 2,651,725 | — | — | SOP + measures (24,359 chars extracted) |

**There is no single analysis-ready wide file** — you must pivot and merge on `SID`.
N = 7,624 participants under main exclusions; 7,767 in the `_few_excl` variants [README].

### 4.2 Condition variable

`group`, carried in **every** file and constant per `SID`. 18 levels: `control` (n = 850) +
`STPB`, `CF_general`, `CF_personalized`, `impact_text`, `impact_quiz`, `letter`,
`ES_promotion_self`, `ES_promotion_other`, `ES_prevention_self`, `ES_prevention_other`,
`MCII_individual`, `MCII_collective`, `moral_values`, `norm_text`, `norm_quiz`,
`social_relevance`, `self_relevance` (n = 370–428 each) [README]. Reference level is `control`
(the Rmd sets `factor(..., levels = c("control", ...))` and uses `contrast(emmeans(...),
"trt.vs.ctrl1")`).
Manuscript display names, from the Rmd (in the factor's own order): Personal Benefits, Carbon
Footprint (General), Carbon Footprint (Personalized), Impact Information (Text), Impact Information
(Quiz), Letter to Future Gen, Imagination (Promotion-Self), Imagination (Promotion-Other),
Imagination (Prevention-Self), Imagination (Prevention-Other), Action Planning (Individual), Action
Planning (Collective), Moral Values, Social Norms (Text), Social Norms (Quiz), News Comments
(Social-Rel), News Comments (Self-Rel).

### 4.3 Outcomes (identified by `scale_name`)

| file | `scale_name` values | scale (from `SOP_and_measures.docx`) |
|---|---|---|
| messages | `msg_share_broad`, `msg_share_narrow`, `msg_read`, `msg_rel_self`, `msg_rel_social`, `msg_emo_pos`, `msg_emo_neg` | **0–100** sliders, 5 headlines per person sampled from 26 |
| petitions | `petition_sign_intention`, `petition_share_broad`, `petition_share_narrow` | **0–100** sliders, 3 petitions per person from a pool of 10 |
| petitions | `petition_sign` | categorical: `yes` / `no` / `no_later` / `no_unsure` |
| petitions | `petition_link_clicks` | 0–3 count |
| actions | `action_intention`, `action_ease`, `action_env_impact`, `action_approval` | **1–7** Likert, 12 `item`s (car, contact, conversations, donate, energy, flights, meat, petition, recycle, vegan, vegetarian, volunteer) |
| actions | `action_current`, `action_current_flight_*` | scale varies by action (hence `value_z`, standardised **within item**) |
| emotions | `emo_angry/anxious/determined/disengaged/hopeful/hopeless/sad/uncertain` | **1–5** |
| other_dvs | `self_efficacy`, `concern_risk`, `climate_knowledge`, `uncertainty` | **1–5** |
| other_dvs | `distance` (`geographic`,`social`,`temporal`,`mean`) | 1–5 (temporal 1–7) |
| other_dvs | `climate_change_cause` | 6-category |

**No composites are pre-computed** except `other_dvs` rows with `item == "mean"` and the
`value_z` column. Everything else must be aggregated.

### 4.4 Moderators vs. the target's six

From `demographics_data.csv` (`scale_name` = the variable, `value` = the answer) and
`indiv_diffs_data_few_excl.csv`:

| target moderator | where | levels seen |
|---|---|---|
| gender | `gender` | `Man`, `Woman`, `Non-binary`, `Gender fluid`, `Prefer not to say` (+ `gender_trans`) → map Man/Woman/Other |
| age_band | `age` (free numeric string) | cut directly; **sample is deliberately skewed young**: quota 40% 18–35, 40% 36–54, 20% 55–90 (SOP) |
| race | `race_ethnicity` | `White`, `Black or African American`, `East Asian`, `South Asian`, `Southeast Asian`, `American Indian or Alaskan Native`, `Racial/ethnic identity not listed`, `Prefer not to say` (+ free-text `race_ethnicity_self`); Hispanic in a separate `hispanic_latinx` (Yes/No/Prefer not to say). Asian-detail must be collapsed; the target's `Hispanic / Latino` requires combining two variables |
| education | `ses_degree` | `High school graduate (GED)`, `High school graduate (diploma)`, `Some college (1-4 years, no degree)`, `Associate's degree…`, `Bachelor's degree (BA, BS, etc)`, `Master's degree (MA, MS, MENG, MSW, etc)`, `Professional school degree (MD, DDC, JD, etc)`, `Doctorate degree (PhD, EdD, etc)` → **maps onto the target's 6 levels** (no "less than high school" observed) |
| income | `ses_income_household` | `Less than $5,000`, `$5,000 through $11,999`, `$12,000 through $15,999`, `$16,000 through $24,999`, `$25,000 through $34,999`, `$35,000 through $49,999`, `$50,000 through $74,999`, `$75,000 through $99,999`, `$100,000 through $149,999`, `$150,000 and greater`, `Prefer not to say`. **Cuts at 30k / 56k / 168k do not align**; 100k does |
| party | `indiv_diffs`, `scale_name == "politics"`, `item == "affiliation"` | `Democratic Party`, `Republican Party`, `Independent`, `Libertarian Party`, `Green Party`, `Other`, `Not registered` → collapses to the target's four. Also `item == "party"` (1–7 strong-Dem…strong-Rep) and `item == "ideology"` (1–7, higher = more conservative). **Only in the `_few_excl` file (N = 7,767)** |

Extras: `ses_savings`, `ses_subjective` (1–10 ladder), `state`, `zipcode`, `climate_anxiety`, `IAF`.

### 4.5 Weights / clustering / country

- No weights.
- **Non-independence is structural**: 5 headlines and 3 petitions per participant, 12 actions per
  participant, each a separate row. The authors' models are `lmer(... + (1|SID))` (and `brm` with
  random intercepts for people *and* stimuli). A naive respondent-pooled mean ignores stimulus
  sampling; a naive row-pooled t-test is anticonservative.
- US-only by Prolific screen (residence = United States); `state` exists if you want to assert it.

### 4.6 ATE recipe (pp)

1. Choose the exclusion variant: main (N = 7,624; `messages/petitions/actions/emotions/other_dvs/
   demographics_data.csv`) or `_few_excl` (N = 7,767; keeps climate-change skeptics — **required**
   if you want the `indiv_diffs` moderators, which only ship in that variant).
2. For each `scale_name`, filter, then **collapse to one value per `SID`** (mean over `item`).
   Merge on `SID`; `group` is already carried.
3. `ATE_k = mean(Ȳ_SID | k) − mean(Ȳ_SID | control)`.
4. **pp conversion**: `msg_*`, `petition_share_*`, `petition_sign_intention` are 0–100 → ×1;
   1–7 Likerts (`action_*`, `distance_temporal`) → **×100/6**; 1–5 scales (`emo_*`,
   `self_efficacy`, `concern_risk`, `uncertainty`, `climate_knowledge`) → **×100/4**;
   `petition_sign` binarised (`yes` vs rest) → **×100**; `petition_link_clicks` (0–3) → ×100/3.
   Never use `value_z` for a pp table — it is a within-item z-score.
5. Exclusions (SOP, already applied to the main files): GPT-4-scored text quality (manual review of
   scores ≤3/10), TaskMaster mouse-tracking off-task flags on every writing page, self-reported
   cheating/AI/dishonesty, failing **two** attention checks, climate-change denial (cause =
   "no such thing"/"entirely natural" **or** mean > 4 on the 5-point Uncertainty & Skepticism scale),
   outliers winsorised/removed per measure. The `_few_excl` files reverse only the denial exclusion.

### 4.7 Message texts — **NO for interventions; YES for stimuli**

`SOP_and_measures.docx` documents procedure, exclusions, and every outcome item **verbatim**, but
contains **no intervention content** (searching it for `STPB`, `Moral Values`, `Intervention
Conditions` returns nothing; `Carbon Footprint`/`Social Norm`/`News Comments`/`Guided Imagination`
appear only in the pre-registration link list). Intervention materials live in the seven linked
per-intervention OSF pre-registrations, which are **not on disk**.
What *is* on disk: the **stimuli** — `messages_data.csv` carries `main_headline` and `snippet` for
each of the 26 NYT climate headlines, and `petitions_data.csv` carries `petition_text` and
`petition_link` for each of the 10 petitions. So you can read what participants *rated*, not what
they were *treated with*.

### 4.8 Gotchas

- **Sample is not a US quota sample**: Prolific, ≥95% approval, ≥50 prior tasks, gender-balanced by
  design, deliberately young-skewed, and **screened to climate-change believers** (Prolific
  "Do you believe in climate change? yes"). Base rates are far more pro-climate than a census panel.
- Tournament-wide comparisons were **not preregistered** (SOP says so explicitly); only the
  per-intervention analyses were.
- Attention checks were changed mid-flight (copy-paste → choice selection) because of browser issues.
- The Rmd loads fitted `.RDS` model objects from a `./models` folder that was **not downloaded** —
  no published ATE table is reproducible from disk without refitting.
- `tournament_analysis_OSF.Rmd` has a real bug (`file_list[i]` inside a `for (model in ...)` loop).
- `maxed_out` / `actions_data_notmaxed_*`: ceiling-effect handling differs between the two action
  files.

### 4.9 What a good held-out task looks like / distance to the target

The only dataset here with **information-sharing** outcomes at scale, and 17+1 arms is a close match
to 16+1. But its outcome battery has almost no overlap with the target's 13, its population is
screened-believer Prolific rather than census-quota, and its interventions are unreadable. The
useful carve is **structural**: an 17 × k ATE table (k = the 6–8 person-level collapsed outcomes)
used to measure how *small and how tightly clustered* real megastudy ATEs are when arms are ~400 —
i.e. a prior on the ATE **dispersion** the target will show, not on any particular message. Also the
best on-disk example of a repeated-measures design where a naive analysis inflates significance.

---

## 5. voelkel2024 — Strengthening Democracy Challenge (SDC)

### 5.1 Files

| path | bytes | rows | cols |
|---|---|---|---|
| `/workspace/datasets/voelkel2024/downloads/SDC - Data - Recoded.csv` | 25,374,043 | 35,253 (**35,252 data rows**) | **113** |
| `/workspace/datasets/voelkel2024/downloads/SDC - Data - Anonymized.csv` | 9,177,726 | 35,253 | **70** |
| `/workspace/datasets/voelkel2024/downloads/SDC - Data - Intervention Names.csv` | 1,397 | 27 (26 data) | 2 |
| `/workspace/datasets/voelkel2024/downloads/SDC - Data - Outcome Names.csv` | 1,327 | 24 (23 data) | 3 |
| `/workspace/datasets/voelkel2024/downloads/SDC - Questionnaire.pdf` | 1,738,844 | 374 pp | **contains all intervention texts** |
| `/workspace/datasets/voelkel2024/downloads/SDC - Read Me.pdf` | 70,690 | 2 pp | script inventory |
| `SDC - Data - Intervention - Coding J.xlsx`, `... Coding N.xlsx` | 10,318 / 18,084 | — | two independent codings of intervention features |

Analysis-ready = `SDC - Data - Recoded.csv`.

### 5.2 Condition variable

`Condition`, **27 arms**: `Null_Control`, `Alternative_Control`, and 25 interventions
(`Befriending_Meditation`, `Chatbot_Quiz`, `Civity_Storytelling`, `Common_Identity`,
`Contact_Project`, `Counterfactual_Selves`, `Democratic_Fear`, `Economic_Interests`,
`Empathy_Beliefs`, `Epistemic_Rescue`, `Harmful_Experiences`, `Inparty_Elites`, `Learning_Goals`,
`Media_Trust`, `Misperception_Competition`, `Misperception_Democratic`, `Misperception_Film`,
`Misperception_Suffering`, `Moral_Differences`, `Outparty_Friendship`, `Partisan_Threat`,
`Party_Overlap`, `System_Justification`, `Utah_Cues`, `Violence_Efficacy`).
**`Null_Control` is the reference** (no treatment) and is deliberately oversampled — in my 1,200-row
head sample it has 200 rows vs 24–61 for every other arm, i.e. roughly 4–5×.
`Alternative_Control` is an active/placebo control arm.
`SDC - Data - Intervention Names.csv` maps data labels → manuscript names (e.g. `Utah_Cues` →
"Pro-Democracy Bipartisan Elite Cues", `Chatbot_Quiz` → "Correcting Policy Misperceptions Chatbot").

### 5.3 Outcomes

All primary/secondary outcomes are **0–100 sliders** (questionnaire: every DV item is a
0/10/…/100 bar) and the composites are **pre-computed** in the recoded file:

| column | manuscript name | items in `Anonymized.csv` |
|---|---|---|
| `PA` | Partisan Animosity | from `PA_Fth_Rep_1`,`PA_Fth_Dem_1`,`PA_DG_1`,`PA_Dem_Pol_1`,`PA_Dem_Vot_1`,`PA_Rep_Pol_1`,`PA_Rep_Vot_1` (exact formula **UNVERIFIED** — `SDC - Script - Step 2.R` is not on disk) |
| `ADA` | Support for Undemocratic Practices | `ADA_1_1..ADA_4_1` |
| `SPV` | Support for Partisan Violence | `SPV_1_2, SPV_2_2, SPV_3_1, SPV_4_2`; `SPV_D` dichotomised |
| `SUC` | Support for Undemocratic Candidates | `SUC_1_1..SUC_4__1` |
| `OppBip` | Opposition to Bipartisan Cooperation | `SupBip_1_1`,`SupBip_2_1` |
| `SocDistrust` | Social Distrust | `SocTru_1` |
| `SocDis` | Social Distance | `SocDis_1_1`,`SocDis_2_1` |
| `BEPF` | Biased Evaluation of Politicized Facts | `BEPF_R1..R4`, `BEPF_D1..D4` |
| `EleDen` | Election Denial | |
| `ODR_1..ODR_4` | Opposition to Automatic Voter Registration / Voter ID / Vote by Mail / Ban of Gerrymandering | `SDR_1_1..SDR_4_1` |
| `PA_Out`, `PA_Ing`, `PA_Diff`, `PA_DG` | feeling-thermometer / dictator-game splits | `PA_DG` is 0–50 cents rescaled to 0–100 (**UNVERIFIED** — sample max is 100) |
| `Composite` | Composite of Outcomes | pre-computed; head-sample mean ≈ 37.9, SD 12.5 |
| `Med_Dis, Med_Pid, Med_Ang, Med_Une, Med_Div, Med_Thr` | six mediators | |

### 5.4 Moderators vs. the target's six

| target moderator | column | note |
|---|---|---|
| gender | `Gender` | `Male` / `Female` / `Other` — **exact match** |
| age_band | `Age` (numeric; head-sample mean 57.4) | cut directly. **Sample is old** relative to a census quota |
| race | `Race` | recoded single-select `White`/`Black`/`Hispanic`/`Asian`/`Other`; raw multi-select `Race_1..Race_5` in `Anonymized.csv` with survey labels `White / Caucasian`, `Black / African American`, `Hispanic / Latino`, `Asian / Asian American`, `Other` — **verbatim the target's five levels** |
| education | `Education` | `HS or less` / `Some college` / `Bachelor` / `Postgraduate` — 4 levels; the target's 6 are **not** recoverable |
| income | **ABSENT** | no income variable in either file, and the questionnaire never asks |
| party | `Party_Gen` (1 Rep / 2 Dem / 3 Ind) + `Party_Rep`,`Party_Dem`,`Party_Ind` | true independents and "Other" were **screened out of the study** (`fail = True_indp_other` branch in the questionnaire's survey flow) → effectively a two-party sample. `Ideology` (1–7) and `PI_Pre` (0–100 party-identity importance) also present |

### 5.5 Weights / clustering / country

- **Weights ship with the data**, one per outcome: `weights_ada, weights_spv, weights_pa,
  weights_suc, weights_bepf, weights_oppbip, weights_socdistrust, weights_socdis, weights_composite,
  weights_pa_ft, weights_pa_dg, weights_odr1..4, weights_eleden, weights_med_*`
  (head-sample `weights_pa`: mean 1.09, min 1.00, max 3.13 — attrition/post-stratification weights).
  `SDC - Data - Outcome Names.csv` gives the outcome→weight pairing explicitly. **This is the only
  dataset of the five with weights.**
- `Supplier` ∈ {`Bovitz`, `Dynata`, `Luth`} — three panel vendors; a plausible cluster/strata
  variable.
- US-only; no country column.

### 5.6 ATE recipe (pp)

1. Load `SDC - Data - Recoded.csv` (35,252 rows). Reference `Condition == "Null_Control"`.
   Decide explicitly whether `Alternative_Control` is a 26th "treatment" or a second control.
2. Per outcome `Y`, drop rows with `Attrited_<Y> == 1` (one flag per outcome:
   `Attrited_PA, Attrited_ADA, Attrited_SPV, Attrited_SUC, Attrited_BEPF, Attrited_OppBip,
   Attrited_SocDistrust, Attrited_SocDis, Attrited_Composite, Attrited_PA_Out, Attrited_PA_DG,
   Attrited_ODR_1..4, Attrited_EleDen, Attrited_Med_*`). In my head sample `Attrited_PA == 1`
   ⇔ `PA` is NaN, so this is equivalent to complete-case on the outcome.
   README's post-exclusion N = 32,059 vs 35,252 rows in the file — **the exclusion is not a single
   stored flag**; reproducing exactly 32,059 from on-disk material is **UNVERIFIED**.
3. `ATE_k = weighted.mean(Y|k, w=weights_<y>) − weighted.mean(Y|Null_Control, w=weights_<y>)`,
   using the outcome's own weight column (unweighted is a defensible alternative but is a different
   estimand from the paper's).
4. **pp conversion**: all listed outcomes are 0–100 → ×1. `SPV_D` (dichotomised) → ×100.
5. Preregistered exclusions applied *before* the file: consent/filter refusal, failing attention
   check 1 ("select somewhat disagree"), failing the video/article check ("What was the topic of the
   short article you just read about?" ≠ Event licensing), and **true independents / "Other" party
   are screened out entirely** — all visible as `EndSurvey: Advanced` branches in the questionnaire's
   Survey Flow (pp. 2–5).

### 5.7 Message texts — **YES**

`SDC - Questionnaire.pdf` (374 pages) contains 119 `Start of Block:` sections including the full
stimulus for every intervention, keyed by the study's 4-character codes (e.g. `XANC - …` Epistemic
Rescue with its 12 trivia items, `VN9B - Republican/Democrat …` Misperception Democratic,
`6256 - Economic Interests`, `Q3EV - Moral Differences`, `GL18 - Common Identity`,
`MP2C - Inparty Elites`, `Q29Y - System Justification`, `ILPC - Utah Cues`,
`JLQR - Violence Efficacy`, `C855 - Civity Storytelling`, `0OCN - Media Trust`,
`62VB - Chatbot Quiz`, `172G - Befriending Meditation`, `RER9 - Counterfactual Selves`,
`ARCD - Harmful Experiences`, `BOXM - Outparty Friendship`, `7WIG - Misperception Film`,
`XOVS - Party Overlap`, `CCT5 - Misperception Competition`, `7539 - Misperception Suffering`,
`8Z5I - Threat`, `JQ1Z - Learning Goals`, `KUU4 - Video`, `46OS - Empathy Beliefs`,
`BUNU - Parts 1–3`, plus `Alternative Control`). `Null_Control` has no block by construction.
Some arms are **videos** (`Contact_Project` / `KUU4 - Video`, `Misperception_Film`) or
**interactive** (chatbot, live trivia quiz with a matched partner) — for these the PDF gives the
wrapper, not the media.

### 5.8 Gotchas

- **Wrong topic.** The outcomes are partisan animosity and antidemocratic attitudes, not climate or
  trust in scientists. The only adjacent item is `SocDistrust` (Social Distrust, single item).
- Heavy piping: nearly every DV is worded with `${e://Field/Inparty_Person}` etc., so the *same*
  column means different things for Republicans and Democrats. Any pooled distribution is a mixture.
- Two controls with different roles and very different n.
- Recoding script not on disk → composite formulas must be inferred from the questionnaire.
- **No income moderator**; education only 4 levels; effectively no Independents.
- Old sample (head-sample mean age 57).
- Several arms are multi-part or interactive; treatment dose is very unequal.

### 5.9 What a good held-out task looks like / distance to the target

Best **structural** practice substrate of the five for the ATE-prediction *skill*, because it is the
only one with (a) 25 readable text interventions, (b) 13+ pre-computed 0–100 outcome composites,
(c) survey weights, and (d) an oversampled pure control — i.e. an ATE table of almost exactly the
target's shape (25 × 13 vs 16 × 13). Carve: hold out the 25 × 13 pp ATE matrix + the 25 × 13 × 5
moderator table (gender, age band, race, education, party — income is impossible), predict blind
from the questionnaire's intervention texts, score with the full section-1/2/3 metric set.
Distance: the *content* is maximally far from climate trust, so it calibrates **process** (how well
we rank and scale message effects at all, and whether our α/β calibration is systematically off),
not climate priors. Its ATE distribution is likely smaller and tighter than a climate-trust study's
because the outcomes are entrenched partisan attitudes; do not port magnitudes.

---

## 6. Comparison

| | voelkel2026 | goldwert2026 | vlasceanu2024 | bbprime2025 | voelkel2024 |
|---|---|---|---|---|---|
| n (rows) | 13,821 | 31,324 | 59,440 (US 8,253) | 7,624 participants (long files) | 35,252 |
| arms | **13** (10 msg + 3 controls, pooled → 11) | **18** (17 + `Control`) | **12** (11 + `Control`) | **18** (17 + `control`) | **27** (25 + 2 controls) |
| n per arm | ~1,057–1,069 | ~1,733–1,745 | ~660 US per arm (**UNVERIFIED**, from 8,253/12) | 370–428; control 850 | control ≈4–5× the rest |
| outcome scales | 9 × 0–100 slider composites + 0–100 donation-cents | 0–100 sliders, **$0–10 donation**, **0/1** petition/newsletter/video, 0–1 composites | 0–100 sliders (13 items), **0/1** share, **0–8** WEPT | 0–100 sliders (messages/petitions), **1–7** actions, **1–5** emotions/efficacy | 13+ × 0–100 slider composites |
| composites pre-computed | **yes** | yes (0–1 groupings) | **no** | **no** (except `item=="mean"`) | **yes** |
| gender | ✅ exact | ✅ (thin `Other`) | ✅ (3+4→Other) | ✅ | ✅ exact |
| age band | ✅ from `Age` | ✅ (young-skewed) | ✅ | ✅ (young-skewed by quota) | ✅ (old-skewed) |
| race | ✅ exact 5 levels (deidentified `Race`) | ⚠️ fine-grained, needs collapsing; Hispanic separate | ❌ **absent** | ⚠️ needs collapsing; Hispanic separate | ✅ exact 5 levels |
| education | ⚠️ 5 raw / 3 recoded levels | ✅ provider `Education` maps to 6 | ⚠️ 4 levels | ✅ maps to 6 (no "<HS") | ⚠️ 4 levels |
| income | ⚠️ `Income_B` 1–11, **labels unknown** | ⚠️ bands misaligned | ⚠️ bands misaligned | ⚠️ bands misaligned | ❌ **absent** |
| party | ✅ via `Party_N` (8 pt) | ⚠️ 3 levels, no Independent | ❌ absent (ideology sliders only) | ✅ affiliation (`_few_excl` only) | ⚠️ no true Independents/Other |
| **message texts on disk** | **YES** (Qualtrics PDF, all 13) | **PARTLY** (~11–12/17 readable; 6 are videos not on disk) | **NO** | **NO** (interventions); stimuli yes | **YES** (374-pp questionnaire; 2 video arms partial) |
| **real-behaviour outcomes** | **YES** ($1 donation allocation) | **YES** ($0–10 donation, petition, 2 newsletters, share) | **YES** (social-media share, WEPT effort task) | partial (`petition_link_clicks`; the rest are intentions) | **YES** (dictator game, 50¢) |
| weights | no | no | no | no | **YES** (per-outcome `weights_*`) |
| repeated measures / clustering | none | none | country (subset to `Usa`) | **yes** — 5 headlines / 3 petitions / 12 actions per SID | none (panel `Supplier` strata) |
| topic overlap with target | climate, no trust | climate advocacy, no trust | climate, no trust | climate, no trust | **none** (democracy) |
| verbatim target items | `concern_1..3`, `policy_general`, `behavior_meat/transport/fly`, ≈`behavior_donate` | `donation_ams` units, `newsletter_signup` units | `belief_post`, 7 of `policy_specific_1..7` | — | — |

### One-paragraph verdict

For **magnitudes and response distributions**, voelkel2026 is the anchor: same format, same
population, same slider granularity, and five of the target's thirteen outcomes are built from
*verbatim* items. For **absolute levels of the target's `belief_post` and `policy_specific_*`**,
vlasceanu2024's US subsample is the anchor (verbatim items again), but it cannot train message
ranking because the texts are missing. For **the two behavioural outcomes in their own units**
($0–10 donation, 0/1 newsletter), goldwert2026 is the only source. For **practising the prediction
process end-to-end at the target's table shape with readable stimuli**, voelkel2024 is the best
substrate despite being off-topic — and it is the only place to learn what survey weights do to an
ATE table. bbprime2025 is the weakest per unit of effort: unreadable interventions, a screened
non-representative sample, long-format data needing reassembly, and an outcome battery that barely
touches the target's — its value is as a prior on ATE *dispersion* at ~400/arm and as the sharing
outcome family.

### Blinding note

Nothing resembling target-study human outcome data was encountered. All five datasets are other,
published studies. No web access was used; no model calls were made.
