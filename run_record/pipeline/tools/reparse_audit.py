#!/usr/bin/env python
"""Re-derive every scoreboard row through TODAY's parser, and record which parser made it.

    /opt/kernel/venv/bin/python tools/reparse_audit.py            # read-only audit
    /opt/kernel/venv/bin/python tools/reparse_audit.py --write     # rewrite the board + artefacts

Standing finding 72 established that a stored prediction is a parser version as much as a model
answer: `20260817-practice-t67`'s hackenburg2025 prediction disagrees with today's parser on 23 of
292 cells, because session 10 hardened `ssb.predict.parse` after that file was written. `AGENTS.md`
says improvement is a query over `runs/scoreboard.csv`, and a board whose rows were produced by
several parser versions is a query over an inconsistent file.

This re-parses every transcript on disk with the parser that exists today - same brief (including a
variant's transformed brief and its title aliases), same whole-brief part union as
`draws_value.draw_frames`, same median aggregation, same `ssb.task.score_task` - and compares the
13 stored metrics to the re-derived ones. `--write` then makes the board one parser version:

  * runs/scoreboard.csv.pre-reparse   the board as it was, untouched, kept forever
  * every re-derived row's metrics replaced by the re-derived values
  * `parser_version` column on every row (a row with no transcripts on disk cannot be re-derived
    and is marked `unverified`, never silently stamped with today's version)
  * the run's own `tasks/<t>/prediction.csv` and `stages/calibration/pairs.csv` updated in place
    with a `.pre-reparse` backup beside each, so `tools/verify_scoreboard.py` still reproduces the
    row from the run's own evidence.

Nothing here calls a model: every transcript is on disk and already paid for.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402

METRICS = ["directional_agreement", "spearman_rho", "pearson_r", "pearson_r_within_outcomes",
           "rmse_pp", "r_adj", "rmse_adj", "cal_alpha", "cal_beta", "shrinkage_factor",
           "vs_no_effect_floor_directional", "vs_no_effect_floor_rmse",
           "vs_all_positive_directional", "vs_all_positive_rmse"]
ROUNDING = 5e-7          # "beyond rounding": the board stores ~6 decimals


def _mark_unverified(new, idx, sb):
    """A row with no transcripts cannot be re-derived - but it may already CARRY a version.

    Since session 12 every row is stamped at append time (`ssb.gates.scoreboard_append`), so a
    scripted dry-run row whose transcripts are not in the `transcript_drawN_partM` shape was still
    parsed by a known parser. Overwriting that stamp with `unverified` would throw away the only
    record there is; `unverified` is for a row that has no stamp at all.
    """
    have = "" if "parser_version" not in sb.columns else str(sb.at[idx, "parser_version"] or "")
    if not have or have == "nan":
        new.loc[idx, "parser_version"] = "unverified"


def _note_field(note: str, key: str, default=None):
    for part in str(note).split(";"):
        part = part.strip()
        if part.startswith(key + "="):
            return part.split("=", 1)[1]
    return default


def rebuild(task_dir: Path, run_dir: Path, task: str, draws: int, variant: str):
    """Today's parser over the transcripts this run left, in the run's own prompt shape.

    Each part transcript is parsed against the WHOLE brief (finding 72: today's arm->part split is
    not necessarily the split that was paid for) and the parts are unioned keeping the first
    NON-NULL answer, stably - the same rule `tools/practice.py` applies at call time.
    """
    bpath = task_dir / "brief" / ("task_%s.json" % variant)
    if not bpath.exists():
        bpath = task_dir / "brief" / "task.json"
    b = json.loads(bpath.read_text())
    vmeta = {}
    pp = run_dir / "stages" / "prompt_plans.json"
    if pp.exists():
        vmeta = (json.loads(pp.read_text()).get(task) or {}).get("variant") or {}
    conds = [a["title"] for a in b["arms"]]
    outs = ([o["name"] for o in b["outcomes"]] if isinstance(b["outcomes"], list)
            else list(b["outcomes"]))
    al = vmeta.get("title_aliases") or {}
    conds_acc = conds + [x for c in conds for x in al.get(c, [])]
    back = vmeta.get("rename_back") or {}
    frames = []
    for dr in range(draws):
        got = []
        for f in sorted(task_dir.glob("transcript_draw%d_part*.txt" % dr)):
            g = ssb.predict.parse(f.read_text(), conds_acc, outs)
            if back:
                g["condition"] = g["condition"].map(lambda c: back.get(c, c))
                g = (g.assign(_na=g.ate.isna()).sort_values("_na", kind="stable")
                      .drop_duplicates(["condition", "outcome"], keep="first")
                      .drop(columns="_na"))
            got.append(g)
        if not got:
            return None
        g = pd.concat(got)
        frames.append(g.assign(_na=g.ate.isna()).sort_values("_na", kind="stable")
                       .drop_duplicates(["condition", "outcome"], keep="first")
                       .drop(columns="_na").reset_index(drop=True))
    return ssb.predict.aggregate(frames)


def main(write=False, tol=ROUNDING):
    pv = ssb.predict.parser_version()
    board = RUN / "runs" / "scoreboard.csv"
    sb = pd.read_csv(board)
    out_rows, moved = [], []
    print("parser version (hash of the parsing functions): %s\n" % pv)
    print("%-36s%-15s%7s%7s%12s  %s" % ("run", "task", "cells", "nan", "max|Δmetric|", "verdict"))
    new = sb.copy()
    dup_keys = sb.groupby(["run_id", "task_id"]).size().to_dict()
    if "parser_version" not in new.columns:
        new["parser_version"] = "unverified"
    for idx, r in sb.iterrows():
        run_dir = RUN / "runs" / str(r.run_id)
        task_dir = run_dir / "tasks" / str(r.task_id)
        rec = {"run_id": r.run_id, "task_id": r.task_id, "stub": bool(r.stub),
               "n_cells_stored": r.n_cells}
        if str(r.task_id) == "TARGET":
            # The target row carries no Section-1 metrics (no sealed truth exists for it), so
            # "does it move" is a question about the 208 predicted cells the card was built from,
            # not about a score. Re-parse the stage-5 transcripts and compare to the ate_pp_raw.csv
            # the run wrote: this is the one row where a parser change would move a DEPOSIT.
            st = run_dir / "stages" / "target"
            raw = st / "ate_pp_raw.csv"
            trs = sorted(st.glob("transcript_draw*_part*.txt"))
            if not raw.exists() or not trs:
                rec["status"] = "unverified"
                _mark_unverified(new, idx, sb)
                out_rows.append(rec)
                continue
            b = ssb.predict.target_brief()
            cn = [a["title"] for a in b["arms"]]
            on = ([o["name"] for o in b["outcomes"]] if isinstance(b["outcomes"], list)
                  else list(b["outcomes"]))
            agg = ssb.predict.aggregate([ssb.predict.parse(f.read_text(), cn, on) for f in trs])
            sto = pd.read_csv(raw)
            mm = sto.merge(agg[["condition", "outcome", "ate"]], on=["condition", "outcome"],
                           suffixes=("_stored", "_new"))
            worst = float((mm.ate_stored - mm.ate_new).abs().max()) if len(mm) else float("nan")
            status = "same" if worst <= tol else "MOVED"
            rec.update({"status": status, "worst_metric": "ate_pp_raw (208 cells)",
                        "worst_diff": worst, "n_cells_reparsed": len(mm),
                        "n_nan": int(agg.ate.isna().sum())})
            print("%-36s%-15s%7d%7d%12.2e  %s" % (r.run_id, r.task_id, len(mm),
                                                  rec["n_nan"], worst, status))
            if status == "MOVED":
                moved.append(rec)
                rec["status"] = status = "MOVED-TARGET"      # never rewritten here: a card is REBUILT
            new.loc[idx, "parser_version"] = pv if status == "same" else "STALE-target"
            out_rows.append(rec)
            continue
        if not task_dir.exists() or not list(task_dir.glob("transcript_draw*_part*.txt")):
            rec["status"] = "unverified"
            _mark_unverified(new, idx, sb)
            out_rows.append(rec)
            continue
        draws = int(_note_field(r.note, "draws", 1) or 1)
        variant = _note_field(r.note, "variant", "base") or "base"
        agg = rebuild(task_dir, run_dir, str(r.task_id), draws, variant)
        if agg is None:
            rec["status"] = "unverified"
            _mark_unverified(new, idx, sb)
            out_rows.append(rec)
            continue
        tmp = run_dir / "tasks" / str(r.task_id) / "prediction_reparsed.csv"
        agg[["condition", "outcome", "ate"]].to_csv(tmp, index=False)
        sc = ssb.task.score_task(task_dir, tmp)
        worst, worst_k = 0.0, ""
        for k in METRICS:
            if k not in sc or pd.isna(r.get(k)):
                continue
            dif = abs(float(r[k]) - float(sc[k]))
            if dif > worst:
                worst, worst_k = dif, k
        nan = int(agg.ate.isna().sum())
        status = "same" if worst <= tol else "MOVED"
        # A (run_id, task_id) that appears twice is finding 46's defect, NOT a parser difference:
        # a run re-executed into an existing id overwrote its transcripts while the board kept both
        # sets of rows, so only the LATER row can be re-derived from what is on disk and the earlier
        # one is unverifiable by construction. Re-deriving it would silently overwrite the record of
        # a documented defect with a number from a different execution.
        if status == "MOVED" and dup_keys.get((r.run_id, r.task_id), 0) > 1:
            status = "superseded"
        rec.update({"status": status, "worst_metric": worst_k, "worst_diff": worst,
                    "n_cells_reparsed": len(agg) - nan, "n_nan": nan,
                    **{("new_" + k): sc.get(k) for k in METRICS}})
        if status == "MOVED":
            moved.append(rec)
        out_rows.append(rec)
        print("%-36s%-15s%7d%7d%12.2e  %s" % (r.run_id, r.task_id, len(agg), nan, worst, status))
        if status == "superseded":
            new.loc[idx, "parser_version"] = "unverified-duplicate-run-id"
        elif write:
            for k in METRICS:
                if k in sc and not pd.isna(r.get(k)):
                    new.loc[idx, k] = float(sc[k])
            new.loc[idx, "parser_version"] = pv
            # keep the run's own artefacts consistent with the row (verify_scoreboard.py reads them)
            pred = task_dir / "prediction.csv"
            if pred.exists() and status == "MOVED":
                bak = task_dir / "prediction.csv.pre-reparse"
                if not bak.exists():
                    bak.write_text(pred.read_text())
            if status == "MOVED":
                agg[["condition", "outcome", "ate"]].to_csv(pred, index=False)
                pf = run_dir / "stages" / "calibration" / "pairs.csv"
                if pf.exists():
                    pb = run_dir / "stages" / "calibration" / "pairs.csv.pre-reparse"
                    if not pb.exists():
                        pb.write_text(pf.read_text())
                    pr = pd.read_csv(pf)
                    sel = ((pr.task == r.task_id) if "task" in pr.columns
                           else pd.Series(True, index=pr.index))
                    mp = agg.set_index(["condition", "outcome"]).ate.to_dict()
                    pr.loc[sel, "pred"] = [mp.get(k, np.nan) for k in
                                           zip(pr.loc[sel, "condition"], pr.loc[sel, "outcome"])]
                    pr.to_csv(pf, index=False)
        tmp.unlink()

    d = pd.DataFrame(out_rows)
    n_re = int((d.status != "unverified").sum())
    print("\n%d of %d rows re-derived through parser %s; %d unverifiable (no transcripts on disk)"
          % (n_re, len(d), pv, int((d.status == "unverified").sum())))
    n_sup = int((d.status == "superseded").sum())
    print("%d row(s) MOVED beyond rounding (%.0e); %d superseded (duplicate run_id, finding 46)"
          % (len(moved), tol, n_sup))
    for m in moved:
        print("   %-34s%-15s %s %.6f -> %.6f (Δ %.2e)"
              % (m["run_id"], m["task_id"], m["worst_metric"],
                 float(sb[(sb.run_id == m["run_id"]) & (sb.task_id == m["task_id"])]
                       [m["worst_metric"]].iloc[0]), m["new_" + m["worst_metric"]],
                 m["worst_diff"]))
    outdir = RUN / "runs" / "_reparse"
    outdir.mkdir(exist_ok=True)
    d.to_csv(outdir / "reparse_audit.csv", index=False)
    print("\naudit -> %s" % (outdir / "reparse_audit.csv"))
    if write:
        pre = RUN / "runs" / "scoreboard.csv.pre-reparse"
        if not pre.exists():
            pre.write_text(board.read_text())
            print("old board kept -> %s" % pre)
        cols = [c for c in new.columns if c != "parser_version"] + ["parser_version"]
        new[cols].to_csv(board, index=False)
        print("board rewritten -> %s (one parser version, %s)" % (board, pv))
    else:
        print("READ-ONLY: nothing written to the board. Re-run with --write to make it one version.")
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--tol", type=float, default=ROUNDING)
    a = ap.parse_args()
    main(a.write, a.tol)
