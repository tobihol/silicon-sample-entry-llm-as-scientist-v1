#!/usr/bin/env python
"""The length treatments for the stage-3 prompt experiment (runs/_lenexp/PREREG.md).

One function, `apply(brief, variant)`, transforms a carved brief BEFORE `plan_prompts` sees it.
That is the whole seam: everything downstream - the frozen argv, the cache key, the parser, the
scorer, the leak audit - is untouched, so a variant run differs from the base run in exactly the
text of the prompt and in nothing else.

    /opt/kernel/venv/bin/python tools/length_variants.py        # what each treatment does, per task

Five variants:

  base          identity. Its calls are already cached from 20260815-practice-01, so the reference
                costs nothing and is matched draw-for-draw.
  debias_instr  one paragraph in the brief's NOTES saying length is weakly related to effect size.
                The stimulus is not touched. The only variant that could become a target card:
                the target's stimuli may never be trimmed (standing finding 44).
  debias_wc     the same paragraph plus `[N words]` on every arm.
  eqlen         every arm head-trimmed to L = the shortest arm's word count. Exactly equal
                presented length; Spearman(presented, original) = 0.00 by construction.
  proptrim      every arm head-trimmed to the same fraction p, with p set so the task's total
                presented words match eqlen's. Same trimming, same total loss, length ordering
                intact. This is the control that makes eqlen readable.

Both trimming variants carry the SAME marker on EVERY arm, and it names neither the arm's original
length nor L - a marker that says "412 of 1,693 words" would hand back the cue the treatment
exists to remove. Nothing is summarised: a second model rewriting a stimulus changes the thing
being predicted (standing finding 17).
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]

VARIANTS = ["base", "debias_instr", "debias_wc", "eqlen", "proptrim"]

# The measured claim in the debias paragraph is this harness's own, from the five practice tasks:
# mean human Spearman(arm mean ATE, word count) = +0.106 (standing finding 59). It is stated as
# "about +0.1" and is training-data evidence, never anything about the target.
DEBIAS = (
    "LENGTH: the messages differ substantially in how much text they contain. Message length is "
    "only weakly related to effect size - across comparable multi-arm message experiments the rank "
    "correlation between a message's word count and its measured effect is about +0.1. Do not give "
    "a longer message a larger predicted effect because it is longer; judge each message on its "
    "content and on the mechanism it is trying to use."
)

EXCERPT_MARKER = "\n\n[excerpt: the opening portion of this message is shown]"
EXCERPT_NOTE = ("Each message below is shown as an excerpt of its opening rather than in full. "
                "Predict the effect of the message as the study ran it.")

# A task is excluded from the trimming variants if equalising deletes the stimulus rather than
# shortening it. Fixed in PREREG.md before any call: voelkel2024 keeps 0.02 and is out.
MIN_KEEP_FRACTION = 0.10


def n_words(text: str) -> int:
    return len(str(text).split())


def head_words(text: str, n: int) -> str:
    """The first `n` whitespace-delimited words, with the original whitespace between them kept.

    Slicing the string rather than re-joining `split()` preserves paragraph breaks, which are part
    of how the stimulus reads.
    """
    if n <= 0:
        return ""
    ends = [m.end() for m in re.finditer(r"\S+", text)]
    if len(ends) <= n:
        return text
    return text[: ends[n - 1]].rstrip()


def plan(brief: dict, variant: str) -> dict:
    """What the treatment will do to this brief, without doing it. Used by the report and by the
    exclusion rule."""
    w = [n_words(a.get("text") or "") for a in brief["arms"]]
    total = sum(w)
    L = min(w) if w else 0
    keep_eq = (L * len(w) / total) if total else 0.0
    return {"variant": variant, "n_arms": len(w), "words_total": total, "words_min": L,
            "words_max": max(w) if w else 0,
            "eqlen_L": L, "eqlen_keep_fraction": round(keep_eq, 4),
            "proptrim_p": round(keep_eq, 4),
            "eligible_for_trim_variants": keep_eq >= MIN_KEEP_FRACTION}


def apply(brief: dict, variant: str) -> tuple[dict, dict]:
    """(transformed brief, metadata). `base` returns an unchanged copy, so a base run's cache keys
    are identical to the original practice run's and cost nothing."""
    if variant not in VARIANTS:
        raise SystemExit("unknown variant %r; one of %s" % (variant, VARIANTS))
    b = json.loads(json.dumps(brief))
    meta = plan(brief, variant)
    if variant == "base":
        meta["changed"] = False
        return b, meta
    meta["changed"] = True

    if variant in ("debias_instr", "debias_wc"):
        b["note"] = ((b.get("note", "") + " ") if b.get("note") else "") + DEBIAS
        if variant == "debias_wc":
            for a in b["arms"]:
                a["text"] = "[%d words]\n%s" % (n_words(a.get("text") or ""), a.get("text") or "")
        meta["note_added"] = DEBIAS
        return b, meta

    # --- the two trimming variants ---------------------------------------------------------
    if not meta["eligible_for_trim_variants"]:
        raise SystemExit(
            "%s: %s would keep only %.1f%% of the task's words (L = %d over %d arms). Below the "
            "%.0f%% floor fixed in runs/_lenexp/PREREG.md - that deletes the stimulus rather than "
            "shortening it, and the resulting score would measure nothing."
            % (brief.get("task_id"), variant, 100 * meta["eqlen_keep_fraction"], meta["eqlen_L"],
               meta["n_arms"], 100 * MIN_KEEP_FRACTION))
    L, p = meta["eqlen_L"], meta["proptrim_p"]
    kept = []
    for a in b["arms"]:
        t = a.get("text") or ""
        n = L if variant == "eqlen" else max(1, round(p * n_words(t)))
        a["text"] = head_words(t, n) + EXCERPT_MARKER
        kept.append(n)
    b["note"] = ((b.get("note", "") + " ") if b.get("note") else "") + EXCERPT_NOTE
    meta["presented_words"] = kept
    meta["presented_total"] = sum(kept)
    return b, meta


def main() -> int:
    tasks = ["voelkel2026", "goldwert2026", "vlasceanu2024", "bbprime2025", "voelkel2024"]
    src = RUN / "runs/20260815-practice-01/tasks"
    print("%-15s %5s %7s %6s %6s %7s %8s %s"
          % ("task", "arms", "words", "min", "max", "eqlen_L", "keep", "trim variants"))
    for t in tasks:
        f = src / t / "brief" / "task.json"
        if not f.exists():
            continue
        m = plan(json.loads(f.read_text()), "base")
        print("%-15s %5d %7d %6d %6d %7d %7.2f  %s"
              % (t, m["n_arms"], m["words_total"], m["words_min"], m["words_max"], m["eqlen_L"],
                 m["eqlen_keep_fraction"],
                 "yes" if m["eligible_for_trim_variants"] else "NO - below the 10% floor"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
