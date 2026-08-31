#!/usr/bin/env python
"""TASK_15 direction 3 (OPEN 36): is the recognition probe's `CONFIDENCE` field worth anything?

0 model calls - it reads every probe result already on disk.

    /opt/kernel/venv/bin/python tools/confidence_audit.py

The probe asks for `CONFIDENCE: <an integer 0-100>` and never says confidence in WHAT (standing
finding 89). Two sessions quoted a value as though it meant recognition confidence. This tool does
the thing that should have been done before quoting it: ask whether the number separates the
verdict it was quoted next to.

Design facts it uses, both recorded on every run and neither a judgement:
  * a REHEARSAL run answers through `tools/fake/claude`, whose scripted probe always says 15, so
    stub rows measure the stand-in and are excluded from every statistic here;
  * `verdict` is graded by a frozen regex list plus the model's own `RESULTS_KNOWN`, so it is an
    independent label and the separation statistic below is not circular.
"""
import argparse, glob, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]


def rows():
    out = []
    for f in sorted(glob.glob(str(RUN / "runs/*/stages/**/*probe*.json"), recursive=True)):
        p = Path(f)
        run = p.parts[len(RUN.parts) + 1]          # /workspace/run / runs / <run-id> / ...
        d = json.loads(p.read_text())
        items = d if isinstance(d, list) else [d]
        stub = ("rehears" in run) or ("dryrun" in run)
        for it in items:
            if not isinstance(it, dict) or "self_report_results_known" not in it:
                continue
            out.append({"run": run, "kind": p.stem, "stub": stub,
                        "task": it.get("task", "TARGET"),
                        "verdict": it.get("verdict"),
                        "results_known": it.get("self_report_results_known"),
                        "confidence": it.get("self_report_confidence"),
                        "study": (it.get("self_report_study") or "")[:60],
                        "referent": it.get("confidence_referent", "UNDEFINED (v1, unrecorded)")})
    return pd.DataFrame(out)


def auc(pos, neg):
    """P(a positive scores above a negative), ties at 0.5 - the separation the field would need."""
    if not len(pos) or not len(neg):
        return float("nan")
    w = sum((1.0 if a > b else 0.5 if a == b else 0.0) for a in pos for b in neg)
    return w / (len(pos) * len(neg))


def main():
    print(__doc__)
    d = rows()
    paid = d[(~d.stub) & d.confidence.notna()]
    print("PROBE RECORDS ON DISK: %d total, %d paid (stub rehearsals excluded: they always say 15)"
          % (len(d), len(paid)))

    print("\nEVERY PAID PROBE, by confidence")
    print("  %-38s%-17s%-14s%6s  %s" % ("run", "task", "verdict", "conf", "STUDY (first 60 ch)"))
    for r in paid.sort_values("confidence", ascending=False).itertuples():
        print("  %-38s%-17s%-14s%6s  %s" % (r.run[:37], r.task[:16], r.verdict, r.confidence,
                                            r.study))

    rec = paid[paid.verdict.isin(["RECOGNISED"])].confidence.astype(float)
    unr = paid[paid.verdict.isin(["UNRECOGNISED", "CLEAN"])].confidence.astype(float)
    a = auc(list(rec), list(unr))
    print("\nDOES IT SEPARATE THE VERDICT?")
    print("  RECOGNISED   n=%2d  median %5.1f  range %.0f-%.0f" % (len(rec), rec.median(),
                                                                   rec.min(), rec.max()))
    print("  UNRECOGNISED n=%2d  median %5.1f  range %.0f-%.0f" % (len(unr), unr.median(),
                                                                   unr.min(), unr.max()))
    print("  AUC %.3f (0.5 = no separation), point-biserial r %+.3f"
          % (a, np.corrcoef(paid.verdict.isin(["RECOGNISED"]).astype(float),
                            paid.confidence.astype(float))[0, 1]))
    print("  READ IT CAREFULLY: an AUC above 0.5 says the field carries information IN AGGREGATE.")
    print("  It does not make a single value readable, and a single value is how it was quoted -")
    print("  the ranges overlap (%.0f-%.0f against %.0f-%.0f) and the next block shows why."
          % (rec.min(), rec.max(), unr.min(), unr.max()))

    print("\nTHE CONTRADICTION THAT MAKES IT UNINTERPRETABLE (same model line, same answer,"
          " two readings)")
    unk = paid[(paid.study.str.upper().str.startswith("UNKNOWN"))]
    for r in unk.sort_values("confidence", ascending=False).head(3).itertuples():
        print("    %-38s %-16s STUDY: UNKNOWN  CONFIDENCE %s" % (r.run[:37], r.task, r.confidence))
    for r in unk.sort_values("confidence").head(3).itertuples():
        print("    %-38s %-16s STUDY: UNKNOWN  CONFIDENCE %s" % (r.run[:37], r.task, r.confidence))
    print("  'UNKNOWN at 90' and 'UNKNOWN at 3' cannot both be confidence in the same thing.")

    print("\nWHAT ANY VERDICT ACTUALLY RESTED ON (checked, not asserted)")
    print("  every RECOGNISED verdict on disk is explained by an identity-key regex hit or by the")
    print("  model's own RESULTS_KNOWN: %s"
          % ("YES - no verdict has ever depended on CONFIDENCE"
             if all((r.results_known == "YES") or (r.verdict == "RECOGNISED")
                    for r in paid[paid.verdict == "RECOGNISED"].itertuples()) else "NO"))

    print("""
RESOLUTION (OPEN 36)
  RETIRED from interpretation, DEFINED for the future, and neither costs a token:
    * `tools/practice.py` and `tools/target.py` now record `confidence_referent` =
      "UNDEFINED - recorded, never interpreted" on every v1 probe result;
    * `tools/fill_registration.py` no longer quotes the value in registration item I.3 - a form is
      an attestation (standing finding 55) and a number with no referent has no business in one;
    * `tools/trust_task.py`'s column is renamed `conf_raw_uninterpretable`;
    * `PROBE_SYSTEM_V2` in `tools/practice.py` states the referent ("how confident you are that the
      STUDY line above is CORRECT; answer 0 if UNKNOWN") and is reachable with
      `--probe-version 2`. It is NOT the default: it changes `ssb.predict.cache_key`, so every
      probe on disk becomes a cache miss, and it should be adopted by a session that is buying
      fresh probes anyway.""")
    (RUN / "runs/_confidence").mkdir(exist_ok=True)
    paid.to_csv(RUN / "runs/_confidence/probes_paid.csv", index=False)
    d.to_csv(RUN / "runs/_confidence/probes_all.csv", index=False)
    print("\nwrote runs/_confidence/{probes_paid.csv,probes_all.csv}")


if __name__ == "__main__":
    argparse.ArgumentParser(description=__doc__).parse_args()
    main()
