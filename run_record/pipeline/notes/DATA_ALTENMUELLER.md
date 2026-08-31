# DATA_ALTENMÜLLER — Altenmüller, Wingen & Schulte (2024), Study 4b

Reconnaissance for carving **Study 4b** as a practice task. Every number below was produced by
running the command shown; nothing is quoted from memory. Where the source is ambiguous it is
marked **UNCERTAIN**.

- Dataset root: `/workspace/datasets/altenmueller2024/`
- Paper: Altenmüller, M. S., Wingen, T., & Schulte, A. (2024). *Explaining Polarized Trust in
  Scientists: A Political Stereotype-Approach.* Science Communication. doi:10.1177/10755470231221770
- OSF: https://osf.io/rvj4q/ · License CC BY 4.0
- Python used: `/opt/kernel/venv/bin/python` (pandas 2.x, scipy 1.17.1, pdfplumber 0.11.10).
  `pdftotext` is **absent** in this container; PDFs were read with `pdfplumber` (see §5).

## 0. Files that matter

| Role | Exact path |
|---|---|
| Raw data | `downloads/Data & Code/Data/rawdata_study4b.csv` |
| Codebook / analysis | `downloads/Data & Code/Analysis Scripts/analysis_study4b.Rmd` |
| Instrument | `downloads/Materials/Qualtrics Survey Study 4b.pdf` (8 pages) |
| Preregistration | `downloads/Preregistrations/Preregistration Study 4b.pdf` (AsPredicted #90072, 2 pages) |
| Supplement | `downloads/SupplementaryInformation.pdf` (12 pages; Table S5 and Fig. S5 are Study 4b) |

`rawdata_study4b.csv`: 288,064 bytes,
sha256 `5dd4f6104cb79fbfc4e4f2081a2d9b7d38f4751ed4c8436338a21bfb886a9217`.

---

## 1. Loading the CSV: header rows, shape, condition labels

**Qualtrics 3-row header, plus 5 experimenter test rows.** Line 1 = variable names, line 2 =
question text, line 3 = `ImportId` JSON. The R script reads with `read.csv` (line 1 becomes the
header) and then deletes **seven** further rows — the 2 remaining header rows *and* 5 test trials:

```r
data_imp<-read.csv(filename, stringsAsFactors = F, na.strings ="")
#delete first seven rows that contain variable names and test trials by the experimenter
data1<-data_imp[-c(1:7),]
```

Verified equivalent in pandas (the two frames compare `.equals()` → `True`):

```python
P = "/workspace/datasets/altenmueller2024/downloads/Data & Code/Data/rawdata_study4b.csv"
raw = pd.read_csv(P, dtype=str, keep_default_na=False, na_values=[""])   # (769, 55) == R data_imp
d1  = raw.iloc[7:]                                                       # (762, 55) == R data1
# one-liner equivalent, checked identical:
alt = pd.read_csv(P, skiprows=[1,2], dtype=str, keep_default_na=False, na_values=[""]).iloc[5:]
```

| Frame | Shape | Meaning |
|---|---|---|
| file | 770 lines | 1 header line + 769 records |
| `raw` / R `data_imp` | **769 × 55** | includes 2 leftover header rows + 5 test rows |
| `d1` / R `data1` | **762 × 55** | real respondents |

The 5 test rows (`raw.iloc[2:7]`) have real `ResponseId`s and a `condition` but **all DV cells
are NaN** — they are experimenter previews, not zero-filled data.

**Condition column: `condition`** (a Qualtrics embedded data field, string). The three EXACT
labels — copy these verbatim, they are lower-case and unpunctuated:

| Arm | Exact string in `condition` | n in `d1` | n after exclusions |
|---|---|---|---|
| sociological | `sociological research institute` | 254 | **245** |
| economic | `economic research institute` | 253 | **250** |
| interdisciplinary (exploratory) | `economic and sociological research institute` | 254 | **246** |
| — | `NaN` | 1 | 0 |

```python
d1.condition.value_counts(dropna=False)
# {'sociological research institute': 254, 'economic and sociological research institute': 254,
#  'economic research institute': 253, nan: 1}
```

`FL_5_DO` is the Qualtrics block randomiser that assigned the arm (`FL_28` 254 / `FL_39` 254 /
`FL_29` 253, 1 NaN) — it is redundant with `condition`; the mapping of `FL_*` codes to arm names
was **not** verified and should not be relied on.

---

## 2. Exclusions — the authors' rule, and the reproduction

The **only** exclusion rule is the preregistered attention check. Quoted from
`analysis_study4b.Rmd`:

```r
#select numeric variables
numeric_variables<-c("competent","intelligent","educated","professional","experienced","qualified",
 "honest", "sincere", "just", "fair","moral", "ethical", "responsible","considerate","similarity",
 "support","information_seeking","attention_check","lawyer","politicized","age","pol_orientation",
 "pol_preference")
#turn into numeric
data2[,c(numeric_variables)] <-data.frame(lapply(data2[,c(numeric_variables)], function(x) as.numeric(x)))
#select only variables that matter for our analyses into final dataframe
data3<-data2[,c("condition",numeric_variables,"gender")]
```

```r
data4<-subset(data3, attention_check == 1)
```

```r
#for main analyses we exclude the exploratory condition, as preregistered
data_ana<-subset(data_ana, condition != "economic and sociological research institute")
```

Prereg wording (AsPredicted #90072, Q6): *"Participants will receive an attention check question:
'If you read this, select "not at all". We will exclude participants who do not choose "not at
all".'"* — and Q4/Q5: the third arm is **exploratory**, all preregistered analyses are
economists vs. sociologists only.

**Two subtleties that a naive carve gets wrong.**
1. R's `subset()` drops rows where the predicate is `NA`, so the 11 respondents with a *missing*
   attention check are excluded too. Pandas `d3[d3.attention_check==1]` does the same; a
   `.query()`/`isin` on a fillna'd column would not.
2. There is **no** filter on `Finished`, `Progress`, `Status` or duration. Do not add one — it
   changes n (see §7).

### Reproduction

```python
numeric_variables = [...as above...]
d2 = d1.copy()
for c in numeric_variables: d2[c] = pd.to_numeric(d2[c], errors="coerce")
d3 = d2[["condition"]+numeric_variables+["gender"]]
d4 = d3[d3.attention_check == 1]                                           # n = 741
d_ana = d4[d4.condition != "economic and sociological research institute"]  # n = 495
```

```
attention_check value counts in d3:  1.0→741, 2.0→2, 4.0→2, 5.0→3, 6.0→3, NaN→11
n excluded = 762 - 741 = 21   (10 wrong answers + 11 missing — matches the Rmd's prose
                               "Ten participants had to be excluded ... but there were also 11 missings")
```

| Frame | n | Per arm |
|---|---|---|
| `data4` (all 3 arms) | **741** ✓ matches README/paper | eco 250 / interdisc 246 / soc 245 |
| `data_ana` (preregistered, 2 arms) | **495** ✓ | eco 250 / soc 245 |

Both targets reproduce **exactly**. The paper's "total controlled N = 2,859" = 199 + 1,000 + 325 +
840 + 495, i.e. Study 4b counted **without** its exploratory arm.

---

## 3. Dependent variables

### 3.1 Storage and conversion — read this first

**Every** variable in the raw CSV is a **string** (`read.csv(..., stringsAsFactors = F)` /
`dtype=str`), because the two leftover header rows put text in every column. All 23 variables in
`numeric_variables` must be cast with `as.numeric` / `pd.to_numeric(..., errors="coerce")`
**after** the 7 rows are dropped. Empty cells are `""` in the file and must be read as NA
(`na.strings=""` in R; `na_values=[""]` in pandas) — otherwise `as.numeric("")` warnings become
silent zeros in a careless port. `condition` and `gender_3_TEXT` stay strings; `gender` is a
string of a digit and is **not** in the R script's numeric list (it is kept as character and only
`table()`d).

Command used for the ranges below:
```python
for c in numeric_variables: print(c, d4[c].min(), d4[c].max(), d4[c].notna().sum(), d4[c].isna().sum())
```

### 3.2 METI — Münsteraner Epistemic Trustworthiness Inventory (Hendriks et al. 2015)

14 bipolar adjective pairs, **7-point semantic differential**, presented as a matrix. Item stem
(page 2 of the survey PDF, bold in the original):

> Please think about the scientists who work at this ${e://Field/condition}. We are now going to ask you
> some questions about these scientists. Please complete the following statements.
>
> **In my view, scientists who work at this research institute are likely to be ...**

`${e://Field/condition}` is piped, so respondents read e.g. "…who work at this **sociological
research institute**."

| CSV column | Left (negative) pole | Right (positive) pole | Composite |
|---|---|---|---|
| `competent` | incompetent | competent | expertise |
| `intelligent` | unintelligent | intelligent | expertise |
| `educated` | poorly educated | well educated | expertise |
| `professional` | unprofessional | professional | expertise |
| `experienced` | inexperienced | experienced | expertise |
| `qualified` | unqualified | qualified | expertise |
| `honest` | dishonest | honest | morality |
| `sincere` | insincere | sincere | morality |
| `just` | unjust | just | morality |
| `fair` | unfair | fair | morality |
| `moral` | immoral | moral | morality |
| `ethical` | unethical | ethical | morality |
| `responsible` | irresponsible | responsible | morality |
| `considerate` | inconsiderate | considerate | morality |

**Scale: 1–7, 1 = negative pole, 7 = positive pole. Higher = more trust.**
The survey PDF prints only the two anchor labels, no numerals (pages 3–5); the 7-point claim comes
from the preregistration (*"14 opposite adjective pairs … on a 7-point scale"*) and from the
observed data, which take integer values 1–7 on every item (`competent` min 2, `experienced`
min 2; all others span 1–7).

**No item is reverse-scored.** All 14 are printed with the negative pole on the left, and the R
script applies no recodes before averaging. Corroborated by the correlation matrix: all 91
inter-item correlations are positive (min .411, max .808, n = 741); Cronbach α (n = 741) =
**.944** expertise, **.954** morality, **.960** all 14.

Compositing, quoted from the Rmd:

```r
#average trust (two factors, see below)
data5$expertise<-rowMeans(data5[,c("competent","intelligent","educated","professional","experienced","qualified")])
data5$moralTrust<-rowMeans(data5[,c("honest", "sincere", "just", "fair","moral", "ethical","responsible","considerate")])
```

`rowMeans` defaults to `na.rm = FALSE`, so **a single missing item makes the composite NA**. In
pandas that is `.mean(axis=1, skipna=False)` — the pandas default (`skipna=True`) is wrong here
and would silently change n. There is exactly one such case: `experienced` has 1 NA in n=741, so
`expertise` has 1 NA (n = 740 of 741; 494 of 495 in `data_ana`). All other METI items are complete.

The authors chose the 2-factor solution deliberately (CFA in the Rmd: 2 factors fit better than 1;
3 factors — expertise / benevolence / integrity — not better than 2). **They never composite all
14 into one score**; if a carve wants a single "trust" outcome that is the harness's choice, not
the authors', and should be labelled as such.

### 3.3 Single-item DVs

All three are **1–7, anchored 1 = "Not at all", 7 = "Completely"** (survey PDF pages 5–6;
preregistration Q3). All numeric-in-string, complete (0 NA in n=741), higher = more.

| CSV column | Exact item wording (survey PDF / CSV header row 2) |
|---|---|
| `support` | *How much do you think would you support such a policy?* |
| `information_seeking` | *How much would you be interested in learning about further findings and suggestions from these researchers?* |
| `similarity` | *In terms of my own political and ideological views, I feel similar to these scientists.* |

`support` is preceded by a per-arm policy preamble (§5.2). **The policy itself is never specified
in Study 4b** — it is "a new policy … suggesting that this policy would have positive consequences
for society". (Study 4a, by contrast, names two concrete policies and counterbalances them. Do not
carry 4a's design over.)

`similarity` is the mediator in the authors' models, not a primary DV; the preregistration words
it "…I feel similar to **this group**", the fielded item says "…these scientists". Fielded wording
governs.

### 3.4 Attention check and the two collaborator items

| Column | Wording | Scale | Note |
|---|---|---|---|
| `attention_check` | *If you read this, select "Not at all".* | 1–7, anchors "Not at all" … "Very much" | correct answer = **1**; the exclusion rule |
| `politicized` | *Since science has been politicized by the left, conservatives can no longer trust it.* | **1–5** (Strongly disagree / Disagree / Neither agree nor disagree / Agree / Strongly agree) | collected for an external collaborator; prereg says it will **not** be analysed; 1 NA |
| `lawyer` | *Scientists reason more like a lawyer defending a particular position than a dispassionate scientist searching for the truth.* | **1–5**, same anchors | same; 1 NA |

`politicized` and `lawyer` are the only 5-point items in the file — a carve that assumes a uniform
1–7 range across all items will mis-scale them (pp of scale range differs).

---

## 4. Politics and demographics

```r
#avaraged political orientation
data5$conservative<-rowMeans(data5[,c("pol_orientation","pol_preference")])
#centered variable
data5$conser_cent<-scale(data5$conservative, center = T, scale = F)
```

| Column | Item | Scale, direction |
|---|---|---|
| `pol_orientation` | *What is your political orientation?* | 1–7, **1 = Very liberal → 7 = Very conservative** |
| `pol_preference` | *What is your political preference?* | 1–7, **1 = Strongly prefer Democrats → 7 = Strongly prefer Republicans** |
| `conservative` (derived) | mean of the two | 1–7, **higher = more conservative** |
| `conser_cent` (derived) | `conservative` grand-mean centred (not scaled) | mean of `data_ana` = 3.3986 |

Direction confirmed three ways: the survey PDF prints "Very liberal … Very conservative" and
"Strongly prefer Democrats … Strongly prefer Republicans" left-to-right (page 7); the derived
variable is named `conservative`; and SI Table S5's note reads *"political orientation: 1 = very
liberal, 7 = very conservative"*.

⚠ **The preregistration lists the endpoints in the opposite order** (*"ranging from 'very
conservative' to 'very liberal'"*, *"from 'strongly prefer Republicans' to 'strongly prefer
Democrats'"*). This is a **drafting error in the prereg**, not a coding to honour — the fielded
instrument, the script and the SI all agree on 1 = liberal. Verified: `cor(conservative,
moralTrust)` is **negative** in the sociological arm (r = −0.203), which is the paper's direction
(conservatives trust sociologists less).

`cor.test(data_all$pol_orientation, data_all$pol_preference)` → **r = 0.8558, n = 739**, above the
prereg's r > .7 threshold for averaging, so the composite is licensed.

Descriptives in `data_ana`: `conservative` M = 3.399, SD = 1.746, n = 493 (2 NA);
140 of 495 are above the scale midpoint (`conservative > 4`).

### Demographics — there are only two

| Column | Coding | Notes |
|---|---|---|
| `age` | integer years, free text→numeric. `data_ana`: n = 493, M = 40.44, SD = 13.22, range 18–84 | 2 NA |
| `gender` | **1 = Female, 2 = Male, 3 = Prefer to self-identify** (survey PDF page 7, choice order) | string in CSV, not cast by the script; `data_ana`: 259 / 229 / 5, 2 NA |
| `gender_3_TEXT` | free text for gender 3 | 4 non-null values in `d1`: `Transgender Female`, `non-binary`, `non-binary`, `nonbinary` |

⚠ **There is no education, no income, no race/ethnicity, no region, no party-ID-as-category
variable in Study 4b.** The prereg says only *"demographic variables (age and gender) to describe
our sample"*. Any moderator beyond {age, gender, continuous conservatism} is **not carvable** from
this study.

⚠ **Gender-coding discrepancy in the authors' own script.** The descriptives chunk reads:
```r
# 1 = women
table(data_ana$gender)
229/(259+229+5)
```
The comment says 1 = women, but 229 is the count of `gender == 2`. Under the survey's choice order
(Female first) the proportion of women in `data_ana` is 259/493 = **52.5%**, not the 46.5% the
script computes. Either the comment or the arithmetic is wrong; the survey PDF is the only
primary evidence and it puts **Female first**. Treat any published "% women" for Study 4b as
**UNCERTAIN** and use the PDF ordering for a carve.

---

## 5. Verbatim stimuli

**Extraction method.** `pdftotext` is not installed in this container. Used:

```bash
/opt/kernel/venv/bin/python -m pip install pdfplumber      # 0.11.10
/opt/kernel/venv/bin/python -c "
import pdfplumber
pdf = pdfplumber.open('/workspace/datasets/altenmueller2024/downloads/Materials/Qualtrics Survey Study 4b.pdf')
print(pdf.pages[1].extract_text())   # page 2: the three vignettes
print(pdf.pages[4].extract_text())   # page 5: the three policy preambles
"
```
Bold face was recovered separately by grouping `page.chars` on `'Bold' in c['fontname']`
(fonts on page 2: `TSHXOT+ArialMT` regular, `RCSSFG+Arial-BoldMT` / `TRKJGN+Arial-BoldMT` bold).
Line breaks below are the PDF's; the fielded Qualtrics text was a single flowing paragraph.
Extraction was clean — no ligature or hyphenation damage, and every word is a common English word;
**no word in these vignettes is uncertain.**

### 5.1 The manipulation (survey PDF pages 1–2)

Shown to every arm before the vignette (block "Intro Politics Manipulation"):

> In this study, we are interested in how you perceive a specific group of people. Thus, in the following,
> we describe such a group and are interested in your opinion about this group. We would like you to
> thoroughly read the short description of this group first.

Then, immediately above each vignette:

> Please read the description below carefully. **You will be asked a couple of questions about this
> text.**

**Arm 1 — sociological** (`condition == "sociological research institute"`), Qualtrics block
"Sociologists Manipulation":

> Please imagine you come across a report by scientists from a specific research institute. Imagine that
> you recognize the name of this institute and remember that **this institute is an institute for
> sociological research and that all researchers working at that institute are sociologists.** Their
> research topics are sociological and they use sociological theories and methods. In the present report,
> new findings from a research project by these sociologists are presented.

**Arm 2 — economic** (`condition == "economic research institute"`), block "Economists Manipulation":

> Please imagine you come across a report by scientists from a specific research institute. Imagine that
> you recognize the name of this institute and remember that **this institute is an institute for
> economic research and that all researchers working at that institute are economists.** Their
> research topics are economic and they use economic theories and methods. In the present report, new
> findings from a research project by these economists are presented.

**Arm 3 — interdisciplinary, exploratory** (`condition == "economic and sociological research
institute"`), block "Interdisciplinary Manipulation":

> Please imagine you come across a report by scientists from a specific research institute. Imagine that
> you recognize the name of this institute and remember that **this institute is an institute for
> economic and sociological research. All researchers working at that institute are either
> economists or sociologists.** Their research topics are economic and sociological and they use
> economic and sociological theories and methods. In the present report, new findings from a research
> project by these researchers are presented.

**What differs between arms.** The frame is identical word-for-word; only the discipline words
change. Bold in the source marks (roughly) the manipulated clause, and the bold spans differ
slightly between arms as rendered.

| Slot | sociological | economic | interdisciplinary |
|---|---|---|---|
| "an institute for **___** research" | sociological | economic | economic and sociological |
| "all researchers … are **___**" | sociologists | economists | *"All researchers working at that institute are **either economists or sociologists**"* (new sentence — the interdisciplinary arm splits "Their…" off, so its clause structure is **not** a pure word swap) |
| "Their research topics are **___**" | sociological | economic | economic and sociological |
| "they use **___** theories and methods" | sociological | economic | economic and sociological |
| "findings … by these **___** are presented" | sociologists | economists | researchers |

The interdisciplinary arm is also **7 words longer** than the other two and changes sentence
boundaries, so it is not length-matched. The soc and eco arms **are** exact length twins (one word
swapped per slot). Word counts (whitespace split, verified on the extracted text): sociological 71,
economic 71, interdisciplinary 78 (chars 471 / 455 / 522).

### 5.2 Policy-support preamble (survey PDF page 5)

Piped per arm, immediately before the `support` item. Bold as in the source:

- interdisciplinary: **Please imagine that researchers from this institute for economic and sociological research suggest a new policy.** This policy results from economic and sociological research and theorizing, suggesting that this policy would have positive consequences for society.
- sociological: **Please imagine that researchers from this institute for sociological research suggest a new policy.** This policy results from sociological research and theorizing, suggesting that this policy would have positive consequences for society.
- economic: **Please imagine that researchers from this institute for economic research suggest a new policy.** This policy results from economic research and theorizing, suggesting that this policy would have positive consequences for society.

### 5.3 Preamble to the similarity item (page 6)

> Please think about the scientists who work at the research institute you just imagined.

---

## 6. Numbers a rebuild can be checked against

### 6.1 Published — SI Table S5 (n = 495, the 2-arm `data_ana`)

The SI prints M/SD/correlations for the preregistered sample. Recomputed values in the last two
columns; **every one reproduces to 2 dp**.

| Variable | SI M | SI SD | recomputed M | recomputed SD |
|---|---|---|---|---|
| participants' political orientation (`conservative`) | 3.40 | 1.75 | 3.3986 | 1.7463 |
| expertise-based trust (`expertise`) | 6.17 | 0.92 | 6.1690 | 0.9177 |
| morality-based trust (`moralTrust`) | 5.45 | 1.05 | 5.4535 | 1.0497 |
| information seeking (`information_seeking`) | 5.63 | 1.32 | 5.6263 | 1.3162 |
| policy support (`support`) | 5.12 | 1.14 | 5.1172 | 1.1375 |
| perceived similarity (`similarity`) | 4.24 | 1.31 | 4.2364 | 1.3050 |

Correlations (SI value → recomputed): pol–exp −.13→−.127, pol–mor −.11→−.106, pol–info −.15→−.153,
pol–supp −.21→−.215, pol–sim −.21→−.214, exp–mor .73→.729, exp–info .45→.454, exp–supp .49→.487,
exp–sim .37→.368, mor–info .48→.476, mor–supp .55→.549, mor–sim .54→.543, info–supp .52→.521,
info–sim .50→.496, supp–sim .53→.527. SI note: *"All items were measured on scales from 1 to 7
(political orientation: 1 = very liberal, 7 = very conservative)."*

### 6.2 Published — the p-values hard-coded in the Rmd

The Rmd halves each two-sided p for its one-tailed test, so the two-sided values are **printed in
the script itself** and are the sharpest available check. All four reproduce **exactly** on the
model `lm(DV ~ dummy_sociologist * conser_cent, data = data_ana)`
(`dummy_sociologist`: 1 = sociological, 0 = economic):

| DV | Rmd literal | recomputed p of the **interaction** |
|---|---|---|
| `expertise` | `0.26111   /2` | **0.26111** |
| `moralTrust` | `0.0755/2` | **0.07550** |
| `support` | `0.0593/2` | **0.05927** |
| `information_seeking` | `0.01048/2` | **0.01048** |

Full recomputed coefficient tables (b [SE], t, p; two-sided):

| DV | n | R² | `dummy_sociologist` | `conser_cent` | interaction |
|---|---|---|---|---|---|
| expertise | 492 | .0188 | +0.0236 [0.0823], t 0.29, p .774 | −0.0420 [0.0323], t −1.30, p .194 | −0.0532 [0.0473], t −1.13, p .261 |
| moralTrust | 493 | .0649 | **+0.4588 [0.0919], t 4.99, p <.001** | −0.0228 [0.0361], t −0.63, p .528 | −0.0940 [0.0528], t −1.78, p .0755 |
| support | 493 | .0531 | +0.0131 [0.1000], t 0.13, p .896 | −0.0891 [0.0393], t −2.27, p .0237 | −0.1086 [0.0574], t −1.89, p .0593 |
| information_seeking | 493 | .0380 | +0.1031 [0.1169], t 0.88, p .378 | −0.0356 [0.0459], t −0.78, p .438 | **−0.1725 [0.0671], t −2.57, p .0105** |
| similarity | 493 | .0883 | **+0.3746 [0.1128], t 3.32, p <.001** | −0.0590 [0.0443], t −1.33, p .184 | **−0.2218 [0.0648], t −3.42, p <.001** |

(The intercept is the economic arm at mean conservatism: expertise 6.160, moralTrust 5.230,
support 5.109, information_seeking 5.581, similarity 4.054.)

Also reproduced from the Rmd's follow-up chunk:
`cor.test(data_soc$moralTrust, data_soc$conservative)` → **r = −0.2031, p = .00143, n = 244**;
`cor.test(data_eco$...)` → **r = −0.0380, p = .5505, n = 249**.
`cor.test(pol_orientation, pol_preference)` on `data_all` → **r = 0.8558, n = 739**.
SI Fig. S5 quotes one path coefficient in text: *"one path from condition on policy support:
−0.29***"* (standardised, from the bootstrapped `lavaan` model — **not** recomputed here).

### 6.3 Recomputed only (NOT in the paper) — the arm contrast a carve would score

The authors never run a bare condition contrast; these are recomputed for rebuild-checking only.
Sociological − economic, `data_ana`, Welch t-test, Cohen's d on the pooled SD:

| DV | M soc (SD, n) | M eco (SD, n) | diff | t | p | d |
|---|---|---|---|---|---|---|
| expertise | 6.1803 (0.9223, 245) | 6.1580 (0.9149, 249) | +0.0223 | 0.270 | .787 | 0.024 |
| moralTrust | 5.6821 (0.9757, 245) | 5.2295 (1.0729, 250) | **+0.4526** | 4.912 | <.001 | 0.441 |
| support | 5.1224 (1.1775, 245) | 5.1120 (1.0992, 250) | +0.0104 | 0.102 | .919 | 0.009 |
| information_seeking | 5.6735 (1.3366, 245) | 5.5800 (1.2970, 250) | +0.0935 | 0.789 | .430 | 0.071 |
| similarity | 4.4163 (1.2955, 245) | 4.0600 (1.2927, 250) | +0.3563 | 3.063 | .002 | 0.275 |

Third (exploratory) arm, `economic and sociological research institute`, n = 246:
expertise 6.2839 (0.8828), moralTrust 5.6235 (1.0553), support 5.1829 (1.1897),
information_seeking 5.7602 (1.3834), similarity 4.3740 (1.4450), conservative 3.4309 (1.7176),
age 40.61 (13.04).

Cronbach α on n = 741: expertise .944, morality .954, all-14 .960.

---

## 7. Caveats — what makes a naive carve wrong

1. **Header rows are 3, but 7 rows must go.** Dropping only the 2 extra header rows leaves 5
   experimenter test trials with a real `condition` and all-NaN DVs in the frame. They are removed
   by the attention-check filter anyway, but they corrupt any pre-exclusion count.
2. **Everything is a string.** All 23 analysis variables are character in the CSV; `gender` is a
   string of a digit and is *not* in the authors' numeric list. Empty cells must be read as NA
   (`na.strings=""` / `na_values=[""]`), or a naive cast turns `""` into 0.
3. **`subset(..., attention_check == 1)` drops NA.** 21 exclusions = 10 wrong answers + 11
   missing. Forgetting the NA half gives n = 752, not 741.
4. **`rowMeans(na.rm = FALSE)`.** Pandas' default `skipna=True` differs and would keep one extra
   `expertise` value (n 494 → 495 in `data_ana`). Use `skipna=False`.
5. **The interdisciplinary arm is exploratory and is excluded from every preregistered analysis.**
   Carving all three arms is defensible but is *not* what the paper reports, and the paper's own
   headline N (2,859) counts Study 4b as 495. A 3-arm carve must say so.
6. **No filter on `Finished` / `Progress` / `Status` / duration, and do not add one.** Among the
   741 retained, 62 have `Finished == 0` (61 at `Progress == 96`, 1 at 78) — they answered the DVs
   and stopped in the demographics block, which is exactly the 2 missing `age`/`gender` and
   2 missing politics values. The 4 rows with `Status == 8` in `d1` are all already removed by the
   attention check. `DistributionChannel` is `anonymous` for all 762; `Consent == 1` for all 762;
   no duplicate `ResponseId`.
7. **METI item order is randomised per respondent** (`METI_DO`, 754 distinct orders among 762 rows,
   8 NA) — an item-position effect is averaged out, but the raw column order is not the presented
   order. `FL_5_DO` records the arm randomiser. There is **no counterbalancing of policies** in 4b
   (that is Study 4a).
8. **Two different scale lengths.** 1–7 for all DVs and politics items; **1–5** for `politicized`
   and `lawyer`. Converting to percentage-points of scale range needs the right divisor per item.
9. **Only two demographics exist** (age, gender). No education, income, race, region. The only
   continuous moderator is `conservative` (1–7). Any moderator table beyond that cannot be built
   from this file.
10. **The prereg's stated scale endpoints are reversed relative to the fielded instrument** (§4).
    Trust the survey PDF, the script and SI Table S5: 1 = very liberal.
11. **The authors' own gender arithmetic is internally inconsistent** (§4). Do not import a
    "% women" figure without deciding which of the two you mean.
12. **The manipulation is source *identity*, not a persuasive message.** Arms differ only in the
    scientists' discipline; there is no argument, no evidence and no persuasion attempt, and the
    "policy" is deliberately contentless. The interdisciplinary arm is additionally not
    length-matched (78 vs 71 words) and changes sentence structure.
13. **The headline effect is an interaction, not a main effect.** On `expertise`, `support` and
    `information_seeking` the arm main effect is indistinguishable from zero (|d| ≤ 0.07); only
    `moralTrust` (d = 0.44) and `similarity` (d = 0.28) move on the marginal contrast. A carve
    scored on marginal ATEs alone is scoring mostly noise on three of the four DVs.
14. **One-tailed tests throughout.** The prereg specifies one-tailed tests for all directional
    hypotheses and the Rmd halves each p by hand. Two of the paper's four "supported" results
    (`moralTrust` p = .038, `support` p = .030 one-tailed) are not significant two-tailed.
15. **`similarity` is a mediator, not an outcome** in the authors' framing, and it is measured
    *after* the DVs (survey PDF page 6, after the attention check).

---

*Written by a reconnaissance child agent. No predictions of any effect were produced; every
statistic above is a ground-truth quantity recomputed from the mounted file, reported so that a
carve can be checked against the authors' own published output.*
