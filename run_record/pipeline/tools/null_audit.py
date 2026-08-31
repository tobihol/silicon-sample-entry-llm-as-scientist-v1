#!/usr/bin/env python
"""tools/null_audit.py - the permutation null underneath every scoreboard row. 0 model calls.

    /opt/kernel/venv/bin/python tools/null_audit.py                 # every paid, non-target row
    /opt/kernel/venv/bin/python tools/null_audit.py --tasks koetke2024 --perms 2000
    /opt/kernel/venv/bin/python tools/null_audit.py --selftest      # recovers a known answer

WHY. `tools/task_power.py` gives the CEILING above a score - the best an oracle could do given
sampling noise in the human ATEs. Session 16 found, on orchinik2024, that a row can sit two
standard deviations INSIDE a null nobody had computed: the FLOOR beneath a score, i.e. what the
SAME prediction earns against the SAME table when the treatment did nothing. A correlation on a
small table needs both limits or it is not a score (standing finding 93).

WHAT IT DOES. For each (run_id, task_id) it re-reads the run's own stored prediction.csv, loads
the adapter's respondent-level data, shuffles the ARM LABEL across respondents (within
`control_strata` where the adapter declares one, because an arm must sit in exactly one stratum),
recomputes the ATE table with `ssb.task.true_ates` - the same function the carve uses - and
re-scores the unchanged prediction with `ssb.task.score_task`'s own scoring path. That is a null
in which the prediction, the table's shape, the arm sizes and the outcome structure are all held
fixed and only the treatment assignment is destroyed.

READING IT. `z = (observed - null mean) / null SD` and a one-sided p (the share of shuffles at or
beyond the observed value). RMSE is signed the other way: lower is better, so its p is the share
of shuffles at or BELOW. **A row within 2 SD of its own null is flagged** - not wrong, but not
distinguishable from a structured prediction scored against noise, which is a different claim
from the one a bare correlation makes.

The permutation is exact under the sharp null of no effect for any respondent. It does not test
"the predictor is useless"; it tests "this number could not have arisen from a table with no
treatment signal in it".
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(RUN / "tools"))
import ssb  # noqa: E402

OUT = RUN / "runs" / "_null"
METRICS = ["directional_agreement", "spearman_rho", "pearson_r",
           "pearson_r_within_outcomes", "rmse_pp"]
LOWER_IS_BETTER = {"rmse_pp"}


# ------------------------------------------------------------------ scoring one shuffled table
def _score(truth: pd.DataFrame, pred: pd.DataFrame) -> dict:
    d = truth.merge(pred.rename(columns={"ate": "pred"}), on=["condition", "outcome"])
    d = d.rename(columns={"ate": "human", "se": "se_human"})
    S = ssb.score
    return {"directional_agreement": S.directional_agreement(d.pred, d.human),
            "spearman_rho": S.spearman_rho(d.pred, d.human),
            "pearson_r": S.pearson_r(d.pred, d.human),
            "pearson_r_within_outcomes": S.pearson_r_within_outcomes(d),
            "rmse_pp": S.rmse_pp(d.pred, d.human),
            "n_cells": int(len(d))}


def _shuffled(arm: np.ndarray, strata: np.ndarray | None, rng) -> np.ndarray:
    """Permute the arm label. WITHIN stratum where the adapter declares one: tappin2023's arms
    each argue a different policy issue, so a free shuffle would put an arm in several issues at
    once and `true_ates` refuses it. Within-stratum is also the right null there - it destroys
    the assignment while preserving the design."""
    if strata is None:
        return rng.permutation(arm)
    out = arm.copy()
    for s in np.unique(strata):
        m = strata == s
        out[m] = rng.permutation(arm[m])
    return out


def null_for(task: str, preds: dict, perms: int, seed: int, _cache={}) -> tuple[dict, dict]:
    """`perms` shuffled scorecards for one task, against EVERY prediction of that task.

    The shuffled ATE table is the expensive part and it does not depend on the prediction, so
    all of a task's board rows share one set of shuffles. That is also the right statistics:
    two models scored against the same null are directly comparable."""
    if task not in _cache:
        ad = ssb.task.load_adapter(task)
        df = ssb.task.load_dataset(ad).reset_index(drop=True)
        _cache[task] = (ad, df)
    ad, df = _cache[task]
    d = df.copy()
    arm = d["_arm"].to_numpy()
    strata = (d[ad["control_strata"]].astype(str).to_numpy()
              if ad.get("control_strata") else None)
    rng = np.random.default_rng(seed)
    out = {k: [] for k in preds}
    for _ in range(perms):
        d["_arm"] = _shuffled(arm, strata, rng)
        t = ssb.task.true_ates(d, ad)
        for k, p in preds.items():
            out[k].append(_score(t, p))
    return ({k: pd.DataFrame(v) for k, v in out.items()},
            {"n_respondents": int(len(df)), "n_arms": int(len(set(arm))),
             "strata": ad.get("control_strata")})


def verdicts(observed: dict, null: pd.DataFrame) -> pd.DataFrame:
    out = []
    for m in METRICS:
        v, col = observed.get(m), null[m].dropna().to_numpy()
        mu, sd = float(np.mean(col)), float(np.std(col, ddof=1))
        if v is None or not np.isfinite(v) or not len(col):
            out.append({"metric": m, "observed": v, "null_mean": mu, "null_sd": sd,
                        "z": np.nan, "p": np.nan, "verdict": "NA"})
            continue
        if m in LOWER_IS_BETTER:
            z = (mu - v) / sd if sd else np.nan
            p = float((col <= v).mean())
        else:
            z = (v - mu) / sd if sd else np.nan
            p = float((col >= v).mean())
        # z is signed so that POSITIVE always means "better than a no-signal table" - including
        # for RMSE, where lower is better. A negative z beyond -2 is therefore not a pass: it says
        # the score is WORSE than what the same prediction earns against a table with no treatment
        # signal in it, which for RMSE is what under-dispersion looks like (finding 34): a shuffled
        # table's ATEs are pure noise and small, and so are ours.
        out.append({"metric": m, "observed": float(v), "null_mean": mu, "null_sd": sd,
                    "z": float(z), "p": p,
                    "verdict": ("WITHIN 2 SD OF NULL" if abs(z) < 2 else
                                "clear of null" if z > 0 else "WORSE THAN NULL")})
    return pd.DataFrame(out)


# ------------------------------------------------------------------------------- self-test
def selftest() -> None:
    """A known answer, per standing finding 90: build a table whose treatment truly does nothing,
    and check that a prediction of it sits INSIDE its own null; then add real signal and check the
    same prediction rule sits outside. Nothing here compares two implementations of one convention.

    The trap this self-test hit while being written, and which is the point of writing it: a
    "good predictor" built as `observed ATE + small noise` scores z = +3.4 against the null even
    when tau = 0, because it has copied the table's own SAMPLING noise. A prediction must be built
    from the TRUE effects, never from the realised ones, or the null is being asked about a
    predictor that cannot exist.
    """
    m, k, n = 6, 8, 400
    for tau, expect in ((0.0, "centred"), (6.0, "clear")):
        rng = np.random.default_rng(7)
        true = rng.normal(0, tau, (k, m))                      # arm x outcome, in pp
        arms = ["control"] + [f"a{i}" for i in range(k)]
        cond = np.array([arms[r % (k + 1)] for r in range(n * (k + 1))])
        d = pd.DataFrame({"cond": cond})
        for j2 in range(m):
            eff = np.array([0.0 if c == "control" else true[arms.index(c) - 1, j2] for c in cond])
            d[f"y{j2}"] = 50 + eff + rng.normal(0, 12, len(d))
        ad = {"dataset": "selftest", "condition_col": "cond",
              "arms": {a: a for a in arms}, "control_arms": ["control"],
              "outcomes": {f"y{j2}": {"col": f"y{j2}", "lo": 0, "hi": 100} for j2 in range(m)}}
        d["_arm"] = d["cond"]
        truth = ssb.task.true_ates(d, ad)
        pred = truth[["condition", "outcome"]].copy()
        pred["ate"] = [true[arms.index(c) - 1, int(o[1:])] for c, o in
                       zip(pred.condition, pred.outcome)]
        pred["ate"] = pred.ate + rng.normal(0, 1.0, len(pred))   # knows the TRUTH, not the table
        obs = _score(truth, pred)
        nl, arm0, r2 = [], d["_arm"].to_numpy(), np.random.default_rng(11)
        for _ in range(200):
            d["_arm"] = r2.permutation(arm0)
            nl.append(_score(ssb.task.true_ates(d, ad), pred))
        v = verdicts(obs, pd.DataFrame(nl)).set_index("metric")
        z = float(v.loc["pearson_r_within_outcomes", "z"])
        ok = (abs(z) < 2) if expect == "centred" else (z > 4)
        print("  tau=%.1f  r_within observed %+.3f  null %+.3f +- %.3f  z=%+.2f  -> want %s  %s"
              % (tau, v.loc["pearson_r_within_outcomes", "observed"],
                 v.loc["pearson_r_within_outcomes", "null_mean"],
                 v.loc["pearson_r_within_outcomes", "null_sd"], z, expect,
                 "OK" if ok else "FAIL"))
        assert ok, "selftest failed at tau=%.1f (z=%+.2f)" % (tau, z)
    print("  selftest OK: with no true effect an oracle prediction is INSIDE its own null; with "
          "real effects the same rule is outside it")


# ------------------------------------------------------------------------------------- main
def rows_to_audit(tasks: list[str] | None) -> pd.DataFrame:
    sb = pd.read_csv(ssb.gates.SCOREBOARD)
    sb = sb[(sb.stub.astype(str).str.lower() == "false") & (sb.task_id != "TARGET")]
    sb = sb[~sb.note.astype(str).str.startswith("QUARANTINED")]
    if tasks:
        sb = sb[sb.task_id.isin(tasks)]
    keep = []
    for r in sb.itertuples():
        p = RUN / "runs" / r.run_id / "tasks" / r.task_id / "prediction.csv"
        if p.exists():
            keep.append({"run_id": r.run_id, "task_id": r.task_id, "pred": p, "note": str(r.note),
                         "n_cells": int(r.n_cells),
                         **{m: getattr(r, m) for m in METRICS}})
    return pd.DataFrame(keep)


def main(tasks, perms, seed, quick):
    OUT.mkdir(parents=True, exist_ok=True)
    todo = rows_to_audit(tasks)
    if quick:                       # one row per task: fast smoke test, not the deliverable
        todo = todo.sort_values("run_id").drop_duplicates("task_id")
    print("null audit: %d scoreboard row(s) over %d task(s), %d shuffles each\n"
          % (len(todo), todo.task_id.nunique(), perms))
    allv, meta = [], {}
    for task, grp in todo.groupby("task_id"):
        t0 = time.time()
        preds = {r.run_id: pd.read_csv(r.pred) for r in grp.itertuples()}
        nulls, info = null_for(task, preds, perms, seed)
        meta[task] = info
        print("%-16s  %d respondents, %d arms, %d row(s), %.0fs"
              % (task, info["n_respondents"], info["n_arms"], len(preds), time.time() - t0))
        for r in grp.itertuples():
            v = verdicts({m: getattr(r, m) for m in METRICS}, nulls[r.run_id])
            v.insert(0, "task_id", task)
            v.insert(0, "run_id", r.run_id)
            allv.append(v)
            flag = v[v.verdict == "WITHIN 2 SD OF NULL"].metric.tolist()
            print("   %-36s %s" % (r.run_id,
                                   ("FLAG " + ",".join(flag)) if flag else "all rows clear"))
            for x in v.itertuples():
                print("      %-26s obs %+8.4f   null %+7.4f +- %6.4f   z %+7.2f  p %.4f  %s"
                      % (x.metric, x.observed, x.null_mean, x.null_sd, x.z, x.p, x.verdict))
    V = pd.concat(allv, ignore_index=True)
    V.to_csv(OUT / "null_audit.csv", index=False)
    (OUT / "meta.json").write_text(json.dumps({"perms": perms, "seed": seed, "tasks": meta,
                                               "at": time.strftime("%Y-%m-%dT%H:%M:%S")}, indent=1))

    print("\n" + "=" * 100)
    print("SUMMARY - a row WITHIN 2 SD of its own permutation null is not distinguishable from a "
          "structured\nprediction scored against noise. It is not wrong; it is unsupported.\n")
    for m in METRICS:
        s2 = V[V.metric == m]
        print("  %-28s %2d of %2d rows within 2 SD, %2d WORSE than null   (null SD %.3f-%.3f)"
              % (m, int((s2.verdict == "WITHIN 2 SD OF NULL").sum()), len(s2),
                 int((s2.verdict == "WORSE THAN NULL").sum()), s2.null_sd.min(), s2.null_sd.max()))
    print("\nby task - null SD of the two rows the campaign quotes, and what is flagged on EVERY "
          "row of that task:")
    print("  %-16s %6s %5s   %-9s %-9s   %s" % ("task", "arms", "cells", "SD(rho)",
                                                "SD(r_wthn)", "always-flagged"))
    for t, s2 in V.groupby("task_id"):
        flagged = [m for m in METRICS
                   if len(s2[s2.metric == m])
                   and (s2[s2.metric == m].verdict == "WITHIN 2 SD OF NULL").all()]
        print("  %-16s %6d %5d   %-9.3f %-9.3f   %s"
              % (t, meta[t]["n_arms"] - 1,
                 int(todo[todo.task_id == t].n_cells.iloc[0]) if "n_cells" in todo else 0,
                 s2[s2.metric == "spearman_rho"].null_sd.mean(),
                 s2[s2.metric == "pearson_r_within_outcomes"].null_sd.mean(),
                 ", ".join(flagged) or "-"))
    print("\nwritten: %s" % (OUT / "null_audit.csv"))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--tasks", nargs="*", default=None)
    ap.add_argument("--perms", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=20260822)
    ap.add_argument("--quick", action="store_true",
                    help="one run per task - the null is a property of the table, not the model")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        raise SystemExit(0)
    raise SystemExit(main(a.tasks, a.perms, a.seed, a.quick))
