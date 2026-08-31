#!/usr/bin/env python
"""Where does the practice score saturate in the number of draws? Measured, not argued.

Standing finding 43 compared ONE draw against the deposited 3-draw median and found the median
fractionally worse on RMSE. That is two points of a curve read at its ends. This reads every point:
for k = 1, 2, 3 it scores EVERY subset of the paid draws (3 singletons, 3 pairs, 1 triple), pools
over the five tasks, and puts an arm-clustered interval on the k -> k' contrast. It also extends the
pool with the `claude-fable-5` draw bought in session 6, so a 4-member mixed pool can be read as a
fourth point - the aggregation finding 48 priced.

    /opt/kernel/venv/bin/python tools/draw_scaling.py

Costs nothing: every transcript is on disk and already paid for. Four rules the campaign brief
imposes are honoured here rather than in prose: the metric is declared before the run (all four
Section-1 rows, with `pearson_r_within_outcomes` primary), the contrast is reported
leave-one-study-out, `voelkel2026` is reported separately because it is the design twin, and a
negative result is reported as a result.
"""
import argparse, itertools, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(RUN / "tools"))
import ssb  # noqa: E402
from ssb import score as S  # noqa: E402
from draws_value import draw_frames, TASKS  # noqa: E402

B = 2000
RNG = np.random.default_rng(20260816)


def pooled_frame(run, task_frames, tasks):
    """One long frame of (task, arm, outcome, pred, human) for a chosen aggregate per task."""
    out = []
    for t in tasks:
        truth = pd.read_csv(run / "tasks" / t / "sealed" / "truth.csv")
        m = truth.merge(task_frames[t][["condition", "outcome", "ate"]]
                        .rename(columns={"ate": "pred"}), on=["condition", "outcome"])
        m = m.rename(columns={"ate": "human"}).dropna(subset=["pred"])
        m["task"], m["arm"] = t, t + "|" + m.condition
        out.append(m)
    return pd.concat(out, ignore_index=True)


def metrics(d):
    return {"dir": S.directional_agreement(d.pred, d.human),
            "rho": S.spearman_rho(d.pred, d.human),
            "r_within": S.pearson_r_within_outcomes(d),
            "rmse": S.rmse_pp(d.pred, d.human)}


def boot_delta(a, b, metric):
    """Cluster bootstrap on the arm of metric(a) - metric(b); a and b share their arms."""
    arms = sorted(set(a.arm))
    ia = {k: g.index.values for k, g in a.groupby("arm")}
    ib = {k: g.index.values for k, g in b.groupby("arm")}
    out = []
    for _ in range(B):
        pick = RNG.choice(len(arms), len(arms), replace=True)
        ra = np.concatenate([ia[arms[i]] for i in pick])
        rb = np.concatenate([ib[arms[i]] for i in pick])
        va, vb = metrics(a.loc[ra])[metric], metrics(b.loc[rb])[metric]
        if np.isfinite(va) and np.isfinite(vb):
            out.append(va - vb)
    return float(np.mean(out)), tuple(np.percentile(out, [2.5, 97.5]))


def main(run="runs/20260815-practice-01", fable_run="runs/20260815-practice-02-fable", draws=3,
         tasks_override=None):
    run, frun = RUN / run, RUN / fable_run
    per_task = {}
    for t in (tasks_override or TASKS):
        fs = draw_frames(run, t, draws)
        if not fs:
            continue
        ff = draw_frames(frun, t, 1) if frun.exists() else []
        per_task[t] = {"opus": fs, "fable": ff}
    tasks = sorted(per_task)
    print(f"{len(tasks)} tasks, {draws} opus draws each"
          + (f", + 1 fable draw on {sum(bool(v['fable']) for v in per_task.values())}" ))

    rows = []
    curves = {}
    for k in range(1, draws + 1):
        subsets = list(itertools.combinations(range(draws), k))
        vals = []
        for sub in subsets:
            agg = {t: ssb.predict.aggregate([per_task[t]["opus"][i] for i in sub]) for t in tasks}
            d = pooled_frame(run, agg, tasks)
            m = metrics(d)
            m.update({"k": k, "subset": "".join(map(str, sub)), "model": "opus"})
            vals.append(m)
            rows.append(m)
        curves[k] = pd.DataFrame(vals)
    # the 4th point: 3 opus draws + the fable draw, aggregated as one panel
    mixed = None
    if all(per_task[t]["fable"] for t in tasks):
        agg = {t: ssb.predict.aggregate(per_task[t]["opus"] + per_task[t]["fable"]) for t in tasks}
        mixed = pooled_frame(run, agg, tasks)
        m = metrics(mixed)
        m.update({"k": 4, "subset": "012+fable", "model": "opus3+fable1"})
        rows.append(m)

    print("\n=== the curve: mean over all subsets of size k, pooled over tasks ===")
    print(f"{'k':>3}{'subsets':>9}{'dir':>9}{'rho':>9}{'r_within':>10}{'rmse':>8}"
          f"{'  (spread over subsets: dir/rho/r_within/rmse)'}")
    for k in range(1, draws + 1):
        c = curves[k]
        print(f"{k:>3}{len(c):>9}{c['dir'].mean():>9.4f}{c['rho'].mean():>+9.4f}"
              f"{c['r_within'].mean():>10.4f}{c['rmse'].mean():>8.4f}"
              f"   {c['dir'].std():.4f}/{c['rho'].std():.4f}/{c['r_within'].std():.4f}/{c['rmse'].std():.4f}")
    if mixed is not None:
        m = metrics(mixed)
        print(f"{4:>3}{1:>9}{m['dir']:>9.4f}{m['rho']:>+9.4f}{m['r_within']:>10.4f}"
              f"{m['rmse']:>8.4f}   (3 opus draws + 1 claude-fable-5 draw)")

    print("\n=== the draw-to-draw NOISE FLOOR (SD over the 3 single draws, pooled) ===")
    c1 = curves[1]
    for met in ("dir", "rho", "r_within", "rmse"):
        print(f"  {met:<9} single-draw values {', '.join(f'{v:+.4f}' for v in c1[met])}"
              f"   SD {c1[met].std():.4f}")

    print("\n=== contrast: 3-draw median minus a single draw, cluster-bootstrapped on the arm ===")
    d3 = pooled_frame(run, {t: ssb.predict.aggregate(per_task[t]["opus"]) for t in tasks}, tasks)
    d1 = pooled_frame(run, {t: per_task[t]["opus"][0] for t in tasks}, tasks)
    contrast = {}
    for met in ("dir", "rho", "r_within", "rmse"):
        mean, (lo, hi) = boot_delta(d3, d1, met)
        point = metrics(d3)[met] - metrics(d1)[met]
        contrast[met] = {"point": point, "boot_mean": mean, "ci": [lo, hi]}
        print(f"  {met:<9} point {point:+.4f}   boot mean {mean:+.4f}   CI [{lo:+.4f}, {hi:+.4f}]"
              f"   {'excludes 0' if lo * hi > 0 else 'includes 0'}")

    print("\n=== leave-one-study-out: the same contrast with each task held out ===")
    print(f"{'held out':<15}{'dir':>9}{'rho':>9}{'r_within':>10}{'rmse':>9}")
    loso = []
    for t in tasks:
        keep = [x for x in tasks if x != t]
        a = pooled_frame(run, {x: ssb.predict.aggregate(per_task[x]["opus"]) for x in keep}, keep)
        b = pooled_frame(run, {x: per_task[x]["opus"][0] for x in keep}, keep)
        r = {"held_out": t, **{m: metrics(a)[m] - metrics(b)[m]
                               for m in ("dir", "rho", "r_within", "rmse")}}
        loso.append(r)
        print(f"{t:<15}{r['dir']:>+9.4f}{r['rho']:>+9.4f}{r['r_within']:>+10.4f}{r['rmse']:>+9.4f}")

    print("\n=== the design twin on its own (voelkel2026) ===")
    if "voelkel2026" in tasks:
        a = pooled_frame(run, {"voelkel2026": ssb.predict.aggregate(per_task["voelkel2026"]["opus"])},
                         ["voelkel2026"])
        b = pooled_frame(run, {"voelkel2026": per_task["voelkel2026"]["opus"][0]}, ["voelkel2026"])
        for met in ("dir", "rho", "r_within", "rmse"):
            print(f"  {met:<9} 1 draw {metrics(b)[met]:+.4f} -> 3-draw median {metrics(a)[met]:+.4f}"
                  f"   delta {metrics(a)[met] - metrics(b)[met]:+.4f}")

    out = pd.DataFrame(rows)
    dst = run / "stages" / "calibration" / "draw_scaling.csv"
    out.to_csv(dst, index=False)
    (run / "stages" / "calibration" / "draw_scaling.json").write_text(json.dumps(
        {"contrast_3_minus_1": contrast, "loso": loso}, indent=1))
    print(f"\nwritten: {dst}")
    return 0


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--run", default="runs/20260815-practice-01")
    a.add_argument("--fable-run", default="runs/20260815-practice-02-fable")
    a.add_argument("--draws", type=int, default=3)
    a.add_argument("--tasks", nargs="*", default=None,
                   help="task ids to read from --run (default: the five original practice tasks)")
    n = a.parse_args()
    sys.exit(main(n.run, n.fable_run, n.draws, n.tasks))
