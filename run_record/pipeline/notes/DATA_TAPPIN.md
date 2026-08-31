# DATA_TAPPIN — tappin2023 as practice task 6

Session 10. Everything here is a description of human data already on disk plus the checks the
builder runs; no model call is involved and no prediction appears.

## 1. Paths

| what | path |
|---|---|
| source microdata | `/workspace/datasets/tappin2023/downloads/replication_materials/data/data_RM.rds` (126,264 x 46) |
| codebook | `.../data/codebook.xlsx` (46 rows) |
| **verbatim messages** | `/workspace/datasets/tappin2023/downloads/supplementary_information.pdf`, Supplementary Table 1 — the ONLY copy |
| plain conversion | `runs/_scratch/tappin_RM.csv` (Rscript `readRDS` -> csv; not an input) |
| **derived analysis file** | `inputs/derived/tappin2023_cells.csv` (25,181 x 23) — built by `tools/build_tappin.py` |
| extracted messages | `inputs/texts/tappin2023_arms.json` (48) + `..._provenance.json` |
| composed arm texts | `inputs/texts/tappin2023_brief_arms.json` (48 + Control) |
| adapter | `inputs/adapters/tappin2023.json` |

`pyreadr` is absent from `/opt/kernel/venv`; R **is** installed, so the conversion goes through
`Rscript -e 'readRDS(...); write.csv(...)'`. `pypdf` was installed into the project venv for the
SI extraction.

## 2. The arm derivation, and the two red paths that check it

There is no 48-level message id. Each respondent saw, for each of their 5 issues, the message
that argues AGAINST their own party leader's position, so

    arm = item (1-24) x direction, direction = opposite of `biden` (Democrats) / `trump` (Republicans)

which yields exactly 48 arms and makes every arm's readers one party. `tools/build_tappin.py`
refuses to write the derived file unless both of these hold on the data itself:

1. **`likertAgree_recoded` is reproduced from the in-party leader's stance at 1.000**, and at
   **0.169** if the two leader columns are swapped. The codebook documents that column as
   "1 = strongly disagree with in-party leader", so reproducing it fixes the party -> leader
   mapping exactly, and the swapped fit shows the check is diagnostic rather than vacuous.
2. **The direction-signed ATE is +4.88 pp with 40 of 48 arms moving in the argued direction**;
   flipping the assumed direction gives -4.88 pp and 8 of 48. A derivation that is backwards would
   have every message pushing readers away from what it argues, on 24 of 24 issues.

## 3. The carve (96 cells)

* **48 arms**, n_treat 94-171, n_control 92-167, matching the README's per-arm cell sizes.
* **Two outcomes**, both the same 7-point agreement item, split by cue block:
  `agree_nocue` (Info-only vs Control) and `agree_leader_cue` (Both vs Cue-only). The second is the
  message's effect on top of a cue saying the reader's own party leader takes the opposite view.
* **Stratum-matched control.** The 48 arms argue about 24 different policies, so a pooled control
  mean is nobody's counterfactual. `ssb.task.true_ates` gained one optional key,
  `control_strata`, which differences each arm against the control rows sharing its
  issue x direction cell. Absent (tasks 1-5) the behaviour is unchanged.
* **Power** (`tools/task_power.py`, no model call): `agree_nocue` var_signal 25.98, ceiling on r
  **0.801**; `agree_leader_cue` var_signal 34.24, ceiling **0.834**; pooled 96 cells, ceiling
  **0.817** — inside the 0.681-0.931 band of the five tasks already carved.
* The two outcomes correlate **+0.750** across arms, so the second is not a copy of the first.
* Prompt size: **15,141 tiktoken tokens, one part, nothing truncated** (longest arm 1,347 chars
  against the 12,000 cap). The target's prompt is 9,892.

## 4. What this task is worth, and its known weaknesses

* It is the first practice task where **the message direction varies**: 24 arms argue for their
  policy and 24 against, so the all-positive baseline is wrong on half the table by construction
  and directional agreement measures something (standing finding 4's situation, generalised).
* Its own headline reproduces from the carve: the persuasive effect is **+4.88 pp with no cue and
  +5.47 pp when the reader's own party leader is quoted taking the opposite side**.
* **Party is confounded with the arm by design** — an arm's readers are all of one party — so no
  condition x party interaction is estimable within an arm. Recorded in the adapter under
  `moderators_unavailable`.
* Each respondent contributes up to 5 issue rows; SEs treat rows as independent, the same
  convention the other adapters use.
* **The outcome is a 7-point Likert item, not a slider.** pp are pp of the 1-7 range. Do not
  import a LEVEL from it: the ten-issue comparison against hackenburg2025's sliders in
  `notes/DATA_HACKENBURG.md` finds no constant offset (mean -0.5 pp, range -17.6 to +11.9).
