"""ssb.deposit - turn a card into validated submission repositories.

The benchmark enforces "one repo = one entry", so a full submission is three
directories: Tier 1, Tier 2 (two files) and Tier 3. This module builds them from
one card, so the three can never disagree, and then runs the benchmark's own R
validator (`make check`) against each. The validator is the only authority on
whether a file is depositable; nothing here re-implements its rules.
"""
from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pandas as pd

from . import card as _card
from . import spec

SKIP = {".git", "predictions", "raw_data_deposit"}


def stage(dest, tier: int, files: dict[str, pd.DataFrame], meta_updates: dict) -> Path:
    """Copy the read-only template to `dest`, drop in prediction files, write metadata."""
    dest = Path(dest)
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for item in spec.BENCHMARK.iterdir():
        if item.name in SKIP:
            continue
        (shutil.copytree if item.is_dir() else shutil.copy2)(item, dest / item.name)
    (dest / "predictions").mkdir()
    (dest / "raw_data_deposit").mkdir()
    for name, df in files.items():
        df.to_csv(dest / "predictions" / name, index=False)
    meta = json.loads((spec.BENCHMARK / "metadata.json").read_text())
    meta.update(meta_updates)
    meta["tier"] = tier
    meta["coverage"] = {"interventions": len(spec.load()["interventions"]),
                        "outcomes": len(spec.load()["outcomes"])}
    meta["blinding_attestation"] = True
    # Two template defaults the validator CANNOT catch - it only asserts they are non-empty
    # strings - but which `make zenodo_citation` copies into the deposited citation, and which
    # the organisers read. They are facts about this pipeline, not operator preferences, so the
    # harness fills them rather than leaving "per-respondent simulation, single model" and
    # "gpt-4o-mini" in a deposit that is neither.
    meta["approach_family"] = ("analysis-first prediction (ATEs, cell means, moderation and "
                               "distributions predicted directly) with backward synthesis of the "
                               "Tier-1 rows; no per-respondent generation")
    if meta_updates.get("model"):
        meta["models"] = [meta_updates["model"]]
    meta.setdefault("models", [])
    (dest / "metadata.json").write_text(json.dumps(meta, indent=2))
    return dest


def _r(dest: Path, target: str) -> subprocess.CompletedProcess:
    return subprocess.run(["make", target], cwd=dest, capture_output=True, text=True)


def build(run_dir, crd: _card.Card, tier1: pd.DataFrame, meta: dict,
          version: int = 1, entry: str = "primary") -> dict:
    """Build and validate all three tiers. Returns {tier: {"dir","verdict","report"}}."""
    run_dir = Path(run_dir)
    team = meta.get("team_id") or "team"
    out = {}
    payloads = {
        1: {f"{team}_T1_{entry}_v{version}.csv": tier1},
        2: {f"{team}_T2_{entry}_v{version}_cells_main.csv": crd.tier2_main(),
            f"{team}_T2_{entry}_v{version}_cells_moderator.csv": crd.tier2_moderator()},
        3: {f"{team}_T3_{entry}_v{version}.csv": crd.tier3()},
    }
    for tier, files in payloads.items():
        d = stage(run_dir / f"submission_T{tier}", tier, files, {**meta, "entry": entry})
        m = _r(d, "manifest")
        _r(d, "zenodo_citation")   # the validator warns when .zenodo.json is missing
        c = _r(d, "check")
        report = (d / "metadata_check_report.txt")
        text = report.read_text() if report.exists() else (c.stdout + c.stderr)
        verdict = next((l.split()[1] + (" WITH WARNINGS" if "WARNINGS" in l else "")
                        for l in text.splitlines() if l.startswith("OVERALL:")), "UNKNOWN")
        out[tier] = {"dir": str(d), "verdict": verdict,
                     "n_fail": text.count("[FAIL]"), "n_warn": text.count("[warn]"),
                     "manifest_ok": m.returncode == 0, "report": text}
    return out


def summarise(res: dict) -> str:
    return "\n".join(
        f"  Tier {t}: {r['verdict']}  ({r['n_fail']} FAIL, {r['n_warn']} warn)  -> {r['dir']}"
        for t, r in sorted(res.items()))
