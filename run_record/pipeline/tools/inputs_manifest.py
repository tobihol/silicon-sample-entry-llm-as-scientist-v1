#!/usr/bin/env python
"""A hash manifest of inputs/, so a run records what its prompts were actually built from.

`run.json` records `frozen_sha256` (gate G1) and `spec_sha256`, and nothing at all about `inputs/` -
the stimuli, adapters, texts, profile pool, baselines and format parameters that determine every
prompt and every deposited baseline. The cache offers partial protection, because a changed input
changes the prompt and therefore the cache key; but the symptom of that is a silent extra CALL, not
a warning, and two scoreboard rows built from different inputs would compare as if they were the
same experiment.

    /opt/kernel/venv/bin/python tools/inputs_manifest.py --write     # record the current state
    /opt/kernel/venv/bin/python tools/inputs_manifest.py             # verify against the record

Exit code is non-zero on any drift, so it can gate a run.
"""
import argparse, hashlib, json, sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
INPUTS = RUN / "inputs"
MANIFEST = RUN / "inputs" / "MANIFEST.sha256.json"
SKIP = {"MANIFEST.sha256.json"}


def scan():
    out = {}
    for f in sorted(INPUTS.rglob("*")):
        if not f.is_file() or f.name in SKIP:
            continue
        rel = str(f.relative_to(INPUTS))
        h = hashlib.sha256(f.read_bytes()).hexdigest()
        out[rel] = {"sha256": h, "bytes": f.stat().st_size}
    return out


def digest(files: dict) -> str:
    """One hash over the whole tree, cheap to record in run.json."""
    blob = "\n".join("%s %s" % (k, v["sha256"]) for k, v in sorted(files.items()))
    return hashlib.sha256(blob.encode()).hexdigest()


def write():
    files = scan()
    MANIFEST.write_text(json.dumps({"digest": digest(files), "n_files": len(files),
                                    "files": files}, indent=1))
    print("wrote %s\n  %d files, tree digest %s" % (MANIFEST, len(files), digest(files)[:16]))
    return digest(files)


def verify(quiet=False):
    if not MANIFEST.exists():
        print("no manifest; run with --write once to record the current inputs/")
        return None
    rec = json.loads(MANIFEST.read_text())
    now = scan()
    added = sorted(set(now) - set(rec["files"]))
    removed = sorted(set(rec["files"]) - set(now))
    changed = sorted(k for k in set(now) & set(rec["files"])
                     if now[k]["sha256"] != rec["files"][k]["sha256"])
    ok = not (added or removed or changed)
    if not quiet:
        print("inputs/ manifest: %d files recorded, %d present" % (rec["n_files"], len(now)))
        print("  tree digest recorded %s" % rec["digest"][:16])
        print("  tree digest now      %s  %s" % (digest(now)[:16], "MATCH" if ok else "DRIFT"))
        for lab, xs in (("changed", changed), ("added", added), ("removed", removed)):
            for x in xs:
                print("    %-8s %s" % (lab, x))
    return ok


def current_digest() -> str:
    """What a run should record in run.json."""
    return digest(scan())


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true", help="record the current inputs/ as the baseline")
    a = ap.parse_args()
    if a.write:
        write()
    else:
        ok = verify()
        sys.exit(0 if ok is not False else 1)
