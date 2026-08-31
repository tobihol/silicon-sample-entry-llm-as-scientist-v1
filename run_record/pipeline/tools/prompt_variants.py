#!/usr/bin/env python
"""Prompt treatments for the stage-3 information/reasoning experiment (runs/_promptexp/PREREG.md).

The same seam `tools/length_variants.py` opened, widened by exactly one thing: a variant may also
replace the SYSTEM prompt. Everything else downstream - the frozen argv, the cache key (which
covers system AND user), the parser, the scorer, the leak audit - is untouched, so a variant run
differs from the base run in the text of the prompt and in nothing else.

    /opt/kernel/venv/bin/python tools/prompt_variants.py         # what each treatment does, per task

Variants (`base` and the four length treatments are delegated to `length_variants`):

  reason        SYSTEM replaced: the model may write a short rationale per message BEFORE the CSV
                block. The frozen argv sets MAX_THINKING_TOKENS=0 and cannot be changed, so
                in-text reasoning is the only reasoning channel this pipeline has, and it has
                never been tested. The CSV contract is unchanged, so the parser is unchanged.
  reason_rank   SYSTEM replaced: first rank the messages from most to least effective overall,
                then emit the CSV. A ranking is what Section 1's Spearman row scores, so this asks
                for the scored quantity directly instead of as a by-product of 208 numbers.
  anontitles    ABLATION: every arm title is replaced by a neutral label (`Message A` ...). The
                stimulus text is untouched. Tests whether the message-level signal comes from the
                text or from the frame's NAME. Parsed answers are mapped back to the real titles
                before scoring, so nothing downstream sees the pseudonyms.
  noitems       ABLATION: the outcome item wordings are removed; the model keeps each outcome's
                name and scale. Tests how much of the within-outcome skill is carried by the item
                text rather than by the outcome label.

An ablation is not a candidate prompt: `anontitles` and `noitems` remove real information and are
run to find out what the predictor is using. `reason` and `reason_rank` are the only two that could
become the pipeline's prompt, and only if they beat the measured draw-to-draw noise floor.
"""
from __future__ import annotations

import json
import string
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / "tools"))
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import length_variants  # noqa: E402
import ssb  # noqa: E402

NEW = ["reason", "reason_rank", "anontitles", "noitems"]
VARIANTS = length_variants.VARIANTS + NEW

_BASE = ssb.predict.SYSTEM

# The CSV contract below is copied from the frozen predictor's own SYSTEM prompt verbatim, so the
# only thing these treatments change is whether prose may precede the table.
REASON_SYSTEM = _BASE.replace(
    "- Answer ONLY with CSV: a header line `condition,outcome,ate` then one row per cell. No prose.",
    "- First write a short analysis: for each message, at most two sentences on the mechanism you\n"
    "  expect it to work through, on whom, and how strong you expect it to be RELATIVE to the other\n"
    "  messages. Be concrete about which messages you expect to beat which.\n"
    "- Then write the line `---` on its own, and after it answer with CSV only: a header line\n"
    "  `condition,outcome,ate` then one row per cell, and nothing after the last row.")

RANK_SYSTEM = _BASE.replace(
    "- Answer ONLY with CSV: a header line `condition,outcome,ate` then one row per cell. No prose.",
    "- First write `RANKING:` followed by the message titles ordered from the one you expect to have\n"
    "  the LARGEST average effect across the outcomes to the one you expect to have the smallest\n"
    "  (ties allowed, one per line, most effective first), and one line saying which outcomes you\n"
    "  expect to move most and least.\n"
    "- Then write the line `---` on its own, and after it answer with CSV only: a header line\n"
    "  `condition,outcome,ate` then one row per cell, and nothing after the last row.")


def _titles(brief):
    return [a["title"] for a in brief["arms"]]


def plan(brief: dict, variant: str) -> dict:
    if variant in length_variants.VARIANTS:
        return length_variants.plan(brief, variant)
    m = {"variant": variant, "task": brief.get("task_id"), "n_arms": len(brief["arms"])}
    if variant == "anontitles":
        m["renamed"] = len(brief["arms"])
    if variant == "noitems":
        outs = brief["outcomes"]
        items = (outs.values() if isinstance(outs, dict) else outs)
        m["questions_removed"] = sum(1 for o in items if str(o.get("question", "")).strip())
    if variant in ("reason", "reason_rank"):
        m["system_replaced"] = True
    return m


def apply(brief: dict, variant: str) -> tuple[dict, dict]:
    """(transformed brief, metadata). `base` is the identity, so its cache keys are the original
    practice run's and cost nothing. Metadata may carry `system` (a replacement SYSTEM prompt) and
    `rename_back` (pseudonym -> real condition title, applied to the PARSED answer)."""
    if variant not in VARIANTS:
        raise SystemExit("unknown variant %r; one of %s" % (variant, VARIANTS))
    if variant in length_variants.VARIANTS:
        return length_variants.apply(brief, variant)

    b = json.loads(json.dumps(brief))
    meta = plan(brief, variant)
    meta["changed"] = True

    if variant == "reason":
        meta["system"] = REASON_SYSTEM
        return b, meta
    if variant == "reason_rank":
        meta["system"] = RANK_SYSTEM
        return b, meta

    if variant == "anontitles":
        # Neutral labels in presentation order. The order itself is information the base prompt
        # also carries (the arms are listed in some order), so nothing is added.
        labels = ["Message %s" % s for s in
                  (list(string.ascii_uppercase) +
                   ["A%s" % c for c in string.ascii_uppercase])[:len(b["arms"])]]
        back, aliases = {}, {}
        for a, lab in zip(b["arms"], labels):
            short = lab.split(" ", 1)[1]          # "Message A" -> "A"
            back[lab] = a["title"]
            back[short] = a["title"]              # the model may answer with the bare letter
            aliases[lab] = [short]
            a["title"] = lab
        meta["rename_back"] = back
        # MEASURED, not anticipated: the first paid call of this arm answered `A,Belief_Post,0.6`
        # rather than `Message A,...`, and the parser - correctly - refuses to invent a condition
        # it was not given, so all 90 cells came back NaN and the run aborted before scoring. The
        # abort is the guard working; the fix is to hand the parser the abbreviation as an alias of
        # the arm it can only mean, and to map it back with everything else.
        meta["title_aliases"] = aliases
        return b, meta

    if variant == "noitems":
        outs = b["outcomes"]
        if isinstance(outs, dict):
            for v in outs.values():
                v["question"] = ""
        else:
            for v in outs:
                v["question"] = ""
        return b, meta

    raise SystemExit("unhandled variant %r" % variant)


if __name__ == "__main__":
    import pandas as pd
    rows = []
    for t in ("voelkel2026", "goldwert2026", "vlasceanu2024", "bbprime2025", "voelkel2024"):
        p = RUN / "runs/20260815-practice-01/tasks" / t / "brief" / "task.json"
        if not p.exists():
            continue
        b = json.loads(p.read_text())
        for v in NEW:
            nb, m = apply(b, v)
            _, user = ssb.predict.build_prompt(nb)
            _, base_user = ssb.predict.build_prompt(b)
            rows.append({"task": t, "variant": v,
                         "user_chars": len(user), "base_chars": len(base_user),
                         "delta_chars": len(user) - len(base_user),
                         "system_replaced": bool(m.get("system")),
                         "titles_changed": len(m.get("rename_back", {}))})
    print(pd.DataFrame(rows).to_string(index=False))
