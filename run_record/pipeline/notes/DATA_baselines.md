# DATA_baselines.md — TISP / CCAM / GSS / GLIGORIC2025

Recon only. Everything below was read from the files named. **No outcome means, SDs, or
distributions were computed** from any of these datasets (ground rule: authoring/recon only) —
only file shape, column names, value codings, availability-by-wave counts, and demographic cell
counts. Where a number would have to be *estimated from data*, this file says what to compute and
on which file, not the number. No model calls were made. Nothing about the sealed target study's
human results was sought or encountered.

Target-study schema facts quoted here come from `/workspace/benchmark/codebook.csv` (63 rows,
columns `section, qualtrics_label, target_label, question_text, response_options`), which is
instrument metadata, not results.

---

## 0. Headline finding (drives everything else)

`/workspace/benchmark/codebook.csv` rows 6–17 show the target study's 12 trust items are the
**TISP 12-item scale re-worded from "most scientists" to "most climate scientists" and re-hosted on
0–100 sliders**. Item-by-item, target ← TISP:

| target `target_label` | target question text (codebook.csv) | TISP column (`ds_final`) | TISP question text (core-questionnaire_english.pdf) |
|---|---|---|---|
| trust_competence_1 | How incompetent or competent are most climate scientists? | *(no exact match)* | TISP uses `TRUST_SCI_expert` "How expert or inexpert…" |
| trust_competence_2 | How unintelligent or intelligent… | `TRUST_SCI_intellig` | How intelligent or unintelligent are most scientists? |
| trust_competence_3 | How unqualified or qualified… | `TRUST_SCI_qualified` | How qualified or unqualified … high-quality research? |
| trust_integrity_1 | How dishonest or honest… | `TRUST_SCI_honest` | How honest or dishonest are most scientists? |
| trust_integrity_2 | How unethical or ethical… | `TRUST_SCI_ethical` | How ethical or unethical are most scientists? |
| trust_integrity_3 | How insincere or sincere… | `TRUST_SCI_sincere` | How sincere or insincere are most scientists? |
| trust_benevolence_1 | How unconcerned or concerned … about people's wellbeing? | `TRUST_SCI_concerned` | identical wording |
| trust_benevolence_2 | How uneager or eager … to improve others' lives? | `TRUST_SCI_improve` | identical wording |
| trust_benevolence_3 | How inconsiderate or considerate … of others' interests? | `TRUST_SCI_otherint` | identical wording |
| trust_openness_1 | How open, if at all, … to feedback? | `TRUST_SCI_open` | How open are most scientists to feedback? |
| trust_openness_2 | How unwilling or willing … to be transparent? | `TRUST_SCI_trans` | identical wording |
| trust_openness_3 | How much or how little attention … to other people's views? | `TRUST_SCI_otherviews` | identical wording |

So the subscale mapping is **confirmed by the target codebook itself** (not inferred): competence =
{competent, intelligent, qualified}, integrity = {honest, ethical, sincere}, benevolence =
{concerned, improve/eager, considerate}, openness = {feedback, transparent, attention}. Only one
item differs (`competent` replaces TISP's `expert`), and TISP's referent is *all* scientists, the
target's is *climate* scientists.

Two further verbatim carry-overs from TISP into the target instrument:

- `policy_role_1..4` (codebook rows 30–33) = TISP `NORMPERC_integrate / _advocate / _communicate /
  _involved`, with "scientists" → "climate scientists" and "politicians" → "policy makers".
- `policy_specific_1..5` (codebook rows 37–41) = TISP `CLIM_POLSUPPORT_fueltax / _publictransport /
  _sustenergy / _protection / _foodtax`, near-verbatim. (`policy_specific_6` green jobs and
  `_7` clean waterways have no TISP twin.)

TISP is therefore the level anchor for 3 of the 13 scored outcomes' item content
(trust_multidimensional, policy_role_mean, most of policy_specific_mean) plus `trust_post`
(`CLIM_TRUST`), not just the primary one.

---

## 1. TISP — `/workspace/datasets/tisp`

### 1.1 Files, shape, subsetting, weights

| item | value |
|---|---|
| microdata (preferred) | `/workspace/datasets/tisp/downloads/ds_final.sav` — SPSS, **69,534 rows × 140 cols** (pyreadstat metadata) |
| microdata (alt) | `/workspace/datasets/tisp/downloads/ds_final.csv` — **141 header fields**, `;`-delimited, UTF-8-with-BOM, 78,432 physical lines |
| instrument | `/workspace/datasets/tisp/downloads/core-questionnaire_english.pdf` — 33 pages, gives every item's exact anchors |

CSV gotchas (verified, not guessed): (a) the CSV carries one column the .sav does not,
`Response_TYPE`; (b) numerics use **decimal commas** (`WEIGHT_CNTRY` = `0,0256288252919756`), so a
naive `read_csv` yields strings; (c) free-text fields (e.g. `DEM_GENDER_2_TEXT`) contain embedded
newlines/quotes — pandas raised `ParserError: Expected 141 fields ... saw 143` on line 68 of the US
subset. **Use the .sav.**

- Subset to US: `COUNTRY_CODE == "USA"` (also `COUNTRY_NAME`, `LAB`). Counted by awk on the CSV:
  **n = 2,559** (matches the README). Other large cells: DEU 8,014, AUS 3,523, POL 3,002, CAN 2,507.
  A `COUNTRY_CODE` value literally `"NA"` occurs 2,736 times — that is **Namibia**, not missing;
  string-read the column or it silently becomes NaN.
- All TISP respondents are adults (`DEM_AGE` ≥ 18 by design; US min observed 18).
- Weights: `WEIGHT_CNTRY` (post-stratification within country — the right one for a US-only mean;
  US range 0.766–1.378, mean 1.0003), `WEIGHT_GLOBL` (full data), `WEIGHT_SSIZE` (sample-size),
  `WEIGHT_MLVLM` (rescaled for multilevel). No PSU/strata variables.

### 1.2 The 12 trust items: scale, direction, coding

Columns (in file order): `TRUST_SCI_expert, _honest, _concerned, _open, _intellig, _ethical,
_improve, _trans, _qualified, _sincere, _otherint, _otherviews`.

- **5-point, 1–5, fully labelled at every point** (from the questionnaire PDF, e.g.
  `TRUST_SCI_honest`: 1 "Very dishonest", 2 "Somewhat dishonest", 3 "Neither honest nor dishonest",
  4 "Somewhat honest", 5 "Very honest").
- **All 12 keyed positively; no reverse-coded item; no don't-know option** on this block.
  (`DEM_POL_*` do have a 99 = "I don't know" code; the trust block does not.)
- Observed value range in-file is 1–5 with no negative missing codes.
- Two adjacent single items with the same 1–5 format: `TRUST_PEW` ("How much confidence do you have
  in scientists to act in the best interests of the public?", 1 "No confidence at all" … 5 "A great
  deal of confidence") and `TRUST_METHOD`. And critically `CLIM_TRUST`: *"To what extent do you trust
  scientists in your country who work on climate change?"* 1 "Not at all" … 5 "Very strongly" — the
  closest existing analogue of the target's `trust_post` ("How much do you trust climate
  scientists?", 0 = not at all … 100 = very strongly).

### 1.3 Converting a TISP US mean onto the target's 0–100 slider

What is needed, exactly:

1. Compute the weighted (`WEIGHT_CNTRY`) US mean of each of the 12 items on the 1–5 scale, then the
   four 3-item subscale means, then their mean (the target's `trust_multidimensional` is the mean of
   the four *subscales*, not of the 12 items — equal weighting of subscales; here they are equal-n
   so the two coincide, but replicate the codebook's order anyway).
2. Linear rescale `x_100 = (x_5 − 1)/4 × 100`, i.e. 1→0, 2→25, 3→50, 4→75, 5→100.
3. Apply three corrections, each of which is a judgement call and none of which TISP can settle:
   - **Referent shift** "most scientists" → "most climate scientists". Direction unknown a priori;
     `CLIM_TRUST` vs `TRUST_PEW` within TISP US is the only in-sample handle on it (both 1–5, both
     asked of the same respondents) — a computable diagnostic, not yet computed here.
   - **Response-format shift** 5-point radio → 0–100 slider. Discrete-Likert means do **not** map
     linearly onto slider means: the slider has no forced midpoint gravity, and empirically slider
     responses heap on multiples of 5 and endpoints. Use `gatewaybelief` (within-person Likert↔slider
     in the same respondents) and `orchinik2024`/`sce` (heaping) for this bridge — outside this
     file's scope but it is the load-bearing step. UNVERIFIED here.
   - **Time shift**: TISP was fielded Nov 2022 – Aug 2023 (README); the target study is 2026.
4. Variance, not just the mean, has to be carried: a 1–5 item has at most 5 support points, so the
   TISP SD is **not** a usable estimate of the target slider SD. Tier-1 variance-ratio scoring must
   take spread from a native-slider source (`voelkel2026`, `goldwert2026`, `orchinik2024`), with TISP
   supplying only the location. This is the single biggest misuse risk for TISP.

### 1.4 TISP demographics vs the six target moderators (US subsample, n = 2,559)

Counts below are cell counts on the 2,559-row US subset (unweighted), from
`DEM_*` columns of `ds_final.sav`. No outcome variable entered these counts.

| target moderator | TISP column | verdict |
|---|---|---|
| gender (Male/Female/Other) | `DEM_GENDER` (sav codes 1/2/3 carrying value-labels '0','1','2'; questionnaire: 0 = Woman, 1 = Man, 2 = Prefer to self-describe, 99 = Prefer not to say) | usable for Male/Female. **US counts: 1,387 Woman, 1,172 Man, 0 self-describe** → no "Other" cell at all |
| age_band (18-29/30-44/45-59/60+) | `DEM_AGE` (raw years) — rebuild bands from it | usable. **US: 18-29 = 436, 30-44 = 766, 45-59 = 640, 60+ = 717** |
| — | `DEM_AGEGRP` | do **not** use blind: its .sav value labels are out of numeric order (1='18-29', 2='30-39', **3='50-59'**, **4='40-49'**, 5='60+'); cross-tab against `DEM_AGE` confirms the labels are right and the codes are non-monotonic. US: 436 / 515 / 431 / 460 / 717 |
| race/ethnicity (5 levels) | **none** | **TISP has no race or ethnicity variable at all.** Any race-level baseline must come from elsewhere (CCAM, GSS, ACS/CES) |
| education (6 levels) | `DEM_EDU` (1 = Did not attend school, 2 = Primary, 3 = Secondary, 4 = Higher education incl. "university degree or higher-education diploma") + derived `DEM_EDU_uni`, `_collbot2`, `_collbot3` | **4 levels, not 6**, and level 4 is broader than "Bachelor's+". US: 15 / 97 / 1,042 / **1,405**. Collapsing the target's 6 levels onto these 4 loses the MA vs PhD contrast entirely |
| income (5 USD bands) | `DEM_INCOME` (free-numeric, local currency), `DEM_INCOME_USD`, `DEM_INCOME_USD_log` | usable but **continuous, self-reported, open-numeric** — must be cut into the target's 5 bands by hand. US: 56 missing; quartiles $23,000 / $49,000 (median) / $92,000. Note the target's bands are *household* income; TISP asks "household's yearly **net** income" (net, not gross) |
| party (Rep/Dem/Ind/Other) | **none.** Only `DEM_POL_conservative` and `DEM_POL_right`, each 1–5 (1 = Strongly liberal / left-leaning … 5 = Strongly conservative / right-leaning, 99 = don't know → NaN) | **no partisan-identity variable.** US `DEM_POL_conservative`: 364 / 303 / 718 / 413 / 565, 196 NaN. Ideology→party is a modelling assumption, not a recode |

Other TISP columns worth knowing about for the target's non-trust outcomes: `CLIM_GOV_*` (7 items,
1–5, government trust — adjacent to `inst_trust_*`), `CLIM_POLSUPPORT_*` (5 items but only a
**3-point** support scale plus a 4 = "Not applicable" code — a bad scale twin for a 0–100 slider),
`CLIM_EMO_*` (9 items, 1–5), `CLIM_WEATHERPAST/FUTU_*`, `SCIPOP_*` (8 items science populism),
`SDO_*` (4 items, 1–10), `WILLVUL_*`, `NORMPERC_*` (6 items, 1–5).

---

## 2. CCAM — `/workspace/datasets/ccam`

### 2.1 Files, shape, subsetting, weights

- `/workspace/datasets/ccam/downloads/CCAM SPSS Data 2008-2024.sav` — **35,309 rows × 58 cols**.
- `/workspace/datasets/ccam/downloads/Survey Methods and Codebook 2008-2024.pdf` (not text-mined here).
- All respondents are **US adults by construction** — no country filter needed; there is no
  citizenship/adult flag to apply.
- `wave` 1–31 with labels "Nov 2008" … "Dec 2024"; `year` is a **coded** variable 1–16 whose labels
  are 2008, 2010, 2011, …, 2024 (so `year == 12` means 2020 — never treat it as a calendar number).
- Weights: `weight_wave` (use for a single-wave estimate; mean 1.000, range 0.06–5.28) and
  `weight_aggregate` (use when pooling waves; mean 0.945). No strata/PSU columns.
- Redistribution is prohibited by YPCCC terms (README) — never ship rows in a public deposit.

### 2.2 Mapping CCAM onto target outcomes

| target outcome | closest CCAM variable(s) | CCAM scale | fit |
|---|---|---|---|
| `belief_post` ("Human activities are causing climate change", 0–100 accuracy) | `happening` (1 No / 2 DK / 3 Yes); `cause_recoded` (human vs natural causes); `sci_consensus` (4 levels, "Most scientists think global warming is happening") | 2–4 categorical | **partial.** `cause_recoded` matches the *content* (human causation) but is a forced choice, not a 0–100 accuracy rating |
| `concern_mean` | `worry` (1 Not at all worried … 4 Very worried); plus `harm_personally`, `harm_US`, `harm_future_gen`, `harm_plants_animals` (1 Not at all … 4 A great deal, 0 = DK) | 4-point | **good content fit, wrong granularity.** Target `concern_1..3` are 0–100 sliders (concern / seriousness / relative importance). `priority` (1 Low … 4 Very high) is the twin of `concern_3` ("relative to other issues") |
| `policy_general` ("US government should do more to reduce global warming") | no exact item; nearest are `priority` and `transition_economy` | 4-point | **weak** |
| `policy_specific_mean` | `reg_CO2_pollutant`, `fund_research`, `reduce_tax`, `generate_renewable`, `transition_economy`, `priority_cleanenergy` (all 1 Strongly oppose … 4 Strongly support) | 4-point | **good content fit** for 3 of the target's 7 sub-items (fossil-fuel tax, sustainable energy, forests only loosely) |
| `behavior_mean` | `discuss_GW` (1 Never … 4 Often) only | 4-point | **weak** — matches `behavior_talk` alone |
| `trust_*`, `funding_perceptions`, `inst_trust_*`, `donation_ams`, `newsletter_signup` | **nothing** | — | **CCAM carries no trust-in-scientists item and no institutional-trust battery.** |

### 2.3 Availability by year (non-missing counts, computed on 5 columns only)

```
year  n     happening sci_consensus worry harm_future_gen reg_CO2 fund_res priority transition teach_gw discuss_GW
2008  2164  2164      2164          2164  2164            2164    2164     2164     0          0        2164
2011  2010  2010      2010          2010  2010            1000    2010     2010     0          0        2010
2015  2593  2593      1263          2593  2593            2593    2593     2593     0          0        2593
2020  2065  2065      2065          2065  2065            2065    2065     2065     1036       1036     2065
2023  2044  2044      2044          2044  2044            1011    1011     2044     2044       1033     2044
2024  2044  2044      2044          2044  2044            2044    1013     2044     2044       1013     2044
```
(full 16-row table reproducible with `wave/year/<vars>` only.) Practical points: the core belief /
worry / harm / discuss items are present in **every** wave; `transition_economy` exists only from
2020; `teach_gw` and several policy items are **split-ballot half samples** in many waves (e.g.
`fund_research` n = 1,011 of 2,044 in 2023) — always take the per-wave denominator from the variable,
not from `n`.

### 2.4 What CCAM can and cannot do here

Can: give nationally-representative **US level and trend** for climate belief/worry/policy support,
and the **shape of demographic gaps** (`gender`, `age_category` 3 bands, `educ_category` 4 bands,
`income_category` 3 bands, `race` 5 levels incl. Hispanic, `party_w_leaners`, `ideology`,
`party_x_ideo`) — the only one of my four datasets with **both race and party** on climate content.
Its `race` levels (White NH / Black NH / Other NH / Hispanic / 2+ NH) do **not** contain an Asian
category, so the target's "Asian / Asian American" cell has no CCAM anchor.

Cannot: say anything about (a) trust in scientists, (b) any *treatment effect* — CCAM is
observational cross-sections, so between-wave or between-group differences are **not** ATEs, and
(c) slider distributions — every substantive item is a 2–4 point categorical.

---

## 3. GSS — `/workspace/datasets/gss`

- `/workspace/datasets/gss/downloads/GSS_stata/gss7224_r3a.dta` — **75,699 rows × 6,943 cols**,
  1972–2024 cumulative. Must be read with `encoding='latin1'` (UTF-8 read raises
  `UnicodeDecodeError` on the value labels).
- US adults by design. Weights: `wtssps` (person post-stratification; non-missing **1972–2024**),
  `wtssnrps` (nonresponse-adjusted), `wtssall` (legacy; non-missing only **1972–2018** — do not use
  for the 2021+ web-mode waves). `ballot` marks split-ballot administration; every item below is
  ballot-restricted in some years, hence the sub-sample n's.
- Missing/special values are **string codes inside otherwise numeric columns** (`'i'` iap, `'d'`
  don't know, `'n'` no answer, `'s'` skipped on web, `'y'` not available that year, …), so pyreadstat
  returns `object` dtype. Filter to numeric before anything else.

Trust-in-science items actually present:

| variable | wording (label) | scale | years present | total n |
|---|---|---|---|---|
| `consci` | Confidence in scientific community | **3-point**: 1 a great deal, 2 only some, 3 hardly any (higher = *less* confidence) | 33 years, 1973–2024 (…2016, 2018, 2021, 2022, 2024) | 47,873 (2024: 2,121) |
| `conmedic` | Confidence in medicine | same 3-point | same 33 years | 50,660 |
| `trustsci` | "We trust too much in science" | 5-point, 1 strongly agree … 5 strongly disagree (**reverse-worded**) | 1998, 2008, 2018 only | 3,684 |
| `scibnfts` | Benefits of sci research outweigh harmful results | 3-point (1 benefits greater, 2 about equal [volunteered], 3 harmful greater) | 2006–2018 (7 waves) | 8,203 |
| `natsci` | Supporting scientific research (spending) | 3-point too little / about right / too much | 2002–2024 (12 waves) | 28,756 |
| `natenvir` | Improving & protecting environment (spending) | same 3-point | 34 waves 1973–2024 | 40,790 |
| `scienthe`, `scitest1..5`, `sciimp1..8`, `seeksci`, … | science-attitude / literacy module | mixed | intermittent | — |

Moderators: `sex` (1 male / 2 female — binary only, no "Other"), `age` (raw, 89 = 89+), `race`
(1 white / 2 black / 3 other — **no Hispanic and no Asian category**; `hispanic` is a separate
5-level item present only in later years), `degree` (0 less than HS … 4 graduate — 5 levels, not the
target's 6), `income` (21 bands, nominal dollars, top-coded "$25,000 or more" in the old series;
`coninc`/`realinc` are constant-dollar), `partyid` (0–6 + 7 other → collapses cleanly to the
target's Rep/Dem/Ind/Other), `polviews` (1–7).

**Honest limits of mapping GSS onto a 0–100 slider.** (1) `consci` has **three** ordered categories
and a reversed direction; there is no defensible linear map from a 3-point mean onto a 0–100 slider
mean — the only honest quantity is the *proportion* "a great deal", which is a different statistic
from a slider mean. (2) `consci` asks about "the people running… the scientific community"
(institutional confidence), not about scientists' competence/integrity/benevolence/openness, and not
about **climate** scientists. (3) Mode change: 2021+ waves are largely web/push-to-web, a documented
break in the confidence series. (4) Split ballots mean per-year n is ~half the wave. Net: GSS is
usable as a **direction-and-ordering** prior for demographic gaps in trust (party, education, race
with the 3-level limitation) and as a long-run trend check; it is **not** usable to set the target's
control-condition slider level.

---

## 4. GLIGORIC2025 — `/workspace/datasets/gligoric2025` (the trust-ATE prior)

### 4.1 Files

| file | what |
|---|---|
| `downloads/Main Study/Analyses (data and codes)/dataMainStudy.csv` | **7,800 × 82** microdata |
| `downloads/Main Study/Analyses (data and codes)/R-Code-Markdown.html` | rendered analysis **with all reported estimates** (the numbers below are read from it, not recomputed) |
| `downloads/Main Study/Analyses (data and codes)/R Code Main Study.R`, `R Code Markdown.Rmd` | the analysis code / de-facto codebook |
| `downloads/Main Study/Materials/Materials (word exported from Qualtrics).docx` | **the five message texts, verbatim** (extracted below) |
| `downloads/Main Study/Materials/Qualtrics file.qsf` | full instrument |
| `downloads/Pilot Study 1/IdeologyTrust data.csv` | 3,509 × 1,271, ideology × trust across occupations (warmth/morality/competence batteries) |
| `downloads/Pilot Study 2/Pilot Study 2 data.csv` | **201 × 21** message pre-test: ratings of the 4 candidate messages + 10 named conservatives (`KerryEmanuel`, `MiltonFriedman`, `AynRand`, `ThomasSowell`, `WilliamBuckley`, `HenryKissinger`, `RonaldReagan`, `GeorgeWBush`, `JohnMcCain`, `ArnoldSchwar`) |

### 4.2 Design — read carefully, it is not a general-population messaging trial

- Sample: N = 7,800 US (Prolific-style panel; `Age` mean 41.98, SD 16.10, min 16(!), max 99;
  `Gender` 50.3 % / 49.5 % / 0.2 %; `Education` 6 levels, 6.3 / 28.8 / 14.5 / 26.1 / 3.2 / 21.0 %).
  **Ideology is quota-skewed by design**: `Ideology` 1–10 counts are
  237/187/250/240/196 for liberals (1–5) and 1368/1172/2223/926/1001 for conservatives (6–10) —
  **5,690 conservatives vs 1,110 liberals.**
- **Only conservatives (`Ideology > 5`) were randomized.** `table(Condition, Ideology)` in the HTML
  shows every liberal (Ideology 1–5) sits in Control and zero in any message arm.
  Arm sizes: **Control 2,248** (of which **1,138 conservatives**, 1,110 liberals),
  Co-Benefit 1,095, ConservativeScientists 1,116, Norms 1,116, RespectableConservatives 1,114,
  ValueBased 1,111. Conservative analysis sample = **6,690**.
- Outcome: trust in **35 scientist occupations**, each rated on **two 7-point bipolar items**
  (`<occ>_1` not credible↔credible, `<occ>_2` untrustworthy↔trustworthy), averaged per occupation.
  **Each respondent rated only 4 randomly assigned occupations** (verified: exactly 8 non-missing
  item columns per row; 26,760 obs / 6,690 ids = 4; 8,992 / 2,248 = 4 in control). Climate-relevant
  occupations in the set: `climatologists`, `meteorologists`, `environmental scient`, `ecologists`,
  `oceanographers`.
- Manipulation delivery: the message is **one or two sentences printed above the rating grid on the
  same page** ("This particularly applies to the scientific occupations below…"), not a standalone
  message page. Exposure is minimal and the DV is immediate.
- Manipulation check `BelievabilityExper_1..3` (7-point; item 3 reverse-coded): message means
  4.94–5.01 (SD ≈ 1.19–1.26), 11–14 % below the midpoint. The messages were **believed**; the null
  is not a failed manipulation check.
- No race, no income, no party-ID variable in the file. Moderators available: `Gender`, `Age`,
  `Education` (6 levels, different from the target's 6), `Ideology` (1–10), `PolIdentification` (1–7).

### 4.3 The five message texts (verbatim, from `Materials (word exported from Qualtrics).docx`)

- **Control** — "We ask you to evaluate the scientific occupations below on two attributes. We are
  interested in your view - there are no right or wrong answers."
- **Norms** — "Recent research shows that scientists are among the most trusted professions in the
  US. Various surveys with representative samples in the US found that a majority of conservative
  respondents (over 70%) reported high levels of confidence in scientists. This particularly applies
  to the scientific occupations below…"
- **ConservativeScientists** — "Although there are ideological differences among scientists, many
  scientists in fact consider themselves conservatives. Currently, there are approximately 400 000
  conservative scientists working in the US alone. …"
- **Co-Benefit** — "Many scientists work to develop new jobs and promote technological innovation,
  actively contributing to the economy. In certain countries, it is estimated that scientists
  directly contribute as much as 11% to the Gross Domestic Product each year. …"
- **RespectableConservatives** — "Over the course of the last 75 years, various respected
  conservatives have publicly signaled their trust in scientists. For example, conservative
  politicians such as ${e://Field/Politician} relied heavily on scientists' input on various issues,
  whereas many scientists and intellectuals such as ${e://Field/Intellectual} were conservatives
  themselves. …" (piped from George Bush / Henry Kissinger / William F. Buckley / Ayn Rand, two of
  four shown at random — per the debrief text).
- **ValueBased** — "Many scientists work to preserve the world we live in and protect it against
  various natural and societal threats. They actively engage to conserve the order of the communities
  we love, giving us a sense of security and stability. …"

### 4.4 The reported effects (copied from `R-Code-Markdown.html`, not recomputed)

H3 model: `lmer(Trust ~ (1|id) + (1|Occupation) + Condition)` on conservatives; 26,760 obs, 6,690 ids,
35 occupations. Fixed effects on the raw 1–7 scale, intercept (Control) = **5.146** (SE 0.060):

| arm | raw Δ (1–7 pts) | SE | p | SMD | 95 % CI (SMD) | TOST p (|d|<0.1) |
|---|---|---|---|---|---|---|
| Co-Benefit | **−0.0135** | 0.0497 | .786 | −0.009 | [−0.076, 0.057] | .004 |
| ConservativeScientists | **+0.0131** | 0.0495 | .791 | 0.009 | [−0.057, 0.075] | .004 |
| Norms | **+0.0497** | 0.0495 | .315 | 0.034 | [−0.032, 0.100] | .025 |
| RespectableConservatives | **+0.0082** | 0.0495 | .868 | 0.006 | [−0.061, 0.072] | .003 |
| ValueBased | **+0.0178** | 0.0495 | .720 | 0.012 | [−0.054, 0.078] | .005 |

Condition means (emmeans): Control 5.146, Co-Benefit 5.132, ConservativeScientists 5.159,
Norms 5.195, RespectableConservatives 5.154, ValueBased 5.163. Variance components:
id 1.152, Occupation 0.085, residual 0.902 (so between-person SD ≈ 1.07 on a 1–7 scale).

H4 (Condition × strength of political identification, standardized): all five interactions n.s.
(β = 0.006 to 0.045, p = .18–.93); main effect of `PolIdentification` β = 0.095, p = 5.9e-05.
H1 (control arm only, standardized): Ideology → Trust **β = −0.142, 95 % CI [−0.182, −0.102]**,
p < .001 (2,248 ids, 8,992 obs; marginal R² 0.020).
H5 abandoned as flawed; only believability descriptives reported.

### 4.5 What this licenses, and what it does not

Converted to the benchmark's units: a 1–7 scale spans 6 points, so **1 raw point = 16.67 pp**. The
five ATEs are therefore **−0.22, +0.22, +0.83, +0.14, +0.30 pp**, with 95 % CIs on the SMD that
exclude |d| > ~0.08 in every case (TOST against d = 0.1 significant for all five arms).

Licensed:
- A **strong, equivalence-tested prior that a short informational text moves trust in scientists by
  well under 1 pp** on an immediate, same-page, 7-point trust measure — in the sub-population the
  messages were designed for and where the headroom was largest.
- All five effects are **positive-ish but indistinguishable from zero**; the *ordering*
  (Norms > ValueBased > ConservativeScientists ≈ RespectableConservatives > Co-Benefit) is pure
  noise at these SEs and must not be used as a ranking prior.
- Believability ≈ 5/7 means "no effect" cannot be blamed on disbelief; this is evidence for genuine
  attitude stickiness, which is what should be transported.
- A ceiling fact: conservatives' mean trust is already **5.15/7 = 69 pp**, i.e. the headroom argument
  ("conservatives distrust scientists so there is room to move") is weaker than it looks.

**Not** licensed:
- It is **not** a general-population ATE. Liberals and moderates (Ideology 1–5) were never randomized;
  the design cannot estimate an effect for them, and pooling the control arm's liberals into a
  "general sample" ATE would be a comparison of non-randomized groups. Any transport to the target's
  census-quota sample is an assumption, not a finding.
- It is **not** about climate scientists specifically (35 occupations pooled, 4 per respondent;
  climatologists are 1 of 35), and not about the target's four trust dimensions (2 items: credible,
  trustworthy — closest to the *competence* and *integrity* facets; **nothing** on benevolence or
  openness).
- It says nothing about the target's other 12 outcomes — no belief, concern, policy, institutional
  trust, donation or signup measure exists in this study. Transporting "trust ATEs are ~0" to
  `donation_ams` or `policy_specific_mean` is unsupported by this file.
- The messages are weak-dose (one sentence, same page as the DV, no attention-forcing, ~2 min
  survey). The target study's interventions are full messages; a dose argument can move the prior up,
  but nothing in this dataset calibrates by how much.
- Sub-population heterogeneity is bounded, not zero: the H4 interaction CIs still admit |d| up to
  ~0.07 per unit of political identification.

---

## 5. Synthesis — what a control-condition baseline can be anchored on, outcome by outcome

"Anchor" below = a dataset that measures *the same construct in a US adult sample*, from which a
level can be transported after scale bridging. None of these numbers has been computed yet; this is
the sourcing plan, with each limitation named.

| # | target outcome (0–100 unless noted) | best anchor | how | limitation that must be carried |
|---|---|---|---|---|
| 1 | **trust_multidimensional** (PRIMARY) | **TISP US** `TRUST_SCI_*` 12 items, n = 2,559, weight `WEIGHT_CNTRY` | exact item match (11/12); subscale means → mean of 4; (x−1)/4×100 | 5-pt→slider bridge; "scientists"→"climate scientists" referent shift; 2022/23→2026; **SD not transportable** |
| 2 | trust_post ("How much do you trust climate scientists?") | **TISP US** `CLIM_TRUST` (1–5, "trust scientists in your country who work on climate change") | same rescale | single item; "in your country" clause; 5-pt granularity |
| 3 | distrust_post | **no anchor.** No dataset here asks distrust separately | — | must be modelled off trust_post (asymmetry, not 100−trust: distrust items typically sum with trust to < 100) — UNVERIFIED, needs a literature or slider-format source |
| 4 | funding_perceptions (reverse of "too much/too little spending on climate research") | **GSS** `natsci` (support for scientific research spending) and `natenvir` (environment spending), 3-point too little/right/too much, 1973–2024; CCAM `fund_research` (renewables R&D, 4-pt support) | direction + demographic gaps only | 3-point categorical → the target's 0/50/100-anchored slider is a *different* response object; GSS asks about science generally, CCAM about renewables |
| 5 | policy_role_mean | **TISP US** `NORMPERC_integrate/_advocate/_communicate/_involved` (1–5) — verbatim item twins | (x−1)/4×100, mean of 4 | referent "scientists"→"climate scientists"; 5-pt→slider |
| 6 | inst_trust_mean (EPA, NASA, NOAA, universities, federal government) | **weak**: TISP `CLIM_GOV_trustworthy` (government, 1–5) covers one of five; nothing here covers EPA/NASA/NOAA/universities | — | **essentially unanchored in these four datasets.** GSS `confed`, `coneduc`, `consci` are 3-point confidence-in-institutions items and are the only lever; they are institution-*running-people* items, not 0–100 trust sliders |
| 7 | belief_post ("Human activities are causing climate change", accuracy) | **CCAM** `cause_recoded` + `sci_consensus` + `happening`, 2008–2024, `weight_wave` | proportion-based; convert with an external Likert/binary→slider bridge | categorical; CCAM asks *what causes it*, target asks *how accurate is the statement* |
| 8 | concern_mean (concern / seriousness / relative importance) | **CCAM** `worry` (4-pt), `harm_*` (4-pt), `priority` (4-pt, matches concern_3's "relative to other issues") | per-item → composite | 4-point; no slider variance |
| 9 | policy_general ("US government should do more") | **CCAM** `priority`, `transition_economy` (2020+) | closest available | no exact item anywhere in these four |
| 10 | policy_specific_mean (7 items) | **TISP US** `CLIM_POLSUPPORT_*` gives verbatim twins for 5 of 7 (fuel tax, public transport, sustainable energy, forests, food tax); **CCAM** `reg_CO2_pollutant`, `fund_research`, `reduce_tax`, `generate_renewable` for level/trend | TISP for item identity, CCAM for US representativeness | TISP's scale is only **3 points + a "Not applicable" code** — worse than CCAM's 4; green-jobs and clean-water items have no twin |
| 11 | behavior_mean (6 intentions, next 12 months) | **CCAM** `discuss_GW` covers `behavior_talk` only | — | **5 of 6 sub-items unanchored here.** Needs `voelkel2026`/`goldwert2026` |
| 12 | **donation_ams** ($0–10) | **no anchor** in these four datasets | — | no behavioural/incentivized measure exists in TISP, CCAM, GSS or Gligorić. Must come from `goldwert2026` (real donation) — and the $0-10 whole-dollar grid is heavily lumpy (0 and 10 spikes) |
| 13 | **newsletter_signup** (0/1) | **no anchor** in these four datasets | — | same; `goldwert2026`/`bbprime2025` are the only sources with a real signup/petition rate |

Effect-size prior (all 208 intervention × outcome cells): the only trust-specific randomized
evidence here is **Gligorić 2025 → ATEs of −0.22 to +0.83 pp on a 7-point trust measure, all
equivalence-bounded below d = 0.1**, in conservatives only, from a one-sentence dose. CCAM and GSS
are observational and license **no** effect prior at all; TISP is cross-sectional and licenses none
either. Any predicted ATE materially larger than ~1–2 pp on the trust outcomes needs its warrant
from a *different* dataset (the megastudy twins), and that warrant should be recorded.

Demographic-baseline coverage for the six moderators (scoring row: "Demographic baseline RMSE",
control-condition subgroup means):

| moderator | trust outcomes | climate outcomes |
|---|---|---|
| gender | TISP US (Male/Female only; **no "Other" respondents at all**) | CCAM (Male/Female only) |
| age_band | TISP US via raw `DEM_AGE` (exact bands rebuildable) | CCAM only has 3 bands (18-34/35-54/55+) — must use raw `age` |
| race | **none in TISP** → GSS `race` (3 levels, no Hispanic/Asian) for trust; CCAM `race` (5 levels, no Asian) for climate | CCAM (no Asian cell) |
| education | TISP 4 coarse levels (no MA/PhD split) | CCAM `educ` 14 levels → collapsible, but not onto the target's exact 6 |
| income | TISP continuous USD (net, self-reported) | CCAM `income` 21 bands (gross) → the target's 5 bands are constructible |
| party | **none in TISP** (ideology 1–5 only); GSS `partyid` maps cleanly to Rep/Dem/Ind/Other | CCAM `party`/`party_w_leaners` maps cleanly |

The recurring hole: **race × trust and party × trust have no single-source anchor** — TISP has the
trust scale but neither moderator; CCAM and GSS have the moderators but not the scale. Any
`race × condition` or `party × condition` prediction on the trust outcomes is therefore a
*composition* of two datasets (level from TISP, gap shape from GSS/CCAM), and that composition
should be stated as an explicit modelling assumption in `OPEN.md`.

---

## 6. Blinding note

Nothing resembling target-study results was encountered. The one adjacency worth flagging: the
target instrument is a near-verbatim re-host of TISP's trust, NORMPERC and CLIM_POLSUPPORT blocks
(section 0). That is *instrument* overlap read from `/workspace/benchmark/codebook.csv`, which is
part of the released submission template, and from public TISP documentation — no human outcome data
of the target study is involved.
