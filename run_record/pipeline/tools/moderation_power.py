#!/usr/bin/env python
"""Is there any predictable treatment-effect MODERATION? Section 3 of the frozen table, measured.

Section 3 ("Subgroup heterogeneity", Tiers 1-2) scores Section-1 metrics minus RMSE on condition x
moderator interactions, for six moderators. The card predicts **exactly zero** interaction: it
anchors subgroup LEVELS (351 offsets, standing finding 11) and carries no condition dimension at
all, so `submission_T2`'s 5,616 moderator cells reconstruct an interaction of 0.0000000000 pp.
Nothing had ever asked whether that zero is a good prediction, and no practice task ever scored a
moderation cell: 0 of 1,101.

    /opt/kernel/venv/bin/python tools/moderation_power.py

Two measurements of the same question, and they disagree, which is the point of running both.

  ANALYTIC (finding 36's test): var(true) = var(observed) - mean(SE^2), whose sqrt over sd(observed)
    is the ceiling on attainable Pearson r. It needs the noise variance of `ATE_level - ATE_overall`,
    and that depends on how ATE_overall weights the levels, because the two terms are correlated.
    Assume equal weights and 18 of 21 task x moderator combinations look detectable at a ceiling of
    0.28-0.57. Assume no correlation at all and 19 of 21 look undetectable. **The whole conclusion is
    an artefact of an unverified weighting assumption** - and neither equal nor n-weighting reproduces
    ATE_overall exactly here, because the level ATEs use level-specific controls and the overall one
    pools them.

  EMPIRICAL (finding 40's rule: do not simulate what can be measured): recompute each task's
    interaction table on two random halves of its own respondents and correlate them, with the MAIN
    EFFECT split-half correlation from the identical splits as the internal control.

The empirical one is the arbiter, and it is unambiguous: interactions replicate at r ~ 0.03 while
main effects on the very same respondents and splits replicate at 0.36-0.78. There is no
moderation signal to predict at these sample sizes, so the card's zero is close to optimal and no
batch should be bought to improve it.
"""
import argparse, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
from ssb import task as T  # noqa: E402

TASKS = ["voelkel2026", "goldwert2026", "vlasceanu2024", "bbprime2025", "voelkel2024"]


def analytic(name, mod, assume):
    ad = T.load_adapter(name)
    df = T.load_dataset(ad)
    ov = T.true_ates(df, ad, None).set_index(["condition", "outcome"])
    tm = T.true_ates(df, ad, mod).dropna(subset=["ate", "se"])
    if tm.empty:
        return None
    recs = []
    for (c, o), g in tm.groupby(["condition", "outcome"]):
        if (c, o) not in ov.index:
            continue
        w = 1.0 / len(g)
        for i, r in g.iterrows():
            if assume == "independent":
                var_i = r.se ** 2
            else:  # equal-weight decomposition
                var_i = (r.se ** 2) * (1 - w) ** 2 + sum(
                    (gg.se ** 2) * w ** 2 for _, gg in g.iterrows() if gg.name != i)
            recs.append((r.ate - ov.loc[(c, o), "ate"], var_i))
    if len(recs) < 10:
        return None
    a = pd.DataFrame(recs, columns=["inter", "var_noise"])
    v, mse = a.inter.var(), a.var_noise.mean()
    return {"cells": len(a), "var_obs": v, "mean_noise": mse, "var_signal": v - mse,
            "ceiling_r": float(np.sqrt(max(v - mse, 0) / v))}


def empirical(name, mod, n_splits=8, seed=0):
    ad = T.load_adapter(name)
    df = T.load_dataset(ad)
    return split_half(df, ad, mod, n_splits, seed)


def split_half(df, ad, mod, n_splits=8, seed=0):
    """The arbiter itself, on a frame rather than an adapter name, so `--selftest` can hand it
    respondents whose interaction size I chose."""
    rng = np.random.default_rng(seed)
    inter_r, main_r = [], []
    for _ in range(n_splits):
        h = rng.random(len(df)) < 0.5
        try:
            oa = T.true_ates(df[h], ad, None).set_index(["condition", "outcome"]).ate
            ob = T.true_ates(df[~h], ad, None).set_index(["condition", "outcome"]).ate
            ta = T.true_ates(df[h], ad, mod).dropna(subset=["ate"])
            tb = T.true_ates(df[~h], ad, mod).dropna(subset=["ate"])
        except Exception:
            return None
        for t, o in ((ta, oa), (tb, ob)):
            t["inter"] = t.ate - t.set_index(["condition", "outcome"]).index.map(o)
        k = ["condition", "outcome", "moderator_level"]
        j = ta[k + ["inter"]].merge(tb[k + ["inter"]], on=k, suffixes=("_a", "_b")).dropna()
        if len(j) > 20:
            inter_r.append(j.inter_a.corr(j.inter_b))
        jm = pd.concat([oa.rename("a"), ob.rename("b")], axis=1).dropna()
        if len(jm) > 5:
            main_r.append(jm.a.corr(jm.b))
    if not inter_r:
        return None
    return {"n_splits": len(inter_r), "interaction_r": float(np.mean(inter_r)),
            "inter_sd": float(np.std(inter_r)), "main_effect_r": float(np.mean(main_r))}


def selftest(reps=40, seed=20260822, verbose=True):
    """Known-answer recovery for the ARBITER, which is the statistic every session 13-16 verdict
    about moderation rests on (findings 53, 81, 82).

    Complementary halves make the identity exact: with S the variance of the FULL-sample estimate
    and nu^2 the per-cell noise variance of that estimate, a half carries 2 nu^2 and its deviation
    from the full estimate carries nu^2, so

        E[split-half r]  =  tau^2 / (tau^2 + 2 nu^2)

    with tau the TRUE across-cell SD of the interaction. Zero true interaction must therefore read
    r = 0 - not -1, and not "small but positive because it is real". This simulates respondents with
    a chosen tau, runs them through the SAME `split_half` the arbiter uses, and compares.
    """
    rng = np.random.default_rng(seed)
    arms = ["Control"] + ["a%d" % i for i in range(1, 6)]
    outs = ["o%d" % i for i in range(4)]
    levels = ["L1", "L2", "L3"]
    n_per, sd_resp = 600, 20.0                       # respondents per arm, response SD in pp
    ad = {"dataset": "selftest", "condition_col": "arm",
          "arms": {a: a for a in arms}, "control_arms": ["Control"],
          "outcomes": {o: {"col": o, "lo": 0, "hi": 100} for o in outs},
          "moderators": {}, "filters": [], "weight_col": None}
    ok = True
    if verbose:
        print("\nSELFTEST - does the split-half arbiter recover a KNOWN interaction? "
              "(%d reps, %d arms x %d outcomes x %d levels, n = %d per arm, response SD %.0f pp)"
              % (reps, len(arms) - 1, len(outs), len(levels), n_per, sd_resp))
    def simulate(tau, rep):
        inter = {(a, o, l): rng.normal(0, tau) for a in arms[1:] for o in outs for l in levels}
        main = {(a, o): rng.normal(0, 4.0) for a in arms[1:] for o in outs}
        rows = []
        for a in arms:
            lvl = rng.choice(levels, n_per)
            r = {"arm": [a] * n_per, "mod": lvl}
            for o in outs:
                mu = 50.0 if a == "Control" else 50.0 + main[(a, o)] + np.array(
                    [inter[(a, o, l)] for l in lvl])
                r[o] = rng.normal(mu, sd_resp)
            rows.append(pd.DataFrame(r))
        df = pd.concat(rows, ignore_index=True)
        df["_arm"] = df.arm
        return df

    def inter_series(df):
        ov = T.true_ates(df, ad, None).set_index(["condition", "outcome"]).ate
        tm = T.true_ates(df, ad, "mod").dropna(subset=["ate"]).copy()
        tm["inter"] = tm.ate - tm.set_index(["condition", "outcome"]).index.map(ov)
        return tm.set_index(["condition", "outcome", "moderator_level"]).inter

    # The two variance components of finding 82's identity r = (S - N) / (S + N), MEASURED on
    # tau = 0 runs instead of derived. A hand-derived nu^2 is wrong here (tried, and it missed by
    # 0.12-0.26) because the interaction estimate subtracts an overall ATE that shares its control
    # noise, and because a random 50% split is not two exactly complementary halves.
    nu2s, Ns = [], []
    for rep in range(reps):
        df0 = simulate(0.0, rep)
        f = inter_series(df0)
        nu2s.append(float(f.var(ddof=1)))
        h = rng.random(len(df0)) < 0.5
        for part in (df0[h], df0[~h]):
            a_ = inter_series(part)
            j = pd.concat([f.rename("f"), a_.rename("a")], axis=1).dropna()
            Ns.append(float((j.a - j.f).var(ddof=1)))
    nu2, N = float(np.mean(nu2s)), float(np.mean(Ns))
    if verbose:
        print("  measured on tau = 0: full-sample cell noise nu^2 = %.3f pp^2, half-vs-full"
              " deviation N = %.3f pp^2" % (nu2, N))
        print("  %10s%14s%14s%12s" % ("true tau", "measured r", "predicted r", "main-effect r"))
    for tau in (0.0, 2.0, 6.0):
        got, mains = [], []
        for rep in range(reps):
            e = split_half(simulate(tau, rep), ad, "mod", n_splits=2, seed=rep)
            if e:
                got.append(e["interaction_r"])
                mains.append(e["main_effect_r"])
        S = tau ** 2 + nu2
        pred = (S - N) / (S + N)
        good = abs(np.mean(got) - pred) < 0.10
        ok &= good
        if verbose:
            print("  %10.1f%14.3f%14.3f%12.3f   %s"
                  % (tau, np.mean(got), pred, np.mean(mains), "ok" if good else "FAIL"))
    if verbose:
        print("  VERDICT:", "OK - the arbiter reads 0 when there is no interaction and rises with"
                            " a real one, on the identity of standing finding 82"
              if ok else "FAIL - the moderation verdicts rest on this statistic")
    return ok


def main(n_splits, seed):
    print("\n=== ANALYTIC, and why it cannot decide this ===")
    rows = []
    for n in TASKS:
        for mod in sorted(T.load_adapter(n).get("moderators", {})):
            r = {"task": n, "moderator": mod}
            for assume in ("independent", "equal_weight"):
                a = analytic(n, mod, assume)
                if a:
                    r[f"ceil_{assume}"] = a["ceiling_r"]
            rows.append(r)
    A = pd.DataFrame(rows)
    print(A.round(3).to_string(index=False))
    for c in ("ceil_independent", "ceil_equal_weight"):
        if c in A:
            print(f"  {c}: {(A[c] > 0).sum()} of {len(A)} combinations look detectable")
    print("  Two defensible noise assumptions, opposite conclusions. This is not a measurement.")

    print(f"\n=== EMPIRICAL: split-half replication, {n_splits} splits (the arbiter) ===")
    rows = []
    for n in TASKS:
        for mod in sorted(T.load_adapter(n).get("moderators", {})):
            e = empirical(n, mod, n_splits, seed)
            if e:
                rows.append({"task": n, "moderator": mod, **e})
    E = pd.DataFrame(rows)
    print(E.round(3).to_string(index=False))
    mi, mm = E.interaction_r.mean(), E.main_effect_r.mean()
    print(f"\n  mean interaction split-half r = {mi:+.3f}   (range {E.interaction_r.min():+.3f} "
          f"to {E.interaction_r.max():+.3f})")
    print(f"  mean MAIN EFFECT split-half r = {mm:+.3f}   <- same respondents, same splits, same code")
    print(f"  combinations with interaction r > 0.25: {(E.interaction_r > 0.25).sum()} of {len(E)}")
    print("\nVERDICT: treatment-effect moderation does not replicate across halves of the same")
    print("sample, in five megastudies of 4,000-20,000 respondents, while main effects on the very")
    print("same splits replicate strongly. Section 3 is at chance for ANY predictor at these sample")
    print("sizes, so the card's exact-zero interaction is close to optimal and buying a batch to")
    print("predict moderation would be buying noise (standing finding 53).")
    return 0


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--splits", type=int, default=8)
    a.add_argument("--seed", type=int, default=0)
    a.add_argument("--selftest", action="store_true",
                   help="known-answer recovery of the split-half arbiter (finding 82's identity)")
    n = a.parse_args()
    if n.selftest:
        sys.exit(0 if selftest() else 1)
    sys.exit(main(n.splits, n.seed))
