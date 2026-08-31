"""ssb.spec - the single source of truth, parsed from the read-only benchmark.

Nothing in this harness hardcodes a condition name, an outcome name, a moderator
level, or a scale range. They are all read from /workspace/benchmark at call time,
so a change to the benchmark template surfaces as a diff, not as silent drift.
"""
from __future__ import annotations

import csv
import functools
import hashlib
import json
import os
import re
from pathlib import Path

BENCHMARK = Path(os.environ.get("SSB_BENCHMARK", "/workspace/benchmark"))
RUNROOT = Path(os.environ.get("SSB_RUNROOT", "/workspace/run"))
DATASETS = Path(os.environ.get("SSB_DATASETS", "/workspace/datasets"))

_SPEC_R = BENCHMARK / "scripts" / "lib" / "submission_spec.R"
_CODEBOOK = BENCHMARK / "codebook.csv"
_STIMULI = RUNROOT / "inputs" / "stimuli.json"


def _r_vector(src: str, name: str) -> list[str]:
    """Extract the string literals of an R `name <- c(...)` assignment."""
    m = re.search(rf"\b{name}\s*<-\s*c\(", src)
    if not m:
        raise KeyError(f"{name} not found in submission_spec.R")
    i = m.end()
    depth, start = 1, i
    while depth:
        if src[i] == "(":
            depth += 1
        elif src[i] == ")":
            depth -= 1
        i += 1
    return re.findall(r'"([^"]*)"', src[start : i - 1])


def _r_named_vector(src: str, name: str) -> dict[str, str]:
    m = re.search(rf"\b{name}\s*<-\s*c\(", src)
    if not m:
        raise KeyError(name)
    i, depth, start = m.end(), 1, m.end()
    while depth:
        if src[i] == "(":
            depth += 1
        elif src[i] == ")":
            depth -= 1
        i += 1
    body = src[start : i - 1]
    return dict(re.findall(r'"([^"]*)"\s*=\s*"([^"]*)"', body))


def _r_moderators(src: str) -> dict[str, list[str]]:
    m = re.search(r"moderators\s*<-\s*list\(", src)
    i, depth, start = m.end(), 1, m.end()
    while depth:
        if src[i] == "(":
            depth += 1
        elif src[i] == ")":
            depth -= 1
        i += 1
    body = src[start : i - 1]
    out, pos = {}, 0
    for mm in re.finditer(r"(\w+)\s*=\s*c\(", body):
        j, d = mm.end(), 1
        s = j
        while d:
            if body[j] == "(":
                d += 1
            elif body[j] == ")":
                d -= 1
            j += 1
        out[mm.group(1)] = re.findall(r'"([^"]*)"', body[s : j - 1])
    return out


@functools.lru_cache(maxsize=1)
def load() -> dict:
    """Return the benchmark spec as a plain dict. Cached per kernel."""
    src = _SPEC_R.read_text()
    interventions = _r_vector(src, "interventions")
    outcomes = _r_vector(src, "outcomes")
    scale_0_100 = _r_vector(src, "scale_0_100")
    trust_items = [f"trust_{d}_{i}" for d in ("competence", "integrity", "benevolence", "openness") for i in (1, 2, 3)]
    mods = _r_moderators(src)
    # scale range per outcome, in native units -> the divisor for pp conversion
    ranges = {}
    for o in outcomes:
        if o in scale_0_100:
            ranges[o] = (0.0, 100.0)
        elif o == "donation_ams":
            ranges[o] = (0.0, 10.0)
        elif o == "newsletter_signup":
            ranges[o] = (0.0, 1.0)
        else:  # a new outcome appeared in the template - fail loudly
            raise ValueError(f"outcome {o!r} has no declared scale; update ssb.spec")
    return {
        "interventions": interventions,
        "conditions": ["control"] + interventions,
        "outcomes": outcomes,
        "scale_0_100": scale_0_100,
        "trust_items": trust_items,
        "moderators": mods,
        "moderator_levels": [(m, l) for m, ls in mods.items() for l in ls],
        "ranges": ranges,
        "codenames": _r_named_vector(src, "codenames"),
        "spec_sha256": hashlib.sha256(_SPEC_R.read_bytes()).hexdigest(),
    }


def tier1_columns() -> list[str]:
    """Tier-1 column order, reconstructed from the spec exactly as submission_spec.R builds it."""
    s = load()
    return (
        ["profile_id", "condition"]
        + list(s["moderators"].keys())
        + ["trust_multidimensional"]
        + s["trust_items"]
        + [o for o in s["outcomes"] if o != "trust_multidimensional"]
    )


def selftest() -> str:
    """Check the reconstructed Tier-1 header against the shipped example. Cheap; run it in every run."""
    ex = BENCHMARK / "predictions" / "example_T1_primary_v1.csv"
    with ex.open() as fh:
        hdr = next(csv.reader(fh))
    if hdr != tier1_columns():
        raise AssertionError(
            "tier1_columns() no longer matches the shipped example header; "
            f"missing={set(hdr)-set(tier1_columns())} extra={set(tier1_columns())-set(hdr)}"
        )
    return "spec selftest ok: " + summary()


def to_pp(value, outcome: str):
    """Convert a native-unit effect on `outcome` into percentage points of its scale range."""
    lo, hi = load()["ranges"][outcome]
    return value * 100.0 / (hi - lo)


def from_pp(value, outcome: str):
    lo, hi = load()["ranges"][outcome]
    return value * (hi - lo) / 100.0


@functools.lru_cache(maxsize=1)
def codebook() -> list[dict]:
    with _CODEBOOK.open() as fh:
        return list(csv.DictReader(fh))


@functools.lru_cache(maxsize=1)
def composites() -> dict[str, list[str]]:
    """outcome -> the item columns it averages (from the codebook), for outcomes that are composites."""
    return {
        "trust_multidimensional": load()["trust_items"],
        "policy_role_mean": [f"policy_role_{i}" for i in range(1, 5)],
        "inst_trust_mean": ["inst_trust_epa", "inst_trust_nasa", "inst_trust_noaa", "inst_trust_universities", "inst_trust_federal_gov"],
        "concern_mean": [f"concern_{i}" for i in range(1, 4)],
        "policy_specific_mean": [f"policy_specific_{i}" for i in range(1, 8)],
        "behavior_mean": ["behavior_meat", "behavior_transport", "behavior_solar", "behavior_fly", "behavior_talk", "behavior_donate"],
    }


@functools.lru_cache(maxsize=1)
def stimuli() -> dict:
    """The 16 intervention texts + 3 control fillers, extracted from survey/questionnaire.txt.

    Built by tools/extract_stimuli.py; regenerate if the questionnaire changes
    (the stored source_sha256 is checked here).
    """
    d = json.loads(_STIMULI.read_text())
    live = hashlib.sha256((BENCHMARK / "survey" / "questionnaire.txt").read_bytes()).hexdigest()
    if live != d["source_sha256"]:
        raise RuntimeError(
            "questionnaire.txt changed since inputs/stimuli.json was built; "
            "re-run tools/extract_stimuli.py"
        )
    return d


def intervention_text(title: str) -> str:
    for s in stimuli()["stimuli"]:
        if s["title"] == title:
            return s["text"]
    raise KeyError(title)


def summary() -> str:
    s = load()
    return (
        f"conditions={len(s['conditions'])} outcomes={len(s['outcomes'])} "
        f"moderator_levels={len(s['moderator_levels'])} "
        f"tier3_cells={len(s['interventions'])*len(s['outcomes'])} "
        f"tier2_main_cells={len(s['conditions'])*len(s['outcomes'])} "
        f"tier2_mod_cells={len(s['conditions'])*len(s['moderator_levels'])*len(s['outcomes'])} "
        f"spec_sha256={s['spec_sha256'][:12]}"
    )
