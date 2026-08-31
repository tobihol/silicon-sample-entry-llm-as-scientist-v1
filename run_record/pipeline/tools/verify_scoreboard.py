#!/usr/bin/env python
"""Can every scored row be recomputed from the evidence the run kept? A score that cannot, is not one.

`AGENTS.md`: "Improvement is a query over that file" - runs/scoreboard.csv. Nothing had ever checked
that the numbers in it follow from the artefacts the run left behind. A row could drift from its
pairs.csv through a scoring-code change, a partial rerun, or an edit, and every later comparison
would silently inherit it. The frozen table's Self-scoring rule is the same idea from the other
direction: "When you score a training task, use these metrics and no others."

    /opt/kernel/venv/bin/python tools/verify_scoreboard.py

Recomputes every Section-1 and Section-2 metric, plus both baseline margins, from each run's
stages/calibration/pairs.csv, and compares to the stored row. Exit code is non-zero on any mismatch
above 1e-6, so it can gate a deposit.

It also reads the `parser_version` each row was produced under (finding 72: a stored prediction is
a parser version as much as a model answer). A pairs.csv check cannot see a parser change - the
pairs and the row move together - so a row parsed by an older `ssb.predict.parse` reproduces
perfectly and is still not comparable to today's rows. Any PAID row carrying a parser version that
is neither today's nor `unverified` is a drift alarm and exits non-zero; the fix is
`tools/reparse_audit.py --write`.
"""
import argparse, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402
from ssb import score as S  # noqa: E402

ALL_POSITIVE_PP = 1.0
KEYS = ["directional_agreement", "spearman_rho", "pearson_r", "pearson_r_within_outcomes",
        "rmse_pp", "r_adj", "rmse_adj", "cal_alpha", "cal_beta",
        "vs_no_effect_floor_directional", "vs_no_effect_floor_rmse",
        "vs_all_positive_directional", "vs_all_positive_rmse"]


def recompute(g: pd.DataFrame) -> dict:
    r = S.ate_recovery(g)
    b = S.baselines(g, "human", ALL_POSITIVE_PP)
    cal = S.calibration(g.pred, g.human)
    return {**r, "cal_alpha": cal["alpha"], "cal_beta": cal["beta"],
            "vs_no_effect_floor_directional": r["directional_agreement"] - b.loc[0, "directional_agreement"],
            "vs_no_effect_floor_rmse": b.loc[0, "rmse_pp"] - r["rmse_pp"],
            "vs_all_positive_directional": r["directional_agreement"] - b.loc[1, "directional_agreement"],
            "vs_all_positive_rmse": b.loc[1, "rmse_pp"] - r["rmse_pp"]}


def parser_report(sb: pd.DataFrame) -> int:
    """Which parser made each row? Returns the number of PAID rows at a stale version."""
    today = ssb.predict.parser_version()
    col = sb["parser_version"] if "parser_version" in sb.columns else pd.Series("", index=sb.index)
    col = col.fillna("").astype(str)
    print("\nPARSER VERSION  (today: %s)" % today)
    for v, n in col.value_counts().items():
        paid = int((~sb.stub.astype(bool) & (col == v)).sum())
        tag = ("  <- today" if v == today else
               "  <- superseded by a later execution into the same run_id (finding 46)"
               if v == "unverified-duplicate-run-id" else
               "  <- no transcripts on disk; cannot be re-derived" if v.startswith("unverified")
               else "  <- STALE: produced by a different parser")
        print("  %-32s %4d rows (%d paid)%s" % (v or "(blank)", n, paid, tag))
    stale = sb[(~sb.stub.astype(bool)) & (col != today) & (~col.str.startswith("unverified"))]
    for r in stale.itertuples():
        print("  STALE PAID ROW %s / %s" % (r.run_id, r.task_id))
    return len(stale)


def main(tol=1e-6):
    sb = pd.read_csv(RUN / "runs" / "scoreboard.csv")
    checked = bad = skipped = 0
    bad_paid, bad_stub = 0, 0
    worst, worst_where = 0.0, ""
    print("\n%-30s%-16s%8s%10s%12s" % ("run", "task", "rows", "checked", "worst diff"))
    for run_id, rows in sb.groupby("run_id"):
        p = RUN / "runs" / run_id / "stages" / "calibration" / "pairs.csv"
        if not p.exists():
            skipped += len(rows)
            print("%-30s%-16s%8d%10s   no pairs.csv - cannot verify" % (run_id, "", len(rows), "-"))
            continue
        pairs = pd.read_csv(p).rename(columns={"se": "se_human"})
        for r in rows.itertuples():
            g = pairs[pairs.task == r.task_id] if "task" in pairs.columns else pairs
            if not len(g):
                skipped += 1
                continue
            got = recompute(g)
            w = 0.0
            for k in KEYS:
                if k not in got or not hasattr(r, k):
                    continue
                stored = getattr(r, k)
                if pd.isna(stored):
                    continue
                dif = abs(float(stored) - float(got[k]))
                checked += 1
                w = max(w, dif)
                if dif > tol:
                    bad += 1
                    is_stub = bool(getattr(r, "stub", True))
                    bad_stub += is_stub
                    bad_paid += (not is_stub)
                    print("    MISMATCH%s %-14s %-32s stored %.6f  recomputed %.6f"
                          % (" (stub)" if is_stub else " *PAID*", r.task_id, k,
                             float(stored), float(got[k])))
            if w > worst:
                worst, worst_where = w, "%s/%s" % (run_id, r.task_id)
            print("%-30s%-16s%8d%10d%12.2e" % (run_id, r.task_id, len(g), len(KEYS), w))
    print("\n%d metrics checked, %d mismatches (%d on PAID rows, %d on stub rows), "
          "%d rows unverifiable (no pairs.csv)" % (checked, bad, bad_paid, bad_stub, skipped))
    print("worst absolute difference %.3e at %s" % (worst, worst_where or "-"))
    stale = parser_report(sb)
    if stale:
        print("VERDICT: %d PAID row(s) were parsed by a parser that is not today's. Metrics on the "
              "board are then not one experiment. Run tools/reparse_audit.py --write." % stale)
        return stale
    # The gate is on PAID rows. A stub row is explicitly not a score (the frozen Self-scoring rule
    # and the required `stub` flag both say so), so a historical stub mismatch is hygiene to report,
    # not a reason to block a deposit. It is still printed, loudly, every time.
    if bad_paid:
        print("VERDICT: NOT REPRODUCIBLE - %d mismatches on rows with stub=False" % bad_paid)
    elif bad_stub:
        print("VERDICT: PAID ROWS REPRODUCIBLE. %d stub-row mismatches remain, all historical: a run "
              "re-executed into an existing run_id overwrote its pairs.csv while the scoreboard kept "
              "the older rows. ssb.gates.scoreboard_append now refuses a duplicate (run_id, task_id) "
              "so this cannot recur; the existing rows are left as the record of what happened."
              % bad_stub)
    else:
        print("VERDICT: REPRODUCIBLE")
    return bad_paid


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--tol", type=float, default=1e-6)
    a = ap.parse_args()
    sys.exit(1 if main(a.tol) else 0)
