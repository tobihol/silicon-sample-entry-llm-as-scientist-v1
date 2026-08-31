#!/usr/bin/env python
"""Stage 3 for arm `fresheyes`, with this arm's own elicitation (PREREG.md section 2).

A thin wrapper around tools/practice.py. It does NOT edit any shared file: it installs a shim in
place of `practice.prompt_variants` that delegates every existing variant to the real registry and
adds exactly one new name, `fresheyes`, whose transform lives in tools/fresheyes_variant.py.

    /opt/kernel/venv/bin/python tools/fresheyes_practice.py --model claude-opus-5 --run-id ...
    ... --execute --approved --max-billed-tokens N
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / "tools"))
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))

import practice          # noqa: E402
import prompt_variants   # noqa: E402
import fresheyes_variant  # noqa: E402

TASKS = ["voelkel2026", "vlasceanu2024", "goldwert2026", "bbprime2025", "orchinik2024", "kim2024"]


class _Shim:
    """Everything prompt_variants exposes, plus `fresheyes`."""
    VARIANTS = list(prompt_variants.VARIANTS) + ["fresheyes"]

    @staticmethod
    def plan(brief, variant):
        if variant != "fresheyes":
            return prompt_variants.plan(brief, variant)
        return {"variant": "fresheyes", "task": brief.get("task_id"), "n_arms": len(brief["arms"])}

    @staticmethod
    def apply(brief, variant):
        if variant != "fresheyes":
            return prompt_variants.apply(brief, variant)
        task = brief.get("task_id")
        levels = fresheyes_variant.control_levels_from_data(task)
        res = fresheyes_variant.resolution_note(task)
        b, meta = fresheyes_variant.apply(brief, levels, res)
        meta["system"] = fresheyes_variant.SYSTEM
        meta["changed"] = True
        meta["levels"] = {k: round(float(v), 3) for k, v in levels.items()}
        return b, meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--draws", type=int, default=3)
    ap.add_argument("--tasks", nargs="*", default=None)
    ap.add_argument("--execute", action="store_true")
    ap.add_argument("--approved", action="store_true")
    ap.add_argument("--rehearsal", action="store_true")
    ap.add_argument("--max-billed-tokens", type=int, default=None)
    ap.add_argument("--probe-version", type=int, default=2)
    ap.add_argument("--allow-missing-cells", type=float, default=0.0)
    a = ap.parse_args()

    practice.prompt_variants = _Shim
    practice.main(model=a.model, run_id=a.run_id, draws=a.draws, tasks=a.tasks or TASKS,
                  execute=a.execute, approved=a.approved, rehearsal=a.rehearsal,
                  max_billed_tokens=a.max_billed_tokens, variant="fresheyes",
                  probe_version=a.probe_version, allow_missing_cells=a.allow_missing_cells)


if __name__ == "__main__":
    main()
