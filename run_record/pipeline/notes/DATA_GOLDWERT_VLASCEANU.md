# DATA_GOLDWERT_VLASCEANU.md — verification note (child A, adapters stage)

Written by the child agent that built `inputs/adapters/goldwert2026.json`,
`inputs/adapters/vlasceanu2024.json`, `inputs/texts/goldwert2026_arms.json`,
`inputs/texts/vlasceanu2024_arms.json` and `inputs/measured/goldwert2026_format.json`.
No model calls, no git, no writes outside those paths and this file.
Everything below was computed in-session with pandas on the full files; nothing is quoted from
`notes/DATA_experiments.md` without re-checking it against the data.

**Blinding**: nothing I opened describes the target study. The only target-side thing I touched is
`ssb.spec.load()["moderators"]` (level strings from `/workspace/benchmark/codebook.csv`, an
instrument file). No target outcome data was sought or seen. Nothing to report.

---

## 1. goldwert2026 — Climate Advocacy Megastudy

`/workspace/datasets/goldwert2026/downloads/advocacy_data.csv`, 31,324 data rows x 113 cols.

### 1.1 What I checked

| check | result |
|---|---|
| condition variable | `condName`, 18 levels, 1,733–1,745 each — matches the README |
| `Country Of Residence` as a filter | **REJECTED**: populated for only 10,568/31,324 rows (it is a panel-provider column). Recon said "United States for every sampled row" — true of the first 1,500 rows only. Do not filter on it. |
| completion | `Finished == 1` for 22,374/31,324 (71.4%). `Progress` is 100 for 99.5% of finishers and median 80 for the rest — this is genuine dropout, not a coding artefact. |
| **differential attrition** | completion by arm ranges **61.2% (LetterFuture) to 79.5% (HopeAngerNarratives)**; Control is 64.2%, the 3rd-lowest of 18. The long writing/video arms lose the most people. |
| NaN-vs-0 coding | `newsletter`, `letter`, `donation_bin` are coded **0** for people who never reached the question; `petition`, `newsletter1`, `newsletter2`, `donation`, `video` carry real NaN. Verified: `letter` = 54.1% among those who reached the DV block vs 2.4% among those who did not. |
| composite formulas | `newsletter == (newsletter1 or newsletter2)` reproduced exactly (match rate 1.000) against the formula in `Advocacy_Cleaning_main.ipynb`. |
| rename_dict | quoted verbatim from the notebook AND independently confirmed against the Qualtrics block titles inside the .docx (e.g. `Start of Block: 7. Moral Identity Frame` inside `Connecting_to_Ecological_Disruptions.docx` ⇔ `MoralIdentity → EcologicalDisruptions`; `8. External Locus of Control` ⇔ `ExternalLOC → ShiftFocusIndColl`; `3. Call to Action` ⇔ `CallToAction → CoBenefits`; `11. Positive Emotions` ⇔ `PositiveEmotion → CollEfficacyEmoBenefit`; `12. Naturalistic Hope`; `13. Fear Messaging Collective Action`; `14. Anger Consensus Dynamic Norm`). All 18 docx map 1-to-1 onto the 18 `condName` levels. |

### 1.2 The decision that matters: `filters: [{"col":"Finished","eq":1}]`

Without it the outcome columns are mutually inconsistent (see the NaN-vs-0 row above) and an ATE on
`newsletter` or `letter` is a pure attrition artefact: Control has the 3rd-lowest completion rate, so
every arm would look good on a missing-as-zero binary. With it, the conditioning set is uniform
across all 12 outcomes and every core outcome is ≥94% complete (belief_1 99.8%, donation 100%,
petition 100%, newsletter 100%, letter 100%, pol_candidate 94.0%).

It is still **post-treatment conditioning**. These are complier-ish ATEs, not ITT ATEs. That is
written into the adapter's caveats, and it is the reason this dataset should be scored on ordering,
not magnitude.

### 1.3 Carve result

n = 22,374; 18 arms (17 interventions + Control), arm n **1,060–1,385**; 12 outcomes;
**17 x 12 = 204 cells, 0 NaN**, ATE range **−12.59 to +9.17 pp**.
`ssb.task.carve("goldwert2026", ...)` builds `brief/task.json` (17 arms with text) +
`brief/template.csv` (204 rows) + `sealed/truth.csv` + `sealed/manifest.json`.

Per-outcome mean ATE (pp): conversation +4.85, pol_campaign +4.46, donation +3.99,
pol_candidate +3.44, petition +2.31, march +1.99, belief_1 +1.32, newsletter1 +1.09,
newsletter +0.92, policy_1 −0.58, **letter −6.02**.

**`letter` is a dose/fatigue outcome, not a persuasion outcome.** Its per-arm rate tracks
intervention burden almost monotonically (Control 61.6% → IndStructuralChange, the 11,825-char
writing arm, 49.1%), so every arm has a negative letter ATE. I kept it — it is a real measured
behaviour and dropping outcomes whose sign is inconvenient is worse — but the caveat is in the
adapter and the predictor is not told (that hint is not available for the target either).

### 1.4 Moderators

| moderator | column | levels produced | NaN share (of finishers) |
|---|---|---|---|
| gender | `Gender` | Male, Female | 1.3% |
| age_band | `Age` (18–97) | 18-29, 30-44, 45-59, 60+ | 0.9% |
| party | `Party` | Democrat, Republican | **29.2%** |
| education | provider `Education` | all six target levels | **58.5%** |
| income | provider `Household Income` | all five target levels | **65.5%** |

All level strings are byte-identical to `ssb.spec.load()["moderators"]`.

Deliberate omissions, each of which would have required a guess:
- **party `Other` left unmapped.** The item has only Democrat/Republican/Other — there is **no
  Independent option** — and 29% picked `Other`, so this study's `Other` is a mixture of true
  independents and true others, while the target's `Other` is a ~3% residual. Passing it through
  would have put an Independent-flavoured ATE on the target's `Other` label.
- **race left out entirely.** The only race column is the provider's `Race` (41.5% coverage) and it
  has **no Hispanic/Latino level** — Hispanic identity lives in a separate `Hispanic` column. A
  single-column recode would silently classify Hispanic respondents as White/Other, and the adapter
  format cannot express a two-column recode.
- **two income bands left unmapped**: `$50,000-$59,999` straddles the target's $56,000 cut and
  `$150,000-$174,999` straddles $168,000. That dents the income distribution at those two points
  (~13% of the covered subsample) but does not invent a level.
- education/income/race come from provider columns present for only 10,568 of 31,324 rows.

Moderator carves verified working for gender, age_band, party, income (min n_treat 171).

---

## 2. vlasceanu2024 — Global Climate Intervention Tournament (US subsample)

`/workspace/datasets/vlasceanu2024/downloads/data63.xlsx`, sheet `data4joe (1)`,
59,440 rows x 28 cols; `Country == "Usa"` → **8,253** rows, which matches the OSF README exactly.

### 2.1 What I checked

- pandas reads the literal `"NA"` strings as NaN; every outcome column comes back numeric with the
  right support (Belief/Policy 0–100 float, `SHAREcc` ∈ {0,1}, `WEPTcc` integer 0–8, no NaN).
- 12 `condName` levels; US arm n **534–734** (`LetterFutureGen` 534 and `FutureSelfCont` 591 are
  small worldwide too: 4,022 and 4,194 vs ~5,150 for the rest, so this is design, not a US quirk).
- `Gender` takes values 1, 2, 4 only (code 3 "prefer not to say" is already NA); `Edu` 1–4 (5
  already NA); `Income` 1–8 (9 already NA).
- **Item mapping corroborated, not merely assumed.** The analysis file drops the item suffixes, so
  `Policy1..9 → CC_policy_1,2,3,5,6,7,8,9,10` is an inference from column order. It is confirmed by
  the US mean pattern: the three items the codebook calls taxes land on Policy1 (52.9), Policy5
  (58.7) and Policy9 (46.9) — the three lowest-supported — and the two protect-nature items land on
  Policy6 (79.7) and Policy8 (77.3) — the two highest. `Belief1..4 → Belief.in.CC_1,2,4,5` cannot be
  corroborated this way (all four sit at 69.6–71.4) and remains **UNVERIFIED beyond column order**.

### 2.2 Outcome set: 13 items + 2 behaviours, not composites

Item-level, as the recon recommended, for three reasons: (a) composites are **not** pre-computed in
this file and the paper's own index definitions are not on disk, so a hand-built BeliefMean/
PolicyMean would be an unverified estimand; (b) the target scores single items — its `belief_post`
is one item and its `policy_specific_1..7` are single items — so item level is the matching shape;
(c) seven of the target's `policy_specific` items are near-verbatim these Policy items, so the
item-level control means are directly usable as Tier-1 baseline anchors.
`SHAREcc` gets `lo 0, hi 1` (×100 → pp) and `WEPTcc` gets `lo 0, hi 8` (×12.5 → pp), exactly as the
recipe requires; the scaling is done by `true_ates`' `100/(hi-lo)`.

### 2.3 Carve result

n = 8,253; 12 arms; 15 outcomes; **11 x 15 = 165 cells, 0 NaN**, ATE range **−8.56 to +10.53 pp**,
median |ATE| 3.88 pp. Control-arm means: Belief1–4 65.7/67.7/66.3/66.4; Policy1–9
49.9/64.0/60.6/70.3/54.5/77.6/65.7/75.2/42.6; SHAREcc 0.53; WEPTcc 5.05/8.
Every belief, policy and share ATE is positive; **WEPTcc is negative for 9 of 11 arms** (down to
−8.6 pp) — attitudes up, costly effortful behaviour down or flat.

### 2.4 Moderators — only two survive

`gender` (Male / Female / Other, from codes 1/2/4; 0.8% NaN) and `age_band` (0.4% NaN). Level
strings byte-identical to the spec. The other four are in `moderators_unavailable` with the reason:

- **race**: no race or ethnicity item exists anywhere in the 1,107-variable codebook.
- **party**: no party item exists. Only `Politics2_1`/`Politics2_9`, continuous 0–100 ideology.
  Cutting those into Republican/Democrat/Independent would be inventing a coding.
- **education**: `Education.2` is *years of schooling* — `[2] 7-12 (up to high school)` straddles
  "Less than high school" and "High school diploma / GED"; `[3] 13-16` straddles "Some college or
  Associate's" and "Bachelor's"; `[4] >17 years` straddles "Master's / Professional" and
  "Doctorate". **No** target level is recoverable.
- **income**: bands 4 ($25–49,999), 5 ($50–99,999) and 7 ($150–199,999) straddle the target's
  $30,000 / $56,000 / $168,000 cuts, and bands 4+5 hold 50% of the US subsample. Mapping only the
  clean bands would leave the two middle target levels empty.

### 2.5 The limitation that dominates this dataset

**No intervention text is on disk.** Only 4 files were downloaded; the wordings live in OSF folders
that are not mounted. `inputs/texts/vlasceanu2024_arms.json` is therefore `{arm: ""}` plus a
`_note`. A predictor sees 11 bare condition names. Use this task for Tier-1 distribution and
baseline anchoring and for the demographic-baseline row — **not** for message ranking, and do not
read a poor ATE score here as a failure of message comprehension.

---

## 3. Message texts extracted (goldwert2026)

18 .docx read by unzipping and concatenating `w:t` nodes from `word/document.xml` (python-docx
returns nothing for these files; content sits in tables and textboxes). Keys are `condName` labels.
Qualtrics scaffolding (question ids, "Page Break", "Display This Question", response options) is
deliberately **not** stripped — it is the participant-visible page structure.

Lengths (chars, incl. any marker line): IndStructuralChange 11,825 · HopeAngerNarratives 9,483 ·
MispCorrectionRisks 7,789 · EcologicalDisruptions 7,586 · CollEfficacyEmoBenefit 7,585 ·
DynamicAngerNorm 4,903 · BindingMorals 4,681 · SystemJustification 3,839 · ThreatInjustEfficacy
3,821 · GlobalHealthThreat 3,221 · CoBenefits 2,886 · BipartisanEliteCues 2,546 · LetterFuture
2,526 · ShiftFocusIndColl 1,646 · ActivistPerspective 1,402 · GuiltCollResponsibility 1,356 ·
ClimatePolicyLiteracy 1,204 · Control 509.

**7 of 18 arms depend on video that is not on disk** and carry an explicit marker line:
- content is *entirely* video (marker: "content not on disk … everything below is only the
  surrounding on-screen instructions and comprehension items"): `Control`,
  `ClimatePolicyLiteracy`, `ShiftFocusIndColl`, `ActivistPerspective`.
- content is *partly* video: `GlobalHealthThreat`, `CollEfficacyEmoBenefit`, `BipartisanEliteCues`.
Several other arms are writing tasks: the .docx gives the prompt, but the stimulus the participant
produced is their own.

---

## 4. `inputs/measured/goldwert2026_format.json` — closes OPEN.md item 6

Headline numbers, **finishers (`Finished == 1`), CONTROL arm** — the unprimed-baseline anchors:

| quantity | value |
|---|---|
| donation ($0–10), n | 1,116 |
| mean / SD / median | **$4.73 / 3.81 / $5** |
| share at exactly $0 | **29.7%** |
| share at exactly $5 | **28.9%** |
| share at exactly $10 | **23.7%** |
| share at a whole dollar | **99.7%** |
| all other integers $1–$9 combined | 17.7% (each 1.5–3.7%) |
| newsletter1 (single 0/1 signup) | **24.7%** (n 1,114) |
| newsletter2 (single 0/1 signup) | 21.9% (n 1,116) |
| newsletter (either of the two) | 32.1% |
| petition (0/1) | 27.9% |
| letter written (0/1) | 61.6% |
| video share willingness (0/1) | 32.7% (n 851, social-media users only) |

Full file (all 31,324 rows, complete cases), **control arm**: donation mean $4.77, SD 3.79,
0/5/10 shares 29.0% / 29.6% / 23.8%, n 1,212; newsletter1 24.3%, newsletter2 21.8%, petition 27.6%.
Full file, **overall**: donation mean $5.15, SD 3.84, 0/5/10 shares 25.6% / 28.5% / 28.6%, n 23,732.

Three facts for `synth.DEFAULT_HEAPING`:
1. The $0–10 donation is a **three-spike distribution**: ~82% of all mass sits on $0, $5 and $10 in
   the control arm; the seven interior values share the remaining ~18%. A smooth or unimodal
   generator will fail the Distributions rows (OVL, KS D, Wasserstein-1) even with the mean right.
2. It is **integer-valued to 99.7%** even though the instrument here allowed off-integer values —
   the target's `donation_ams` is integers-only by construction, so round hard.
3. A single 0/1 newsletter sign-up sits at **~22–25% in an unprimed control arm**, and asking twice
   only lifts "at least one" to ~32% — the second ask converts about 8 points, so do not treat two
   sign-up items as independent draws (r = 0.54 among respondents who saw both).

Both base rates come from a *paid online panel that had just completed a climate survey*. The
target's respondents are also a paid panel reading a climate message, so the transfer is close, but
this is one study, and the caveat about post-treatment conditioning applies to the arm-level
numbers (it does not affect the control-arm baselines much — control-arm completion is 64.2%, and
the full-file and finishers-only control numbers differ by <1 point on every quantity above).

---

## 5. What I could NOT verify, and what I dropped

| item | status |
|---|---|
| goldwert `belief_1` / `policy_1` item wording | **NOT in the codebook**; only the block name `BeliefandPolicySupport` is known. Kept as outcomes with an honest "wording NOT in the codebook" question string. |
| goldwert preregistered exclusions | Applied upstream per readme.txt + the cleaning notebook; the *counts* are not stored on disk, so the claim "already applied" is taken on trust. |
| goldwert Hispanic coverage | The `Hispanic` column IS populated (18,942 "No…" + ~1,745 "Yes…" + 10,637 NaN), contrary to the recon note's "empty in my 1,500-row sample". Still unusable for the target's race variable, because it is a *separate* column from `Race`. |
| goldwert video stimulus content | Not on disk for 7 arms. Marked in the texts file. |
| vlasceanu `Belief1..4` → codebook item mapping | Inferred from column order; **not corroborable** (all four means are within 1.8 points). |
| vlasceanu preregistered exclusions | The cleaning script is not on disk. None applied beyond the country filter. |
| vlasceanu intervention texts | Do not exist on disk. Written up as `{arm: ""}` + `_note`. |
| **DROPPED goldwert outcomes** | `video` (72.8% coverage), `flyless` (59.5%), `lessbeef` (89.2%), `bank` (81.8%), `donation_bin` (redundant + NaN-as-0), and the four 0–1 composites, which average items with different missingness. |
| **DROPPED goldwert moderators** | race (no Hispanic level in any single column); party `Other`; two straddling income bands. |
| **DROPPED vlasceanu moderators** | race, party, education, income — all four for the reasons in §2.4. |

## 6. One harness limitation I worked around instead of fixing

`ssb.task.true_ates(df, ad, moderator=...)` raises `ValueError: cannot convert float NaN to integer`
whenever any (moderator level × arm × outcome) cell has n ≤ 2: `wm()` returns NaN and `int(an)`
cannot take it. It bites in exactly two places:

- `goldwert2026`, `moderator="education"` — the `Less than high school` level is 66 people over 18
  arms (min 0 per arm) and `Doctorate degree / Ph.D.` is 185 (min 5).
- `vlasceanu2024`, `moderator="gender"` — the `Other` level is 88 people over 12 arms, and the
  `WorkTogetherNorm × Other` cell has n = 2 for `Policy1..9` and `SHAREcc`.

Both mappings are *correct*, so I kept them rather than mutilate the recode to dodge a crash.
Marginal carves and the gender / age_band / party / income (goldwert) and age_band (vlasceanu)
moderator carves all run clean. One-line fix on the harness side if a run needs those two carves:
make `n_treat` / `n_control` nullable (`"n_treat": an`) instead of `int(an)`, or drop levels whose
minimum cell is < 3 before carving. I did not touch `.prime/agent/skills/ssb/src/`.
