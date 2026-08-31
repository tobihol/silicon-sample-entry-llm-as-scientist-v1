#!/usr/bin/env python
"""The pre-registered verdicts of trust practice task #4 (orchinik2024), and nothing else.

    /opt/kernel/venv/bin/python tools/orchinik_verdicts.py            # everything, 0 model calls
    /opt/kernel/venv/bin/python tools/orchinik_verdicts.py --perms 2000

Pre-registration: `runs/_trusttask4/PREREG.md`, written before any model call. Every verdict below
was fixed there; this file only computes them. Three model lines were bought (`claude-opus-5` at
3 draws, `claude-sonnet-5` and `claude-fable-5` at 1 each) so that a verdict is a statement about
the TASK and not about a draw.

The one thing here that is not in the prereg is the PERMUTATION NULL, and it is the most important
output. This task's marginal attainable-r ceiling is 0.534 - the lowest non-zero one on the board -
and the ceiling answers only half the question. It says what a PERFECT predictor could score. It
says nothing about what a structured but arbitrary prediction scores against a table this noisy, and
the answer turns out to be: a great deal. Shuffling the arm labels across the 2,545 respondents and
re-scoring the SAME prediction gives a null with SD 0.34-0.42 on every correlation row. Quote both
limits or quote neither.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd
from scipy import stats as st

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / "tools"))
from build_orchinik import ARMS, CONTROL, LEVELS, FAMILIES, outcome_cols, load   # noqa: E402
from tau_estimate import cell_tau2, pool                                          # noqa: E402
from task_power import power                                                      # noqa: E402

RUNS = {"claude-opus-5": "20260821-practice-orchinik",
        "claude-sonnet-5": "20260821-practice-orchinik-sonnet-5",
        "claude-fable-5": "20260821-practice-orchinik-fable-5"}
PRIMARY = "claude-opus-5"
TREAT = [v for v in ARMS.values() if v != CONTROL]
NAMES = list(outcome_cols())
PERCEPTION = [n for n in NAMES if not n.startswith("belief")]
BELIEF = [n for n in NAMES if n.startswith("belief")]
# the three trust benchmarks already on the board (finding 78 / 84 / 88), median |ATE| in pp
TRUST_BENCHMARKS = {"gligoric2025": (0.42, 0.90), "koetke2024": (2.16, 1.20),
                    "altenmueller2024": (4.33, 1.60)}


def frame():
    d = load()
    cols = [c for c, *_ in outcome_cols().values()]
    return d["arm"].to_numpy(), d[cols].to_numpy(float)


def human_table(arm, X, armv=None):
    armv = arm if armv is None else armv
    c = X[armv == CONTROL].mean(0)
    rec = [(a, n, (X[armv == a].mean(0) - c)[i]) for a in TREAT for i, n in enumerate(NAMES)]
    return pd.DataFrame(rec, columns=["condition", "outcome", "human"])


def predictions():
    out = {}
    for m, r in RUNS.items():
        out[m] = pd.read_csv(RUN / "runs" / r / "tasks" / "orchinik2024" /
                             "prediction.csv").rename(columns={"ate": "pred"})
    return out


def score(h, p, subset=None):
    j = h.merge(p, on=["condition", "outcome"])
    if subset is not None:
        j = j[j.outcome.isin(subset)]
    j = j.copy()
    j["hd"] = j.human - j.groupby("outcome").human.transform("mean")
    j["pd_"] = j.pred - j.groupby("outcome").pred.transform("mean")
    sgn = np.where(j.pred == 0, 0.5, (np.sign(j.human) == np.sign(j.pred)).astype(float))
    return {"n": len(j), "dir": float(sgn.mean()),
            "rho": float(st.spearmanr(j.human, j.pred).statistic),
            "r": float(np.corrcoef(j.human, j.pred)[0, 1]),
            "r_within": float(np.corrcoef(j.hd, j.pd_)[0, 1]) if j.hd.std() else np.nan,
            "rmse": float(np.sqrt(((j.human - j.pred) ** 2).mean())),
            "beta": float(np.polyfit(j.pred, j.human, 1)[0]),
            "alpha": float(np.polyfit(j.pred, j.human, 1)[1])}


def ceilings(truth):
    out = {}
    for lab, sub in (("all 50", truth), ("perception", truth[truth.outcome.isin(PERCEPTION)]),
                     ("belief", truth[truth.outcome.isin(BELIEF)])):
        p = power(sub.ate, sub.se, sub.n_treat, sub.n_control, sub.outcome)
        out[lab] = (p["max_attainable_r"], p["within_ceiling_r"])
    return out


def permutation_null(arm, X, preds, n=1000, seed=31415):
    """Shuffle the arm labels across respondents and re-score the SAME prediction."""
    rng = np.random.default_rng(seed)
    keep = {m: {k: [] for k in ("all", "perception", "belief")} for m in preds}
    for _ in range(n):
        pa = rng.permutation(arm)
        h = human_table(arm, X, pa)
        for m, p in preds.items():
            for lab, sub in (("all", None), ("perception", PERCEPTION), ("belief", BELIEF)):
                keep[m][lab].append(score(h, p, sub))
    return {m: {k: pd.DataFrame(v) for k, v in d.items()} for m, d in keep.items()}


def tau_readings(truth, arm, X, boot=2000, seed=20260821):
    """tau on the perception and belief strata, with the interval computed by resampling
    RESPONDENTS (prereg rule M4) and, for contrast, by resampling outcomes."""
    def tau_of(t, subset):
        c = []
        for o, g in t[t.outcome.isin(subset)].groupby("outcome"):
            tau2, S, N, k = cell_tau2(g.reset_index(drop=True))
            c.append({"outcome": o, "df": k - 1, "tau2": tau2, "S": S, "N": N})
        c = pd.DataFrame(c)
        return float(np.sqrt(max(pool(c), 0.0))), c

    tp, cp = tau_of(truth, PERCEPTION)
    tb, cb = tau_of(truth, BELIEF)
    rng = np.random.default_rng(seed)
    ix = {a: np.where(arm == a)[0] for a in [CONTROL] + TREAT}
    bp, bb, dif = [], [], []
    for _ in range(boot):
        pick = np.concatenate([rng.choice(v, len(v), True) for v in ix.values()])
        av, Xb = arm[pick], X[pick]
        rows = []
        c0 = Xb[av == CONTROL]
        for i, nme in enumerate(NAMES):
            cv = c0[:, i]
            for a in TREAT:
                tv = Xb[av == a][:, i]
                rows.append({"condition": a, "outcome": nme, "ate": tv.mean() - cv.mean(),
                             "se": np.sqrt(tv.var(ddof=1) / len(tv) + cv.var(ddof=1) / len(cv)),
                             "n_treat": len(tv), "n_control": len(cv)})
        t2 = pd.DataFrame(rows)
        pp_ = pd.DataFrame([{"df": 1, "tau2": cell_tau2(g.reset_index(drop=True))[0]}
                            for _, g in t2[t2.outcome.isin(PERCEPTION)].groupby("outcome")])
        bb_ = pd.DataFrame([{"df": 1, "tau2": cell_tau2(g.reset_index(drop=True))[0]}
                            for _, g in t2[t2.outcome.isin(BELIEF)].groupby("outcome")])
        bp.append(np.sqrt(max(pool(pp_), 0.0)))
        bb.append(np.sqrt(max(pool(bb_), 0.0)))
        dif.append(pool(bb_) - pool(pp_))
    # the same interval computed the WRONG way, on purpose: resample the per-outcome readings
    ro = np.random.default_rng(seed)
    byc = [np.sqrt(max(pool(cp.sample(len(cp), replace=True,
                                      random_state=int(ro.integers(1e9)))), 0.0))
           for _ in range(boot)]
    return {"perception": (tp, np.percentile(bp, [2.5, 97.5]), np.percentile(byc, [2.5, 97.5])),
            "belief": (tb, np.percentile(bb, [2.5, 97.5]), None),
            "delta_tau2": (float(pool(cb) - pool(cp)), np.percentile(dif, [2.5, 97.5]),
                           float(np.mean(np.array(dif) > 0)))}


def main(perms=1000):
    arm, X = frame()
    truth = pd.read_csv(RUN / "runs" / RUNS[PRIMARY] / "tasks" / "orchinik2024" /
                        "sealed" / "truth.csv")
    h = human_table(arm, X)
    preds = predictions()
    ceil = ceilings(truth)

    print("\n1. THE PRE-REGISTERED STRATA  (ceilings from the sealed truth, no model call)")
    print("   %-16s%-10s%7s%8s%8s%8s%9s%8s   %s"
          % ("line", "stratum", "n", "dir", "rho", "r", "r_within", "rmse", "ceilings r / within"))
    for m in RUNS:
        for lab, sub in (("all 50", None), ("perception", PERCEPTION), ("belief", BELIEF)):
            s = score(h, preds[m], sub)
            c = ceil[lab]
            note = ""
            if c[0] == 0:
                note = "  <- marginal NOT INTERPRETED"
            if lab == "perception":
                note = "  <- within NOT INTERPRETED"
            print("   %-16s%-10s%7d%8.3f%8.3f%8.3f%9.3f%8.2f   %.3f / %.3f%s"
                  % (m, lab, s["n"], s["dir"], s["rho"], s["r"], s["r_within"], s["rmse"],
                     c[0], c[1], note))

    print("\n2. THE PERMUTATION NULL  (%d shuffles of the arm labels, the SAME predictions)" % perms)
    print("   the ceiling says what a perfect predictor could score; this says what an arbitrary")
    print("   one does score against a human table this noisy.")
    nulls = permutation_null(arm, X, preds, n=perms)
    for m in RUNS:
        for lab, sub in (("all 50", None), ("perception", PERCEPTION), ("belief", BELIEF)):
            s, nd = score(h, preds[m], sub), nulls[m][{"all 50": "all"}.get(lab, lab)]
            row = "   %-16s%-10s" % (m, lab)
            for k in ("rho", "r", "r_within"):
                p = float((nd[k] >= s[k]).mean())
                row += "  %s %+0.3f (null sd %.2f, p %.3f)" % (k, s[k], nd[k].std(), p)
            print(row)

    print("\n3. PRE-REGISTERED VERDICTS")
    hp = truth[truth.outcome.isin(PERCEPTION)].ate.abs().median()
    print("   P1 in-family magnitude on a SLIDER (band 0.8-2.0 pp, human %.2f pp)" % hp)
    for m in RUNS:
        v = float(preds[m][preds[m].outcome.isin(PERCEPTION)].pred.abs().median())
        print("      %-16s median |predicted| %.2f pp   %s"
              % (m, v, "PASS" if 0.8 <= v <= 2.0 else "FAIL"))
    print("      the series this extends: human 0.42 / 2.16 / 4.33 / %.2f pp against predicted"
          " %.2f / %.2f / %.2f / %.2f pp"
          % (hp, *[TRUST_BENCHMARKS[k][1] for k in TRUST_BENCHMARKS],
             float(preds[PRIMARY][preds[PRIMARY].outcome.isin(PERCEPTION)].pred.abs().median())))
    print("   P2 the study's sign structure: mean(skill_pro) > mean(skill_anti) in BOTH arms"
          " (chance 1/4)")
    for m in RUNS:
        p = preds[m]
        ok = all(p[(p.condition == a) & p.outcome.str.startswith("skill_pro")].pred.mean()
                 > p[(p.condition == a) & p.outcome.str.startswith("skill_anti")].pred.mean()
                 for a in TREAT)
        detail = "; ".join("%s %+0.2f vs %+0.2f" % (a[:4],
                           p[(p.condition == a) & p.outcome.str.startswith("skill_pro")].pred.mean(),
                           p[(p.condition == a) & p.outcome.str.startswith("skill_anti")].pred.mean())
                           for a in TREAT)
        print("      %-16s %s   (%s)" % (m, "PASS" if ok else "FAIL", detail))
    print("   P3 beta - the first trust-family slope on a 0-100 slider (reported, never fitted)")
    rng = np.random.default_rng(4242)
    ix = {a: np.where(arm == a)[0] for a in [CONTROL] + TREAT}
    for m in RUNS:
        s = score(h, preds[m])
        bs = []
        for _ in range(400):
            pick = np.concatenate([rng.choice(v, len(v), True) for v in ix.values()])
            bs.append(score(human_table(arm, X[pick], arm[pick]), preds[m])["beta"])
        lo, hi = np.percentile(bs, [2.5, 97.5])
        print("      %-16s beta %+0.3f [%+0.3f, %+0.3f] (respondent bootstrap), alpha %+0.3f"
              % (m, s["beta"], lo, hi, s["alpha"]))
    print("      for comparison: pooled lambda 1.5212; coarse-scale trust slopes gligoric 0.845,"
          " tappin 0.865, koetke 1.47-1.91")

    print("\n4. TAU - the in-family reading (prereg section 5), 0 model calls")
    t = tau_readings(truth, arm, X)
    tp, ci_r, ci_o = t["perception"]
    tb, ci_b, _ = t["belief"]
    print("   perception (20 outcomes, 2 arms)  tau = %.2f pp   respondents [%.2f, %.2f]"
          "   outcomes [%.2f, %.2f]  <- rule M4: the first is the honest one"
          % (tp, ci_r[0], ci_r[1], ci_o[0], ci_o[1]))
    print("   belief     ( 5 outcomes, 2 arms)  tau = %.2f pp   respondents [%.2f, %.2f]"
          % (tb, ci_b[0], ci_b[1]))
    d, dci, pgt = t["delta_tau2"]
    print("   within-study control: tau2(belief) - tau2(perception) = %+0.3f [%+0.3f, %+0.3f],"
          " P(>0) = %.2f -> NOT resolvable (prereg U3c)" % (d, dci[0], dci[1], pgt))

    print("\n5. CROSS-LINE AGREEMENT  (finding 48: the bias lives in the task, not the model)")
    ms = list(RUNS)
    for i in range(len(ms)):
        for j in range(i + 1, len(ms)):
            a_ = preds[ms[i]].merge(preds[ms[j]], on=["condition", "outcome"])
            print("   corr(pred %s, pred %s) = %+0.3f"
                  % (ms[i], ms[j], np.corrcoef(a_.pred_x, a_.pred_y)[0, 1]))

    print("\n6. THE PROBE, VERSION 2  (this session's direction 1)")
    for m, r in RUNS.items():
        pr = json.loads((RUN / "runs" / r / "stages" / "practice" /
                         "recognition_probe.json").read_text())[0]
        print("   %-16s verdict %-13s study=%-8s confidence=%-4s referent=%r"
              % (m, pr["verdict"], pr["self_report_study"], pr["self_report_confidence"],
                 pr["confidence_referent"]))
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--perms", type=int, default=1000)
    sys.exit(main(ap.parse_args().perms))
