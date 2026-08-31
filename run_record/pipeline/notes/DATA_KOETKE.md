# DATA — koetke2024, altenmueller2024, schmidbetsch2019 (session 13 reconnaissance + rulings)

Three trust-family datasets mounted for TASK_13. One is carved, two are not. Every number here was
verified against the microdata, the authors' own scripts and the survey documents; nothing is taken
from a README.

## koetke2024 — CARVED as trust practice task #2 (Study 5 only)

Source: `/workspace/datasets/koetke2024/downloads/Study 5/`. Build: `tools/build_koetke.py`
(9 red paths). Adapter `inputs/adapters/koetke2024.json`; derived file
`inputs/derived/koetke2024_study5.csv`; arm texts `inputs/texts/koetke2024_arms.json`.
Pre-registration `runs/_trusttask2/PREREG.md`; verdicts `tools/koetke_verdicts.py`.

* **Design.** n = 679, `IHCondition` in {Control 164, Limits of Methods 174, Limits of Results 178,
  Personal Humility 163}. One blog-interview vignette with "Dr. Sandra Wilson" about her own
  social-media-break experiment; the arms differ in her closing answer (verified: Q1 identical in
  all four, Q2 identical in three with one phrase changed in Limits of Results, Q3 the
  manipulation).
* **Codebook** is the study's own `IHS Study 5 Code for OSF.R`. Two reverse codings are
  load-bearing: `METI_1r = 8 − METI_1`, and `Belief in Research_2/_4` reversed. Skipping the belief
  reversals moves those ATEs by up to 11.78 pp **and flips their sign**.
* **Outcomes carved (9):** `trust_meti` (14 items, 1–7), `trust_expertise` / `trust_integrity` /
  `trust_benevolence` (disjoint subsets of the same 14 — the four trust cells are **nested**, not
  independent), `belief_research` (4 items, 1–7), `perceived_humility` (22 items, 1–5, the paper's
  **manipulation check** — the pre-registration scores the table with and without it), `competence`
  and `warmth` (2 items each, 1–5), `followup_interest` (binary).
  **`Behavior Follow` level 3 is "I don't use social media", not an unsure code** (Yes 234 / No 383
  / level 3 62); the outcome is the share answering Yes among all respondents and the brief says so.
* **Moderators:** `party` from `PO Bin` (Democrat 334 / Republican 266 / Other 72, 7 missing) — the
  first real party moderator on a trust practice task. `Age` 18–81. `Gender` is **free text** and is
  normalised by an explicit table, 8 rows left NaN rather than guessed. `Race` is a multi-select
  string and `Edu` has 8 levels, so neither is target-shaped; both are declared unavailable.
* **Scales are coarse throughout**, so the adapter carries `exclude_from_slope` (finding 69, OPEN
  31). No trust-family multiplier is fitted from it — operator directive, TASK_13.
* **Signal** (covariance-aware, finding 79): full 27-cell ceiling **0.850**, within-outcome
  **0.644**, the 4 trust outcomes alone **0.000 marginal / 0.648 within-outcome**.

**Studies 2–4: NOT CARVABLE.** Checked directly in the survey `.docx` files: the condition blocks
contain **no stimulus text at all** — the vignettes are embedded screenshots and the blocks hold
only labels (`IH Condition`, `High IH / Female`). Reconstructing them would mean writing the
stimulus myself, and finding 65 measured what a paraphrased/abbreviated stimulus costs (ρ −0.408
when item wordings are deleted). Study 1 is correlational.

## altenmueller2024 — NOT carved; used as the party-moderation reference (session 13, TASK_13 item 2)

Source: `/workspace/datasets/altenmueller2024/downloads/Data & Code/`. Read with
`tools/party_moderation.py`, which reproduces the authors' exclusion rules exactly (Study 1
n = **199**, Study 4b n = **495** after dropping the exploratory interdisciplinary arm — both match
the paper).

* **Study 1** (`rawdata_study1.csv`, drop first 8 rows, keep `attention_check == 1`): institute
  described as politically **liberal** vs **conservative**; DV = 14 METI items, 1–7;
  `conservative = mean(pol_orientation, pol_preference)`. Party interaction on trust:
  **−46.45 pp (SE 5.48)** at a median split — the largest moderation effect this harness has
  measured anywhere. Split-half r **+0.647** (S/N 4.67).
* **Study 4b** (`rawdata_study4b.csv`, drop first 7 rows, same filter, drop
  `economic and sociological research institute`): sociological vs economic institute — the same
  identity manipulation done implicitly, through discipline. Interaction **−3.75 pp (SE 2.73)**.
* **Why it is not carved as a practice task.** Its arms are *identity labels* on the scientists, not
  message strategies, so its ATEs are not on the target's footing (the target's 16 arms are
  messages). It is a **reference**, not a task. Study 4b would nonetheless make a defensible 2-arm
  task if the harness ever wants a fold that separates "trust family" from "arms that differ
  subtly" — it is listed as next direction 2 in session 13's `REPORT.md`.
* Study 2 is correlational (20 disciplines × 0–10 sliders), Study 3 is German and pre-composited,
  Study 5 has no raw data on the OSF.

## schmidbetsch2019 — NOT bought, and the default was declared before looking

`runs/_trusttask2/PREREG.md` §5 fixed the rule: a bridging probe is bought only if it can be stated
in advance what decision it informs. The outcome is the **credibility of one debating advocate**
(McCroskey semantic differentials), not generalized trust in scientists, and no card quantity
depends on it. Default: **do not buy**. Naming the default in advance is what makes this a recorded
decision rather than an omission. If a later session wants it, the honest use is as a *bridge*
between credibility-shaped and trust-shaped outcomes, and it needs its own pre-registration saying
which card number would move.
