# DATA_VOELKEL2026_FORMAT.md — measurements on the design twin

Run `20260815-dryrun-01`, stage `inputs`. Everything here is a full-file computation on
`/workspace/datasets/voelkel2026/downloads/CCC - Data - Recoded.csv` (13,821 x 139), read in this
session. No model calls. Nothing about the target study's human results was sought or encountered;
per the operator's ruling (TASK_02, OPEN §8) voelkel2026 is approved for use and the shared filler
texts are treated as a structural fact about two instruments.

## 1. Adapter corrections (the DRAFT adapter was wrong in two places)

| field | draft said | the data says |
|---|---|---|
| `Gender` | numeric codes 1/2/3 | **strings** `Female` 7,455 / `Male` 6,237 / `Other` 129. The draft map produced all-NaN and `true_ates(..., moderator='gender')` silently returned an EMPTY table. |
| `Race` | "only in the deidentified file; positional join UNVERIFIED" | **present in the recoded file**, codes 1–5, 1 verified as White against `RaceEthnicity_White` (9,806/9,828) and 3 as Hispanic against `RaceEthnicity_Hispanic` (1,240/1,244). Added as a moderator. |

Confirmed as drafted: `Party_N` 1–8 = Strong Dem / Not very strong Dem / Ind-closer-Dem /
Ind-closer-Neither / Ind-closer-Rep / Not very strong Rep / Strong Rep / Other (crosstab against
`PartyC8` labels, exact). `ConditionR` pools the three control texts (3,183) against ten arms of
1,057–1,069. `Education` is a 3-level collapsed string and `Income_B` has no label table anywhere on
disk — both stay unavailable. `Age` = 2024 − YOB runs 18..124; a handful of implausible YOBs land in
the `60+` band.

Adapter status is now VERIFIED. Message texts for all 10 arms plus the three control fillers were
extracted from `CCC - Questionnaire - Qualtrics.pdf` with pypdf into `inputs/texts/voelkel2026_arms.json`.

## 2. Slider heaping — closes OPEN §7

30 PRE (pre-treatment) 0–100 item columns, control arm, n = 3,183 respondents → **95,437 item
responses**. All-arm PRE (414,380 responses) agrees to < 0.4 pp on every statistic.

| statistic | control-arm PRE | orchinik2024 (probability items) | sce (probability items) |
|---|---|---|---|
| multiples of 5 | **41.2%** | 42.5% | 75.3% |
| multiples of 10 | **31.4%** | 32.3% | — |
| at 0 | **5.9%** | 1.8% | — |
| at 50 | **5.2%** | 3.2% | 16.8% |
| at 100 | **11.4%** | 13.7% | — |
| all values integer | 100% | — | — |

Two findings.

1. **The heaping rate transfers.** An attitude slider in a census-quota climate panel heaps almost
   exactly like orchinik's probability sliders (41.2% vs 42.5% on multiples of 5). The authoring
   session's parameters were not wrong.
2. **The midpoint spike is real on attitude items too.** 5.2% at exactly 50, against ~1.3% from
   smooth rounding. The authoring rule — "the 16.8% at 50 is a probability artefact, leave the
   midpoint alone" — was half right: the probability-item spike is 3x bigger, but the attitude-item
   spike is not zero. Hence the new `slider_atoms` parameter.

**Education gradient: nearly absent.** Multiples of 5 by education: HS-or-less 41.2%, Some college
41.9%, Bachelor-or-postgraduate 40.6%. Inverted to mixture weights this is a ~9% relative spread,
not the 25% that sce's probability items implied. `education_gradient` 0.25 → **0.09**.

Per-family item statistics (control-arm PRE) are in `inputs/format_params.json` under
`_evidence.sliders.per_item_family`; they span means 33.8–71.8 and SDs 28.3–34.3, which is the
range the generator was calibrated over.

## 3. How the parameters were fitted

Not algebra — **simulation**. Each of the eight item families was simulated at its measured
control-arm PRE mean/SD through `ssb.synth._draw_composite` (k = 1) and the five parameters were
iterated until the pooled simulated shares matched the measured ones. Result:

| | measured | simulated |
|---|---|---|
| multiples of 5 | 0.4122 | 0.4166 |
| multiples of 10 | 0.3144 | 0.3163 |
| at 0 | 0.0593 | 0.0606 |
| at 50 | 0.0516 | 0.0514 |
| at 100 | 0.1141 | 0.1153 |

Against the pooled real distribution on the 0–100 grid: **OVL 0.840, KS D 0.052, Wasserstein-1 2.07,
variance ratio 0.998**. The residual is under-mass at 1, 49–53 and 99 — humans sit just off the round
numbers slightly more than the generator does.

## 4. Composite levels and spreads (control arm, PRE = unprimed)

| voelkel2026 | mean | SD | n | target outcome it anchors |
|---|---|---|---|---|
| `Belief_Pre` | 65.00 | 22.27 | 3,181 | `belief_post` |
| `Concern_Pre` | 60.24 | 31.28 | 3,180 | `concern_mean` (items verbatim) |
| `Policies_Pre_3` | 65.34 | 33.01 | 3,182 | `policy_general` (verbatim) |
| `PoliciesSp_Pre` | 52.61 | 23.56 | 3,177 | `policy_specific_mean` (4 items vs the target's 7) |
| `IntentNp_Pre` | 54.83 | 22.60 | 3,176 | `behavior_mean` (3 of 6 items verbatim) |
| `Policies_Pre` | 67.59 | 28.98 | 3,182 | — |
| `Intent_Pre` | 33.81 | 27.95 | 3,175 | — |
| `Candidate_Pre` | 34.66 | 21.51 | 3,180 | — |
| `Companies_Pre` | 71.78 | 26.45 | 3,179 | — |

These are the only human-anchored baselines the card currently has for the non-trust sliders.

## 5. Panel composition (used by the profile pool)

| | voelkel2026 (quota panel) | ACS 2018 adults (census) |
|---|---|---|
| gender Other | 0.93% | not measured by ACS |
| race White / Black / Hispanic / Asian / Other | 71.1 / 12.2 / 9.0 / 5.6 / 2.1 | 63.3 / 11.8 / 16.3 / 5.9 / 2.8 |
| education HS-or-less / Some college / BA+ | 29.2 / 33.5 / 37.3 | 38.9 / 30.3 / 30.9 |
| party (ANES branching) D / R / I / Other | 34.1 / 33.0 / 31.2 / 1.8 | (CES pid3: 32.1 / 29.7 / 34.2 / 4.0) |
| age 18-29 / 30-44 / 45-59 / 60+ | 15.1 / 27.0 / 25.6 / 32.3 | 20.3 / 25.4 / 25.3 / 29.0 |

Even a panel that quotas on age/gender/race lands 8 pp light on Hispanic respondents and 5 pp light
on 18-29s — the quota is not enforced exactly. The pool applies the **education** deviation (the one
that is not quota'd and is largest: +6.4 pp BA+) and records the rest; party is taken from CES
because its instrument matches the target's 4-option self-ID item and voelkel2026's does not.
