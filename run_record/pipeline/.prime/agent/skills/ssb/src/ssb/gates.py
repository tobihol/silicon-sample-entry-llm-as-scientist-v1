"""ssb.gates - what a run is, when it may stop, and how improvement is measured.

A run is a directory under runs/<run-id>/ with a frozen run.json and a stage log.
It may finish only when every gate below is green or explicitly waived in OPEN.md
with a reason. Gate results and self-scores are appended to runs/scoreboard.csv,
so "did this run improve" is a query, not an impression.
"""
from __future__ import annotations

import contextlib
import csv
import fcntl
import hashlib
import io
import json
import os
import time
from pathlib import Path

import numpy as np
import pandas as pd

from . import spec

RUNS = spec.RUNROOT / "runs"
SCOREBOARD = RUNS / "scoreboard.csv"
LOCKS = RUNS / "_locks"
FROZEN = spec.RUNROOT / ".prime" / "agent" / "APPEND_SYSTEM.md"


# ---------------------------------------------------------------- cross-process locking
# Two sessions on separate ARMS share this mount. `open("a")` + `csv.writerow` is not an
# append-safe protocol for a file that is also READ-MODIFY-WRITTEN (the duplicate check reads
# the whole board before deciding), and nothing here ever held a lock. The contract from here:
#   * every writer of runs/scoreboard.csv goes through scoreboard_append()
#   * scoreboard_append() holds an exclusive flock on runs/_locks/scoreboard.lock for the whole
#     read -> check -> write cycle, and replaces the file atomically (temp in the same dir +
#     os.replace), so a concurrent READER never sees a half-written board and a concurrent
#     WRITER never loses a row or duplicates a header.
# flock is advisory and per-open-file-description; it works across processes on the same host
# and is the right primitive here (one mount, several processes, no NFS).

def _lockfile(name: str) -> Path:
    LOCKS.mkdir(parents=True, exist_ok=True)
    return LOCKS / f"{name}.lock"


@contextlib.contextmanager
def exclusive(name: str, timeout: float = 120.0):
    """Hold an exclusive cross-process lock named `name`. Blocks, then raises rather than
    proceeding unlocked: silently continuing without the lock is the failure this exists to stop."""
    p = _lockfile(name)
    fh = p.open("a+")
    t0 = time.time()
    try:
        while True:
            try:
                fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.time() - t0 > timeout:
                    raise TimeoutError(
                        "could not take lock %s within %.0fs; holder recorded as %r"
                        % (p, timeout, p.read_text()[-200:]))
                time.sleep(0.05)
        fh.seek(0)
        fh.truncate()
        fh.write(json.dumps({"pid": os.getpid(), "arm": arm(),
                             "at": time.strftime("%Y-%m-%dT%H:%M:%S")}))
        fh.flush()
        yield
    finally:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()


def _atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` so that no reader ever observes a partial file. The temp file is
    created in the SAME directory, because os.replace is only atomic within one filesystem."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp.{os.getpid()}.{time.time_ns()}"
    with tmp.open("w", newline="") as fh:
        fh.write(text)
        fh.flush()
        os.fsync(fh.fileno())
    os.replace(tmp, path)


def arm() -> str:
    """Which concurrent arm this process belongs to. Empty when the harness runs single-armed,
    which is the historical behaviour and stays the default."""
    return os.environ.get("SSB_ARM", "").strip()

GATES = {
    "G1_frozen_intact": "APPEND_SYSTEM.md hash equals the value recorded at run start",
    "G2_practice_scored": "every training task scored with ssb.score and leak-audited CLEAN",
    "G3_calibration_fitted": "a shrinkage map was fitted on practice pairs and its diagnostics recorded",
    "G4_card_complete": "card.validate() empty: 208 ATEs, 13 baselines, 27x13 offsets, no NA",
    "G5_validator_pass": "benchmark `make check` PASS or PASS WITH WARNINGS for T1, T2, T3, no FAIL",
    "G6_reconstruction": "recomputing analyses from Tier 1 reproduces the card within tolerance",
    "G7_dispersion": "per-outcome synthetic/human SD ratio within tolerance of 1",
    "G8_recorded": "scoreboard row appended and OPEN.md reviewed",
}

TOL = {"G6_tier3_rmse_pp": 0.10, "G6_tier2mod_rmse_pp": 2.50, "G7_sd_ratio": 0.10}


def frozen_hash() -> str:
    return hashlib.sha256(FROZEN.read_bytes()).hexdigest() if FROZEN.exists() else ""


CLAIMS = RUNS / "_locks" / "run_ids.json"


def namespaced(run_id: str) -> str:
    """A run id that cannot collide with the other arm's. `SSB_ARM=b` turns `20260822-practice`
    into `20260822-practice-b`; an id that already carries the suffix is left alone, so a resume
    names the same directory. Without SSB_ARM nothing changes - single-armed runs keep their ids
    and every historical id stays valid."""
    a = arm()
    if not a:
        return run_id
    return run_id if run_id.endswith("-" + a) else f"{run_id}-{a}"


def claim_run_id(run_id: str) -> dict:
    """Record which arm/pid owns a run id, and refuse an id another ARM already owns.

    `new_run` does mkdir(exist_ok=True) so a crashed session can resume into its own directory
    (finding 46 - safe only because nothing had been appended). Two concurrent arms resuming into
    the same id is a different thing: they would overwrite each other's stages while both later
    appending scoreboard rows, producing exactly the unreproducible rows finding 46 documents.
    The claim is taken under the scoreboard lock, so the check and the write cannot interleave."""
    with exclusive("runids"):
        claims = {}
        if CLAIMS.exists():
            try:
                claims = json.loads(CLAIMS.read_text())
            except Exception:
                claims = {}
        prior = claims.get(run_id)
        me = {"arm": arm(), "pid": os.getpid(), "at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        if prior and prior.get("arm", "") != me["arm"]:
            raise KeyError(
                "run_id %r is claimed by arm %r (pid %s, %s) and this process is arm %r. Two arms "
                "writing one run directory overwrite each other's stages while both append "
                "scoreboard rows. Use a distinct --run-id or set SSB_ARM."
                % (run_id, prior.get("arm"), prior.get("pid"), prior.get("at"), me["arm"]))
        claims[run_id] = me
        _atomic_write(CLAIMS, json.dumps(claims, indent=1, sort_keys=True))
    return me


def new_run(run_id: str | None = None, **params) -> Path:
    run_id = namespaced(run_id or time.strftime("%Y%m%d-%H%M%S"))
    owner = claim_run_id(run_id)
    d = RUNS / run_id
    (d / "stages").mkdir(parents=True, exist_ok=True)
    (d / "run.json").write_text(json.dumps(
        {"run_id": run_id, "started": time.strftime("%Y-%m-%dT%H:%M:%S"),
         "spec_sha256": spec.load()["spec_sha256"], "frozen_sha256": frozen_hash(),
         "arm": owner["arm"], "pid": owner["pid"],
         "params": params}, indent=1))
    return d


def record(run_dir, gate: str, passed: bool, detail: str = "") -> dict:
    """Record one gate result. Unknown gate names are refused - the gate list is the contract."""
    if gate not in GATES:
        raise KeyError(f"{gate!r} is not a gate; the list is {sorted(GATES)}")
    p = Path(run_dir) / "gates.json"
    g = json.loads(p.read_text()) if p.exists() else {}
    g[gate] = {"passed": bool(passed), "detail": detail, "at": time.strftime("%H:%M:%S")}
    p.write_text(json.dumps(g, indent=1))
    return g


def check_reconstruction(crd, tier1: pd.DataFrame) -> dict:
    """Gate G6 evidence, in pp: does the deposit say what the card predicted?"""
    from . import synth
    rec = synth.recompute(tier1)
    a = crd.tier3().merge(rec["tier3"], on=["condition", "outcome"], suffixes=("_c", "_r"))
    a["d"] = [spec.to_pp(r.ate_r - r.ate_c, r.outcome) for r in a.itertuples()]
    m = crd.tier2_moderator().merge(
        rec["tier2_moderator"], on=["condition", "moderator", "moderator_level", "outcome"],
        suffixes=("_c", "_r"))
    m["d"] = [spec.to_pp(r.mean_r - r.mean_c, r.outcome) for r in m.itertuples()]
    return {"tier3_rmse_pp": float(np.sqrt((a.d ** 2).mean())),
            "tier3_max_pp": float(a.d.abs().max()),
            "tier2mod_rmse_pp": float(np.sqrt((m.d ** 2).mean())),
            "tier2mod_max_pp": float(m.d.abs().max())}


def verdict(run_dir) -> dict:
    p = Path(run_dir) / "gates.json"
    g = json.loads(p.read_text()) if p.exists() else {}
    missing = [k for k in GATES if k not in g]
    failed = [k for k, v in g.items() if not v["passed"]]
    return {"complete": not missing, "missing": missing, "failed": failed,
            "may_finish": not missing and not failed}


SCOREBOARD_COLS = [
    "run_id", "stage", "stub", "task_id", "n_cells", "directional_agreement", "spearman_rho",
    "pearson_r", "pearson_r_within_outcomes", "rmse_pp", "r_adj", "rmse_adj",
    "cal_alpha", "cal_beta", "shrinkage_factor",
    "vs_no_effect_floor_directional", "vs_no_effect_floor_rmse",
    "vs_all_positive_directional", "vs_all_positive_rmse", "leak_verdict", "note",
    "parser_version"]


def scoreboard_append(row: dict) -> Path:
    """Append one (run, task) row. `stub` is a REQUIRED structural flag, not a note:
    a scripted dry-run number must never be confusable with a practice score, and a
    reader filtering the scoreboard should not have to parse prose to tell them apart.

    PARALLEL SAFETY. The whole read -> duplicate check -> write cycle runs under an exclusive
    flock on runs/_locks/scoreboard.lock, and the board is replaced atomically rather than
    appended in place. Without the lock two concurrent arms can (a) both pass the duplicate
    check for the same (run_id, task_id) and both write it, and (b) interleave inside one
    buffered write, producing a row that no parser can read. Both are demonstrated as red paths
    in tools/test_gates.py."""
    if "stub" not in row:
        raise KeyError("scoreboard row must declare stub=True/False explicitly")
    cols = SCOREBOARD_COLS
    # A stored prediction is a parser version as much as a model answer (finding 72): the board
    # held rows produced by two versions of ssb.predict.parse and nothing said so. Every row now
    # records the parser that made it, so `tools/reparse_audit.py` can tell a re-derivable row from
    # a stale one instead of re-deriving the whole board to find out.
    if not row.get("parser_version"):
        from . import predict as _p
        row = {**row, "parser_version": _p.parser_version()}
    RUNS.mkdir(parents=True, exist_ok=True)
    with exclusive("scoreboard"):
        prior = SCOREBOARD.read_text() if SCOREBOARD.exists() else ""
        # A (run_id, task_id) is the identity of a scored result, and it was not enforced.
        # Re-running into an existing run_id overwrites stages/calibration/pairs.csv while the
        # scoreboard keeps the OLD rows, so the file that AGENTS.md calls the measure of
        # improvement ends up holding numbers that no artefact on disk supports. Found by
        # tools/verify_scoreboard.py on 20260815-rehearsal-03, which carries ten rows for five
        # tasks with disagreeing in_slope flags and one pairs.csv.
        if prior and row.get("run_id") and row.get("task_id"):
            try:
                _sb = pd.read_csv(io.StringIO(prior))
                dup = _sb[(_sb.run_id.astype(str) == str(row["run_id"]))
                          & (_sb.task_id.astype(str) == str(row["task_id"]))]
            except Exception:
                dup = None
            if dup is not None and len(dup):
                raise KeyError(
                    "scoreboard already has %d row(s) for (%s, %s). Re-running into an existing "
                    "run_id overwrites that run's artefacts but not its scoreboard rows, leaving "
                    "numbers nothing can reproduce. Use a new --run-id, or delete the prior rows "
                    "deliberately and say so in the run report."
                    % (len(dup), row["run_id"], row["task_id"]))
        buf = io.StringIO()
        # "\n", not csv's default "\r\n": the board on disk is LF (it has been rewritten by
        # pandas by the quarantine and reparse tools), and a file with two line endings is one
        # more thing a reader has to be told about.
        w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore", lineterminator="\n")
        if not prior:
            w.writeheader()
        w.writerow({k: row.get(k, "") for k in cols})
        text = prior + buf.getvalue()
        if prior and not prior.endswith("\n"):
            text = prior + "\n" + buf.getvalue()
        _atomic_write(SCOREBOARD, text)
    return SCOREBOARD


def list_runs() -> str:
    if not RUNS.exists():
        return "runs: none"
    out = []
    for d in sorted(p for p in RUNS.iterdir() if p.is_dir()):
        v = verdict(d)
        out.append(f"  {d.name}: {'READY' if v['may_finish'] else 'open'} "
                   f"(missing {len(v['missing'])}, failed {len(v['failed'])})")
    return "runs:\n" + ("\n".join(out) or "  none")


def scoreboard_tail(n: int = 8) -> str:
    if not SCOREBOARD.exists():
        return "scoreboard: empty"
    d = pd.read_csv(SCOREBOARD).tail(n)
    keep = [c for c in ["run_id", "task_id", "directional_agreement", "spearman_rho",
                        "rmse_pp", "cal_beta", "leak_verdict"] if c in d.columns]
    return "scoreboard (last %d):\n" % len(d) + d[keep].to_string(index=False)
