#!/usr/bin/env python
"""Quarantine a scoreboard row: keep the evidence, refuse the score.

    /opt/kernel/venv/bin/python tools/quarantine_row.py --run-id <id> --task <task> \
        --reason "recognised (probe named the authors and self-reported RESULTS_KNOWN: YES)"

A recognition probe that fires AFTER the prediction calls leaves a run whose transcripts, pairs and
prediction are all valid artefacts and whose METRICS must not be read as a score - a predictor that
recalls "all five arms were null" passes a null task by memory, and passing by memory is not
calibration. `runs/_trusttask/PREREG.md` pre-registered the consequence before any call: the row
stays, with `stub=False`, every metric NA, and a note that says why.

This is the only sanctioned way to blank a row. It never deletes anything: the run directory, its
pairs.csv, its prediction.csv and its transcripts are untouched, the metrics it computed are printed
here and kept in the run's own summary.json, and the board keeps a backup at
runs/scoreboard.csv.pre-quarantine-<run_id>-<task>.
"""
import argparse, sys
from pathlib import Path

import pandas as pd

RUN = Path(__file__).resolve().parents[1]
BOARD = RUN / "runs" / "scoreboard.csv"
METRICS = ["directional_agreement", "spearman_rho", "pearson_r", "pearson_r_within_outcomes",
           "rmse_pp", "r_adj", "rmse_adj", "cal_alpha", "cal_beta", "shrinkage_factor",
           "vs_no_effect_floor_directional", "vs_no_effect_floor_rmse",
           "vs_all_positive_directional", "vs_all_positive_rmse"]


def main(run_id, task, reason, apply=False):
    sb = pd.read_csv(BOARD)
    sel = (sb.run_id == run_id) & (sb.task_id == task)
    if not sel.any():
        raise SystemExit("no row for (%s, %s)" % (run_id, task))
    print("row as scored (kept in runs/%s/stages/practice/summary.json):" % run_id)
    print(sb.loc[sel, ["task_id"] + METRICS].T.to_string())
    if not apply:
        print("\nDRY RUN - pass --apply to blank the metrics on the board.")
        return 0
    bak = BOARD.with_name("scoreboard.csv.pre-quarantine-%s-%s" % (run_id, task))
    if not bak.exists():
        bak.write_text(BOARD.read_text())
    for k in METRICS:
        sb.loc[sel, k] = pd.NA
    sb.loc[sel, "note"] = "QUARANTINED (%s) - NOT A SCORE; %s" % (reason, sb.loc[sel, "note"].iloc[0])
    sb.to_csv(BOARD, index=False)
    print("\nquarantined %d row(s); backup -> %s" % (int(sel.sum()), bak))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--task", required=True)
    ap.add_argument("--reason", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    sys.exit(main(a.run_id, a.task, a.reason, a.apply))
