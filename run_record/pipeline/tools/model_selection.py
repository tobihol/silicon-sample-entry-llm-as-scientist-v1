#!/usr/bin/env python
"""Model SELECTION on the 187-arm pool: which model line should make the target prediction?

    /opt/kernel/venv/bin/python tools/model_selection.py --noise-only     # the draw-noise floor, no challenger needed
    /opt/kernel/venv/bin/python tools/model_selection.py --bootstrap 2000

Session 6 asked what a second model line bought when AGGREGATED (`tools/models_value.py`, finding
48: nothing, and the indicated action is selection rather than aggregation). This tool asks the
selection question on the widened 187-arm base of session 10, under the rule pre-registered in
`runs/_modelsel/PREREG.md`.

Three properties it has because earlier tools had to learn them the hard way:

  - **A line is a LIST of runs.** Tasks 6 and 7 live in their own run directories (session 10), so
    every lookup searches the line's runs in order, like `tools/prompt_experiment.py` does.
  - **Every contrast names both ends** (finding 52). `challenger - incumbent(1 draw)` and
    `challenger - incumbent(3-draw median, the deposited pipeline)` are different questions and are
    printed as different rows.
  - **Lines are compared on the INTERSECTION of the cells they all answered** (finding 70). A model
    that omitted an arm's rows must not be scored on a different grid from one that did not.
"""
import argparse, itertools, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(RUN / "tools"))
import ssb  # noqa: E402
from ssb import score as S  # noqa: E402
from draws_value import draw_frames  # noqa: E402

TASKS = ["voelkel2026", "goldwert2026", "vlasceanu2024", "bbprime2025", "voelkel2024",
         "tappin2023", "hackenburg2025"]
TWIN = "voelkel2026"
B = 2000
SEED = 20260818

# a line: name -> (list of run dirs, draws available in each)
LINES = {
    "claude-opus-5": ["runs/20260815-practice-01", "runs/20260817-practice-t67"],
    "claude-fable-5": ["runs/20260815-practice-02-fable", "runs/20260817-practice-fable-t67"],
    "claude-sonnet-5": ["runs/20260818-practice-sonnet"],
}


def which(runs, t, rel):
    for r in runs:
        if (RUN / r / "tasks" / t / rel).exists():
            return RUN / r
    return None


def truth_of(t):
    for line in LINES.values():
        r = which(line, t, "sealed/truth.csv")
        if r is not None:
            return pd.read_csv(r / "tasks" / t / "sealed" / "truth.csv")
    raise FileNotFoundError("no sealed truth for " + t)


def line_frames(runs, tasks, draws=1):
    """task -> list of per-draw prediction frames for this line."""
    out = {}
    for t in tasks:
        r = which(runs, t, "brief/task.json")
        if r is None:
            continue
        fs = draw_frames(r, t, draws)
        if fs:
            out[t] = fs
    return out


def long_frame(agg, tasks):
    """(task, arm, condition, outcome, pred, human) for one aggregate-per-task dict."""
    out = []
    for t in tasks:
        if t not in agg:
            continue
        truth = truth_of(t)
        m = truth.merge(agg[t][["condition", "outcome", "ate"]].rename(columns={"ate": "pred"}),
                        on=["condition", "outcome"]).rename(columns={"ate": "human"})
        m = m.dropna(subset=["pred"])
        m["task"], m["arm"] = t, t + "|" + m.condition
        out.append(m)
    return pd.concat(out, ignore_index=True)


def metrics(d):
    return {"dir": S.directional_agreement(d.pred, d.human),
            "rho": S.spearman_rho(d.pred, d.human),
            "r_within": S.pearson_r_within_outcomes(d),
            "rmse": S.rmse_pp(d.pred, d.human)}


def restrict(frames, keys):
    """Keep only the (task, condition, outcome) cells every line answered."""
    out = {}
    for name, d in frames.items():
        m = d.merge(keys, on=["task", "condition", "outcome"], how="inner")
        out[name] = m.reset_index(drop=True)
    return out


def boot_delta(a, b, metric, rng, B=B):
    """Cluster bootstrap on the arm of metric(a) - metric(b). a and b share arms and cells."""
    arms = sorted(set(a.arm) & set(b.arm))
    ia = {k: g.index.values for k, g in a.groupby("arm")}
    ib = {k: g.index.values for k, g in b.groupby("arm")}
    out = []
    for _ in range(B):
        pick = rng.choice(len(arms), len(arms), replace=True)
        ra = np.concatenate([ia[arms[i]] for i in pick])
        rb = np.concatenate([ib[arms[i]] for i in pick])
        va, vb = metrics(a.loc[ra])[metric], metrics(b.loc[rb])[metric]
        if np.isfinite(va) and np.isfinite(vb):
            out.append(va - vb)
    o = np.array(out)
    return float(metrics(a)[metric] - metrics(b)[metric]), float(o.mean()), \
        tuple(np.percentile(o, [2.5, 97.5]))


def noise_floor(tasks, line="claude-opus-5", draws=3):
    """SD over the single draws of ONE line, pooled - the reference band every delta is read against."""
    fs = line_frames(LINES[line], tasks, draws)
    tasks = [t for t in tasks if t in fs and len(fs[t]) == draws]
    rows = []
    for i in range(draws):
        d = long_frame({t: fs[t][i] for t in tasks}, tasks)
        m = metrics(d)
        m["draw"] = i
        rows.append(m)
    df = pd.DataFrame(rows)
    return df, {k: float(df[k].std(ddof=1)) for k in ("dir", "rho", "r_within", "rmse")}


def main(bootstrap=0, noise_only=False, tasks=None, lines=None, legacy_pool=False):
    tasks = tasks or TASKS
    rng = np.random.default_rng(SEED)

    df, sd = noise_floor(tasks, "claude-opus-5", 3)
    print("=== draw-to-draw noise floor: 3 paid claude-opus-5 draws, %d tasks ===" % len(tasks))
    print(df.to_string(index=False))
    print("SD over draws: " + "  ".join("%s %.4f" % (k, v) for k, v in sd.items()))
    if noise_only:
        return

    names = lines or list(LINES)
    single, med = {}, {}
    for name in names:
        fs = line_frames(LINES[name], tasks, 3 if name == "claude-opus-5" else 1)
        have = [t for t in tasks if t in fs]
        if len(have) < len(tasks):
            print("!! %s is missing %s" % (name, sorted(set(tasks) - set(have))))
        single[name] = long_frame({t: fs[t][0] for t in have}, have)
        if name == "claude-opus-5":
            med["claude-opus-5 (3-draw median, deposited)"] = long_frame(
                {t: ssb.predict.aggregate(fs[t]) for t in have}, have)

    allf = dict(single)
    allf.update(med)
    keys = None
    for d in allf.values():
        k = d[["task", "condition", "outcome"]]
        keys = k if keys is None else keys.merge(k, on=["task", "condition", "outcome"], how="inner")
    if legacy_pool:
        # The pool session 10 reported (187 arms / 1,354 cells) was this pool minus whatever the
        # part-wise reconstruction defect dropped. Declared in PREREG.md §3 as a robustness check:
        # the ruling is read on the corrected pool, and this shows whether it depends on the fix.
        from test_draw_frames import old_draw_frames  # noqa: E402
        keep = []
        for t in tasks:
            r = which(LINES["claude-opus-5"], t, "brief/task.json")
            fs = old_draw_frames(r, t, 3)
            if not fs:
                continue
            k = fs[0].dropna(subset=["ate"])[["condition", "outcome"]].copy()
            k["task"] = t
            keep.append(k)
        keys = keys.merge(pd.concat(keep), on=["task", "condition", "outcome"], how="inner")
    allf = restrict(allf, keys)
    n_cells = len(keys)
    n_arms = len(set(allf[names[0]].arm))
    print("\n=== pooled on the common grid: %d arms, %d cells, %d tasks ===" % (n_arms, n_cells, len(tasks)))
    hdr = f"{'line':>44}{'dir':>9}{'rho':>9}{'r_within':>10}{'rmse':>9}"
    print(hdr)
    for name, d in allf.items():
        m = metrics(d)
        print(f"{name:>44}{m['dir']:>9.4f}{m['rho']:>+9.4f}{m['r_within']:>10.4f}{m['rmse']:>9.4f}")

    if len(names) >= 3:
        pan = allf[names[0]][["task", "arm", "condition", "outcome", "human"]].copy()
        preds = [allf[n].set_index(["task", "condition", "outcome"]).pred for n in names]
        idx = allf[names[0]].set_index(["task", "condition", "outcome"]).index
        pan["pred"] = np.median(np.vstack([p.reindex(idx).values for p in preds]), axis=0)
        m = metrics(pan)
        print(f"{'EXPLORATORY 3-line panel (median), selects nothing':>44}"
              f"{m['dir']:>9.4f}{m['rho']:>+9.4f}{m['r_within']:>10.4f}{m['rmse']:>9.4f}")

    print("\n=== per task (1 draw each) ===")
    for t in tasks:
        print(" " + t)
        for name in names:
            d = allf[name][allf[name].task == t]
            if not len(d):
                continue
            m = metrics(d)
            print(f"{'  ' + name:>44}{m['dir']:>9.4f}{m['rho']:>+9.4f}{m['r_within']:>10.4f}{m['rmse']:>9.4f}")

    if not bootstrap:
        return
    inc = "claude-opus-5"
    print("\n=== contrasts, arm-clustered %d-resample 95%% CI, BOTH ENDS NAMED ===" % bootstrap)
    print(f"{'contrast':>58}{'metric':>10}{'point':>9}{'bootmean':>10}{'lo':>9}{'hi':>9}{'  vs draw SD'}")
    res = []
    for name in names:
        if name == inc:
            continue
        for base_label, base in [(inc + " (1 draw)", allf[inc]),
                                 ("claude-opus-5 (3-draw median, deposited)",
                                  allf["claude-opus-5 (3-draw median, deposited)"])]:
            for metric in ("r_within", "dir", "rho", "rmse"):
                pt, bm, (lo, hi) = boot_delta(allf[name], base, metric, rng, bootstrap)
                excl = (lo > 0) or (hi < 0)
                det = abs(pt) > sd[metric] and excl
                res.append({"challenger": name, "baseline": base_label, "metric": metric,
                            "point": pt, "boot_mean": bm, "lo": lo, "hi": hi,
                            "excludes_zero": excl, "detected": det})
                print(f"{name + ' - ' + base_label:>58}{metric:>10}{pt:>+9.4f}{bm:>+10.4f}"
                      f"{lo:>+9.4f}{hi:>+9.4f}   {'DETECTED' if det else ('excl0' if excl else 'ns')}")

    print("\n=== leave-one-study-out on the primary metric (r_within), challenger - incumbent(1 draw) ===")
    loso = []
    for name in names:
        if name == inc:
            continue
        for held in tasks:
            keep = [t for t in tasks if t != held]
            a = allf[name][allf[name].task.isin(keep)]
            b = allf[inc][allf[inc].task.isin(keep)]
            d = metrics(a)["r_within"] - metrics(b)["r_within"]
            loso.append({"challenger": name, "held_out": held, "delta_r_within": d})
        s = pd.DataFrame([x for x in loso if x["challenger"] == name])
        print(" %s: " % name + "  ".join("%s %+.4f" % (r.held_out, r.delta_r_within)
                                         for r in s.itertuples()))
        print("   same sign as pooled in %d of %d folds"
              % (int((np.sign(s.delta_r_within) == np.sign(s.delta_r_within.sum())).sum()), len(s)))

    print("\n=== design twin (%s) only, challenger - incumbent(1 draw) ===" % TWIN)
    for name in names:
        if name == inc:
            continue
        a = allf[name][allf[name].task == TWIN]
        b = allf[inc][allf[inc].task == TWIN]
        ma, mb = metrics(a), metrics(b)
        print(" %s: " % name + "  ".join("d%s %+.4f" % (k, ma[k] - mb[k]) for k in ma))

    out = RUN / "runs/_modelsel"
    out.mkdir(parents=True, exist_ok=True)
    tag = "_legacy187" if legacy_pool else ""
    pd.DataFrame(res).to_csv(out / ("contrasts%s.csv" % tag), index=False)
    pd.DataFrame(loso).to_csv(out / ("loso%s.csv" % tag), index=False)
    json.dump({"noise_sd": sd, "n_arms": n_arms, "n_cells": n_cells, "tasks": tasks,
               "lines": names, "bootstrap": bootstrap, "seed": SEED,
               "pool": "legacy187" if legacy_pool else "corrected202"},
              (out / ("pool%s.json" % tag)).open("w"), indent=2)
    print("\nwrote runs/_modelsel/{contrasts%s.csv,loso%s.csv,pool%s.json}" % (tag, tag, tag))


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--bootstrap", type=int, default=0)
    a.add_argument("--noise-only", action="store_true")
    a.add_argument("--tasks", nargs="*", default=None)
    a.add_argument("--lines", nargs="*", default=None)
    a.add_argument("--legacy-pool", action="store_true",
                   help="restrict to the cells session 10's part-wise reconstruction recovered "
                        "(the '187-arm base'), as a robustness check on the corrected pool")
    x = a.parse_args()
    main(x.bootstrap, x.noise_only, x.tasks, x.lines, x.legacy_pool)
