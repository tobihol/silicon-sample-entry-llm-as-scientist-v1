# DATA_BBPRIME_VOELKEL2024.md - verification note for two 'process practice' adapters

Written by a child agent, plain code only, no model calls. Everything below was computed on the
FULL files in this session unless marked UNVERIFIED. Both adapters carry `status: VERIFIED - ...`
with the same list.

Deliverables:
- `inputs/adapters/bbprime2025.json`, `inputs/adapters/voelkel2024.json`
- `inputs/derived/bbprime2025_analysis.csv` (built here; 7,624 x 32, 1.9 MB)
- `inputs/texts/bbprime2025_arms.json` (empty arm texts + note + rated stimuli),
  `inputs/texts/voelkel2024_arms.json` (real texts, 26 arms, 186 kB)

---

## 1. voelkel2024 - Strengthening Democracy Challenge

**File** `/workspace/datasets/voelkel2024/downloads/SDC - Data - Recoded.csv`, read whole
(35,252 rows x 113 cols; adapter reads 35 columns).

**Arms** 27 = 25 interventions + `Null_Control` + `Alternative_Control`. Raw `Condition` values are
mapped to the manuscript names from `SDC - Data - Intervention Names.csv` (all 27 map, no leftovers).
`Null Control` is the only control arm; `Alternative Control` is carried as a 26th treatment arm and
is a free honesty check (its true effect is near zero). Sizes: Null Control 5,691; Alternative
Control 1,133; interventions 1,126-1,147.

**Outcomes** 9, all 0-100 sliders, all pre-computed in the recoded file, all named in the study's own
`SDC - Data - Outcome Names.csv`: PA, ADA, SPV, SUC, OppBip, SocDistrust, SocDis, BEPF, Composite.
No composite was invented. Complete-case n per outcome 30,911-31,856.
**ATE table** 26 x 9 = 234 cells, zero NaN, range **-10.69 .. +2.59 pp**, mean -1.03, SD 2.10.
Per-outcome means: PA -4.59 (min -10.69), SocDistrust -1.50, Composite -1.01, SocDis -0.95,
SUC -0.42, OppBip -0.31, BEPF -0.30, SPV -0.12, ADA -0.11. Effects are overwhelmingly negative
because every outcome is scored so that higher = worse.

### What I checked, and how
- **Reverse scoring is already applied** - proved exactly, not assumed. Against the raw items in
  `SDC - Data - Anonymized.csv`: `OppBip + mean(SupBip_1_1, SupBip_2_1) == 100.000` on all 31,239
  complete rows; `SocDis + mean(SocDis_1_1, SocDis_2_1) == 100.000` on all 31,228;
  `SocDistrust + SocTru_1 == 100.000` on all 31,247 (SD of the sum = 0 in each case).
  So `reverse` is `false` for every outcome; reversing again would flip 3 of 9 outcomes.
- **Party coding** `Party_Gen` 1=Republican / 2=Democrat / 3=Independent - proved from
  `crosstab(Party_Gen, Inparty_Person)`: 15,009/15,009 of code 1 are piped 'Republican',
  15,525/15,525 of code 2 are piped 'Democrat', code 3 (4,718 leaners) splits 2,410/2,308.
  Corroborated: 82% of Black respondents are code 2; mean Ideology 5.50 (code 1) vs 2.81 (code 2).
- **Weights.** The data ship one weight column per outcome; `ssb.task.true_ates` takes a single
  weight column, so the adapter is UNWEIGHTED. Measured cost: over all 234 cells, weighted vs
  unweighted ATEs correlate **r = 0.9997**, max |difference| **0.19 pp**. Weight columns pairwise
  correlate 0.89-0.97, range 1.00-4.08, no missing.
- **Attrition.** `Attrited_<Y> == 1` is exactly equivalent to `Y` being NaN for 8 of 9 outcomes
  (agreement 1.0000); SUC agrees on 98.83%. No global filter is applied; `true_ates` complete-cases
  each outcome itself.
- **Moderator recodes** - 0.00% unexpected NaN on all five, and every emitted string is verbatim from
  `ssb.spec.load()["moderators"]`:
  gender Male/Female/Other (n 16,040 / 19,074 / 138); age_band 18-29/30-44/45-59/60+;
  race White->`White / Caucasian`, Black->`Black / African American`, Hispanic->`Hispanic / Latino`,
  Asian->`Asian / Asian American`, Other->`Other` (smallest race x arm cell 31);
  education 4 levels -> 4 target levels; party 1/2/3 -> Republican/Democrat/Independent.
- **Carve** `ssb.task.carve("voelkel2024", ...)` builds `brief/` + `sealed/` with 234 cells and
  **non-empty message text for all 26 arms**.

### What I could not verify / dropped
- **N = 32,059** (README, post-preregistered-exclusion) is not reproducible from any single stored
  flag; the file has 35,252 rows and the largest complete-case n is 31,856. UNVERIFIED.
- **income**: absent from both data files and never asked in the questionnaire. Dropped.
- **party 'Other'**: true independents and other-party identifiers were screened out at recruitment,
  so the target's 4th party level has no cases. Recorded in `moderators_unavailable`.
- **education** is 4 levels, and the mapping is deliberately LOSSY: `HS or less` ->
  `High school diploma / GED` (so the target's `Less than high school` is absorbed, not represented)
  and `Postgraduate` -> `Master's degree / Professional degree` (so `Doctorate degree / Ph.D.` is
  absorbed). Kept because the four emitted strings are exact target strings and the collapse is
  documented; a run that needs clean education levels should prefer bbprime2025, which has all six.
- The exact formula for the `PA` and `Composite` composites is still UNVERIFIED (the recoding script
  is not on disk). They are used AS SUBMITTED, which is what the target's scoring rule requires.
- `Coding J.xlsx` / `Coding N.xlsx` were inspected: 25 x 15 tables of coder ratings of intervention
  FEATURES (misperception correction, threat, contact, elite cues, ...) - no intervention text.
  Not used and not deposited anywhere near a brief.

### Message texts (real)
`inputs/texts/voelkel2024_arms.json`, 186 kB, keyed by manuscript arm name. Extracted with pypdf from
`SDC - Questionnaire.pdf` (374 pp) by splitting on `Start of Block: <4-char code> - <name>` and
concatenating, in page order, every block belonging to an arm; Qualtrics timing / page-break /
display-logic scaffolding stripped. All 26 arms have text. The BUNU blocks were unlabelled in the
recon notes - they are **Democratic_Fear** (verified from the content: 'Zimbabwe, Venezuela, Russia
and Turkey are just a few examples of countries where democracy has failed').
Caveats recorded in the file's `_note` key:
- piped fields such as `${e://Field/Inparty_Person}` are left verbatim (the same block reads
  'Republican' or 'Democrat' depending on the respondent);
- six arms are video or interactive and only the wrapper exists on disk: Positive Contact Video,
  Correcting Division Misperceptions, Pro-Democracy Bipartisan Elite Cues, Common Economic Interests,
  Correcting Policy Misperceptions Chatbot, and part 1 of Democratic Collapse Threat;
- sizes are uneven and large: Party Overlap on Policies 31k chars, Bipartisan Joint Trivia Quiz 23k,
  Outpartisans' Willingness to Learn 21k, versus 205 chars for the chatbot. Inlining all of them in a
  brief costs ~46k tokens; the file holds the untruncated text and truncation is left to the caller.

---

## 2. bbprime2025 - BB-PRIME Phase II climate intervention tournament

**Built file** `/workspace/run/inputs/derived/bbprime2025_analysis.csv` - 7,624 rows x 32 columns,
one row per `SID`: `SID`, `group`, 24 collapsed outcomes, `age`, `gender`, `hispanic_latinx`,
`ses_degree`, `race_target`, `party_raw`. No raw long-format rows were copied.

### Join recipe (key `SID`, all files main-exclusion variant)
| source file | rows in | what was taken | SIDs out |
|---|---|---|---|
| `messages_data.csv` | 266,787 | dropped `exclude_item == 1` (980 rows = 140 person-headline pairs x 7 scales; the 41,332 rows where `exclude_item` is NaN were KEPT), then mean of `value` per SID x scale for `msg_share_broad`, `msg_share_narrow`, `msg_rel_self`, `msg_rel_social` | 7,623 |
| `petitions_data.csv` | 106,169 | mean per SID for `petition_sign_intention`, `petition_share_broad`, `petition_share_narrow`; `petition_sign` recoded `yes`=1 else 0 and averaged over the 3 petitions; `petition_link_clicks` as-is (already one row per SID) | 7,622 |
| `actions_data.csv` | 517,214 | mean over the 12 actions for `action_intention`, `action_env_impact`. `value_z` NOT used | 7,624 |
| `emotions_data.csv` | 60,991 | 8 emotions, one row per SID each | 7,624 |
| `other_dvs_data.csv` | 84,039 | `self_efficacy`, `concern_risk` (item == 'mean'); `distance` items geographic/social/temporal; `politics`/`affiliation` as `party_raw` | 7,624 |
| `demographics_data.csv` | 85,449 | `age`, `gender`, `ses_degree`, `hispanic_latinx`; `race_ethnicity` is MULTI-SELECT (8,122 rows for 7,624 SIDs) collapsed to `race_target` | 7,624 |

Outer join on SID -> **7,624 rows in, 7,624 rows out**; `group` present and constant per SID for all
of them. Per-column missingness after the join: 1 for the four msg outcomes, 2 for the five petition
outcomes, 0 for actions/emotions/self_efficacy/concern_risk/distance_geographic/distance_social,
**111 for `distance_temporal`**, 1 for `age`, 26 for `gender`, 35 for `race_target`, 4 for `party_raw`.

`race_target` rule (recorded in the adapter too): `hispanic_latinx == 'Yes'` -> `Hispanic / Latino`;
else drop any 'Prefer not to say' entries; more than one race left -> `Other`; single White ->
`White / Caucasian`; single Black or African American -> `Black / African American`; single East /
South / Southeast Asian -> `Asian / Asian American`; American Indian or Alaskan Native, Native
Hawaiian or Other Pacific Islander, 'Racial/ethnic identity not listed' -> `Other`; nothing left ->
NaN (35 respondents). Result: White 4,666 / Black 1,057 / Hispanic 776 / Asian 648 / Other 442.

### Arms and outcomes
18 arms = 17 interventions + `control`. Sizes reproduce the README exactly: control 850,
interventions 370-428 (norm_text 428, CF_general 428, ..., STPB 370). Arm titles are the manuscript
labels from `tournament_analysis_OSF.Rmd`, taken **positionally** from its
`factor(levels = c('self_relevance', ..., 'STPB'))` / `levels(x) <- c('News Comments (Self-Rel)',
..., 'Personal Benefits')` pair. `notes/DATA_experiments.md` sec 4.2 prints that label list in the
REVERSE order; the Rmd order is the correct one and is confirmed semantically
(self_relevance->Self-Rel, STPB->Personal Benefits, CF_general->Carbon Footprint (General)).

24 outcomes = exactly the dependent variables that `tournament_analysis_OSF.Rmd` runs a
`contrast(emmeans(model, ~ group), 'trt.vs.ctrl1')` on. Nothing was invented and nothing was
composited beyond collapsing each scale to a person-level mean. Scales verified against the data and
against the verbatim item wordings in `SOP_and_measures.docx`: 0-100 sliders (7), 1-7 (2 actions +
distance_temporal), 1-5 (8 emotions + self_efficacy + concern_risk + 2 distance), 0-1
(`petition_sign`, proportion of 3 petitions signed), 0-3 (`petition_link_clicks`).

**ATE table** 17 x 24 = 408 cells, zero NaN, range **-4.53 .. +15.93 pp**, mean +0.98, SD 3.17.
The six largest cells are all `News Comments (Social-Rel)` / `(Self-Rel)` on the message-rating
outcomes (12.7-15.9 pp) - those interventions manipulate precisely what the message items ask about.
The rest of the table sits between -4.5 and +9 pp.

### Moderators
All five emit exact target strings. Unmapped shares (all deliberate): gender 0.34% ('Prefer not to
say', n=26), age_band 0.01% (1 missing age; observed range 18-88), race 0.46% (n=35), education
0.00%, party 4.53% ('Not registered' n=330, 'Not eligible' n=11, plus 4 missing).
**education is the best of any dataset in this repo**: all six target levels are populated -
Less than high school 52, High school diploma / GED 827, Some college or Associate's 2,288,
Bachelor's 3,020, Master's / Professional 1,303, Doctorate / Ph.D. 134 (sums to 7,624).
party: Democratic Party->Democrat 4,281, Independent 1,757, Republican Party->Republican 1,005,
Other/Libertarian/Green->Other 236.

### What I could not verify / dropped
- **income - DROPPED.** `ses_income_household`'s 10 brackets straddle three of the target's four cut
  points: '$25,000 through $34,999' (n=654) straddles $30,000, '$50,000 through $74,999' (n=1,520)
  straddles $56,000, '$150,000 and greater' (n=808) straddles $168,000. Only the $100,000 edge
  aligns. No sub-bracket information exists on disk, so any mapping would be a guess.
- **No intervention text exists.** `SOP_and_measures.docx` (24,667 characters extracted via the docx
  XML) documents the procedure, exclusions and every OUTCOME item verbatim but has no intervention
  content; the two Rmds carry only condition labels; the seven per-intervention OSF pre-registrations
  are not on disk. `inputs/texts/bbprime2025_arms.json` therefore holds `{arm: ""}` for all 17 arms,
  a `_note` recording that search, and a `_rated_stimuli` key with the 26 New York Times
  headline/snippet pairs (`messages_data.csv` columns `main_headline`, `snippet`) and the 10 petition
  texts (`petitions_data.csv` column `petition_text`) that every respondent RATED after treatment -
  identical across arms, so they describe the outcome measure, not the treatment.
- **Recon correction:** `notes/DATA_experiments.md` sec 4.4 says the political moderators ship only in
  `indiv_diffs_data_few_excl.csv`. They also ship in the MAIN `other_dvs_data.csv` under
  `scale_name == 'politics'` (affiliation for 7,620 of 7,624). So no `_few_excl` file was needed and
  the adapter stays entirely within the N = 7,624 main-exclusion variant.
- **Clustering is not modelled.** The authors fit `lmer`/`brm` with random intercepts for people AND
  stimuli; collapsing to person means first (as the recon note prescribes) gives person-level ATEs
  that will not equal the paper's model-based contrasts, and the SEs here ignore stimulus sampling.
  The paper's own tables are not reproducible from disk anyway (the `./models` RDS folder was not
  downloaded), so no published ATE could be checked against these.
- Excluded outcomes and why: `msg_read`, `msg_emo_pos`, `msg_emo_neg`, `action_ease`,
  `action_approval`, `action_person_impact`, `climate_knowledge`, `climate_change_cause`,
  `action_current*` - no condition contrast in the Rmd, or no fixed scale. `uncertainty` also has no
  Rmd contrast AND is truncated by design (a mean > 4 on it was an exclusion criterion; observed max
  is 4).
- Tournament-wide comparisons were not preregistered (the SOP says so). The sample is Prolific,
  screened to climate-change believers, gender-balanced by design, young-skewed (mean age 39.5) and
  56% Democrat / 13% Republican. Magnitudes should not be ported to a census-quota panel.

---

## 3. One harness limitation hit by both (no ssb source was modified)

`ssb.task.true_ates` writes `int(an)` / `int(cn)` where `wm()` returns `np.nan` for any cell with
<= 2 observations, so a moderator with a small level raises
`ValueError: cannot convert float NaN to integer` instead of emitting a NaN ATE.

- voelkel2024: `moderator='gender'` raises (gender 'Other', n=138 over 27 arms).
  `age_band` / `race` / `education` / `party` are fine: 936 / 1,170 / 936 / 702 cells, 0 NaN.
- bbprime2025: `moderator='education'` raises ('Less than high school', n=52 over 18 arms).
  `gender` / `age_band` / `race` / `party` are fine: 1,224 / 1,632 / 2,040 / 1,632 cells, 0 NaN.

Both adapters record this in a `harness_note` key with the one-line adapter-side workaround (drop the
offending level from the map, at the cost of a target moderator level). The clean fix is in
`ssb/task.py` and is the owner's call.

## 4. Unrelated bug found while checking (not touched)

`inputs/adapters/voelkel2026.json` maps `moderators.gender` as `{"1": "Male", "2": "Female",
"3": "Other"}`, but the `Gender` column of `CCC - Data - Recoded.csv` holds the STRINGS
`Female` (7,455) / `Male` (6,237) / `Other` (129). `_map_codes` therefore returns all-NaN, and
`true_ates(df, ad, moderator='gender')` silently returns an EMPTY DataFrame rather than raising.
A one-line map fix (`{"Male": "Male", "Female": "Female", "Other": "Other"}`) would fix it; I did
not edit that file because it is outside my deliverables.

## 5. Blinding

No file encountered in this session described the target study. Everything read was
`/workspace/datasets/bbprime2025/*` and `/workspace/datasets/voelkel2024/*` (plus
`/workspace/benchmark`-derived moderator level strings via `ssb.spec.load()`), and one read of the
existing `voelkel2026` adapter for the bug above. No model or simulator call of any kind was made.
