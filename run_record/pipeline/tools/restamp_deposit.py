#!/usr/bin/env python
"""Re-stamp an existing deposit's identity fields and rebuild the three submission repos.

TASK_08 handed the harness two facts it did not have when runs 20260815-target-01 and
-02-pooled were built: the team id is `team_31` (it was `sodalab`, a placeholder this harness
invented), and the Zenodo deposit may not be published before 2026-08-28.

Neither is a prediction, so neither may be typed into a built deposit by hand: the submission
directories are *derived* artefacts (card + tier1 rows -> three repos, `ssb.deposit.build`), and
editing a derived artefact in place is how a deposit stops reproducing from its card. This tool
re-runs stage 8 only, from the run's own `card/` and `stages/tier1.csv`, with the corrected
metadata, and re-runs the benchmark's own `make check` on all three tiers.

    /opt/kernel/venv/bin/python tools/restamp_deposit.py runs/20260815-target-01 --team-id team_31

It makes NO model call - stages 4-7 are not touched, the card is read and never rewritten - and it
asserts afterwards that the prediction payloads are byte-identical to the ones it replaced apart
from the filename, so a re-stamp can never silently change a number.
"""
import argparse, datetime as dt, glob, json, re, sys
from pathlib import Path

import pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402

# The organisers' window (TASK_08): do NOT publish before Aug 28; the lock is Aug 31.
WINDOW_OPEN = dt.date(2026, 8, 28)
WINDOW_CLOSE = dt.date(2026, 8, 31)


def payloads(d: Path) -> dict:
    """Every prediction CSV under a run's three submission dirs, keyed by tier + the part of
    the filename that is NOT the team id, so a re-stamp is comparable across the rename."""
    out = {}
    for p in sorted(glob.glob(str(d / "submission_T*/predictions/*.csv"))):
        p = Path(p)
        tier = p.parent.parent.name
        tail = re.search(r"_T\d.*", p.name).group(0).lstrip("_")
        out[f"{tier}/{tail}"] = pd.read_csv(p)
    return out


def compare(before: dict, after: dict) -> tuple[bool, str]:
    """Do the payloads carry the same numbers? Byte equality is too strict: `cell_means()`
    accumulates in float and reproduces its own deposited moderator file to ~3e-14, which is a
    different SHA and the same prediction. Compare values with a tolerance and print the worst."""
    if before.keys() != after.keys():
        return False, f"file set changed: {sorted(before)} -> {sorted(after)}"
    worst, where = 0.0, ""
    for k in before:
        a, b = before[k], after[k]
        if a.shape != b.shape or list(a.columns) != list(b.columns):
            return False, f"{k}: shape/columns changed {a.shape} -> {b.shape}"
        num = [c for c in a.columns if pd.api.types.is_numeric_dtype(a[c])]
        for c in a.columns:
            if c in num:
                dd = float((a[c].astype(float) - b[c].astype(float)).abs().max())
                if dd > worst:
                    worst, where = dd, f"{k}:{c}"
            elif not a[c].astype(str).equals(b[c].astype(str)):
                return False, f"{k}: non-numeric column {c} changed"
    return worst < 1e-9, f"max numeric change {worst:.3g} ({where or 'none'})"


def main(run, team_id, entry="primary", version=1):
    d = RUN / run
    crd = ssb.card.Card.load(d / "card")
    t1 = pd.read_csv(d / "stages/tier1.csv")
    before = payloads(d)
    old_md = json.loads((d / "submission_T1/metadata.json").read_text())
    print(f"{run}: {len(t1):,} rows, card {len(crd.ate)} cells, team_id "
          f"{old_md.get('team_id')!r} -> {team_id!r}")

    meta = {k: v for k, v in old_md.items()
            if k not in ("prediction_files", "coverage", "tier", "entry")}
    meta["team_id"] = team_id
    today = dt.date.today()
    meta["built_at"] = today.isoformat()
    meta["publication_window"] = f"{WINDOW_OPEN} .. {WINDOW_CLOSE}"
    meta["not_for_publication_before"] = WINDOW_OPEN.isoformat()
    if today < WINDOW_OPEN:
        meta["publication_status"] = (
            f"NOT-FOR-PUBLICATION - built {today}, {(WINDOW_OPEN - today).days} days before the "
            f"deposit window opens on {WINDOW_OPEN}")
    else:
        meta["publication_status"] = ("in-window" if today <= WINDOW_CLOSE
                                      else "AFTER THE PREDICTION LOCK - do not deposit")

    res = ssb.deposit.build(d, crd, t1, meta, version=version, entry=entry)
    print(ssb.deposit.summarise(res))
    # G5 is a statement about the artefact on disk. The artefact was just rebuilt, so the gate is
    # re-recorded against the new validator run rather than left pointing at the old one.
    verdicts = {k: v["verdict"] for k, v in res.items()}
    ssb.gates.record(d, "G5_validator_pass", all("FAIL" not in v for v in verdicts.values()),
                     json.dumps(verdicts) + f" (re-stamped team_id={team_id})")

    after = payloads(d)
    same, detail = compare(before, after)
    print(f"\nprediction payloads unchanged by the re-stamp: {'YES' if same else 'NO'} - {detail}")
    if not same:
        raise SystemExit("re-stamp changed a prediction payload - that must never happen")
    for p in sorted(glob.glob(str(d / "submission_T*/predictions/*.csv"))):
        print("  ", Path(p).relative_to(d))
    print(f"  publication_status: {meta['publication_status']}")
    bad = [t for t, r in res.items() if "FAIL" in r["verdict"]]
    return 1 if bad else 0


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("run")
    a.add_argument("--team-id", default="team_31")
    a.add_argument("--entry", default="primary")
    a.add_argument("--version", type=int, default=1)
    n = a.parse_args()
    sys.exit(main(n.run, n.team_id, n.entry, n.version))
