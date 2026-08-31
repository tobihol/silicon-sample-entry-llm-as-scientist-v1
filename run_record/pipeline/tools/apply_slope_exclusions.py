#!/usr/bin/env python
"""Apply an adapter's `exclude_from_slope` to a run's already-written pairs.csv.

    /opt/kernel/venv/bin/python tools/apply_slope_exclusions.py [--run runs/<id>] [--write]

`tools/practice.py` now reads `exclude_from_slope` from the adapter, but the two session-10
practice runs were scored before that key existed. The exclusion is a property of the ADAPTER
(a 7-point Likert outcome; LLM-authored stimuli - both written into the adapters' caveats before
either batch was priced), so applying it to an existing pairs.csv is deterministic and
re-derivable, not a re-scoring: no metric on the scoreboard moves, because `in_slope` is read only
by stage 4's `fit_calibration`.
"""
import argparse, json, sys
from pathlib import Path

import pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402


def main(run, write=False):
    p = RUN / run / "stages" / "calibration" / "pairs.csv"
    d = pd.read_csv(p)
    if "out_of_slope_because" not in d.columns:
        d["out_of_slope_because"] = ""
    d["out_of_slope_because"] = d["out_of_slope_because"].astype(object).fillna("")
    changed = []
    for t in d.task.unique():
        why = ssb.task.load_adapter(t).get("exclude_from_slope")
        if not why:
            continue
        m = d.task == t
        if bool(d.loc[m, "in_slope"].any()):
            changed.append((t, int(m.sum())))
            d.loc[m, "in_slope"] = False
            d.loc[m, "out_of_slope_because"] = (
                d.loc[m, "out_of_slope_because"].fillna("").astype(str).str.strip("|")
                .apply(lambda s: "|".join([x for x in [s, why] if x])))
    print("%s: %d pairs, %d in slope after exclusion" % (run, len(d), int(d.in_slope.sum())))
    for t, n in changed:
        print("  excluded %-15s %d pairs" % (t, n))
    if write and changed:
        d.to_csv(p, index=False)
        print("  written")
    return 0


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--run", default="runs/20260817-practice-t67")
    a.add_argument("--write", action="store_true")
    sys.exit(main(a.parse_args().run, a.parse_args().write))
