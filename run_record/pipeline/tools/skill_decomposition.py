#!/usr/bin/env python
"""TASK_14 direction 1: is the predictor's message-level skill TOPIC skill or TONE skill?

Pre-registered in `runs/_decomp/PREREG.md` before any number below was computed. 0 model calls -
every prediction it reads is already on disk and already paid for.

    /opt/kernel/venv/bin/python tools/skill_decomposition.py

The question. Session 13 measured `pearson_r_within_outcomes` = 0.059 on koetke2024, whose three arms
differ only in a rhetorical move inside one paragraph, against 0.68-0.76 on tappin2023 and
hackenburg2025, whose arms differ in CONTENT. The target's 16 arms are framings of one topic, so if
within-outcome skill is a function of how different the arms are from one another, that is a
first-order fact about what the deposited card should be expected to score.

The measure (declared in the prereg, section 3): within-task TF-IDF cosine distance between arm
texts, lowercased, stopworded, no stemming; `D_arm(a)` = mean distance from a to the other arms,
`D_task` = mean over unordered pairs. Jaccard distance on content-word sets is reported beside it as
a robustness check and never substituted for it. No embedding model is used: none is available
offline and buying one would make this a paid experiment.

The decomposition (prereg section 4). With p~ and h~ the predicted and human ATEs demeaned inside
each outcome and z() standardising by the task's pooled SDs, an arm's contribution is
`c(a) = mean over that arm's cells of z(p~) z(h~)`, whose cell-mean over a task is exactly that
task's `pearson_r_within_outcomes`. This decomposes the scored row; it does not invent a metric.
"""
import argparse, json, math, re, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
sys.path.insert(0, str(RUN / "tools"))
import ssb                                                              # noqa: E402
from draws_value import draw_frames                                     # noqa: E402
from task_power import TASK_RUNS, table_for                             # noqa: E402

SEED = 20260820
STOP = set("""a about above after again against all am an and any are aren as at be because been
before being below between both but by can cannot could couldn did didn do does doesn doing don down
during each few for from further had hadn has hasn have haven having he her here hers herself him
himself his how i if in into is isn it its itself just me more most mustn my myself no nor not of
off on once only or other ought our ours ourselves out over own same shan she should shouldn so some
such than that the their theirs them themselves then there these they this those through to too
under until up very was wasn we were weren what when where which while who whom why will with won
would wouldn you your yours yourself yourselves s t don ll re ve m""".split())


def tokens(text):
    return [w for w in re.findall(r"[a-z]+", (text or "").lower())
            if len(w) >= 3 and w not in STOP]


def tfidf_distances(texts):
    """Within-task TF-IDF cosine distance matrix, exactly as the prereg defines it."""
    docs = [tokens(t) for t in texts]
    n = len(docs)
    df = {}
    for d in docs:
        for w in set(d):
            df[w] = df.get(w, 0) + 1
    vecs = []
    for d in docs:
        tf = {}
        for w in d:
            tf[w] = tf.get(w, 0) + 1
        v = {w: (c / max(len(d), 1)) * (math.log((1 + n) / (1 + df[w])) + 1) for w, c in tf.items()}
        nrm = math.sqrt(sum(x * x for x in v.values())) or 1.0
        vecs.append({w: x / nrm for w, x in v.items()})
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j:
                keys = set(vecs[i]) & set(vecs[j])
                D[i, j] = 1.0 - sum(vecs[i][w] * vecs[j][w] for w in keys)
    return D


def jaccard_distances(texts):
    sets = [set(tokens(t)) for t in texts]
    n = len(sets)
    D = np.zeros((n, n))
    for i in range(n):
        for j in range(n):
            if i != j and (sets[i] | sets[j]):
                D[i, j] = 1.0 - len(sets[i] & sets[j]) / len(sets[i] | sets[j])
    return D


def arm_distances(texts):
    n = len(texts)
    Dt, Dj = tfidf_distances(texts), jaccard_distances(texts)
    off = ~np.eye(n, dtype=bool)
    return (Dt.sum(1) / (n - 1), Dj.sum(1) / (n - 1),
            float(Dt[off].mean()), float(Dj[off].mean()))


def contributions(pred, human):
    """Per-cell z(p~) z(h~) after demeaning inside each outcome. Cell-mean = r_within."""
    m = pred.merge(human, on=["condition", "outcome"]).dropna(subset=["pred", "human"])
    m["p_dev"] = m.pred - m.groupby("outcome").pred.transform("mean")
    m["h_dev"] = m.human - m.groupby("outcome").human.transform("mean")
    sp, sh = m.p_dev.std(ddof=0), m.h_dev.std(ddof=0)
    m["contrib"] = (m.p_dev / sp) * (m.h_dev / sh) if sp and sh else np.nan
    return m


def task_frames(task, draws=3):
    run = RUN / "runs" / TASK_RUNS[task]
    fr = draw_frames(run, task, draws)
    if not fr:
        fr = draw_frames(run, task, 1)
    pred = ssb.predict.aggregate(fr)[["condition", "outcome", "ate"]].rename(
        columns={"ate": "pred"})
    truth = pd.read_csv(run / "tasks" / task / "sealed" / "truth.csv")[
        ["condition", "outcome", "ate"]].rename(columns={"ate": "human"})
    brief = json.loads((run / "tasks" / task / "brief" / "task.json").read_text())
    return pred, truth, brief


def boot_ci(vals, stat, n=2000, seed=SEED):
    rng = np.random.default_rng(seed)
    out = []
    for _ in range(n):
        ix = rng.integers(0, len(vals), len(vals))
        s = stat(ix)
        if s is not None and np.isfinite(s):
            out.append(s)
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5)), float(np.mean(out))


def ols(X, y):
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return b


def pair_analysis(tasks, draws=3, seed=SEED):
    """POST-HOC, and labelled as such: it is NOT in `runs/_decomp/PREREG.md`.

    The pre-registered specs ask whether a task's average skill tracks its arms' average lexical
    spread, and with nine tasks that is a small-n question. The sharper form of the same question is
    a PAIR question, and it has thousands of data points: inside one outcome, take every ordered pair
    of arms, ask whether the predictor got the sign of the human CONTRAST right, and regress that on
    how lexically similar the two arms are.

    The confound this has to survive is that similar arms may simply have smaller true differences,
    in which case low accuracy on them is noise and not a skill deficit. The shared control mean
    cancels exactly in a contrast (dh = m_i - m_j), so its standard error is reconstructible from
    truth.csv alone, and `t = |dh| / SE(dh)` - how RESOLVABLE the pair is - enters the regression as
    a covariate and defines the `t > 2` subset reported beside it.
    """
    rows = []
    for t in tasks:
        pred, truth, brief = task_frames(t, draws)
        titles = [a["title"] for a in brief["arms"]]
        texts = [a.get("text", "") for a in brief["arms"]]
        Dt = tfidf_distances(texts)
        pos = {ttl: i for i, ttl in enumerate(titles)}
        tr = pd.read_csv(RUN / "runs" / TASK_RUNS[t] / "tasks" / t / "sealed" / "truth.csv")
        tr["v"] = tr.se ** 2 / (1.0 / tr.n_treat + 1.0 / tr.n_control)
        tr = tr.merge(pred, on=["condition", "outcome"], how="left")
        for o, g in tr.groupby("outcome"):
            g = g.dropna(subset=["pred", "ate"]).reset_index(drop=True)
            v_o = float(g.v.mean())
            for i in range(len(g)):
                for j in range(i + 1, len(g)):
                    if g.condition[i] not in pos or g.condition[j] not in pos:
                        continue
                    dh = g.ate[i] - g.ate[j]
                    dp = g.pred[i] - g.pred[j]
                    se = math.sqrt(v_o / g.n_treat[i] + v_o / g.n_treat[j])
                    rows.append({"task": t, "outcome": o,
                                 "dist": Dt[pos[g.condition[i]], pos[g.condition[j]]],
                                 "dh": dh, "dp": dp, "t": abs(dh) / se if se else np.nan,
                                 "correct": 1.0 if dh * dp > 0 else (0.5 if dp == 0 or dh == 0
                                                                     else 0.0)})
    P = pd.DataFrame(rows).dropna()
    print("\n" + "-" * 96)
    print("POST-HOC (not pre-registered): PAIRS OF ARMS - can the predictor order two arms that")
    print("look alike?  %d within-outcome arm pairs over %d tasks" % (len(P), P.task.nunique()))
    res = P[P.t > 2]
    print("   resolvable pairs (|dh| > 2 SE): %d (%.0f%%)" % (len(res), 100 * len(res) / len(P)))
    for name, sub in (("all pairs", P), ("resolvable only", res)):
        q = sub.assign(bin=pd.qcut(sub.dist, 4, labels=["Q1 most alike", "Q2", "Q3",
                                                        "Q4 most different"], duplicates="drop"))
        line = "   %-17s" % name
        for b, gg in q.groupby("bin", observed=True):
            line += "  %s %.3f (n=%d)" % (b, gg.correct.mean(), len(gg))
        print(line)
    for name, sub in (("all pairs", P), ("resolvable only", res)):
        X = np.column_stack([np.ones(len(sub)), sub.dist.values, sub.t.values,
                             pd.get_dummies(sub.task, drop_first=True).astype(float).values])
        y = sub.correct.values
        b = ols(X, y)
        tl = list(sub.task.unique())
        idx = {tt: np.where(sub.task.values == tt)[0] for tt in tl}
        rng = np.random.default_rng(seed)
        bs = []
        for _ in range(1000):
            pick = rng.integers(0, len(tl), len(tl))
            ii = np.concatenate([idx[tl[p]] for p in pick])
            Xi, yi = X[ii], y[ii]
            keep = [c for c in range(Xi.shape[1]) if np.std(Xi[:, c]) > 0 or c == 0]
            try:
                bb = ols(Xi[:, keep], yi)
                bs.append(bb[1])
            except Exception:
                pass
        lo, hi = float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))
        print("   %-17s correct ~ dist + t + task FE:  dist %+.3f [%+.3f, %+.3f]   t %+.4f"
              % (name, b[1], lo, hi, b[2]))
    print("   per task:  %-16s%8s%9s%9s%9s" % ("task", "pairs", "mean d", "%resolv", "acc(res)"))
    for t, d in P.groupby("task"):
        res_t = d[d.t > 2]
        print("              %-16s%8d%9.3f%8.0f%%%9s"
              % (t, len(d), d.dist.mean(), 100 * len(res_t) / len(d),
                 "%.3f" % res_t.correct.mean() if len(res_t) else "-"))
    P.to_csv(RUN / "runs" / "_decomp" / "pairs.csv", index=False)
    T = pd.read_csv(RUN / "runs" / "_decomp" / "tasks.csv")
    agg = P.groupby("task").apply(
        lambda d: pd.Series({"frac_res": (d.t > 2).mean(),
                             "acc_res": d[d.t > 2].correct.mean() if (d.t > 2).any() else np.nan}),
        include_groups=False).reset_index()
    M = T.merge(agg, on="task")
    live = M[M.ceiling_within > 0]
    print("\n   THE MECHANISM, in three correlations over the %d tasks:" % len(M))
    print("      D_task vs the FRACTION of arm pairs the study can resolve : Spearman %+.3f"
          % M.D_task.corr(M.frac_res, method="spearman"))
    print("      D_task vs the within-outcome CEILING                      : Spearman %+.3f"
          % M.D_task.corr(M.ceiling_within, method="spearman"))
    print("      D_task vs ACCURACY on the pairs that ARE resolvable       : Spearman %+.3f (n=%d)"
          % (live.D_task.corr(live.acc_res, method="spearman"), len(live)))
    print("      i.e. arms that look alike make a study that cannot resolve them, not a predictor")
    print("      that cannot order them. Where the contrast is resolvable the predictor scores")
    print("      0.67-1.00 whatever the lexical distance.")
    return P


def target_projection(norm_skill, lo, hi, practice_run="runs/20260815-practice-01"):
    """What within-outcome r should the deposited card expect on the target?

    Two factors, and the honest answer needs both. NORMALISED skill (what fraction of the attainable
    within-outcome r this predictor reaches) comes from the practice tasks. The target's own
    CEILING cannot be computed - its truth is sealed - so it is written as a function of tau, the SD
    of the true within-outcome-demeaned effects, and scanned over the same values
    `tools/forecast_target.py` scans.

    Inside one outcome the shared control mean cancels under demeaning, so with k arms, n per arm in
    Human 1 and outcome SD sigma, the demeaned noise variance is (sigma^2 / n)(1 - 1/k) = the frozen
    design's se_ate^2 / 2 x (1 - 1/k).
    """
    p = pd.read_csv(RUN / practice_run / "stages" / "calibration" / "pairs.csv")
    sd_out = p.se.mean() / np.sqrt(1 / p.n_treat.median() + 1 / p.n_control.median())
    n_half = 18000 / 17 / 2                                             # frozen file design
    se_t = sd_out * np.sqrt(2 / n_half)
    k = 16
    # the (k-1)-divisor spread of the demeaned cells carries the FULL arm-mean variance, so there
    # is no (1 - 1/k) factor here; `tools/tau_estimate.py --selftest` is the red path that fixed it,
    # and that tool - which estimates tau instead of scanning it - supersedes this table.
    noise_w = se_t ** 2 / 2
    tau_practice = float(np.sqrt(max(p.human.var() - (p.se ** 2).mean(), 0)))
    print("\nTARGET PROJECTION of `pearson_r_within_outcomes` (a projection, not a claim)")
    print("   implied outcome SD %.2f pp, Human-1 n/arm %.0f, SE(ATE) %.2f pp, demeaned noise "
          "SD %.2f pp" % (sd_out, n_half, se_t, math.sqrt(noise_w)))
    print("   %-34s%12s%14s" % ("tau (SD of true demeaned effects)", "ceiling", "expected r_within"))
    for tau in (0.5, 1.0, 2.0, tau_practice):
        ceil = math.sqrt(tau ** 2 / (tau ** 2 + noise_w))
        print("   %-34s%12.3f%9.2f [%.2f, %.2f]"
              % ("%.2f pp%s" % (tau, "  (practice-deconvolved)" if tau == tau_practice else ""),
                 ceil, norm_skill * ceil, lo * ceil, hi * ceil))


def main(draws=3):
    tasks = [t for t in TASK_RUNS]
    arm_rows, task_rows = [], []
    for t in tasks:
        pred, truth, brief = task_frames(t, draws)
        cells = contributions(pred, truth)
        titles = [a["title"] for a in brief["arms"]]
        texts = [a.get("text", "") for a in brief["arms"]]
        dt, dj, Dt_task, Dj_task = arm_distances(texts)
        pw = {a["title"]: len(tokens(a.get("text", ""))) for a in brief["arms"]}
        cei = table_for(RUN / "runs" / TASK_RUNS[t] / "tasks" / t / "sealed" / "truth.csv")
        r_within = float(cells.contrib.mean())
        for i, ttl in enumerate(titles):
            g = cells[cells.condition == ttl]
            if not len(g):
                continue
            arm_rows.append({"task": t, "arm": ttl, "n_cells": len(g),
                             "contrib": float(g.contrib.mean()), "D_tfidf": float(dt[i]),
                             "D_jaccard": float(dj[i]), "words": pw[ttl],
                             "log_words": math.log(max(pw[ttl], 1))})
        task_rows.append({"task": t, "n_arms": len(titles), "n_cells": len(cells),
                          "r_within": r_within, "D_task": Dt_task, "D_jaccard": Dj_task,
                          "ceiling_within": cei["within_ceiling_r"],
                          "ceiling_marginal": cei["max_attainable_r"],
                          "mean_abs_human": float(cells.human.abs().mean()),
                          "norm_skill": (r_within / cei["within_ceiling_r"]
                                         if cei["within_ceiling_r"] > 0 else np.nan)})
    A, T = pd.DataFrame(arm_rows), pd.DataFrame(task_rows)

    print("\n" + "=" * 96)
    print("TASK LEVEL - lexical spread of the arms against within-outcome skill")
    print("%-15s%7s%7s%10s%10s%11s%10s%11s" % ("task", "arms", "cells", "D_task", "D_jacc",
                                               "r_within", "ceiling", "norm skill"))
    for r in T.sort_values("D_task").itertuples():
        print("%-15s%7d%7d%10.3f%10.3f%11.3f%10.3f%11s"
              % (r.task, r.n_arms, r.n_cells, r.D_task, r.D_jaccard, r.r_within,
                 r.ceiling_within, "%.3f" % r.norm_skill if np.isfinite(r.norm_skill) else "-"))

    live = T[np.isfinite(T.norm_skill)].reset_index(drop=True)
    print("\nS1 (task level, n = %d live tasks; gligoric2025 excluded - its ceiling is 0)" % len(live))
    for dv in ["r_within", "norm_skill"]:
        y, x = live[dv].values, live.D_task.values
        pear = float(np.corrcoef(x, y)[0, 1])
        spear = float(pd.Series(x).corr(pd.Series(y), method="spearman"))
        lo, hi, mu = boot_ci(y, lambda ix: (np.corrcoef(x[ix], y[ix])[0, 1]
                                            if np.std(x[ix]) > 0 and np.std(y[ix]) > 0 else None))
        print("   %-12s vs D_task:  Pearson %+.3f [%+.3f, %+.3f]   Spearman %+.3f"
              % (dv, pear, lo, hi, spear))

    print("\nARM LEVEL - %d arms over %d tasks" % (len(A), A.task.nunique()))
    A = A.merge(T[["task", "n_arms"]], on="task")
    # S2: task fixed effects
    Xfe = pd.get_dummies(A.task, drop_first=False).astype(float).values
    X2 = np.column_stack([A.D_tfidf.values, Xfe])
    y = A.contrib.values
    b2 = ols(X2, y)[0]
    arms = A.index.values
    lo2, hi2, _ = boot_ci(arms, lambda ix: ols(X2[ix], y[ix])[0]
                          if np.linalg.matrix_rank(X2[ix]) == X2.shape[1] else None)
    print("   S2  c ~ D_arm + task FE (cluster: arm)         slope %+.3f [%+.3f, %+.3f]"
          % (b2, lo2, hi2))
    # S3: pooled, no FE, with log words; cluster on task
    X3 = np.column_stack([np.ones(len(A)), A.D_tfidf.values, A.log_words.values])
    b3 = ols(X3, y)
    tl = list(A.task.unique())
    idx = {t: A.index[A.task == t].values for t in tl}
    rng = np.random.default_rng(SEED)
    bs = []
    for _ in range(2000):
        pick = rng.integers(0, len(tl), len(tl))
        ii = np.concatenate([idx[tl[p]] for p in pick])
        try:
            bs.append(ols(X3[ii], y[ii])[1])
        except Exception:
            pass
    lo3, hi3 = float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))
    print("   S3  c ~ D_arm + log(words), no FE (cluster: task)  slope %+.3f [%+.3f, %+.3f]"
          % (b3[1], lo3, hi3))
    print("       (log(words) coefficient %+.3f - finding 59's covariate, declared in advance)"
          % b3[2])

    # verdict
    s1 = float(pd.Series(live.D_task).corr(pd.Series(live.norm_skill), method="spearman"))
    if s1 > 0 and lo3 > 0:
        verdict = "SUPPORTED - within-outcome skill tracks how different the arms are"
    elif hi3 < 0:
        verdict = "REFUTED - the slope is negative"
    else:
        verdict = "UNRESOLVED - the interval is the result"
    print("\nVERDICT (prereg section 6): %s" % verdict)

    # target projection
    tb = ssb.predict.target_brief()
    tdt, tdj, Dt_target, Dj_target = arm_distances([a.get("text", "") for a in tb["arms"]])
    print("\nTARGET (prereg section 7): D_task = %.3f (Jaccard %.3f) over its %d arms"
          % (Dt_target, Dj_target, len(tb["arms"])))
    below = (live.D_task < Dt_target).sum()
    print("   that is above %d of the %d live practice tasks" % (below, len(live)))
    x, ynorm = live.D_task.values, live.norm_skill.values
    a1, b1 = np.polyfit(x, ynorm, 1)[::-1]
    proj = b1 + a1 * Dt_target if False else np.polyval(np.polyfit(x, ynorm, 1), Dt_target)
    rng = np.random.default_rng(SEED)
    pr = []
    for _ in range(2000):
        ix = rng.integers(0, len(x), len(x))
        if np.std(x[ix]) > 0:
            pr.append(np.polyval(np.polyfit(x[ix], ynorm[ix], 1), Dt_target))
    print("   S1 projection of NORMALISED skill at the target's D_task: %.2f [%.2f, %.2f]"
          % (proj, np.percentile(pr, 2.5), np.percentile(pr, 97.5)))
    target_projection(proj, float(np.percentile(pr, 2.5)), float(np.percentile(pr, 97.5)))
    pair_analysis(tasks, draws)
    out = RUN / "runs" / "_decomp"
    out.mkdir(exist_ok=True)
    A.to_csv(out / "arms.csv", index=False)
    T.to_csv(out / "tasks.csv", index=False)
    print("\nwritten -> %s/{arms,tasks}.csv" % out)
    return A, T


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--draws", type=int, default=3)
    main(ap.parse_args().draws)
