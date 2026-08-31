# DATA_PEW.md — Pew American Trends Panel W42 / W100 / W114

Recon **and measurement**. Unlike `DATA_baselines.md`, this file *does* carry computed numbers:
that was the point of mounting the dataset. Everything below is survey-weighted, every cell
reports its unweighted n, and every number in this file also lives in
`/workspace/run/inputs/measured/pew_atp_trust.json` (1.4 MB, the machine-readable form —
this note is the human-readable summary and the caveat list).

No *predictor/simulator* calls were made — but the reconnaissance agent that computed these
numbers was itself an Anthropic model (a Claude Code child with file tools), so portions of
the raw `.sav` content it inspected passed through an Anthropic model context (legal
analysis: `docs/legal-review-2026-08-24.md`). Nothing about the sealed target study's human results was sought
or encountered; the only target-study material read was `/workspace/benchmark/codebook.csv`
(instrument metadata: the exact submission levels of the six moderators), quoted in §7.

---

## 0. Headline findings

1. **Party is the dominant cut and it has roughly doubled since 2019.** Confidence in
   "scientists" (Pew's 4-point item, rescaled 0–100, higher = more trust):
   Dem/Lean − Rep/Lean = **+8.5 pp (2019, W42)**, **+21.0 pp (Dec 2021, W100)**,
   **+19.5 pp (Sept 2022, W114)**. On the 4-way `F_PARTY_FINAL` that the target study uses,
   W114 reads Democrat 77.7 / Independent 67.4 / Something-else 62.3 / Republican 56.2.
2. **Race ordering is stable and small next to party**: Asian NH > White NH > Black NH ≈
   Hispanic > Other. W114: 73.2 / 67.2 / 65.8 / 65.3 / 64.1 — a 9.1 pp best-minus-worst
   parity gap against party's 21.6 pp (Dem − Republican). W100 (with the Black/Hispanic
   oversample, so the tightest SEs on the minority cells): 75.7 / 67.6 / 65.4 / 64.5 / 61.2.
3. **Referent shift, the number the harness asked for.** W42 Form 1 rated *medical*,
   *environmental* and *nutrition* research scientists on the same battery, within person.
   Overall the environmental-vs-medical shift is **+0.35 pp (SE 0.57, n = 2,132)** on the
   5-item RQ4 battery — i.e. **zero on average** — but that average hides a
   **11.8 pp partisan interaction (SE 1.09)**: Republicans/leaners rate environmental
   research scientists **6.6 pp below** medical, Democrats/leaners **5.3 pp above**.
   On the single "overall view of this group" item (RQ1) the shift is **−9.6 pp** overall
   and **−22.4 pp among Republicans/leaners** vs −0.6 among Democrats/leaners.
   *The referent shift toward a climate-adjacent scientist is not a level shift; it is a
   fan-out by party.*
4. Chaining the within-person leg to the randomised medical-vs-generic leg gives an implied
   "environmental research scientists" − "scientists" gap of **+0.6 / −0.3 / −1.4 pp**
   (W42 / W100 / W114 second leg, SE ≈ 0.9–1.1). Small, and of ambiguous sign — see §6.4
   for why this chain is weaker than either leg on its own.

---

## 1. Files, shape, weights

| wave | file | rows × cols | fielded | weight column | weight range (mean 1.0) | Kish n_eff (full sample) |
|---|---|---|---|---|---|---|
| W42 | `/workspace/datasets/pew_atp/downloads/w42/ATP_W42.sav` | 4,464 × 200 | Jan 7–21 2019 | `WEIGHT_W42` | 0.105 – 4.679 | 2,596 |
| W100 | `/workspace/datasets/pew_atp/downloads/w100/ATP_W100.sav` | 14,497 × 164 | Nov 30 – Dec 12 2021 | `WEIGHT_W100` | 0.0024 – 6.912 | 6,616 |
| W114 | `/workspace/datasets/pew_atp/downloads/w114/ATP_W114.sav` | 10,588 × 172 | Sept 13–18 2022 | `WEIGHT_W114` | 0.052 – 7.602 | 4,386 |

Read with `pyreadstat.read_sav` under `/opt/kernel/venv/bin/python` (`python`/`python3` are
not on PATH). Codebooks with unweighted frequencies: `ATP_W{42,100,114}_codebook.txt`;
W114 also ships the instrument PDF.

- **W100 oversample caveat.** W100's 14,497 rows are 9,964 ATP panelists **plus a
  4,533-person Black/Hispanic oversample** from Ipsos' KnowledgePanel (README). The ARDA
  distribution carries **no sample-source flag** — nothing in the 164 columns distinguishes
  panel from oversample, so the two cannot be separated or compared. `WEIGHT_W100` has mean
  exactly 1 over all 14,497 rows and is Pew's general-population weight, i.e. it already
  corrects the oversample back to national proportions. Consequence: **W100 weighted
  estimates are nationally representative, but its unweighted n's are badly non-proportional**
  (Black NH 3,042 rows for a weighted 11.6%), and the design effect is large — the Kish
  effective n is 6,616 of 14,497 (46%). Always read `kish_effective_n` next to
  `n_unweighted_valid` in the JSON before treating a W100 cell as precise.
- W114 also carries `WEIGHT_W84_W114` and `WEIGHT_W64_W66_W83_W114` (longitudinal weights for
  panel-conditional analyses). **Not used**; `WEIGHT_W114` is the single-wave weight.
- No PSU/strata variables are distributed with any of the three waves, so the SEs reported here
  are weight-only (see §3).

---

## 2. The confidence item — the one measure all three waves share

Question text, identical across waves: *"How much confidence, if any, do you have in each of
the following to act in the best interests of the public?"*

| wave | "Scientists" | "Medical scientists" | form variable | split |
|---|---|---|---|---|
| W42 | `CONFD_F2_W42` | `CONFD_F1_W42` | `FORM_W42` | Form 2 (2,238) / Form 1 (2,226) |
| W100 | `CONF_G_W100` | `CONF_F_W100` | `FORM_W100` | Forms 2,4 (7,216) / Forms 1,3 (7,281) |
| W114 | `CONF_G_W114` | `CONF_F_W114` | `FORM_W114` | Form 2 (5,277) / Form 1 (5,311) |

**This is a randomised split-ballot, not a skip pattern**: no respondent answers both, so
"scientists" and "medical scientists" are two random halves of the same wave. That is what makes
the medical-vs-generic contrast in §6.3 a clean between-subjects randomised comparison — and it
also means the per-wave n for either referent is ~half the wave.

**Coding (as distributed, all three waves):**
`1 = A great deal of confidence, 2 = A fair amount, 3 = Not too much, 4 = No confidence at all,
99 = Refused` (W114 labels 99 "No answer"). **The raw code runs *downward* in trust.**

**Rescale used everywhere in this note and in the JSON:**

    trust100 = (4 − x) / 3 × 100      # 1→100, 2→66.67, 3→33.33, 4→0 ; higher = MORE trust

`mean_native` in the JSON is the mean of the **raw** 1–4 code (so *lower* = more trust);
`mean_0_100` is the rescaled version (higher = more trust). Do not mix them up.

**Refusals.** Code 99 is dropped from every mean and every distribution and is reported
separately per cell as `n_refused`, `refused_share_unweighted`, `refused_share_weighted`.
On the confidence item refusal is negligible: weighted 0.38% / 0.62% / 0.51% (W42/W100/W114,
"scientists"), 0.15% / 0.43% / 0.25% ("medical scientists"). Refusal on the *cut* variables is
larger and is **kept as its own cell** (`99::Refused`) rather than dropped — e.g. 70 / 255 / 95
party refusals, 60 / 13 / 115 race refusals. Those cells are low-trust outliers
(W114 race-refused = 52.0 pp) and should not be silently pooled anywhere.

**Weighted response distributions, "scientists", valid cases only:**

| wave | great deal | fair amount | not too much | none at all | mean 0–100 (SE) | n unwtd |
|---|---|---|---|---|---|---|
| W42 (2019) | 35.5% | 51.1% | 11.0% | 2.4% | **73.27 (0.69)** | 2,231 |
| W100 (2021) | 28.8% | 48.9% | 16.9% | 5.4% | **67.03 (0.48)** | 7,181 |
| W114 (2022) | 27.9% | 49.2% | 18.3% | 4.6% | **66.80 (0.57)** | 5,259 |

"Medical scientists", same waves: 73.04 / 67.64 / 68.52. Every one of the 4-point cells is in
the JSON at `waves.<w>.items.<COL>.cuts.<cut>.<level>.dist_weighted_valid`.

---

## 3. Standard errors

    SE(weighted mean) = sqrt( Σ wᵢ² (xᵢ − x̄)² ) / Σ wᵢ

the linearised SE of a weighted ratio mean. It captures weight variation but **not** clustering
or stratification, because no PSU/strata variables are distributed. For differences between two
disjoint cells (party groups, the two forms) I report `sqrt(se₁² + se₂²)`; for within-person
contrasts I compute the weighted mean of the paired difference and its own linearised SE, which
is the right (correlation-aware) thing. Every cell also carries `kish_effective_n = (Σw)²/Σw²`;
where that is much below `n_unweighted_valid` (all of W100), the SE is doing real work.

---

## 4. Trust by party

`F_PARTY_FINAL` (1 Republican, 2 Democrat, 3 Independent, 4 Something else, 99 Refused) — the
**same four levels the target study submits**. `PARTY3` in the JSON is my recode of Pew's own
`F_PARTYSUM_FINAL` (1 Rep/Lean Rep, 2 Dem/Lean Dem, 9→3 no lean/DK/Ref); the no-lean cell is
tiny (113 / 276 / 156 valid) because Pew pushes almost every independent to a lean.

**"Scientists", trust100 (SE), unweighted n:**

| level | W42 2019 | W100 2021 | W114 2022 |
|---|---|---|---|
| Republican | 69.96 (1.29) n=570 | 56.13 (0.89) n=1,690 | 56.17 (1.04) n=1,537 |
| Democrat | 78.33 (1.08) n=824 | 78.82 (0.63) n=2,962 | 77.72 (0.93) n=1,722 |
| Independent | 74.60 (1.42) n=551 | 67.68 (0.89) n=1,735 | 67.35 (1.06) n=1,458 |
| Something else | 65.91 (1.96) n=246 | 59.35 (1.66) n=677 | 62.33 (1.84) n=500 |
| Refused | 64.26 (4.85) n=40 | 61.06 (4.99) n=117 | 61.54 (5.39) n=42 |
| **Dem − Rep** | **+8.37 (1.68)** | **+22.69 (1.09)** | **+21.55 (1.39)** |
| Dem/Lean − Rep/Lean | +8.53 (1.41) | +21.00 (0.91) | +19.45 (1.16) |

Two things matter for the harness. (a) The **ordering** Dem > Ind > Something-else ≈ Rep is
identical in all three waves. (b) The **magnitude is not stable in time**: it grew 8 → 22 pp
between Jan 2019 and Dec 2021 and held there through Sept 2022. An anchor taken from W42 is
the *pre-COVID* America; W100/W114 are the post-COVID one. For a 2026 target study, W114 is the
defensible anchor and W42 is a warning about how fast this quantity moves.

Same tables for "medical scientists" are in the JSON; the party gap there is very similar
(W114 Dem/Lean 78.1 vs Rep/Lean 58.9).

---

## 5. Trust by race / ethnicity

| wave | column | levels |
|---|---|---|
| W42 | `F_RACETHN` | White NH, Black NH, Hispanic, **Other**, `9 = Refused` (**no Asian category — Asians fall in "Other"**) |
| W100 | `RACETHNMOD_W100` | White NH, Black NH, Hispanic, Other, **Asian NH**, `99 = Refused` |
| W114 | `F_RACETHNMOD` | White NH, Black NH, Hispanic, Other, **Asian NH**, `99 = Refused` |

Note the refusal code on `F_RACETHN` is **9, not 99** — an easy silent bug.
W100 also ships `RACETHNMOD2_W100` (a Black-multiracial-focused 4-way recode built for that
wave's report); I did not use it, and it is **not** a superset of the five-way variable.

**"Scientists", trust100 (SE), unweighted n:**

| level | W42 2019 | W100 2021 | W114 2022 |
|---|---|---|---|
| White NH | 74.51 (0.84) n=1,439 | 67.56 (0.62) n=3,293 | 67.17 (0.66) n=3,582 |
| Black NH | 70.53 (1.95) n=238 | 64.46 (1.39) n=1,507 | 65.81 (1.81) n=595 |
| Hispanic | 69.52 (1.95) n=366 | 65.39 (1.08) n=1,808 | 65.33 (1.70) n=680 |
| Asian NH | — (in "Other") | 75.70 (2.29) n=192 | 73.17 (2.96) n=184 |
| Other | 76.00 (2.29) n=151 | 61.20 (1.92) n=374 | 64.06 (3.65) n=171 |
| Refused | 66.93 (5.42) n=37 | 29.77 (13.54) n=7 | 51.97 (5.04) n=47 |
| best − worst (excl. refused) | 6.48 | 14.49 | 9.11 |

- **Ordering (both waves that have Asian): Asian NH > White NH > {Black NH, Hispanic} > Other.**
  Black vs Hispanic swap between waves and their difference is within ~1 SE both times — treat
  them as a tie, not as an order.
- W42's "Other" reads *high* (76.0) precisely because it contains Asians; W100/W114 "Other"
  reads *low* (61–64) once Asians are pulled out. **W42's race cut is not comparable to the
  other two and must not be used for the target's 5-level race moderator.**
- The Asian cell is thin even in W100 (192 unweighted, Kish 109) despite the Black/Hispanic
  oversample — the oversample did **not** cover Asians. Its SE (2.3–3.0 pp) is 3–5× the White
  cell's.
- Race spread (9–14 pp best-to-worst, and only 1–3 pp if you drop Asian and Other) is **much
  smaller than the party spread (21 pp)** and, unlike party, does not obviously trend.

---

## 6. Wave 42's research-scientist batteries, and the referent shift

### 6.1 What W42 Form 1 actually asked

`FORM_W42` splits the wave exactly in half and the two halves see **different worlds**:

- **Form 1 (n = 2,226)**: the `RQ*` batteries about *research scientists* — three referents in
  one questionnaire, each respondent answering all three: **medical** (`*_F1A_*`),
  **environmental** (`*_F1B_*`), **nutrition** (`*_F1C_*`) — plus the confidence item about
  **"Medical scientists"** (`CONFD_F1_W42`).
- **Form 2 (n = 2,238)**: the `PQ*` batteries about *practitioners* (medical doctors,
  environmental **health specialists**, dietitians) plus the confidence item about
  **"Scientists"** (`CONFD_F2_W42`).

Verified by crosstab: `RQ1_F1B_W42` is non-missing for exactly the 2,226 Form-1 rows and
`CONFD_F2_W42` for exactly the 2,238 Form-2 rows; the overlap is **zero**.
**Therefore no respondent anywhere in these three waves rates both "environmental research
scientists" and "scientists".** The direct within-person referent shift the harness wanted does
not exist on disk. What exists are two legs, §6.2 and §6.3.

Items and scales (environmental wording shown; medical/nutrition are word-for-word parallel):

| item | wording | response options (raw codes) | 0–100 rescale used |
|---|---|---|---|
| `RQ1_F1B_W42` | "Environmental research scientists conduct research on the environment and how plants, animals and other organisms are affected by it. In general, would you say your view of environmental research scientists is…" | 1 Mostly positive, 2 Mostly negative, 3 Neither, 99 Ref | **codes are not ordinal**: neg 0, neither 50, pos 100 (native mean is on a recode 1 neg / 2 neither / 3 pos) |
| `RQ2_F1B_W42` | "How much, if anything, do you know about what environmental research scientists do?" | 1 A lot, 2 A little, 3 Nothing at all | (3−x)/2×100, higher = knows more |
| `RQ4_F1BA..E_W42` | "Thinking about environmental research scientists, how often would you say they… A do a good job conducting research / B provide fair and accurate information when making statements about their research / C admit mistakes and take responsibility for them / D are transparent about potential conflicts of interest with industry groups in their research / E care about the best interests of the public" | 1 All or most of the time, 2 Some, 3 Only a little, 4 None | (4−x)/3×100, higher = more often |
| `RQ5_F1B_W42` | "Overall, do you think research misconduct by environmental research scientists is…" | 1 A very big problem … 4 Not a problem at all | **(x−1)/3×100 (reversed)**, higher = seen as less of a problem |
| `RQ6_F1B_W42` | misconduct stories are… | 1 Isolated incidents, 2 Signs of a broader problem | 100 / 0 |
| `RQ7_F1B_W42` | which is closer… | 1 "Most … have good intentions, it's the research system that's broken", 2 "The research system can work fine, it's the … scientists that are the problem" | 100 / 0 |
| `RQ8_F1B_W42` | "How often … do you think [they] face serious consequences if they engage in research misconduct?" | 1 All or most … 4 None of the time | (4−x)/3×100 |

The RQ4 A–E block is the closest structural twin on disk to the target's multidimensional trust
battery (competence / integrity / transparency / benevolence). I therefore also report an
**RQ4 A–E composite** = unweighted mean of the five 0–100 item scores, **listwise complete on
all five items for the referent in question** (n = 2,159 environmental, 2,132 for the paired
env-vs-med contrast).

### 6.2 Leg one — environmental vs medical **research scientists**, within person (W42 Form 1)

Weighted, paired, `WEIGHT_W42`. Positive = environmental rated **higher**.

| item | env 0–100 | med 0–100 | env − med (SE) | Rep/Lean (SE) | Dem/Lean (SE) | party interaction (SE) |
|---|---|---|---|---|---|---|
| **RQ4 A–E composite** | **67.16** | **66.78** | **+0.35 (0.57)** | **−6.58 (0.83)** | **+5.25 (0.71)** | **11.83 (1.09)** |
| RQ1 overall view | 71.48 | 81.10 | **−9.63 (1.11)** | −22.44 (1.84) | −0.59 (1.37) | 21.85 (2.29) |
| RQ4A good job | 75.37 | 77.16 | −1.77 (0.70) | | | 10.90 (1.40) |
| RQ4B fair & accurate | 71.37 | 71.99 | −0.54 (0.74) | | | 12.77 (1.43) |
| RQ4C admit mistakes | 57.54 | 55.47 | +2.02 (0.80) | | | 11.07 (1.62) |
| RQ4D transparent re industry | 59.44 | 57.67 | +1.73 (0.82) | | | 10.23 (1.66) |
| RQ4E care about public | 72.10 | 71.63 | +0.47 (0.80) | | | 13.59 (1.56) |
| RQ5 misconduct not a problem | 51.31 | 47.56 | +3.75 (0.81) | | | 8.64 (1.67) |
| RQ8 face consequences | 50.61 | 53.46 | −2.86 (0.76) | | | 8.08 (1.54) |
| RQ2 know about them | 48.59 | 49.60 | −1.05 (0.81) | | | 4.75 (1.63) |
| RQ6 isolated incidents | 57.10 | 57.38 | −0.45 (1.43) | | | 20.46 (2.97) |
| RQ7 good intentions | 67.19 | 68.63 | −1.51 (1.46) | | | 9.73 (2.86) |

("party interaction" = (env−med among Dem/Lean) − (env−med among Rep/Lean), i.e. how much more
the partisan gap opens up when the referent moves from medical to environmental science.
It is **positive on all eleven items**, 4.8–21.9 pp, and ≥ 8 pp on ten of them.)

Levels behind the composite, same respondents, weighted:

| cut | environmental | medical | n unwtd |
|---|---|---|---|
| Republican | 58.99 | 66.23 | 567 |
| Democrat | 74.99 | 69.80 | 776 |
| Independent | 67.89 | 68.16 | 527 |
| Something else | 63.10 | 60.17 | 262 |
| White NH | 67.21 | 68.10 | 1,405 |
| Black NH | 67.52 | 65.44 | 259 |
| Hispanic | 66.68 | 64.15 | 340 |
| Other (incl. Asian) | 67.69 | 63.90 | 132 |
| College grad+ | 70.47 | 71.10 | — |
| HS or less | 63.43 | 63.84 | — |

**The party gap on the same 5-item battery is 2.8 pp for medical research scientists and
14.8 pp for environmental research scientists** (Dem/Lean − Rep/Lean), within the same
respondents on the same scale. Race, by contrast, barely moves the referent shift: env−med is
−0.8 pp for White NH and +2.2 / +2.3 / +3.4 pp for Black NH / Hispanic / Other, a 3–4 pp spread
against party's 11.8.

Nutrition research scientists sit lowest of the three (composite 63.06; env − nut = +4.09,
SE 0.57), so the ordering within Form 1 is environmental ≈ medical > nutrition on the battery,
but medical ≫ environmental on the single "overall view" item.

### 6.3 Leg two — "medical scientists" vs "scientists", randomised between forms

Confidence item, trust100, positive = **medical** higher:

| wave | medical (n) | scientists (n) | medical − scientists (SE) |
|---|---|---|---|
| W42 | 73.04 (2,222) | 73.27 (2,231) | −0.23 (0.98) |
| W100 | 67.64 (7,254) | 67.03 (7,181) | +0.61 (0.68) |
| W114 | 68.52 (5,297) | 66.80 (5,259) | **+1.73 (0.80)** |

By party (W114): Rep/Lean +2.08 (1.17), Dem/Lean +1.82 (1.03) — **no partisan interaction
here**, unlike leg one. By race (W114): Asian NH +7.52 (3.76) is the only cell above 3.2 pp and
it is one thin cell. So: **narrowing "scientists" to "medical scientists" is worth ~0–2 pp of
level and no fan-out; narrowing to "environmental research scientists" is worth ~0 pp of level
and a ~12 pp fan-out.** That asymmetry is the finding.

### 6.4 The chain, and why to distrust it

`(env − med, within person, RQ4 composite) − (med − generic, between form, CONF item)`:

| second leg from | implied environmental − "scientists" | SE |
|---|---|---|
| W42 | +0.58 | 1.14 |
| W100 | −0.26 | 0.89 |
| W114 | −1.38 | 0.98 |

**The two legs use different items** (a five-item 4-point frequency battery vs a single 4-point
confidence item), so the chain assumes a referent contrast expressed in pp of scale range
transfers between the two formats. It is an order-of-magnitude bridge, not a point estimate.
What survives the format worry is the sign and size class: **the overall level shift from
"scientists" to a climate-adjacent scientist referent is within ±1.5 pp of zero, while the
partisan fan-out is ~12 pp.** For comparison, standing finding 10 has TISP's within-person
"most scientists" → "most climate scientists" shift at −3.93 pp; the Pew route gives a smaller
and less certain level shift but adds the party interaction TISP could not (TISP has no party
variable at all).

---

## 7. Mapping to the target study's six moderators

Target levels quoted from `/workspace/benchmark/codebook.csv` (instrument metadata).

| target moderator | target levels | Pew column | verdict |
|---|---|---|---|
| party | Republican \| Democrat \| Independent \| Other | `F_PARTY_FINAL` (1/2/3/4, 99 Ref) | **exact 4-level match.** Use `party4`, not the leaner collapse — the target has no leaner question |
| race | White \| Black \| Hispanic \| Asian \| Other | `F_RACETHNMOD` (W114), `RACETHNMOD_W100` | **exact 5-level match in W100/W114.** `F_RACETHN` (W42) is 4-level and folds Asian into Other — unusable for this moderator |
| gender | Male \| Female \| Other | `F_GENDER` (W100/W114: 1 A man, 2 A woman, 3 In some other way), `F_SEX` (W42: Male/Female only) | usable; the "Other" cell is 100 rows in W100 and 93 in W114 (W114 trust100 = 52.7 ± 8.3 — **13 pp below** men/women, but on 44 valid cases) |
| age_band | 18-29 \| 30-44 \| 45-59 \| 60+ | `F_AGECAT` = 18-29 \| **30-49** \| **50-64** \| **65+** | **bands do not align** and no raw age is distributed in any of the three waves. Only the 18-29 band matches. Age is nearly flat anyway (W114 range 64.1–69.5) |
| education | 6 levels, Less-than-HS → Doctorate | `F_EDUCCAT` (3-way, all waves), `F_EDUCCAT2` (6-way, W42 + W114 only, **not W100**) | partial. Pew's 6-way is Less than HS \| HS grad \| Some college no degree \| Associate's \| College grad/some post grad \| Postgraduate: Pew 3+4 → target "Some college or Associate's", Pew 6 → target Master's **and** Doctorate pooled. The **Master's vs Doctorate contrast has no anchor** |
| income | <30k \| 30–55,999 \| 56–99,999 \| 100–167,999 \| 168k+ | `F_INC_SDT1` (9 bands, W100/W114), `F_INCOME` (9 different bands, W42), `F_INC_TIER2`/`F_INCOME_RECODE` (3-way) | partial. Only the "<\$30,000" boundary is shared; the target's \$55,999 / \$99,999 / \$167,999 cuts fall inside Pew bands, so any mapping interpolates. The top target band (\$168k+) is inside Pew's open "\$100,000 or more" |

Gradients on the secondary cuts (W114, "scientists", trust100): education 72.3 (college+) /
66.6 / 62.4 (HS or less) → **9.9 pp**; income 72.7 (upper) / 66.5 / 64.8 (lower) → **7.9 pp**;
gender 67.2 men / 66.8 women → **0.5 pp**; age 69.5 / 66.6 / 64.1 / 67.7 → **5.4 pp, non-monotonic**.
Full nine-band income and six-level education cells for every wave are in the JSON.

---

## 8. What this can and cannot anchor

**The item is a 4-point verbal confidence scale with only four support points.** Its mean lives
on a 0/33.3/66.7/100 lattice, and 77% (W114) to 87% (W42) of Americans pick one of the two
positive options, so almost all of the variance is a single 'great deal' vs 'fair amount' contrast. That drives
everything below.

**Can anchor (in rough order of confidence):**

1. **Orderings.** Dem > Ind > Rep; Asian > White > {Black ≈ Hispanic} > Other; college+ > some
   college > HS or less. These repeat across two or three independent waves with non-overlapping
   SEs and are the most transferable thing here.
2. **Party gap size**, as a *fraction of scale range*: ~20 pp of a 0–100 range in 2021–22,
   ~2.5× the education gap, ~2× the race spread, ~40× the gender gap. A subgroup-offset table
   for the target's `party` moderator that does not make Dem−Rep the largest single contrast in
   the table is contradicted by every wave here.
3. **The direction and size class of the referent shift**, and specifically that it is a
   **party interaction rather than a level shift** (§6.2). This is measured within person on
   identical items and is the single most target-relevant number in the file.
4. **Relative ordering of the confidence targets** (JSON key
   `context_other_confidence_targets_overall_only`, same item, same respondents, overall only).
   W114: medical scientists 68.5 > scientists 66.8 ≈ the military 66.5 > police 60.9 >
   K-12 principals 58.5 > religious leaders 49.6 > journalists 43.8 ≈ business leaders 43.0 >
   elected officials 36.6. Scientists top the list in all three waves (W42 73.3, W100 67.0),
   with the military always within a few points — useful if the target's `inst_trust_*`
   outcomes need a plausible ordering.

**Cannot anchor:**

1. **Levels on a 0–100 slider.** Every level here is a Likert mean rescaled by fiat; standing
   finding 10 already measured a rescaled coarse-Likert mean running ~5 pp high against a slider
   on near-verbatim items, and a **4**-point scale is coarser than the 3-point case measured
   there. Deposit-facing control-condition levels must not be lifted from this file without that
   correction, and the correction is not measurable here.
2. **Variance, spread, or any distributional metric.** A 4-point item has 4 support points; its
   SD (26.8 pp on the rescale) is an artefact of the lattice, not an estimate of a slider SD.
   Nothing in this file may feed the Tier-1 variance-ratio, OVL, KS or Wasserstein rows.
3. **Any treatment effect.** These are observational cross-sections. Between-wave movement
   (73.3 → 67.0 between Jan 2019 and Dec 2021) is history, not an ATE, and the split-ballot
   contrasts are *wording* experiments, not message interventions.
4. **"Climate scientists" specifically.** The nearest referent on disk is *environmental
   research scientists* (2019 wording, framed around plants/animals/organisms), not climate
   scientists. The gap between those two referents is not measurable anywhere in this dataset.
5. **The target's age bands, the Master's/Doctorate split, or exact income bands** (§7).
6. **Anything about the target study's arms, sample or results.** Nothing here touches them.

---

## 9. Caveats hit, in one list

1. `FORM_*` split-ballot on the confidence item — never pool `CONF_F` and `CONF_G`, and always
   halve your expected n.
2. W42 Form 1 vs Form 2 see disjoint batteries; the environmental-scientists battery and the
   generic-scientists confidence item **cannot** be joined within person.
3. `F_RACETHN` (W42) refusal code is **9**; everything else uses **99**.
4. W42 has **no Asian** race category.
5. W100's oversample is invisible in the file and unweighted W100 n's are not proportional;
   Kish n_eff is 46% of rows.
6. `F_PARTYSUM_FINAL` codes no-lean as **9**, not 3 — my `PARTY3` recodes it to 3.
7. `RQ1`'s raw codes are **not ordinal** (1 positive, 2 negative, 3 neither); a naive mean of the
   raw code is meaningless. The JSON stores a native mean on an explicit 1/2/3 recode.
8. `RQ5` is reverse-keyed relative to trust (1 = very big problem) — the JSON's 0–100 map flips it
   and says so in `rescale_to_0_100`.
9. W100 has **no** `F_EDUCCAT2`; only the 3-way education variable.
10. Refusal cells on the cut variables are low-trust outliers and are reported as their own
    cells, never merged.
11. No PSU/strata → SEs are weight-only and mildly optimistic.
12. **License: Pew EULA via ARDA, research use only, no redistribution.** No row from these files
    may ever appear in a Tier-1 deposit or any public artefact. Only aggregates like this note
    and the JSON may leave `downloads/`.
13. The weighted marginals here were **not** cross-checked against Pew's published toplines
    (no network access in this session). They are reproducible from the pinned files by
    `/tmp`-free re-running of the recipe in §10.

---

## 10. The JSON

`/workspace/run/inputs/measured/pew_atp_trust.json`, ~1.4 MB. Top-level keys:

- `source`, `conventions` — provenance, and the refusal / weight / SE / Kish rules as strings.
- `waves.{w42,w100,w114}` — `file`, `n_rows`, `weight` (+ label, mean, min, max, full-sample
  Kish), `cut_variables` (column name, value labels, derivation), and `items.<COLUMN>` with
  `question_text`, `referent`, `form_filter`, `scale_native`, `native_direction`,
  `rescale_to_0_100`, `value_labels_as_distributed`, and
  `cuts.{overall,party4,party3_with_leaners,race,age_band,gender,education3,education6,income9,income3}`.
  Each cut level is keyed `"<code>::<label>"` and holds
  `n_unweighted_asked, n_unweighted_valid, n_refused, refused_share_unweighted,
  refused_share_weighted, weighted_n_valid, kish_effective_n, dist_weighted_valid,
  dist_unweighted_valid, mean_native, se_native, sd_native_weighted, mean_0_100, se_0_100,
  sd_0_100_weighted`.
- `derived.within_person_referent_shift_w42_form1` — per-item levels for all three referents,
  `env_minus_med_within_person` and `env_minus_nut_within_person` (overall / party3 / party4 /
  race), plus `RQ4_A_to_E_composite` with `levels_by_cut`.
- `derived.between_form_medical_vs_generic_confidence` — per wave, overall / party3 / race.
- `derived.chained_environmental_vs_generic_referent_shift` — the §6.4 chain with its assumption
  written into the JSON.
- `context_other_confidence_targets_overall_only` — elected officials, journalists, the military,
  religious leaders, business leaders, K-12 principals, police, overall only.
- `headline_summary` — the §0 numbers, recomputed from the same cells.

Rebuild recipe: `pyreadstat.read_sav` each `.sav`, apply the wave weight, drop code 99 on the
substantive item, rescale `(4−x)/3×100`, and cut by the columns named in §7. No other filter of
any kind was applied — in particular **no listwise deletion across items** except inside the
explicitly-labelled RQ4 composite and the paired contrasts.
