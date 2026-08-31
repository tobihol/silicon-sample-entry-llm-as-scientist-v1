#!/usr/bin/env python
"""How wide will the prompt experiment's arm-clustered interval be if we add N more arms?

    /opt/kernel/venv/bin/python tools/arm_power_projection.py

The `reason` treatment (OPEN 24) died on its interval, not on its point estimate: +0.0491
r-within with a 2,000-resample arm-clustered 95% CI of [-0.0221, +0.1054] over the 66 arms the
five carved tasks own. Finding 60c measured that such an interval narrows in the number of ARMS
(half-width ~ n^-0.5) and not in draws, so the only way to decide it is more arms.

This is the gate the operator asked for BEFORE any call: measure the scaling on the arms we
already own, extrapolate it to the arm counts the new datasets would buy, and say whether the
question becomes decidable. It makes no model call.

Two projections are printed because the new arms are not shaped like the old ones. tappin2023
contributes 48 arms of ONE cell each; the five carved tasks contribute 66 arms of 9-24 cells
each. The subsample scaling below resamples whole arms from the existing pool, so it answers
"what if we had more arms LIKE these"; the cell-thinned variant repeats the same scaling after
reducing every arm to a single randomly chosen cell, which is the pessimistic end of the range.
The truth for a mixed pool sits between them, and the realised interval is reported in the
session report against these projections.
"""
import json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(RUN / "tools"))
import prompt_experiment as PE  # noqa: E402

B = 600                      # resamples per subsample draw (the CI itself, not the scaling fit)
REPS = 12                    # subsample draws per size
RNG = np.random.default_rng(20260817)


def halfwidth(a, b, met="r_within", nboot=B, rng=RNG):
    """Arm-clustered bootstrap half-width of metric(a) - metric(b), same machinery as
    tools/prompt_experiment.py (which uses 2,000 resamples; fewer here because the scaling fit
    averages over REPS subsamples)."""
    arms = sorted(set(a.arm) & set(b.arm))
    ia = {k: g.index.values for k, g in a.groupby("arm")}
    ib = {k: g.index.values for k, g in b.groupby("arm")}
    vals = []
    for _ in range(nboot):
        pick = rng.choice(len(arms), len(arms), replace=True)
        va = PE.metrics(a.loc[np.concatenate([ia[arms[i]] for i in pick])])[met]
        vb = PE.metrics(b.loc[np.concatenate([ib[arms[i]] for i in pick])])[met]
        if np.isfinite(va) and np.isfinite(vb):
            vals.append(va - vb)
    lo, hi = np.percentile(vals, [2.5, 97.5])
    return (hi - lo) / 2


def thin_to_one_cell(f, rng):
    """One cell per arm, but the SAME outcome within a task - which is the shape tappin2023's 48
    arms have (one 7-point agreement item, one cell per arm). Thinning to a RANDOM cell per arm
    instead makes every outcome group a singleton and `pearson_r_within_outcomes` undefined, which
    is a property of the metric and not of the projection."""
    keep = []
    for t, g in f.groupby("task"):
        outs = sorted(g.outcome.unique())
        o = outs[rng.integers(len(outs))]
        keep.append(g[g.outcome == o])
    return pd.concat(keep)


def scaling(a, b, sizes, label, thin=False):
    rows = []
    for n in sizes:
        hs = []
        for r in range(REPS):
            rng = np.random.default_rng(1000 * n + r)
            arms = sorted(set(a.arm) & set(b.arm))
            pick = set(rng.choice(arms, min(n, len(arms)), replace=False))
            aa, bb = a[a.arm.isin(pick)].reset_index(drop=True), b[b.arm.isin(pick)].reset_index(drop=True)
            if thin:
                aa = thin_to_one_cell(aa, rng).reset_index(drop=True)
                bb = thin_to_one_cell(bb, rng).reset_index(drop=True)
            hs.append(halfwidth(aa, bb, rng=rng))
        rows.append({"n_arms": n, "halfwidth": float(np.mean(hs)), "sd": float(np.std(hs))})
    d = pd.DataFrame(rows)
    k, c = np.polyfit(np.log(d.n_arms), np.log(d.halfwidth), 1)
    print("\n%s: halfwidth = %.3f x n^%.3f   (fit on n = %s)"
          % (label, np.exp(c), k, ", ".join(map(str, sizes))))
    for r in d.itertuples():
        print("   n=%3d  halfwidth %.4f  (sd over %d subsamples %.4f)" % (r.n_arms, r.halfwidth, REPS, r.sd))
    return float(np.exp(c)), float(k), d


def augment(a, b, k, rng, tag="pseudo", cells=1):
    """The pool we will actually have: the 66 real arms with all their cells, PLUS k arms of ONE
    cell each sharing one outcome - the shape tappin2023 (48) and a hackenburg issue (73) add.

    Each pseudo-arm is a real (task, outcome, arm) cell relabelled into a new single-outcome
    pseudo-task, so it carries a real (pred, human) pair and a real treatment delta. The
    assumption, stated rather than hidden: the new task's arms behave like the arms we own. That
    is what makes this a PROJECTION and not a measurement, and the realised interval is reported
    against it afterwards."""
    if k <= 0:
        return a, b
    arms = sorted(set(a.arm) & set(b.arm))
    pick = rng.choice(arms, k, replace=True)
    ea, eb = [], []
    for i, arm in enumerate(pick):
        ga, gb = a[a.arm == arm], b[b.arm == arm]
        outs = sorted(set(ga.outcome) & set(gb.outcome))
        take = list(rng.permutation(outs))[:cells]
        for c, o in enumerate(take):
            ra, rb = ga[ga.outcome == o].iloc[[0]].copy(), gb[gb.outcome == o].iloc[[0]].copy()
            for r in (ra, rb):
                r["task"], r["outcome"] = tag, "%s_item%d" % (tag, c)
                r["arm"] = "%s|arm%03d" % (tag, i)
            ea.append(ra)
            eb.append(rb)
    return (pd.concat([a] + ea, ignore_index=True), pd.concat([b] + eb, ignore_index=True))


SCENARIOS = [("nothing new", []),
             ("tappin 48 arms x 1 cell", [(48, 1)]),
             ("tappin 48 arms x 2 cells", [(48, 2)]),
             ("tappin(48x2) + hackenburg(73x1)", [(48, 2), (73, 1)]),
             ("tappin(48x2) + hackenburg(73x4)", [(48, 2), (73, 4)]),
             ("tappin(48x2) + hackenburg(73x4) + a 2nd 73x4 issue", [(48, 2), (73, 4), (73, 4)])]


def mixed_projection(f, bframe, delta, scenarios=SCENARIOS):
    """The pool we will actually have, per candidate carve. This is the projection that decides
    whether to spend: the `as-is` and `cell-thinned` scalings above bracket it but neither is it,
    because the real pool is 66 rich arms PLUS the new task's arms and the pooled metric is
    computed over CELLS as well as clustered on arms."""
    print("   MIXED POOL projection (%d subsample draws each, |delta| = %.4f):" % (REPS, abs(delta)))
    rows = []
    for name, adds in scenarios:
        hs = []
        for r in range(REPS):
            rng = np.random.default_rng(7000 + 13 * r + len(name))
            aa, bb = f, bframe
            for j, (k, c) in enumerate(adds):
                aa, bb = augment(aa, bb, k, rng, tag="pseudo%d" % j, cells=c)
            hs.append(halfwidth(aa, bb, rng=rng))
        hw, n = float(np.mean(hs)), 66 + sum(k for k, _ in adds)
        rows.append({"scenario": name, "n_arms": n, "n_new_cells": sum(k * c for k, c in adds),
                     "halfwidth": hw, "sd": float(np.std(hs)), "decidable": bool(abs(delta) > hw)})
        print("      %-52s n=%3d  +%4d cells  half-width %.4f (sd %.4f)  %s"
              % (name, n, sum(k * c for k, c in adds), hw, np.std(hs),
                 "EXCLUDES 0" if abs(delta) > hw else "includes 0"))
    return rows


def main():
    base_run = RUN / "runs/20260815-practice-01"
    tasks = [t for t in PE.TASKS if (base_run / "tasks" / t / "prediction.csv").exists()]
    b = PE.base_frame(base_run, tasks)
    out = {}
    for tag, arm_run, bframe in [
            ("opus  reason", RUN / "runs/20260816-promptexp-reason", b),
            ("fable reason", RUN / "runs/20260816-promptexp-fable-reason",
             PE.base_frame(RUN / "runs/20260815-practice-02-fable", tasks))]:
        f = PE.arm_frame(base_run, arm_run, tasks)
        n_arms = len(set(f.arm) & set(bframe.arm))
        delta = PE.metrics(f)["r_within"] - PE.metrics(bframe)["r_within"]
        print("\n=== %s ===  %d arms, delta r_within %+0.4f" % (tag, n_arms, delta))
        full = halfwidth(f, bframe, nboot=2000)
        print("   measured half-width at %d arms: %.4f  -> %s"
              % (n_arms, full, "EXCLUDES 0" if abs(delta) > full else "includes 0"))
        c1, k1, _ = scaling(f, bframe, [20, 30, 40, 50, 66], "as-is (arms like the 5 carved tasks)")
        c2, k2, _ = scaling(f, bframe, [20, 30, 40, 50, 66], "cell-thinned (1 cell per arm)", thin=True)
        row = {"tag": tag, "n_arms": n_arms, "delta_r_within": delta, "halfwidth_now": full,
               "mixed": mixed_projection(f, bframe, delta)}
        for label, (c, k) in {"asis": (c1, k1), "thin": (c2, k2)}.items():
            for n in (114, 129, 186, 201):
                row["hw_%s_%d" % (label, n)] = c * n ** k
        print("   PROJECTION (point estimate held fixed at %+0.4f):" % delta)
        print("      %-28s%10s%10s%10s%10s" % ("arms", "114", "129", "186", "201"))
        for label, name in (("asis", "as-is"), ("thin", "cell-thinned")):
            hs = [row["hw_%s_%d" % (label, n)] for n in (114, 129, 186, 201)]
            print("      %-28s" % name + "".join("%10.4f" % h for h in hs))
            print("      %-28s" % "  decidable?" + "".join(
                "%10s" % ("YES" if abs(delta) > h else "no") for h in hs))
        out[tag] = row
    (RUN / "runs" / "_scratch" / "arm_power_projection.json").write_text(json.dumps(out, indent=1))
    print("\n114 = 66 + tappin2023's 48.  129 = +the 3 arms a hackenburg pilot issue would add "
          "beyond\n186/201 = 66 + 48 + a 72-arm hackenburg issue (with/without its extra arms).")
    return out


if __name__ == "__main__":
    main()
