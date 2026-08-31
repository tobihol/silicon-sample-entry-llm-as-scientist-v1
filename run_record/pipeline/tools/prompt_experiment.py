#!/usr/bin/env python
"""Score the prompt information/reasoning experiment against the rules in runs/_promptexp/PREREG.md.

    /opt/kernel/venv/bin/python tools/prompt_experiment.py

Reads each arm's carved predictions, scores them against the same sealed truth with the same
`ssb.score` functions the scoreboard uses, and applies the pre-registered verdict rules: an effect
counts only if it exceeds the measured draw-to-draw SD of the untreated prompt AND its 2,000-
resample arm-clustered bootstrap interval excludes zero; adoption additionally requires the same
sign in >= 4 of 5 leave-one-study-out folds and no regression on the design twin `voelkel2026`.

The base arm is `20260815-practice-01` draw 0 - byte-identical prompts, already paid for, so the
reference costs nothing and is matched draw-for-draw rather than against a 3-draw median (which
would confound the treatment with the aggregation finding 43 measured as worthless).
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(RUN / "tools"))
import ssb  # noqa: E402
from ssb import score as S  # noqa: E402
from draws_value import draw_frames, TASKS  # noqa: E402

ARMS = ["reason", "reason_rank", "anontitles", "noitems"]
# Session 10 widened the arm base (runs/_openexp24/PREREG.md): tasks 6 and 7 were carved into
# their own runs, so a task's base draw, its sealed truth and its treatment arm may each live in a
# different run directory. Every lookup below therefore searches a LIST of runs and takes the
# first that has the file, which leaves the five original tasks resolving exactly as before.
EXTRA_TASKS = ["tappin2023", "hackenburg2025"]
EXTRA_BASE = {"opus": "runs/20260817-practice-t67",
              "fable": "runs/20260817-practice-fable-t67"}
EXTRA_ARM = {"opus": {"reason": "runs/20260817-promptexp-reason-t67"},
             "fable": {"reason": "runs/20260817-promptexp-fable-reason-t67"}}
ADOPTABLE = {"reason", "reason_rank"}
# measured on the three already-paid base draws by tools/draw_scaling.py, quoted in PREREG.md
DRAW_SD = {"dir": 0.0011, "rho": 0.0046, "r_within": 0.0189, "rmse": 0.0321}
TWIN = "voelkel2026"
B = 2000
RNG = np.random.default_rng(20260816)


def _runs(x):
    return [Path(p) if not isinstance(p, Path) else p for p in ([x] if isinstance(x, (str, Path)) else x)]


def _which(runs, t, rel):
    """The first run directory that has this task's file. One task, one artefact, one run."""
    for r in _runs(runs):
        if (Path(r) / "tasks" / t / rel).exists():
            return Path(r)
    return None


def truth_of(base_run, t):
    r = _which(base_run, t, "sealed/truth.csv")
    if r is None:
        raise FileNotFoundError("no sealed truth for %s in %s" % (t, base_run))
    return pd.read_csv(r / "tasks" / t / "sealed" / "truth.csv")


def arm_frame(base_run, arm_run, tasks):
    """One long (task, arm, outcome, pred, human) frame for a treatment run."""
    out = []
    for t in tasks:
        r = _which(arm_run, t, "prediction.csv")
        if r is None:
            continue          # an arm may cover a subset of tasks; pair_up restricts the base
        pr = pd.read_csv(r / "tasks" / t / "prediction.csv").rename(columns={"ate": "pred"})
        m = truth_of(base_run, t).rename(columns={"ate": "human"}).merge(
            pr[["condition", "outcome", "pred"]], on=["condition", "outcome"]).dropna(subset=["pred"])
        m["task"], m["arm"] = t, t + "|" + m.condition
        out.append(m)
    return pd.concat(out, ignore_index=True) if out else None


def base_frame(base_run, tasks, draw=0):
    out = []
    for t in tasks:
        r = _which(base_run, t, "brief/task.json")
        fs = draw_frames(r, t, draw + 1)
        pr = fs[draw].rename(columns={"ate": "pred"})
        m = truth_of(base_run, t).rename(columns={"ate": "human"}).merge(
            pr[["condition", "outcome", "pred"]], on=["condition", "outcome"]).dropna(subset=["pred"])
        m["task"], m["arm"] = t, t + "|" + m.condition
        out.append(m)
    return pd.concat(out, ignore_index=True)


def pair_up(a, b):
    """Restrict two frames to the cells BOTH answered.

    An answer can be incomplete (claude-fable-5 omitted one arm's four rows from a 292-cell
    table), and a contrast computed over two different grids is not a contrast. Intersecting is
    also a no-op whenever both arms are complete, which is every comparison before this session."""
    key = ["task", "condition", "outcome"]
    common = a[key].merge(b[key], on=key)
    return (a.merge(common, on=key).reset_index(drop=True),
            b.merge(common, on=key).reset_index(drop=True))


def metrics(d):
    return {"dir": S.directional_agreement(d.pred, d.human), "rho": S.spearman_rho(d.pred, d.human),
            "r_within": S.pearson_r_within_outcomes(d), "rmse": S.rmse_pp(d.pred, d.human)}


def boot(a, b, met):
    arms = sorted(set(a.arm) & set(b.arm))
    ia = {k: g.index.values for k, g in a.groupby("arm")}
    ib = {k: g.index.values for k, g in b.groupby("arm")}
    vals = []
    for _ in range(B):
        pick = RNG.choice(len(arms), len(arms), replace=True)
        va = metrics(a.loc[np.concatenate([ia[arms[i]] for i in pick])])[met]
        vb = metrics(b.loc[np.concatenate([ib[arms[i]] for i in pick])])[met]
        if np.isfinite(va) and np.isfinite(vb):
            vals.append(va - vb)
    return float(np.mean(vals)), float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5))


def main(base="runs/20260815-practice-01", prefix="runs/20260816-promptexp-", tag="opus",
         extra=True):
    # The extra-task runs are keyed by MODEL LINE, and the tag names the results file. Matching
    # them on the exact tag silently dropped tasks 6 and 7 whenever the tag carried a suffix
    # (`--tag opus_recheck` scored 1,101 cells over 5 tasks and printed no warning), so the line
    # is resolved by prefix and the resolution is printed.
    line = next((k for k in EXTRA_BASE if tag == k or tag.startswith(k + "_")), None)
    base_run = [RUN / base] + ([RUN / EXTRA_BASE[line]] if extra and line else [])
    if extra and line is None:
        print("!! tag %r matches no model line in EXTRA_BASE - tasks 6 and 7 are NOT included"
              % tag)
    all_tasks = TASKS + (EXTRA_TASKS if extra else [])
    tasks = [t for t in all_tasks if _which(base_run, t, "prediction.csv")]
    bframe = base_frame(base_run, tasks)
    bm = metrics(bframe)
    print(f"base = {base} draw 0, {len(bframe):,} cells over {len(tasks)} tasks")
    print("  " + "  ".join(f"{k} {v:+.4f}" for k, v in bm.items()))

    rows, verdicts = [], {}
    for arm in ARMS:
        d = [RUN / (prefix + arm)] + ([RUN / EXTRA_ARM[line][arm]]
                                      if extra and line and arm in EXTRA_ARM.get(line, {}) else [])
        f = arm_frame(base_run, d, tasks) if any(x.exists() for x in d) else None
        if f is None:
            print(f"\n{arm}: NOT RUN")
            continue
        f, bf = pair_up(f, bframe)
        dropped = len(bframe) - len(bf)
        am, bm = metrics(f), metrics(bf)
        print(f"\n=== {arm} ({len(f):,} cells" +
              (f", {dropped} dropped as unanswered by one side" if dropped else "") + ") ===")
        print(f"{'metric':<10}{'base':>10}{'arm':>10}{'delta':>10}{'draw SD':>10}"
              f"{'boot mean':>11}{'  95% CI':>18}  verdict")
        det = {}
        for met in ("dir", "rho", "r_within", "rmse"):
            delta = am[met] - bm[met]
            bmn, lo, hi = boot(f, bf, met)
            excl = lo * hi > 0
            big = abs(delta) > DRAW_SD[met]
            det[met] = {"delta": delta, "boot_mean": bmn, "ci": [lo, hi],
                        "excludes_zero": bool(excl), "exceeds_draw_sd": bool(big),
                        "detected": bool(excl and big)}
            print(f"{met:<10}{bm[met]:>10.4f}{am[met]:>10.4f}{delta:>+10.4f}{DRAW_SD[met]:>10.4f}"
                  f"{bmn:>+11.4f}   [{lo:+.4f},{hi:+.4f}]  "
                  f"{'DETECTED' if (excl and big) else ('ns' if not excl else 'below draw SD')}")
            rows.append({"arm": arm, "metric": met, "base": bm[met], "value": am[met],
                         "delta": delta, "boot_mean": bmn, "ci_lo": lo, "ci_hi": hi,
                         "draw_sd": DRAW_SD[met], "detected": bool(excl and big)})

        # leave-one-study-out
        loso = {}
        print(f"  LOSO on the primary metric (r_within), each task held OUT of the pool:")
        for t in tasks:
            keep = [x for x in tasks if x != t]
            fa, fb = f[f.task.isin(keep)], bf[bf.task.isin(keep)]
            loso[t] = metrics(fa)["r_within"] - metrics(fb)["r_within"]
            print(f"    without {t:<15}{loso[t]:>+8.4f}")
        same_sign = sum(1 for v in loso.values() if np.sign(v) == np.sign(det["r_within"]["delta"]))
        need_same = int(np.ceil(0.8 * len(loso)))      # 4 of 5 in session 8, 6 of 7 here

        # design twin
        twin = {}
        if TWIN in tasks:
            fa, fb = f[f.task == TWIN], bf[bf.task == TWIN]
            twin = {m: metrics(fa)[m] - metrics(fb)[m] for m in ("dir", "rho", "r_within", "rmse")}
            print(f"  design twin {TWIN}: " + "  ".join(f"{k} {v:+.4f}" for k, v in twin.items()))

        ok_adopt = (arm in ADOPTABLE
                    and det["r_within"]["delta"] > DRAW_SD["r_within"]
                    and det["r_within"]["excludes_zero"]
                    and same_sign >= need_same
                    and twin.get("r_within", -1) >= 0 and twin.get("rho", -1) >= 0
                    and not any(det[m]["detected"] and
                                (det[m]["delta"] < 0 if m != "rmse" else det[m]["delta"] > 0)
                                for m in ("dir", "rho", "rmse")))
        verdicts[arm] = {"metrics": det, "loso_r_within": loso, "loso_same_sign": same_sign,
                         "loso_needed": need_same, "n_tasks": len(loso), "n_cells": int(len(f)),
                         "twin": twin, "adoptable": arm in ADOPTABLE, "ADOPT": bool(ok_adopt)}
        print(f"  PREREG verdict: {'ADOPT' if ok_adopt else ('DO NOT ADOPT' if arm in ADOPTABLE else 'diagnostic only')}"
              f"   (LOSO same sign {same_sign}/{len(loso)}, need {need_same})")

    out = RUN / "runs/_promptexp"
    pd.DataFrame(rows).to_csv(out / f"results_{tag}.csv", index=False)
    (out / f"results_{tag}.json").write_text(json.dumps(
        {"base_run": base, "base": bm, "arms": verdicts}, indent=1))
    print(f"\nwritten: {out}/results_{tag}.csv, {out}/results_{tag}.json")
    return 0


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--base", default="runs/20260815-practice-01")
    a.add_argument("--prefix", default="runs/20260816-promptexp-")
    a.add_argument("--tag", default="opus", help="names the results files, so a second model's "
                                                 "run cannot overwrite the first's")
    a.add_argument("--no-extra", dest="extra", action="store_false",
                   help="exclude the session-10 tasks (6 and 7) - the 5-task pool session 8 saw")
    n = a.parse_args()
    sys.exit(main(n.base, n.prefix, n.tag, n.extra))
