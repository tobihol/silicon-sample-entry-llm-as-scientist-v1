#!/usr/bin/env python
"""Extract participant-facing intervention texts from the mounted Qualtrics (.qsf) exports.

Rebuilds, from scratch and deterministically:

    /workspace/run/inputs/texts/vlasceanu2024_arms.json
    /workspace/run/inputs/texts/bbprime2025_arms.json

Re-run (there is no `python`/`python3` on PATH in this image):

    /opt/kernel/venv/bin/python /workspace/run/tools/extract_qsf_texts.py

Add --dry-run to print per-arm character counts without writing the JSON files,
and --out-dir DIR to write somewhere other than /workspace/run/inputs/texts.

Sources (read-only mounts):
  vlasceanu2024: downloads/materials/usa_1.qsf                     (1 survey, 12 arms)
  bbprime2025:   downloads/materials/Intervention_Tournament_Intervention_Set_1.qsf (14 arms)
                 downloads/materials/Intervention_Tournament_Intervention_Set_2.qsf (3 arms)
                 (Intervention_Tournament_DVs.qsf is the outcome instrument: its flow
                  contains only DV blocks, so it is not read here.)

How arms are resolved (never by block-name string matching):
  * vlasceanu2024 - the survey Flow ("FL") contains a BlockRandomizer that sets the
    embedded fields cond=1..12 / condName, then one Branch per cond value whose subtree
    holds that arm's block(s).  The arm's text is that subtree's blocks, in flow order.
  * bbprime2025 - each qsf's Flow has one top-level BlockRandomizer; each child Group of
    that randomizer is one arm.  The arm id is the value of the embedded field `group`
    (Set 1) or `condition` (Set 2) set anywhere in that subtree; the arm's text is every
    block in that subtree, in flow order.

Rendering rules (see notes/DATA_QSF_TEXTS.md):
  * Qualtrics HTML -> plain text; paragraph breaks kept; <img> -> "[IMAGE]" marker.
  * Timing (PageTimer) questions dropped; the right-aligned page-timer notices
    ("You will be able to advance the page shortly", "... after at least N minutes have
    passed") are dropped as UI chrome when they stand alone on their own line.
  * Choice/answer lists are kept: choices as "- " bullets, matrix answer scales as
    "[response options: a | b | ...]".
  * Piped text (${e://Field/x}, ${q://QIDn/...}, ${lm://Field/n}) is left verbatim.
  * Loop-and-merge blocks (Payload.Options.Looping == "Static"): iteration 1 is rendered
    in full with its merge fields substituted, and iterations 2..N are rendered as only
    the lines that differ from iteration 1, under an explicit "[loop-and-merge ...]"
    header that records the loop randomisation.
  * Text identical to text already emitted earlier in the same arm is emitted once and
    then annotated "[repeated on each of the following N pages]".
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
from collections import OrderedDict

DATASETS = "/workspace/datasets"
DEFAULT_OUT = "/workspace/run/inputs/texts"

VLASCEANU_QSF = f"{DATASETS}/vlasceanu2024/downloads/materials/usa_1.qsf"
BB_SET1 = f"{DATASETS}/bbprime2025/downloads/materials/Intervention_Tournament_Intervention_Set_1.qsf"
BB_SET2 = f"{DATASETS}/bbprime2025/downloads/materials/Intervention_Tournament_Intervention_Set_2.qsf"

# data63.xlsx (the analysis file the adapter reads) renames two of the QSF's condName
# values; the other ten are byte-identical, which forces the correspondence.
VLASCEANU_CONDNAME_TO_ARM = {
    "Control": "Control",
    "Identity-Social-Norms-Intervention": "WorkTogetherNorm",
    "NegativeEmotions": "NegativeEmotions",
    "SciConsens": "SciConsens",
    "CollectAction": "CollectAction",
    "SystemJust": "SystemJust",
    "PsychDistance": "PsychDistance",
    "PluralIgnorance": "PluralIgnorance",
    "Letter2Future": "LetterFutureGen",
    "DynamicNorm": "DynamicNorm",
    "FutureSelfCont": "FutureSelfCont",
    "BindingMoral": "BindingMoral",
}

# raw `group` value in the data -> display arm name (== keys of inputs/adapters/bbprime2025.json "arms")
BB_GROUP_TO_ARM = {
    "self_relevance": "News Comments (Self-Rel)",
    "social_relevance": "News Comments (Social-Rel)",
    "norm_text": "Social Norms (Text)",
    "norm_quiz": "Social Norms (Quiz)",
    "moral_values": "Moral Values",
    "ES_prevention_self": "Imagination (Prevention-Self)",
    "ES_prevention_other": "Imagination (Prevention-Other)",
    "ES_promotion_self": "Imagination (Promotion-Self)",
    "ES_promotion_other": "Imagination (Promotion-Other)",
    "MCII_individual": "Action Planning (Individual)",
    "MCII_collective": "Action Planning (Collective)",
    "letter": "Letter to Future Gen",
    "impact_text": "Impact Information (Text)",
    "impact_quiz": "Impact Information (Quiz)",
    "CF_general": "Carbon Footprint (General)",
    "CF_personalized": "Carbon Footprint (Personalized)",
    "STPB": "Personal Benefits",
}

MAX_CHOICES = 30
MAX_CHOICE_CHARS = 1500

# The two "News Comments" arms loop over the same 26 New York Times headline/snippet pairs
# that this file already stores verbatim under _rated_stimuli.news_headlines (they are the
# message-sharing DV stimuli).  Printing them a second and third time would triple the
# file for no new content, so iterations 2..N of these two blocks are replaced by a pointer.
NYT_LOOP_BLOCKS = {
    "BL_5byBlQLmoJv4tvM": "News Comments - Self",
    "BL_dfZmE4NBv5K9z2m": "News Comments - Social",
}

PAGE_TIMER_NOTICE = re.compile(
    r"^You will be able to (advance the page|proceed)"
    r"( shortly| after at least .*| in a moment)?\.?$",
    re.I,
)


# --------------------------------------------------------------------------- html


def html_to_text(s):
    """Qualtrics rich text -> plain text, keeping paragraph breaks and image markers."""
    if not s:
        return ""
    s = s.replace("\xa0", " ")

    s = re.sub(r"<style[^>]*>.*?</style>", " ", s, flags=re.I | re.S)
    s = re.sub(r"<script[^>]*>.*?</script>", " ", s, flags=re.I | re.S)

    def imgrep(m):
        tag = m.group(0)
        alt = re.search(r'alt="([^"]*)"', tag)
        label = alt.group(1).strip() if alt and alt.group(1).strip() else ""
        return "\n[IMAGE%s]\n" % ((": " + label) if label else "")

    s = re.sub(r"<img[^>]*>", imgrep, s, flags=re.I)
    s = re.sub(r"<(?:br|BR)\s*/?>", "\n", s)
    s = re.sub(r"</(p|div|h[1-6]|tr|li|table|ul|ol|blockquote)\s*>", "\n", s, flags=re.I)
    s = re.sub(r"<li[^>]*>", "\n- ", s, flags=re.I)
    s = re.sub(r"</td\s*>", " ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = s.replace("\xa0", " ").replace("\u200b", "")
    s = re.sub(r"[ \t]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    lines = [ln for ln in s.split("\n") if not PAGE_TIMER_NOTICE.match(ln.strip())]
    s = "\n".join(lines)
    s = re.sub(r"\n{3,}", "\n\n", s)
    return s.strip()


# ------------------------------------------------------------------------- qsf io


class Survey:
    def __init__(self, path):
        self.path = path
        with open(path, encoding="utf-8") as fh:
            doc = json.load(fh)
        els = doc["SurveyElements"]
        self.name = doc["SurveyEntry"].get("SurveyName")
        self.questions = {}
        for e in els:
            if e["Element"] == "SQ":
                pl = e["Payload"]
                qid = pl.get("QuestionID") or e.get("PrimaryAttribute")
                self.questions[qid] = pl
        bl = [e for e in els if e["Element"] == "BL"][0]["Payload"]
        blist = list(bl.values()) if isinstance(bl, dict) else list(bl)
        self.blocks = {b["ID"]: b for b in blist}
        self.flow = [e for e in els if e["Element"] == "FL"][0]["Payload"]["Flow"]


def _ordered(mapping, order_key):
    if not isinstance(mapping, dict):
        return []
    keys = order_key or list(mapping.keys())
    out = []
    for k in keys:
        k = str(k)
        if k in mapping:
            out.append(mapping[k])
    return out


def render_question(pl):
    """One question -> plain text (question text + choices + answer scale)."""
    if pl.get("QuestionType") == "Timing":
        return ""
    seg = html_to_text(pl.get("QuestionText", ""))
    choices = [
        html_to_text(c.get("Display", ""))
        for c in _ordered(pl.get("Choices"), pl.get("ChoiceOrder"))
    ]
    choices = [c for c in choices if c]
    if choices and all(PLACEHOLDER_CHOICE.match(c) for c in choices) and pl.get("QuestionJS"):
        choices = []
        seg = (seg + "\n" if seg else "") + (
            "[the %d response options are set by JavaScript from the shuffled list shown on the "
            "previous screen; Choices holds only 'Choice 1'..'Choice N' placeholders]"
            % len(_ordered(pl.get("Choices"), pl.get("ChoiceOrder"))))
    answers = [
        html_to_text(a.get("Display", ""))
        for a in _ordered(pl.get("Answers"), pl.get("AnswerOrder"))
    ]
    answers = [a for a in answers if a]
    if choices:
        # Exhaustive machine-generated pick lists (the EPA vehicle catalogue in the
        # Carbon Footprint - Personalized arm runs to tens of thousands of characters)
        # are truncated: they are a lookup widget, not message content.
        if len(choices) > MAX_CHOICES or sum(len(c) for c in choices) > MAX_CHOICE_CHARS:
            shown = choices[:6]
            seg = (seg + "\n" if seg else "") + "\n".join("- " + c for c in shown)
            seg += ("\n- [... %d further options in this pick list, truncated here; "
                    "last option: %r]" % (len(choices) - len(shown), choices[-1]))
        else:
            seg = (seg + "\n" if seg else "") + "\n".join("- " + c for c in choices)
    if answers:
        seg = (seg + "\n" if seg else "") + "[response options: " + " | ".join(answers) + "]"
    injected = js_injected_text(pl)
    if injected:
        seg = (seg + "\n" if seg else "") + injected
    return seg.strip()


JS_TEXT_ITEM = re.compile(
    r'\{\s*text:\s*"((?:[^"\\]|\\.)*)"\s*,\s*key:\s*"((?:[^"\\]|\\.)*)"\s*\}')
PLACEHOLDER_CHOICE = re.compile(r"^Choice \d+$")


def js_injected_text(pl):
    """Participant-facing content that a question's JavaScript writes into the page.

    Third storage location after QuestionText and LoopingOptions.Static: the Moral Values
    arm builds its list of six moral values in QuestionJS (`var paragraphs = [{text:...,
    key:...}]`) and shuffles it, so the text is in neither of the usual places.
    """
    js = pl.get("QuestionJS") or ""
    items = JS_TEXT_ITEM.findall(js)
    if not items:
        return ""
    lines = ["[the %d items below are written into the page by the question's JavaScript, "
             "not stored in QuestionText; each participant saw them in a random order]" % len(items)]
    for text, key in items:
        lines.append("- " + html_to_text(text.replace('\\"', '"')) +
                     "  [key: %s]" % key)
    return "\n".join(lines)


def _substitute_loop_fields(text, row):
    def rep(m):
        return str(row.get(m.group(1), m.group(0)))

    text = re.sub(r"\$\{lm://Field/(\d+)\}", rep, text)
    return text


def render_block(survey, block_id):
    """Return list of (label, text) segments for one block, in participant order."""
    b = survey.blocks[block_id]
    opts = b.get("Options") or {}
    looping = opts.get("Looping")
    loop = (opts.get("LoopingOptions") or {}) if looping == "Static" else {}
    static = loop.get("Static") or {}
    segs = []

    def block_questions():
        out = []
        for be in b.get("BlockElements") or []:
            if be.get("Type") != "Question":
                continue
            pl = survey.questions.get(be["QuestionID"])
            if pl is None:
                continue
            out.append((be["QuestionID"], pl))
        return out

    qlist = block_questions()

    if static:
        rows = [static[k] for k in sorted(static, key=lambda x: int(x))]
        n = len(rows)
        rand = loop.get("Randomization")
        subset = loop.get("TotalRandSubset")
        if rand == "Subset" and subset:
            how = ("each participant saw a random %s of the %d items below, "
                   "in random order" % (subset, n))
        elif rand == "All":
            how = "each participant saw all %d items below, in random order" % n
        else:
            how = "each participant saw the %d items below" % n
        header = ("[loop-and-merge block '%s': the page template below was repeated once "
                  "per item; %s. The merge fields come from "
                  "Payload.Options.LoopingOptions.Static, NOT from QuestionText.]"
                  % (b.get("Description"), how))
        segs.append(("LOOP-HEADER", header))
        # iteration 1 in full, later iterations as only the lines that changed
        base_lines = None
        for i, row in enumerate(rows, start=1):
            parts = []
            for qid, pl in qlist:
                txt = render_question({**pl, "QuestionText": _substitute_loop_fields(
                    pl.get("QuestionText", ""), row)})
                if txt:
                    parts.append(txt)
            rendered = "\n\n".join(parts)
            lines = rendered.split("\n")
            if i == 1:
                base_lines = lines
                segs.append(("LOOP-ITEM-1", "item 1 of %d (full page):\n%s" % (n, rendered)))
            elif block_id in NYT_LOOP_BLOCKS:
                continue
            else:
                if len(lines) == len(base_lines):
                    diff = [ln for ln, b0 in zip(lines, base_lines) if ln != b0]
                else:
                    diff = lines
                segs.append(("LOOP-ITEM-%d" % i,
                             "item %d of %d: %s" % (i, n, " / ".join(diff))))
        if block_id in NYT_LOOP_BLOCKS:
            segs.append(("LOOP-POINTER",
                         "[items 2-%d of this loop are the remaining 25 of the same 26 New York "
                         "Times headline/snippet pairs listed verbatim under "
                         "'_rated_stimuli.news_headlines' in this file; only the headline and "
                         "snippet change from page to page. Each participant saw a random 5.]"
                         % n))
        return segs

    for qid, pl in qlist:
        txt = render_question(pl)
        if txt:
            segs.append((qid, txt))
    return segs


def assemble(survey, block_ids):
    """Blocks -> one plain-text string, collapsing exact repeats."""
    segs = []
    for bid in block_ids:
        segs.extend(render_block(survey, bid))
    out, seen = [], OrderedDict()
    for _, txt in segs:
        if txt in seen:
            seen[txt] += 1
            continue
        seen[txt] = 1
        out.append(txt)
    counts = seen
    final = []
    for txt in out:
        c = counts[txt]
        if c > 1:
            txt = txt + "\n[the same screen content was repeated on %d further pages]" % (c - 1)
        final.append(txt)
    return "\n\n---\n\n".join(final).strip()


# ------------------------------------------------------------------- flow walking


def _iter_flow(nodes):
    for n in nodes:
        yield n
        for sub in _iter_flow(n.get("Flow", []) or []):
            yield sub


def _blocks_in(nodes):
    out = []
    for n in _iter_flow(nodes):
        if n.get("Type") in ("Block", "Standard") and n.get("ID", "").startswith("BL_"):
            out.append(n["ID"])
    return out


def _embedded_values(nodes, field):
    vals = []
    for n in _iter_flow(nodes):
        if n.get("Type") == "EmbeddedData":
            for e in n.get("EmbeddedData", []):
                if e.get("Field") == field and e.get("Value"):
                    vals.append(e["Value"])
    return vals


def vlasceanu_arm_blocks(survey):
    """cond value -> (condName, [block ids]) taken from the survey Flow."""
    condname = {}
    for n in _iter_flow(survey.flow):
        if n.get("Type") == "EmbeddedData":
            d = {e["Field"]: e.get("Value") for e in n.get("EmbeddedData", [])}
            if "condName" in d and "cond" in d:
                condname[d["cond"]] = d["condName"]
    arms = OrderedDict()
    shared = []
    for n in _iter_flow(survey.flow):
        if n.get("Type") != "Branch":
            continue
        s = json.dumps(n.get("BranchLogic", {}))
        m = re.findall(r'"LeftOperand": "cond"[^}]*?"RightOperand": "(\d+)"', s)
        if not m:
            continue
        cond = m[0]
        blocks = _blocks_in(n.get("Flow", []) or [])
        if not blocks:
            continue
        if cond in arms:
            # A cond value can be branched on more than once.  Only the FIRST branch is
            # the arm's stimulus (it fires before the shared outcome blocks); the later
            # cond==1 branch holds control-only *measurement* blocks ("1. Control
            # Condition IVs", "... IV - terms probing") asked after the outcomes.
            continue
        arms[cond] = blocks
    # the "Climate Change Information Overview for all" block sits at flow top level,
    # before the arm branches: everyone saw it.
    top = [n for n in survey.flow if n.get("Type") in ("Block", "Standard")]
    for n in top:
        desc = survey.blocks.get(n.get("ID"), {}).get("Description", "")
        if desc.startswith("Climate Change Information Overview"):
            shared.append(n["ID"])
    return condname, arms, shared


def bb_arm_blocks(survey, field):
    """Top-level randomizer child groups -> {group id: [block ids]}."""
    arms = OrderedDict()
    randomizers = [n for n in _iter_flow(survey.flow) if n.get("Type") == "BlockRandomizer"]
    for rnd in randomizers:
        for child in rnd.get("Flow", []) or []:
            sub = [child]
            gids = _embedded_values(sub, field)
            if not gids:
                continue
            blocks = _blocks_in(sub)
            if not blocks:
                continue
            arms.setdefault(gids[0], []).extend(blocks)
    return arms


# ----------------------------------------------------------------------- outputs


def build_vlasceanu():
    s = Survey(VLASCEANU_QSF)
    condname, arms, shared = vlasceanu_arm_blocks(s)
    texts, prov = OrderedDict(), OrderedDict()
    for cond, blocks in arms.items():
        arm = VLASCEANU_CONDNAME_TO_ARM[condname[cond]]
        texts[arm] = assemble(s, blocks)
        prov[arm] = dict(cond=cond, condName=condname[cond],
                         blocks=[(b, s.blocks[b]["Description"]) for b in blocks])
    shared_text = assemble(s, shared) if shared else ""
    return texts, prov, shared_text, s


def build_bbprime():
    texts, prov = OrderedDict(), OrderedDict()
    for path, field in ((BB_SET1, "group"), (BB_SET2, "condition")):
        s = Survey(path)
        for gid, blocks in bb_arm_blocks(s, field).items():
            arm = BB_GROUP_TO_ARM.get(gid)
            if arm is None:
                continue
            texts[arm] = assemble(s, blocks)
            prov[arm] = dict(group=gid, qsf=os.path.basename(path),
                             blocks=[(b, s.blocks[b]["Description"]) for b in blocks])
    return texts, prov


VLASCEANU_NOTE = """PROVENANCE. Participant-facing intervention text extracted verbatim from \
/workspace/datasets/vlasceanu2024/downloads/materials/usa_1.qsf (Qualtrics export, survey \
"USA Climate master survey MSI"), the U.S. instrument of the 63-country Global Climate \
Intervention Tournament, by /workspace/run/tools/extract_qsf_texts.py. SUPERSEDES the earlier \
record here, which was true of the earlier download: at that point only data63.xlsx, \
data_notimers.csv, codebook.xlsx and OSF_READme.txt were mounted, no intervention wording \
existed on disk, and a predictor given this brief saw ONLY the 11 short condition names \
(the task then trained ordering-from-a-label). materials/ is now mounted and every arm has \
its text. The task's other value is unchanged: the 13 Belief/Policy items are near-verbatim \
overlaps with the target's belief_post and policy_specific_1..7, so it anchors distributions \
and baselines as well as ATEs.

ARM NAMING. Arms are resolved from the survey Flow, never by block-title matching: a \
BlockRandomizer sets cond=1..12 with condName, and one Branch per cond value holds that arm's \
block(s). data63.xlsx (what the adapter reads) renames two condName values - cond 2 \
"Identity-Social-Norms-Intervention" -> WorkTogetherNorm and cond 9 "Letter2Future" -> \
LetterFutureGen; the other ten strings are identical in both files, which forces the pairing. \
Control (cond 1) is an active distractor: an excerpt of Dickens' Great Expectations. Control \
respondents also answered two extra measurement blocks ("1. Control Condition IVs", "1. Control \
Condition IV - terms probing") AFTER the shared outcomes; those are measures, not stimulus, and \
are excluded here.

SHOWN TO EVERY ARM (not repeated in each arm string): "Throughout this survey, you may be asked \
to read some information, report your beliefs or behaviors, or even write a small paragraph. \
Before we begin, we would like to clarify what we mean by "climate change". Climate change is \
the phenomenon describing the fact that the world's average temperature has been increasing over \
the past 150 years and will likely be increasing more in the future." An attention check follows \
the intervention for every arm.

CAVEATS. (1) IMAGES: several interventions are partly or mostly pictorial; every <img> is marked \
"[IMAGE]" at its position and no image content is recoverable from the QSF (image bodies live on \
Qualtrics' servers). SciConsens is one image plus one sentence; WorkTogetherNorm is a flyer image \
whose text is not in the file; PsychDistance, CollectAction, SystemJust and DynamicNorm carry \
figures. (2) PIPED TEXT is left verbatim: ${q://QID268/ChoiceNumericEntryValue/1} in \
PluralIgnorance is the respondent's own guess played back to them, and PsychDistance pipes back \
the respondent's own selected local impacts. (3) SOME ARM BLOCKS MIX STIMULUS AND ITEMS: \
WorkTogetherNorm and NegativeEmotions interleave the arm's own mediator/manipulation-check \
sliders with the stimulus; those questions are kept (the participant read them) and appear in \
flow order. (4) Screens whose content is byte-identical to an earlier screen in the same arm \
(e.g. the WorkTogetherNorm flyer re-displayed above each rating) are printed once and annotated. \
(5) Qualtrics page-timer chrome ("You will be able to advance the page shortly") is stripped. \
(6) Free-text writing tasks (LetterFutureGen, FutureSelfCont, PsychDistance) are prompts only; \
what participants wrote is not in the QSF. (7) HTML is stripped to plain text; multiple-choice \
options are "- " bullets and matrix scale points are "[response options: ...]"."""

BBPRIME_NOTE = """PROVENANCE. Participant-facing intervention text extracted verbatim from the two \
Qualtrics exports in /workspace/datasets/bbprime2025/downloads/materials/ - \
Intervention_Tournament_Intervention_Set_1.qsf (14 arms) and \
Intervention_Tournament_Intervention_Set_2.qsf (Personal Benefits, Moral Values, Letter to Future \
Gen) - by /workspace/run/tools/extract_qsf_texts.py. Intervention_Tournament_DVs.qsf was checked \
and is the OUTCOME instrument (its Flow contains only DV blocks: NYT articles, petitions, \
pro-environmental behaviours, emotions, demographics); it contributes no intervention text. \
SUPERSEDES the earlier record here, which was true of the earlier download: materials/ was not \
mounted, SOP_and_measures.docx documents only procedure and outcome items, the .Rmd files carry \
only condition labels, and the arm TITLES were then the entire signal a blind predictor got.

ARM NAMING. Arms are resolved from each survey's Flow: one top-level BlockRandomizer, one child \
Group per arm, and the arm id is the embedded field `group` (Set 1) / `condition` (Set 2), whose \
values are exactly the `group` codes in the microdata and the keys of the adapter's `arms` map. \
The 18th arm, `control`, has no block anywhere (control participants went straight to the DVs), \
so there is no "Control" key here - that is correct, not missing text.

LOOP-AND-MERGE (the caveat that matters). Four arms' entire substantive content lives in \
Payload.Options.LoopingOptions.Static, NOT in QuestionText: Social Norms (Text) and Social Norms \
(Quiz) share a bank of 24 norm statistics (Randomization=Subset, TotalRandSubset=16, so each \
participant saw a random 16 of the 24, in random order); Impact Information (Text) and Impact \
Information (Quiz) share a bank of 8 carbon-impact facts (Randomization=All, so all 8, in random \
order). ALL bank items are reproduced here. Rendering: iteration 1 is printed as a full page with \
its ${lm://Field/n} merge fields substituted, and iterations 2..N are printed as only the lines \
that differ from iteration 1, under a "[loop-and-merge ...]" header. Because the loop order is \
randomised per participant, the printed order is the QSF's storage order, not any participant's.

CAVEATS. (1) PIPED TEXT is left verbatim and is heavy in Carbon Footprint (Personalized), whose \
feedback screens are built almost entirely from ${e://Field/...} values computed from the \
respondent's own car/flight/diet/energy answers - the arm's text therefore shows the template, \
not what any respondent read; the same applies to the quiz arms' "Your Guess: ${q://...}" \
playback. (2) ARM FLOWS INCLUDE SHARED FOLLOW-UP BLOCKS: the four Imagination arms each end with \
"Guided Imagination - Simulation Ratings", and both Action Planning arms continue into the shared \
"Imagine / Obstacle / Review" blocks; these are inside the arm's own randomiser branch, so they \
are part of what that arm's participants did, and they are included in flow order. (3) IMAGES are \
marked "[IMAGE]"; no image content is recoverable from the QSF. (4) Free-text tasks (Letter to \
Future Gen, Moral Values essay/ad, Action Planning) are prompts only. (5) Qualtrics timing \
questions are dropped; HTML is stripped to plain text, choices become "- " bullets and matrix \
scale points "[response options: ...]". (6) The two exports duplicate most blocks; each arm is \
taken from the export whose Flow actually randomises it. (7) '_rated_stimuli' below is unchanged \
from the previous version of this file: it is what every respondent RATED after treatment \
(identical across arms) - the 26 New York Times headline/snippet pairs of the News Headlines Task \
and the 10 petitions of the Petitions Task, verbatim from messages_data.csv (main_headline, \
snippet) and petitions_data.csv (petition_text)."""


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=1)
        fh.write("\n")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--out-dir", default=DEFAULT_OUT)
    ap.add_argument("--provenance", help="also write the block/QID provenance map here (JSON)")
    args = ap.parse_args(argv)

    v_texts, v_prov, v_shared, _ = build_vlasceanu()
    b_texts, b_prov = build_bbprime()

    report = {}
    for name, texts, path in (
        ("vlasceanu2024", v_texts, os.path.join(args.out_dir, "vlasceanu2024_arms.json")),
        ("bbprime2025", b_texts, os.path.join(args.out_dir, "bbprime2025_arms.json")),
    ):
        with open(path, encoding="utf-8") as fh:
            old = json.load(fh)
        existing = [k for k in old if not k.startswith("_")]
        missing = [k for k in existing if k not in texts]
        added = [k for k in texts if k not in existing]
        empty = [k for k in texts if not texts[k].strip()]
        report[name] = dict(existing=len(existing), extracted=len(texts),
                            missing=missing, added=added, empty=empty,
                            chars={k: len(texts[k]) for k in existing if k in texts},
                            total=sum(len(texts[k]) for k in existing if k in texts))
        if missing or added:
            raise SystemExit("arm-key mismatch in %s: missing=%s added=%s" % (name, missing, added))
        out = OrderedDict()
        for k in existing:                      # preserve the existing key order
            out[k] = texts[k]
        out["_note"] = VLASCEANU_NOTE if name == "vlasceanu2024" else BBPRIME_NOTE
        for k in old:                           # preserve any other pre-existing key
            if k.startswith("_") and k != "_note":
                out[k] = old[k]
        if not args.dry_run:
            write_json(path, out)

    if args.provenance and not args.dry_run:
        write_json(args.provenance, {"vlasceanu2024": v_prov, "bbprime2025": b_prov,
                                     "vlasceanu2024_shared_preamble": v_shared})

    json.dump(report, sys.stdout, indent=1)
    sys.stdout.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
