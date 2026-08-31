# DATA_QSF_TEXTS — intervention wordings recovered from the mounted Qualtrics exports

Reconnaissance note for the two datasets whose `inputs/texts/*_arms.json` used to read
"NO intervention text exists on disk" (OPEN item 10). Both now have materials mounted.

Rebuild everything below with:

```
/opt/kernel/venv/bin/python /workspace/run/tools/extract_qsf_texts.py            # writes the two JSONs
/opt/kernel/venv/bin/python /workspace/run/tools/extract_qsf_texts.py --dry-run  # counts only
```

The script prints a coverage report (`existing` / `extracted` / `missing` / `added` /
`empty` / per-arm chars) and **raises** if an arm key in the JSON has no extracted text or
if extraction produces a key that is not already there, so key drift cannot pass silently.

Nothing here is a prediction. All content is verbatim from the QSF files; the only
non-verbatim strings in the outputs are bracketed markers (`[IMAGE]`, `[loop-and-merge …]`,
`[response options: …]`, `[… further options … truncated …]`, `[the same screen content was
repeated on N further pages]`).

---

## 1. How an arm is resolved (both datasets)

Never by matching a block title. Both surveys carry the assignment in the **survey Flow**
(`SurveyElements` → `Element == "FL"`), and the block bodies in the single **BL** element:

* **vlasceanu2024** — one `BlockRandomizer` sets the embedded fields `cond` = 1…12 and
  `condName`; twelve `Branch` nodes then test `cond == N` and their subtree holds that arm's
  block(s). The `condName` values in the flow are the same strings that appear in
  `data_notimers.csv` (verified: `groupby(['cond','condName'])` returns exactly these twelve).
* **bbprime2025** — each intervention QSF has one top-level `BlockRandomizer`; each child
  `Group` is one arm; the arm id is the embedded field `group` (Set 1) or `condition`
  (Set 2), and those values are exactly the `group` codes in the microdata and the keys of
  `inputs/adapters/bbprime2025.json → arms`.

### Rendering rules

| rule | detail |
|---|---|
| HTML | stripped to plain text; `<br>`/`</p>`/`</div>` → newline, `<li>` → `- `, `<style>`/`<script>` removed |
| images | `<img>` → `[IMAGE]` (or `[IMAGE: alt]`); no image content is in the QSF |
| timing | `Timing`/`PageTimer` questions dropped; the standalone page-timer notice "You will be able to advance the page shortly / after at least N minutes have passed" dropped as UI chrome |
| choices | kept as `- ` bullets; matrix scale points as `[response options: a \| b \| …]` |
| long pick lists | > 30 options or > 1500 chars → first 6 plus a count (only the EPA vehicle catalogue hits this) |
| piped text | `${e://Field/…}`, `${q://QID…}`, `${lm://Field/n}` left **verbatim** |
| repeats | a screen byte-identical to an earlier screen in the same arm is printed once, then annotated |
| segment separator | blank line, `---`, blank line between screens |

---

## 2. vlasceanu2024 — `usa_1.qsf` ("USA Climate master survey MSI", 388 KB, 271 SQ elements)

`cond` → `condName` comes from the flow; `data63.xlsx` (what the adapter reads) **renames two
of them**. Ten of the twelve strings are byte-identical across the two files, which forces the
pairing of the remaining two (verified by reading `xl/sharedStrings.xml` out of the xlsx:
it contains `WorkTogetherNorm` and `LetterFutureGen` and no `Identity-…`/`Letter2Future`).

| arm key (adapter / `data63`) | cond | QSF `condName` | block(s) used | chars |
|---|---|---|---|---|
| `Control` | 1 | `Control` | `BL_ehvSF4bV0wjMxXE` “1. Control Distracter” | 1,407 |
| `WorkTogetherNorm` | 2 | `Identity-Social-Norms-Intervention` | `BL_0HrFE2VFMFq0iVg` “2. Identity-Social-Norms-Intervention” | 1,932 |
| `NegativeEmotions` | 3 | `NegativeEmotions` | `BL_0qwAsSewcxQY1AG` “3. Negative-Emotion-Intervention” | 3,866 |
| `SciConsens` | 4 | `SciConsens` | `BL_dj91lgpEnfLpR5k` “4. Scientific Consensus Intervention” | 361 |
| `CollectAction` | 5 | `CollectAction` | `BL_a3OJkQhNk486u5E` “5. Collective Action Intervention_New” | 3,597 |
| `SystemJust` | 6 | `SystemJust` | `BL_8JpZstGJPncoJ0i` “6. System Justification Intervention” | 2,835 |
| `PsychDistance` | 7 | `PsychDistance` | `BL_80S8nR6BxP461YG` “7. Decreasing Psychological Distance Intervention” | 4,357 |
| `PluralIgnorance` | 8 | `PluralIgnorance` | `BL_3fU9UMIQmN8KNRs` “8. Correcting Pluralistic Ignorance Intervention” | 736 |
| `LetterFutureGen` | 9 | `Letter2Future` | `BL_0etEBZItOykfJVs` “9. A Letter to Future GenerationsV2” | 1,820 |
| `DynamicNorm` | 10 | `DynamicNorm` | `BL_3vZ4dLzJQhAsvJ4` “10. Dynamic Social Norms” | 1,169 |
| `FutureSelfCont` | 11 | `FutureSelfCont` | `BL_e58wlb5p6ECAzm6` “11. Future Self-Continuity Intervention” | 1,948 |
| `BindingMoral` | 12 | `BindingMoral` | `BL_50f5X86vqFjVAhM` “12. A Binding Moral Foundations Intervention_v1Globe” | 342 |

**total 24,370 characters across 12 arms; none empty.**

### Ambiguities and decisions

1. **Control is an active distractor**, not a blank: an excerpt of Dickens' *Great
   Expectations* with a "you may be asked about it" framing. Its 1,407 characters are
   stimulus, and they carry no climate content — that is the design.
2. **Control-only measurement blocks excluded.** The flow branches on `cond == 1` a *second*
   time, after the shared outcome blocks, into `BL_bxqPT2San4PU71s` ("1. Control Condition
   IVs", 8 sliders: trust in climate scientists, trust in government, global citizen, …) and
   `BL_0BO54cNtqD1rMxg` ("1. Control Condition IV - terms probing", 9 "willing to act to
   prevent X" wordings). These are *measures asked only of controls*, not stimulus, so the
   script keeps only the first branch per cond value. If a later task wants the extra control
   IVs, they are in those two block ids. (Recorded because it is a real asymmetry: control
   respondents answered ~17 extra items no intervention arm saw.)
3. **Shown to every arm, so not repeated inside any arm string** (block
   `BL_a3HbonDd5tdn3Rc`, "Climate Change Information Overview for all"), immediately before
   the arm block:

   > Throughout this survey, you may be asked to read some information, report your beliefs
   > or behaviors, or even write a small paragraph. Before we begin, we would like to clarify
   > what we mean by "climate change". *Climate change is the phenomenon describing the fact
   > that the world's average temperature has been increasing over the past 150 years and
   > will likely be increasing more in the future.*

   An attention check (`BL_e9zTjxzq8xkHTXU`) follows the intervention for every arm.
4. **Two arms are mostly pictures.** `SciConsens` (361 chars) is one sentence — "Did you know
   that 99% of expert climate scientists agree…" — plus an image and four source citations.
   `WorkTogetherNorm` (1,932 chars) is a *flyer image* whose wording is not in the QSF at all;
   what survives is the framing ("Imagine you are seeing this flyer in your neighborhood"),
   the 20-second forced exposure, and the arm's own 16 mediator sliders, above each of which
   the flyer was re-displayed (hence the "repeated on 15 further pages" annotation).
   **A predictor reading `WorkTogetherNorm` is still reading a label plus a frame, not a
   message.** `BindingMoral` (342 chars) is short but complete.
5. **Arm blocks that mix stimulus and items.** `WorkTogetherNorm` and `NegativeEmotions`
   interleave the arm's own manipulation-check / mediator questions with the stimulus
   (NegativeEmotions asks the same emotion battery before and after its slides). These are
   kept, in flow order, because the participant read them.
6. **Piped text.** `PluralIgnorance` plays the respondent's own estimate back to them
   (`${q://QID268/ChoiceNumericEntryValue/1}% of Americans agree`) before correcting it to
   65%; `PsychDistance` pipes back the local climate impacts the respondent selected. The
   stored string shows the template, not any respondent's screen.
7. **Free-text tasks are prompts only** (`LetterFutureGen`, `FutureSelfCont`, and the closing
   paragraph task of `PsychDistance`). What respondents wrote is not in the QSF.

---

## 3. bbprime2025 — three QSFs in `downloads/materials/`

* `Intervention_Tournament_Intervention_Set_1.qsf` (3.6 MB) — 14 arms.
* `Intervention_Tournament_Intervention_Set_2.qsf` (3.7 MB) — 3 arms (`STPB`,
  `moral_values`, `letter`).
* `Intervention_Tournament_DVs.qsf` (3.7 MB) — **checked and not used.** Its block list is a
  superset (the three exports were forked from one master, so 60+ blocks are duplicated in
  all three), but its *Flow* contains only DV blocks: Intro to DVs → randomised {NYT
  articles, psychological distance, pro-environmental behaviours, self-efficacy} → attention
  check → randomised {concern/risk, petitions, emotions} → attention check → climate
  knowledge → demographics. No intervention is randomised in it. Confirms the parent's
  characterisation.

Each arm is taken from the export whose flow actually randomises it.

| arm key (adapter) | `group` in the data | source | block(s) used | chars |
|---|---|---|---|---|
| `News Comments (Self-Rel)` | `self_relevance` | Set 1 | “News Comments - Self - Intro”; “News Comments - Self” | 2,561 |
| `News Comments (Social-Rel)` | `social_relevance` | Set 1 | “News Comments - Social - Intro”; “News Comments - Social” | 2,565 |
| `Social Norms (Text)` | `norm_text` | Set 1 | “Social Norms - Text - Intro”; “Social Norms - Text” | 4,012 |
| `Social Norms (Quiz)` | `norm_quiz` | Set 1 | “Social Norms - Quiz - Intro”; “Social Norms - Quiz” | 7,443 |
| `Moral Values` | `moral_values` | Set 2 | “Moral Values - Selection”; “Moral Values - Message” | 16,206 |
| `Imagination (Prevention-Self)` | `ES_prevention_self` | Set 1 | “Guided Imagination - Prevention, Self”; “Guided Imagination - Simulation Ratings” | 1,905 |
| `Imagination (Prevention-Other)` | `ES_prevention_other` | Set 1 | “Guided Imagination - Prevention, Other”; “Guided Imagination - Simulation Ratings” | 1,996 |
| `Imagination (Promotion-Self)` | `ES_promotion_self` | Set 1 | “Guided Imagination - Promotion, Self”; “Guided Imagination - Simulation Ratings” | 1,915 |
| `Imagination (Promotion-Other)` | `ES_promotion_other` | Set 1 | “Guided Imagination - Promotion, Other”; “Guided Imagination - Simulation Ratings” | 1,974 |
| `Action Planning (Individual)` | `MCII_individual` | Set 1 | “Action Planning - Individual”; “Action Planning - Imagine”; “Action Planning - Obstacle”; “Action Planning - Review” | 3,654 |
| `Action Planning (Collective)` | `MCII_collective` | Set 1 | “Action Planning - Collective”; “Action Planning - Imagine”; “Action Planning - Obstacle”; “Action Planning - Review” | 4,412 |
| `Letter to Future Gen` | `letter` | Set 2 | “Letter to Future Gen” | 3,118 |
| `Impact Information (Text)` | `impact_text` | Set 1 | “Impact Info - Text - Intro”; “Impact Info - Text” | 2,784 |
| `Impact Information (Quiz)` | `impact_quiz` | Set 1 | “Impact Info - Quiz - Intro”; “Impact Info - Quiz” | 4,514 |
| `Carbon Footprint (General)` | `CF_general` | Set 1 | “Carbon Footprint - General - Feedback” | 2,882 |
| `Carbon Footprint (Personalized)` | `CF_personalized` | Set 1 | “Carbon Footprint - Personalized - Intro”; “Carbon Footprint - Personalized - Vehicle Type”; “Carbon Footprint - Personalized - Auto”; “Carbon Footprint - Personalized - Manual”; “Carbon Footprint - Personalized - Estimate Miles”; “Carbon Footprint - Personalized - Flights”; “Carbon Footprint - Personalized - Diet”; “Carbon Footprint - Personalized - Energy”; “Carbon Footprint - Personalized - Hidden Calc”; “Carbon Footprint - Personalized - Feedback” | 18,772 |
| `Personal Benefits` | `STPB` | Set 2 | “Personal Benefits - Intro”; “Personal Benefits - Task” | 3,292 |

**total 84,005 characters across 17 arms; none empty.**

`control` (n = 850) is the 18th condition and has **no block in any export** — control
participants went straight to the DVs. `inputs/texts/bbprime2025_arms.json` therefore has no
`Control` key, which is correct rather than missing.

### Loop-and-merge: where the content actually lives

Four arms keep their substance in `Payload.Options.LoopingOptions.Static`, **not** in
`QuestionText`. `QuestionText` is a template addressing merge fields as `${lm://Field/n}`.

| block | rows in `Static` | fields/row | `Randomization` | what a participant saw |
|---|---|---|---|---|
| `Social Norms - Text` (`BL_b1OTxOQ2eIqWI7A`) | 24 | 2 (`1` = sentence, `2` = percentage) | `Subset`, `TotalRandSubset` 16 | a random **16 of 24** norm statistics, random order |
| `Social Norms - Quiz` (`BL_9SN2jXNRTAKpvBc`) | 24 (same bank) | 2 | `Subset`, 16 | the same 16, but guessed on a slider first, then corrected |
| `Impact Info - Text` (`BL_8k57YHu44lzQyEK`) | 8 | 3 (`1` = action, `2` = trees, `3` = lbs CO2) | `All` | all **8** carbon-impact facts, random order |
| `Impact Info - Quiz` (`BL_elbPd9A1PNm6f3g`) | 8 (same bank) | 3 | `All` | the same 8, guessed then corrected |
| `News Comments - Self` / `- Social` | 26 | 2 | `Subset`, 5 | a random **5 of 26** NYT headlines |

*Note the parent brief said "the ten norm statistics"; the bank is 24, of which each
participant saw 16.*

**How they were resolved.** For each loop block the script substitutes the row's fields into
the block's question template(s) and renders **iteration 1 as a full page**, then iterations
2…N as **only the lines that differ from iteration 1**, under a header that states the
randomisation. Every bank row is present. Because the loop order is randomised per
respondent, the printed order is the QSF's storage order, not any participant's.

**Exception, for prompt budget:** the two `News Comments` blocks loop over the *same 26 NYT
headline/snippet pairs* that `bbprime2025_arms.json` already stores verbatim under
`_rated_stimuli.news_headlines` (they are also the message-sharing DV stimuli). Iteration 1
is rendered in full and iterations 2–26 are replaced by an explicit pointer to that key.
This is the only place where content was deliberately not repeated; it saves ~21,000
characters across the two arms and loses nothing. The block ids are pinned in the script
(`NYT_LOOP_BLOCKS`).

### A third storage location: QuestionJS

`Moral Values` hides its six moral-value descriptions in **JavaScript**, in neither
`QuestionText` nor `LoopingOptions`: `QID1319461922` carries
`var paragraphs = [{ text: "…", key: "…" }, …]`, shuffles it, writes it into an empty
`<div id="paragraphContainer">`, and stores the shuffled order in the embedded field
`KeyOrder`; the following pick-one question `QID1319461924` then has choice displays that are
literally `"Choice 1"…"Choice 6"`, relabelled at runtime by more JS. The script parses the
`{text:…, key:…}` pairs out of `QuestionJS` and emits them as bullets with an explicit
marker, and replaces the placeholder choice list with a note. A scan of every question in
every arm of all three QSFs found **only this one** question pair with participant-facing
text in JS.

`Moral Values` is also the longest arm (16,206 chars) for a real reason: after the
respondent picks one of six values, they are shown a ~1,600-character tailored message for
that value. All six branches are stored; a respondent read one.

### Other caveats

1. **`Carbon Footprint (Personalized)` (18,772 chars) is mostly instrumentation.** Its ten
   blocks collect car make/model, transmission, fuel, mileage, flights, diet and home energy,
   then a hidden-calculation block, then a feedback screen assembled almost entirely from
   `${e://Field/…}` values (`car_emissions`, `flight_trees`, …). The stored text is the
   template; no respondent saw those literal placeholders. Ten questions are the EPA
   vehicle catalogue as a dropdown (one per model-year band × transmission type,
   1,942–4,665 options each); each is truncated to 6 options plus a count, which is why the
   arm is 19 KB and not the 900 KB it renders to untruncated.
   `Carbon Footprint (General)` (2,882 chars) is the same feedback framing with population
   averages instead, and is fully readable.
2. **Arm flows include shared follow-up blocks, and they are included.** Each of the four
   `Imagination` arms ends with `Guided Imagination - Simulation Ratings`; both
   `Action Planning` arms continue into the shared `Imagine` → `Obstacle` → `Review` blocks
   (which is why they are ~2 KB longer than the Imagination arms). These sit *inside* the
   arm's own randomiser branch, so they are part of that arm's experience, not DV
   contamination. The four Imagination arms are a 2 × 2 (prevention/promotion ×
   self/other) over one shared six-screen script plus the shared ratings block. The
   prevention/promotion contrast is a real content swap (a smog-choked city vs. a green,
   solar-panelled city; character similarity 0.12); the self/other contrast is the *same*
   scenes rewritten in the third person ("Imagine that you are walking…" → "Imagine a
   fictional person who lives in this future city…"; similarity 0.51). Two of the four
   distinctions a predictor must resolve are therefore perspective-only rewrites.
3. **Quiz-vs-text arm pairs are near-identical in content.** `Social Norms (Quiz)` is
   `Social Norms (Text)` plus a guess-then-reveal step (7,443 vs 4,012 chars); the same holds
   for `Impact Information`. The tournament's contrast between them is a *process*
   manipulation, and the extracted texts show that directly.
4. **Free-text tasks are prompts only** (`Letter to Future Gen`, `Moral Values` essay/ad,
   `Action Planning`). Images are `[IMAGE]` markers.
5. `_rated_stimuli` in `bbprime2025_arms.json` is unchanged from the previous version of the
   file and is preserved byte-for-byte by the script.

---

## 4. What this changes for the practice loop

* Both tasks stop being "order 11/17 labels" and become message-reading tasks. The old
  `_note` claim that a predictor sees only condition names is now false for both, and both
  `_note` strings say so while preserving the record of the earlier download.
* **Prompt budget.** vlasceanu2024 adds ~24 KB (~6 K tokens) to a brief; bbprime2025 adds
  ~84 KB (~21 K tokens). If bbprime2025 has to be trimmed, the cheap cuts in order are:
  `Carbon Footprint (Personalized)` (19 KB, mostly a vehicle dropdown and piping),
  `Moral Values` (16 KB, six branches of which a respondent read one), and the second half of
  the `Social Norms (Quiz)` loop (duplicate of the Text bank).
* **Still-blind spots to state in any run report:** `WorkTogetherNorm` and `SciConsens`
  (vlasceanu) are carried by images that do not exist on disk, and
  `Carbon Footprint (Personalized)` (bbprime) is carried by per-respondent numbers that do
  not exist on disk. Predicting those three arms is closer to label-reading than the
  character counts suggest.
