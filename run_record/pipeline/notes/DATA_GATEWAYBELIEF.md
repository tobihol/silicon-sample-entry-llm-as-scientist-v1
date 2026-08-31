# DATA_GATEWAYBELIEF.md — can `/workspace/datasets/gatewaybelief` carve a sixth practice task?

**Question asked.** The harness has **zero practice cells in the target's `trust` family**
(standing finding 33 / OPEN item 18). Can this dataset carve a sixth practice task shaped like the
existing five — an arm × outcome ATE table from a randomised experiment whose arms are *readable
message texts* and whose outcomes include **trust in scientists / climate scientists**?

**Headline answer, all three studies: NO TRUST OUTCOME OF ANY KIND, AND NO MESSAGE TEXT ON DISK.**
Every outcome in all three studies is one of five constructs — perceived scientific consensus (PSC),
belief that climate change is happening, belief that it is human-caused, worry, support for action —
plus (supplemental study only) inoculation-process measures (threat/apprehension/fear/involvement/
motivation), memory, misinformation-discernment (MIST-20), and talk/accessibility.
**PSC is not trust.** PSC asks the respondent to *estimate a percentage of scientists who agree*
(0–100 numeric estimate); the target's trust family asks how competent / honest / ethical / sincere /
benevolent / open **most climate scientists** are and how much the respondent **trusts** them
(`/workspace/benchmark/codebook.csv` rows 8–21, 27–31). Different construct; counting PSC as trust
would be exactly the error standing findings 9 and 20 warn about.

Recon only. Row counts, column names, codings and cell counts below were computed on the full files
with `/opt/kernel/venv/bin/python` + pandas. **No ATE values are recorded here** (they are training
ground truth; keep them in `sealed/` if a task is ever carved). Nothing in `/workspace/run` was
modified beyond writing this file.

---

## 0. What is on disk

`/workspace/datasets/gatewaybelief/downloads/` — 8 files, nothing else, no `materials/`:

| path | what |
|---|---|
| `Experiment 1 data Maertens et al 2020.csv` | 479 × 58 |
| `Experiment 2 data van der Linden et al 2017.csv` | 2,197 × 33 |
| `Supplemental study data Maertens et al 2025.csv` | 1,825 × 384 |
| `Experiment 1 analysis.R` | 16.9 kB — ANCOVAs, lavaan SEM, semPower |
| `Experiment 2 analysis.R` | 27.2 kB — **the only codebook**: maps the Q-numbered columns |
| `Supplemental Study analysis.R` | 4.8 kB — control-group pre/post only |
| `Internal meta analysis GmBM.R` | 9.5 kB — 3-study metaSEM of path coefficients |
| `Figures 6 and 7.R` | 4.6 kB — reshapes Exp 1/2 to long for plotting |

The project **has no codebook** (README says so; confirmed). All four `.R` files were read in full.

### 0.1 Message texts — NOT PRESENT (checked)

- No `materials/`, no `.qsf`, no `.pdf`, no `.docx`, no `.txt`. `find` returns the 8 files above.
- Every quoted string ≥40 chars in the five `.R` files was extracted and inspected: they are filenames,
  column names and lavaan model syntax. **No stimulus text anywhere.**
- The three CSVs contain no stimulus columns. Exp 2 is entirely numeric Q-codes; Exp 1 carries only
  `Duration_*` timers for the message pages; the supplemental study carries `Timer_*` and
  participants' own free text (`Open_Process`, `Open_Memory1..4`), never the stimulus.

This is decisive against the "arms are things a respondent READS" requirement. Contrast with the five
existing tasks: **all five now have verbatim arm text** in `inputs/texts/*_arms.json`, extracted from
mounted materials (`usa_1.qsf`, `CCC - Questionnaire - Qualtrics.pdf`, …). The historical precedent —
`vlasceanu2024` was once carved with bare condition names — is recorded in that file's `_note` as a
**deficiency that was later repaired**, not as an acceptable shape ("the task then trained
ordering-from-a-label"). Reintroducing a labels-only task would move the harness backwards, and it
would do so on a 4-to-6-cell-wide table.

The stimuli here (Cook et al. 97 % pie chart; the Oregon Global Warming Petition "31,000 scientists"
misinformation; the two inoculation texts) are described in the three published papers' SIs, which are
**not mounted**. Fetching them is an operator decision, not a recon finding.

---

## 1. Experiment 1 — Maertens, Anseel & van der Linden 2020 (n = 479)

`Experiment 1 data Maertens et al 2020.csv`, 479 rows × 58 cols. U.S. (`US_State`), ages 18–80.

### 1.1 Condition column and arms

`Condition` (string), 4 levels, randomised, near-balanced:

| arm | n (all rows) | n with `Complete == 1` (has T3) |
|---|---|---|
| `Control` | 120 | 103 |
| `Consensus` | 119 | 106 |
| `Inoculation` | 120 | 105 |
| `Balanced` | 120 | 101 |

Design, reconstructed from the timer columns (`Duration_Filler_T1T2`, `Duration_Consensus_T1T2`,
`Duration_Inoculation_T1T2`, `Duration_Misinfo_T3`; counts are non-null per arm):

- **T1** = baseline, all arms.
- **T1T2 session**: `Control` reads a **filler** (120/120, median 21.7 s); `Consensus` **and
  `Balanced`** read the **same consensus message** (119 and 120, median ≈ 7.2 s); `Inoculation`
  reads the **inoculation text** (120, median 64.0 s). → **at T2 there are only THREE distinct texts
  across four arms** (`Consensus` and `Balanced` are one text, split only for what happens at T3).
- **T3** (~1 week later): `Balanced` (101) and `Inoculation` (105) read the **misinformation**
  (Oregon-petition style); `Control` and `Consensus` read nothing. → at T3 the four arms are four
  distinct *histories*: nothing / consensus only / consensus→misinfo / inoculation→misinfo.
- Redundant dummies: `Consensus` = 1 for Consensus/Inoculation/Balanced, `Inoculation` = 1 for the
  Inoculation arm, `Misinfo` = 1 for Balanced/Inoculation rows that completed T3.

### 1.2 Outcomes — all five, with scale, and none is trust

| column stem | wave suffixes | lo | hi | n (T1/T2 = 479, T3 = 415) | construct |
|---|---|---|---|---|---|
| `PSC` | `.T1 .T2 .T3` | 0 | 100 | 479/479/415 | **perceived scientific consensus** — % of climate scientists estimated to agree. NOT trust. |
| `Belief` | `.T1 .T2 .T3` | 1 | 7 | 479/479/415 | belief that climate change is happening (integer Likert) |
| `HumanCausation` | `.T1 .T2 .T3` | 1 | 7 | 479/479/415 | belief it is human-caused (integer Likert) |
| `Worry` | `.T1 .T2 .T3` | 1 | 7 | 479/479/415 | worry about climate change (integer Likert) |
| `SupportForAction` | `.T1 .T2 .T3` | 1 | 7 | 479/479/415 | support for public action (integer Likert) |

Pre-computed difference columns `<stem>_Diff_T2T1`, `_T3T2`, `_T3T1` exist for all five.
**Trust outcome present? NO.** Nothing in the 58 columns names or measures trust, credibility,
confidence in scientists, or any institution.

### 1.3 Moderators

| target moderator | column | note |
|---|---|---|
| gender | `Sex` — `Female` 244 / `Male` 235 | **no `Other` level** (target has one) |
| age_band | `Age` (18–80, integer) | re-cuttable to the target bands: 18-29 = 173, 30-44 = 203, 45-59 = 75, **60+ = 28** (≈ 7 per arm — unusable per moderator cell) |
| party | `PoliticalParty` — Democrat 227 / Independent 140 / Republican 65 / Other 47 | **exact 4 target levels**; but min arm × level cell = **7** (Balanced × Other) |
| education | `Education` 1–5 + `Education_Category` (`Less than high school` 5, `High school graduate` 54, `Some college` 159, `Undergraduate degree` 180, `Graduate degree` 81) | the target's 6 levels split Master's vs Doctorate — **not recoverable** |
| race | — | **absent** |
| income | — | **absent** |
| extra | `Ideology` 1–7 (1 = liberal … 7 = conservative), `Ideology_Category`, `US_State`, `YearOfBirth`, two attention checks | |

### 1.4 VERDICT — Experiment 1: **NOT CARVABLE** (as a sixth *trust* practice task)

Reasons, in order of severity: (1) **no trust outcome** — it cannot buy the thing it was asked to buy;
(2) **no message text on disk**, so the arms would be four bare labels; (3) at T2 only three distinct
texts exist across four arms; (4) the table would be 3 arms × 5 outcomes = **15 cells at n ≈ 100–120
per arm**, against 165–208 cells at n ≈ 340–1,070 in the five existing tasks — the per-cell sampling
noise on a 1–7 Likert at n = 100 is comparable to the effects, so the score would mostly measure
noise; (5) no race, no income, no gender `Other`, and party cells as thin as 7 — the Section-3
subgroup rows are not carvable at all.

---

## 2. Experiment 2 — van der Linden, Leiserowitz, Rosenthal & Maibach 2017 (n = 2,197)

`Experiment 2 data van der Linden et al 2017.csv`, 2,197 × 33, raw Qualtrics export, Q-numbered.
U.S. (`Q52` = state, 1–51).

### 2.1 Condition column and arms

`FL_32_DO` (string, Qualtrics flow order), 6 levels + 21 rows with no condition (drop those):

| arm | n | what it was (from the published design; **text not on disk**) |
|---|---|---|
| `Control` | 363 | no climate message |
| `PieChartOnly` | 339 | the 97 %-consensus pie chart |
| `CounterOnly` | 392 | the misinformation only (Oregon Petition) |
| `Pie-Counter` | 355 | consensus then misinformation |
| `Pie+Inoc-Counter` | 363 | consensus + brief inoculation, then misinformation |
| `Pie+Indepthinoc-Counter` | 364 | consensus + in-depth inoculation, then misinformation |
| (missing) | 21 | |

The authors' script only ever uses `mis.cond` = Control (0) vs CounterOnly (1); the other four arms
are unused by them but are perfectly usable.

### 2.2 Outcomes — the five constructs, pre (Q3–Q11) and post (Q31–Q39)

Mapping is from `Experiment 2 analysis.R` (the only documentation):

| construct | pre | post | lo–hi | n post (per arm 337–392) |
|---|---|---|---|---|
| **PSC** (perceived scientific consensus, 0–100 slider) | `Q8_1` | `Q36_1` | 0–100 | 2,170 |
| belief CC happening (**derived**, 5-point) | `Q3_1` + `Q5_1` | `Q31_1` + `Q33_1` | 1–5 | 2,171 |
| human causation (**derived**, 5-point) | `Q6_1` + `Q7_1` | `Q34_1` + `Q35_1` | 1–5 | **1,637** (branching; ~270/arm) |
| worry | `Q10_1` | `Q38_1` | 1–7 | 2,167 |
| support for action | `Q11_1` | `Q39_1` | 1–7 | 2,169 |

Belief and human-causation are **recodes across two branched items each** (exact recode lines are in
the script and are reproduced in §2.4 below); the human-causation recode leaves "unsure / don't know
the cause" respondents `NA`, hence n = 1,637, and the authors ship a sensitivity recode that folds
them to the midpoint.

**Undocumented columns** (the script maps none of them): `Q4_1`, `Q9_1`, `Q32_1`, `Q37_1` (7-point),
`Q40_1`, `Q41_1`, `Q44_1`, `Q45_1` (3-point), `Q42_1`, `Q43_1`, `Q46_1`, `Q47_1` (7-point, branched
on the preceding 3-point item). Their behaviour was profiled to see whether any could be trust:

- `Q4_1`/`Q32_1` track belief-in-CC (certainty of that belief).
- `Q9_1`/`Q37_1`: pre-values are flat across arms (4.30–4.53) and post-values are **monotone in
  consensus dose** (PieChartOnly 6.02 > Pie+Indepth 5.51 > Pie+Inoc 5.23 > Pie-Counter 5.16 >
  CounterOnly 4.70 > Control 4.50), r ≈ 0.45 with post-PSC. This is a **consensus item** (agreement/
  certainty about scientific agreement), not trust.
- `Q40/Q42`, `Q44/Q46` are gate-then-rate pairs whose gates move massively with condition (`Q40_1` = 1
  for 100 % of the branch that then answers `Q42_1`); `Q46_1`/`Q47_1` correlate **−0.49/−0.45** with
  post-PSC. Shape is "did you see / how convincing did you find [the message / the petition]" —
  message-level manipulation checks.
- **None of the twelve can be established as trust in scientists**, and the harness's own rule
  (findings 20, 26: check what a field actually is before scoring it) forbids promoting an
  undocumented column to a scored outcome. **Trust outcome present? NO.**

### 2.3 Moderators

| target moderator | column | coding (from the script) | verdict |
|---|---|---|---|
| gender | `Q49` | 2 = male, 3 = female | **no `Other`**; usable as 2 levels |
| age_band | `Q50` | 1 = 18-24, 2 = 25-44, 3 = 45-64, 4 = 65+ | **does not nest** in the target's 18-29/30-44/45-59/60+; and `4` is n = 39 total (3–9 per arm) |
| education | `Q51` | 1 = some HS or less, 2 = HS grad, 4 = college grad, 5 = graduate degree, 6 = some college/associate/vocational | 5 levels, no Master's/Doctorate split |
| party | `Q53` | 1 = Republican, 2 = Democrat, 3 = Independent, 9 = Other, 10 = no party/not interested | **4 target levels obtainable** if 9+10 → `Other`; min arm cell 56 |
| ideology | `Q54_1` | 8 = very liberal, 7 = somewhat liberal, 4 = moderate, 3 = somewhat conservative, 1 = very conservative | extra |
| race | — | **absent** | |
| income | — | **absent** | |
| state | `Q52` | 1–51 | |

Sample is heavily skewed young/liberal (58.5 % aged 25–44; 47.9 % liberal vs 24.4 % conservative;
55.7 % female) — a poor stand-in for the target's census-quota panel.

### 2.4 Exact recodes needed (from `Experiment 2 analysis.R`)

```
belief.T1: Q3_1==1 -> 1 ; Q5_1==2 -> 2 ; Q5_1==3 -> 3 ; Q5_1==1 -> 4 ; Q3_1==3 -> 5
belief.T2: Q31_1==1 -> 1 ; Q33_1==2 -> 2 ; Q33_1==3 -> 3 ; Q33_1==1 -> 4 ; Q31_1==3 -> 5
hcaused.T1: (Q6_1==5 | Q7_1==7 | Q3_1==1 | Q5_1==2) -> 1 ; (Q6_1==1|Q7_1==1) -> 2 ;
            (Q6_1==2|Q7_1==2) -> 3 ; (Q6_1==3|Q7_1==3) -> 4 ; (Q6_1==6|Q7_1==6) -> 5 ; else NA
hcaused.T2: same with Q34_1/Q35_1/Q31_1/Q33_1
```

### 2.5 VERDICT — Experiment 2: **NOT CARVABLE** (as a sixth *trust* practice task)

The best-shaped of the three: 5 treatment arms × 5 outcomes = **25 cells**, n 339–392 per arm, one
0–100 slider outcome, party mappable to all four target levels. But: (1) **no trust outcome**, which
is the entire reason the question was asked; (2) **no message text on disk** — five bare labels, and
four of the five arm names (`Pie-Counter`, `Pie+Inoc-Counter`, `Pie+Indepthinoc-Counter`) leak the
design's dose ordering while conveying nothing a predictor could *read*; (3) two of five outcomes are
author-derived recodes across branched items, one of them with 25 % structural missingness; (4) no
race, no income, no gender `Other`, non-nesting age bands.
**Would become CARVABLE WITH CAVEATS as a sixth *non-trust* task if — and only if — the arm texts
were mounted**; it would then train message reading on a misinformation/inoculation contrast, which
is a genuinely different message family from the five existing tasks. It would still add **zero**
trust cells.

---

## 3. Supplemental study — Maertens, Rode, Logemann & van der Linden 2025 (n = 1,825)

`Supplemental study data Maertens et al 2025.csv`, 1,825 × 384. All rows have `Complete == 1`,
`AttentionCheck == 1`, `InTime == 1` (the file is already the cleaned analysis sample).
U.S. (`State`, 50 levels), ages 18–93 (median 33, from `Age_Year`).

### 3.1 Condition columns and arms

Two crossed columns plus a pre-joined one:

- `Group`: `Control` 771 / `Inoc` 810 / `InocInoc` 244
- `Measurement`: `T1` 619 / `T2` 517 / `T3` 689  (delay between inoculation and misinformation)
- `Condition` = the 7 realised cells:

| `Condition` | n | flow (confirmed from the timer columns) |
|---|---|---|
| `Control_T1` | 302 | control ranking task → misinfo at T1 |
| `Control_T2` | 263 | control task → misinfo at T2 |
| `Control_T3` | 206 | control task → misinfo at T3 |
| `Inoc_T1` | 317 | inoculation (median 60.8 s) → misinfo at T1 |
| `Inoc_T2` | 254 | inoculation → misinfo at T2 |
| `Inoc_T3` | 239 | inoculation → misinfo at T3 |
| `Inoc_B_T3` | 244 | inoculation + **booster at T2** (median 45.8 s) → misinfo at T3 |

`InocInoc` exists **only** at T3, so `Group × Measurement` is not a full factorial.
Dummies `Inoc1` (1,054) and `Inoc2` (244) encode the two inoculation doses.
The control arm's "message" is a **ranking task** (`ControlTask_*_GROUP`, `ControlTask_*_*_RANK`,
median 23.7 s), not a text to read.

### 3.2 Outcomes

Baseline `.Pre` (all 1,825) and post `.T1`/`.T2`/`.T3` (only at the respondent's assigned wave):

| stem | lo | hi | note |
|---|---|---|---|
| `PSC` | 0 | 100 | **perceived scientific consensus**. NOT trust. |
| `BeliefInCC` | 1 | 7 | **continuous** slider here (50–60 distinct values), not integer Likert |
| `HumanCausation` | 1 | 7 | continuous |
| `Worry` | 1 | 7 | continuous |
| `SupportForAction` | 1 | 7 | continuous |

Secondary blocks, post-only, per wave: `Apprehension_1..6`, `Fear_1..3`, `Motivation_1..3`,
`Involvement_1..6`, `Accessibility`, `Talk1_1/Talk1_2/Talk2/Talk3`, `Remember`, `Memory1..5`,
`Interference_1..3`, `MIST_1..20` (+ pre-computed `Apprehension.`, `Fear.`, `Involvement.`,
`Motivation.`, `ThreatIndex.`, `Memory.`, `Talk.`, `MIST20_V.` composites per wave). These are
**inoculation-process and misinformation-discernment** measures — threat appraisal, memory of the
message, ability to spot fake headlines. **Trust outcome present? NO.** No column in the 384 measures
trust, credibility or confidence in scientists or institutions.

### 3.3 Moderators

| target moderator | column | note |
|---|---|---|
| gender | `Gender` — Male 898 / Female 880 / Non-binary 37 / Transgender 6 / Other 4 | mappable to Male/Female/`Other` (47) |
| age_band | `Age_Year` (1929–2004) | re-cuttable to the target bands |
| party | `PoliticalParty` — Democrat 894 / Independent 538 / Republican 191 / **NA 202** | **no `Other` level**, 11 % missing, Republicans thin (21 in `InocInoc`) |
| education | `Education` 1–5, `Education_Groups`, `Education_Category` (Low/Medium/High) | no Master's/Doctorate split |
| race | — | **absent** |
| income | — | **absent** |
| extra | `Ideology` 1–7, `Ideology_Category1/2`, `State`, `News_SocialMedia`, `News_Twitter`, `NewsOutlet` (free text) | |

### 3.4 VERDICT — Supplemental study: **NOT CARVABLE**

(1) **No trust outcome.** (2) **No message text on disk**, and the control arm is a ranking task
rather than a readable message, so the arm contrast is not "text A vs text B" at all. (3) The
manipulation is **delay × inoculation-dose**, not message content: the four ATE-bearing contrasts
(`Inoc` at three delays, `InocInoc` at T3) differ mostly in *when* the misinformation arrived, which
is not a message-prediction task and has no analogue in the target. (4) `InocInoc` exists only at T3,
so the design is unbalanced. (5) The `.Pre` block is the study's real asset — 1,825 within-person
0–100 slider × 1–7 continuous-slider pairs — which is what the dataset README already claims it is
here for (the Likert→slider bridge), and that value is **unchanged by this verdict**.

---

## 4. Adapter-template field audit (`inputs/adapters/_TEMPLATE.json`)

Assessed for the best of the three (Experiment 2). Fillable / not:

| field | Exp 2 | note |
|---|---|---|
| `dataset`, `file`, `reader` | ✅ | plain CSV, `na_values` default is fine |
| `sample_description` | ✅ | 2,176 U.S. adults, Qualtrics panel, skewed young/liberal; must state that arms are labels only |
| `condition_col` | ✅ | `FL_32_DO` |
| `arms` (6) / `control_arms` | ✅ | drop the 21 rows with a missing condition |
| `filters` | ✅ | `FL_32_DO` not null |
| `outcomes` | ⚠️ | 3 direct columns (`Q36_1`, `Q38_1`, `Q39_1`) + 2 **derived** columns the adapter schema has no field for — `belief` and `hcaused` need a recode step the template cannot express (`col` is a single string). Would need either a pre-recode tool or an adapter-schema extension. |
| `outcomes[*].question` | ❌ | **no item wordings exist on disk.** The `question` strings that every existing adapter carries verbatim would have to be paraphrased from the R comments — i.e. invented. |
| `moderators.gender` | ⚠️ | 2 levels only, no `Other` |
| `moderators.age_band` | ❌ | `Q50`'s 18-24/25-44/45-64/65+ does not nest in the target bands |
| `moderators.party` | ✅ | `Q53` 1/2/3/(9,10)→Other |
| `moderators_unavailable` | — | race: absent; income: absent; education: no Master's/Doctorate split |
| `weight_col` | ✅ | `null` (none exists) |
| `message_texts_file` / `message_texts_source` | ❌ | **the blocking field.** Nothing to point at. |
| `provenance.verified_by` / `caveats` | ✅ | this file |

Exp 1 and the supplemental study fail the same `message_texts_*` and `question` fields, plus
`moderators.gender` (Exp 1 has no `Other`) and, for the supplemental study, `condition_col` itself —
its arms are a delay × dose cross, not a message set.

---

## 5. Bottom line

| study | trust outcome? | arm texts on disk? | verdict |
|---|---|---|---|
| Experiment 1 (Maertens 2020) | **NO** | **NO** | **NOT CARVABLE** — 15 cells at n ≈ 100/arm, 3 distinct texts, no race/income/gender-Other |
| Experiment 2 (van der Linden 2017) | **NO** | **NO** | **NOT CARVABLE** as asked. Best shape (5×5 = 25 cells, n 339–392); would be CARVABLE WITH CAVEATS as a *non-trust* misinformation/inoculation task **only if the SI stimulus texts were mounted** |
| Supplemental (Maertens 2025) | **NO** | **NO** | **NOT CARVABLE** — manipulation is delay × dose, control arm is a ranking task, not a message |

**`gatewaybelief` cannot supply a trust-family practice cell.** Standing finding 33 and OPEN item 18
are untouched by this dataset; the honest options there remain (a) find a randomised experiment with a
trust-in-scientists outcome elsewhere, or (b) keep the cross-family extrapolation declared in writing.
Of the mounted datasets, the ones that actually measure trust in scientists are observational
(`tisp`, `pew_atp`, `gss`) or measure it under a *scientist-type* randomisation rather than a
*message* randomisation (`gligoric2025` — 35 randomly assigned scientist types, already used for
findings 5 and 15). Whether `gligoric2025` can be re-shaped into an arm × outcome ATE table whose
"arms" are scientist descriptions is a different question from the one asked here, and it is the one
worth asking next.

The dataset's established value — the within-person 0–100 slider × 1–7 Likert joint distribution
(Likert→slider bridge, README §"Why it is here") — is unaffected by every verdict above.
