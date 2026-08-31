#!/usr/bin/env python
"""TASK_15 direction 1: tau - the SD of TRUE within-outcome-demeaned MESSAGE effects.

Pre-registered in `runs/_tau/PREREG.md` (estimator, restriction rules, projection rule, and the
rule for the range's centre) before any number below was computed. Arm codes are frozen in
`runs/_tau/arm_codes.json`. 0 model calls: every input is a sealed truth table already on disk.

    /opt/kernel/venv/bin/python tools/tau_estimate.py

Why it exists. Session 14 projected the deposited card's `pearson_r_within_outcomes` as 0.26-0.60
*as a function of tau*, and left tau unpinned - so the projection's whole width was tau. tau is a
property of the STUDY (how much its messages really differ), computable from any carved task's
sealed truth with no model call, and the only reason it was never computed is that nobody asked the
question in this form.

The estimator (prereg section 2). Inside one outcome the shared control mean cancels exactly under
demeaning, so with S the sample variance of the selected arms' ATEs and N the mean diagonal of
M V M (M the centring matrix, V the finding-79 sampling covariance),  tau^2 = S - N,  kept signed
per cell and pooled by degrees of freedom.
"""
import argparse, json, math, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / "tools"))
from task_power import TASK_RUNS                                        # noqa: E402

SEED = 20260821
CLIMATE = ["voelkel2026", "goldwert2026", "vlasceanu2024", "bbprime2025"]
NONCLIMATE_SLIDER = ["hackenburg2025", "voelkel2024"]
COARSE = ["tappin2023", "gligoric2025"]
TRUST = ["gligoric2025", "koetke2024", "altenmueller2024"]
MIN_ARMS = 4                                                            # prereg R2
NORM_SKILL = (0.66, 0.46, 0.82)     # runs/_decomp/, re-run after the noise-divisor fix
TARGET_K, TARGET_N = 16, 18000 / 17 / 2                                 # frozen design, Human 1


def load():
    codes = json.loads((RUN / "runs/_tau/arm_codes.json").read_text())
    truth, briefs = {}, {}
    for t, r in TASK_RUNS.items():
        truth[t] = pd.read_csv(RUN / "runs" / r / "tasks" / t / "sealed" / "truth.csv")
        briefs[t] = json.loads((RUN / "runs" / r / "tasks" / t / "brief" / "task.json").read_text())
    return codes, truth, briefs


def outcome_class(meta):
    """prereg R3, implemented strictly: `slider` is the target's own 0-100 rating format."""
    lo, hi, q = meta.get("lo"), meta.get("hi"), str(meta.get("question", ""))
    if "BEHAVIOUR" in q or "donation" in q.lower() or "allocation of" in q.lower():
        return "behaviour"
    if lo == 0 and hi == 100:
        return "slider"
    import re
    m = re.search(r"(\d+)\s+items|mean over the (\d+)|mean of (\d+)", q)
    n_items = max([int(g) for g in (m.groups() if m else []) if g] or [0])
    return "likert_mean" if n_items >= 3 else "likert_item"


def cell_tau2(g):
    """S - N for one (task, outcome) cell, prereg section 2. Returns (tau2, S, N, k)."""
    k = len(g)
    v_o = float((g.se ** 2 / (1.0 / g.n_treat + 1.0 / g.n_control)).mean())
    cov = v_o / float(g.n_control.mean())
    V = np.full((k, k), cov)
    np.fill_diagonal(V, (g.se.values ** 2))
    M = np.eye(k) - np.ones((k, k)) / k
    # trace/(k-1), NOT the mean of the diagonal: S below uses ddof=1, so the noise term must use
    # the same divisor. The mean of the diagonal is (sigma^2/n)(1-1/k) and E[S] = tau^2 + sigma^2/n,
    # so subtracting the mean of the diagonal leaves sigma^2/(nk) of spread that is not there -
    # caught by --selftest, which read tau = 0.43 pp when the truth was 0.00.
    N = float(np.trace(M @ V @ M) / (k - 1))
    S = float(np.var(g.ate.values, ddof=1))
    return S - N, S, N, k


def cells(codes, truth, briefs, tasks, arm_codes, outcome_kinds):
    rows = []
    for t in tasks:
        keep = {a for a, (c, _) in codes[t].items() if c in arm_codes}
        d = truth[t]
        d = d[d.condition.isin(keep)]
        for o, g in d.groupby("outcome"):
            if outcome_class(briefs[t]["outcomes"][o]) not in outcome_kinds:
                continue
            g = g.dropna(subset=["ate", "se"])
            if len(g) < MIN_ARMS:
                continue
            tau2, S, N, k = cell_tau2(g.reset_index(drop=True))
            rows.append({"task": t, "outcome": o, "k": k, "df": k - 1, "S": S, "N": N,
                         "tau2": tau2, "tau": math.sqrt(max(tau2, 0.0))})
    return pd.DataFrame(rows)


def pool(c):
    return float((c.df * c.tau2).sum() / c.df.sum()) if len(c) else float("nan")


def boot(c, n=2000, seed=SEED):
    """percentile bootstrap clustered on the TASK (prereg section 2)."""
    rng, tasks, out = np.random.default_rng(seed), sorted(c.task.unique()), []
    for _ in range(n):
        pick = rng.choice(tasks, size=len(tasks), replace=True)
        sub = pd.concat([c[c.task == t] for t in pick])
        out.append(math.sqrt(max(pool(sub), 0.0)))
    return float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def infamily_slider(boot=1000, seed=SEED, verbose=True):
    """prereg `runs/_trusttask4/PREREG.md` U1-U3: the orchinik2024 in-family reading.

    U1 - it enters as TRUST-SLIDER with R2 relaxed from >= 4 arms to >= 2, labelled, never pooled
         silently into the R2-passing anchor.
    U2 - the interval resamples RESPONDENTS. The 25 outcomes are repeated measures on the same
         2,545 people, so an interval computed by resampling OUTCOMES is far too narrow; both are
         printed, because the gap between them is the point.
    """
    sys.path.insert(0, str(RUN / "tools"))
    import build_orchinik as bo                                          # noqa: E402
    d = bo.load()
    oc = bo.outcome_cols()
    perception = [n for n in oc if not n.startswith("belief")]
    belief = [n for n in oc if n.startswith("belief")]
    arm = d["arm"].to_numpy()
    X = d[[c for c, *_ in oc.values()]].to_numpy(float)
    names = list(oc)
    treat = [a for a in bo.ARMS.values() if a != bo.CONTROL]

    def tau2_of(armv, Xv, subset):
        acc = []
        c0 = Xv[armv == bo.CONTROL]
        for i, nme in enumerate(names):
            if nme not in subset:
                continue
            cv = c0[:, i]
            rows = []
            for a in treat:
                tv = Xv[armv == a][:, i]
                rows.append({"ate": tv.mean() - cv.mean(),
                             "se": math.sqrt(tv.var(ddof=1) / len(tv) + cv.var(ddof=1) / len(cv)),
                             "n_treat": len(tv), "n_control": len(cv)})
            acc.append({"df": 1, "tau2": cell_tau2(pd.DataFrame(rows))[0]})
        return pool(pd.DataFrame(acc)), pd.DataFrame(acc)

    out = {}
    rng = np.random.default_rng(seed)
    ix = {a: np.where(arm == a)[0] for a in [bo.CONTROL] + treat}
    boots = {"perception": [], "belief": []}
    for _ in range(boot):
        pick = np.concatenate([rng.choice(v, len(v), True) for v in ix.values()])
        for lab, sub in (("perception", perception), ("belief", belief)):
            boots[lab].append(math.sqrt(max(tau2_of(arm[pick], X[pick], sub)[0], 0.0)))
    for lab, sub in (("perception", perception), ("belief", belief)):
        t2, cells_ = tau2_of(arm, X, sub)
        ci = np.percentile(boots[lab], [2.5, 97.5])
        out[lab] = {"tau": math.sqrt(max(t2, 0.0)), "ci_respondents": list(ci),
                    "cells": len(cells_)}
        if verbose:
            ro = np.random.default_rng(seed)
            byc = [math.sqrt(max(pool(cells_.sample(len(cells_), replace=True,
                                                    random_state=int(ro.integers(1e9)))), 0.0))
                   for _ in range(boot)]
            print("  orchinik2024 %-11s tau = %.2f pp   respondents [%.2f, %.2f]"
                  "   outcomes [%.2f, %.2f] <- too narrow, rule U2"
                  % (lab, out[lab]["tau"], ci[0], ci[1],
                     np.percentile(byc, 2.5), np.percentile(byc, 97.5)))
    return out


def report_stratum(name, c, bootstrap=True):
    if not len(c):
        print("  %-34s  no qualifying cell" % name)
        return float("nan")
    tau2 = pool(c)
    tau = math.sqrt(max(tau2, 0.0))
    lo, hi = boot(c) if bootstrap and c.task.nunique() > 1 else (float("nan"),) * 2
    per = c.groupby("task").apply(lambda g: math.sqrt(max(pool(g), 0.0)), include_groups=False)
    print("  %-34s tau = %5.2f pp  [%s]  cells %3d  arms/cell %.1f  per task: %s"
          % (name, tau, ("%.2f, %.2f" % (lo, hi)) if lo == lo else "  -  ,  -  ",
             len(c), c.k.mean(), ", ".join("%s %.2f" % (t, v) for t, v in per.items())))
    return tau


def project(tau, sd_by_outcome, norm=NORM_SKILL):
    """prereg section 4: ceiling per target outcome, then expected within-outcome r."""
    nu2 = sd_by_outcome ** 2 / TARGET_N       # see cell_tau2: the (k-1)-divisor spread of the
    #                                            demeaned cells carries the FULL arm-mean variance
    ceil = np.sqrt(tau ** 2 / (tau ** 2 + nu2))
    c = float(ceil.mean())
    return c, norm[0] * c, norm[1] * c, norm[2] * c


def posthoc(codes, truth, briefs, prim, sd, low, centre, tau_p):
    """POST-HOC (not in the prereg): how much of the primary tau is one task, and what the two
    R2-failing trust tasks say. Reported beside the pre-registered numbers, never instead of them."""
    print("\nPOST-HOC ROBUSTNESS  (labelled: none of this is pre-registered, and none of it"
          " replaces the centre above)")
    per = {t: math.sqrt(max(pool(g), 0.0)) for t, g in prim.groupby("task")}
    print("  per-task tau, primary stratum: %s"
          % ", ".join("%s %.2f" % (t, v) for t, v in sorted(per.items(), key=lambda kv: kv[1])))
    print("  median over the four tasks              tau = %.2f pp" % np.median(list(per.values())))
    lbo = prim[prim.task != "bbprime2025"]
    print("  leave-bbprime2025-out (df-pooled)       tau = %.2f pp" % math.sqrt(max(pool(lbo), 0.0)))
    print("  design twin voelkel2026 alone           tau = %.2f pp" % per["voelkel2026"])
    print("  why bbprime2025 is 6.5: its two News Comments arms manipulate the perceived relevance")
    print("  of the very headlines msg_rel_* and msg_share_* then ask about - proximal cells"
          " (tau 7.8-8.6) that no target outcome resembles.")
    print("\n  the two trust tasks that FAIL R2, computed anyway and reported only"
          " (k = 3 and k = 2, so 2 df and 1 df):")
    for t, kinds in (("koetke2024", ("trust_meti", "trust_expertise", "trust_integrity",
                                     "trust_benevolence")),
                     ("altenmueller2024", ("trust_expertise", "trust_morality"))):
        rows = []
        for o in kinds:
            g = truth[t][truth[t].outcome == o].dropna(subset=["ate", "se"]).reset_index(drop=True)
            if len(g) >= 2:
                rows.append(cell_tau2(g))
        tau2 = float(np.average([r[0] for r in rows], weights=[r[3] - 1 for r in rows]))
        print("    %-17s trust outcomes only: tau = %.2f pp  (%s)"
              % (t, math.sqrt(max(tau2, 0.0)),
                 ", ".join("%s %.2f" % (o, math.sqrt(max(r[0], 0.0)))
                           for o, r in zip(kinds, rows))))
    print("\n  what the post-hoc numbers do to the projection:")
    for lab, tv in (("design twin only", per["voelkel2026"]),
                    ("median over tasks", float(np.median(list(per.values())))),
                    ("leave-bbprime-out", math.sqrt(max(pool(lbo), 0.0)))):
        c, e, elo, ehi = project(tv, sd.values)
        print("    %-22s tau %.2f pp -> ceiling %.3f, expected r %.2f [%.2f, %.2f]"
              % (lab, tv, c, e, elo, ehi))


def selftest(reps=4000, seed=SEED):
    """Does the estimator recover a KNOWN tau? A red path for the one number this session quotes.

    Simulates the exact structure it assumes: k treated arms of n respondents each plus ONE shared
    control of n_c, outcome SD sigma, true demeaned effects drawn with a known SD. Reports bias at
    tau = 0 (the estimator must not read spread that is not there) and at tau = 1 and 3 pp.
    """
    rng = np.random.default_rng(seed)
    print("\nSELFTEST - recovery of a known tau (4,000 reps per row; k=8 arms, n=430, "
          "n_control=850, sigma=25 pp)")
    print("  %8s%12s%12s%12s" % ("true tau", "mean tau^", "median tau^", "P(tau^ = 0)"))
    ok = True
    for tau in (0.0, 1.0, 3.0):
        est = []
        for _ in range(reps):
            k, n, nc, sig = 8, 430, 850, 25.0
            t = rng.normal(0, tau, k) if tau > 0 else np.zeros(k)
            t = t - t.mean()
            ybar = t + rng.normal(0, sig / math.sqrt(n), k)
            ybar_c = rng.normal(0, sig / math.sqrt(nc))
            g = pd.DataFrame({"ate": ybar - ybar_c,
                              "se": sig * math.sqrt(1 / n + 1 / nc),
                              "n_treat": n, "n_control": nc})
            est.append(cell_tau2(g)[0])
        est = np.array(est)
        # the pooled estimator averages tau^2 over many cells, so the unbiased object is the MEAN
        m = math.sqrt(max(est.mean(), 0.0))
        med = math.sqrt(max(np.median(est), 0.0))
        z = float((est <= 0).mean())
        print("  %8.2f%12.2f%12.2f%12.3f" % (tau, m, med, z))
        ok = ok and abs(m - tau) < 0.15
    print("  VERDICT:", "OK - unbiased in tau^2, and reads 0.00 when there is nothing there"
          if ok else "BIASED - do not quote tau")
    return ok


def main(run_selftest=False):
    if run_selftest:
        selftest()
    codes, truth, briefs = load()
    print(__doc__.split("Why it exists.")[0])
    print("ARM CODES (runs/_tau/arm_codes.json), prereg R1")
    for t in TASK_RUNS:
        vc = pd.Series([v[0] for v in codes[t].values()]).value_counts().to_dict()
        print("  %-16s %s" % (t, vc))

    print("\nOUTCOME CLASSES, prereg R3 (strict: slider = lo 0, hi 100, not BEHAVIOUR/donation)")
    for t in TASK_RUNS:
        vc = pd.Series([outcome_class(m) for m in briefs[t]["outcomes"].values()]).value_counts()
        print("  %-16s %s" % (t, vc.to_dict()))

    print("\nTAU BY STRATUM  (pp of scale range; SD across message arms inside one outcome,"
          " sampling noise removed)")
    prim = cells(codes, truth, briefs, CLIMATE, {"MESSAGE"}, {"slider"})
    tau_p = report_stratum("PRIMARY climate x message x slider", prim)
    sens1 = cells(codes, truth, briefs, CLIMATE, {"MESSAGE", "MIXED"}, {"slider"})
    report_stratum("  + MIXED arms", sens1)
    sens2 = cells(codes, truth, briefs, CLIMATE, {"MESSAGE"}, {"slider", "likert_mean"})
    report_stratum("  + multi-item Likert means", sens2)
    beh = cells(codes, truth, briefs, CLIMATE, {"MESSAGE"}, {"behaviour"})
    report_stratum("  behavioural outcomes (excluded)", beh)
    nc = cells(codes, truth, briefs, NONCLIMATE_SLIDER, {"MESSAGE"}, {"slider"})
    report_stratum("SECONDARY non-climate x slider", nc)
    co = cells(codes, truth, briefs, COARSE, {"MESSAGE"}, {"likert_mean", "likert_item"})
    report_stratum("SECONDARY coarse Likert", co)
    tr = cells(codes, truth, briefs, TRUST, {"MESSAGE"}, {"slider", "likert_mean", "likert_item"})
    tau_t = report_stratum("TRUST-FAMILY anchor (R2: >=4 arms)", tr, bootstrap=False)
    print("     trust cells: %s" % (", ".join("%s/%s k=%d tau=%.2f" % (r.task, r.outcome, r.k, r.tau)
                                              for r in tr.itertuples()) if len(tr) else "none"))
    for t in ("koetke2024", "altenmueller2024"):
        print("     %-17s %d arms - fails R2, no within-outcome spread is estimable"
              % (t, truth[t].condition.nunique()))

    print("\nPER-CELL DETAIL, primary stratum")
    print("  %-15s%-26s%4s%9s%9s%9s%8s" % ("task", "outcome", "k", "S", "N", "tau2", "tau"))
    for r in prim.itertuples():
        print("  %-15s%-26s%4d%9.2f%9.2f%9.2f%8.2f"
              % (r.task, r.outcome[:25], r.k, r.S, r.N, r.tau2, r.tau))

    # ---- the range, its centre, and the projection (prereg sections 4 and 5) -------------
    base = pd.read_csv(RUN / "runs/20260815-target-01/card/baseline.csv")
    sd = base.set_index("outcome").control_sd.copy()
    sd["donation_ams"] *= 10.0                                          # $0-10 -> pp
    sd["newsletter_signup"] *= 100.0                                    # 0/1  -> pp
    low = tau_t if tau_t == tau_t and tau_t > 0 else 0.5
    subst = "" if low == tau_t else "  (trust anchor <= 0 -> prereg's 0.5 pp substitution)"
    centre = math.sqrt(low * tau_p)
    print("\nTHE RANGE (prereg section 5: ends = trust anchor and primary stratum,"
          " centre = their geometric mean)")
    print("  low  tau = %.2f pp%s\n  centre   = %.2f pp\n  high tau = %.2f pp" %
          (low, subst, centre, tau_p))
    # ---- TASK_16: the in-family reading, and what prereg U3 does with it ------------------
    print("\nIN-FAMILY READING (TASK_16, runs/_trusttask4/PREREG.md U1-U3): orchinik2024's Bovitz")
    print("  message experiment - 2 arms, 0-100 sliders, climate-scientist PERCEPTION outcomes,")
    print("  2,545 US quota-panel respondents. R2 relaxed from >=4 arms to >=2 and labelled.")
    inf = infamily_slider()
    hi_inf = inf["perception"]["ci_respondents"][1]
    moved = hi_inf < tau_p
    print("  U3a: the in-family 95%% interval %s the published high end (%.2f vs %.2f) -> the high"
          % ("EXCLUDES" if moved else "does not exclude", hi_inf, tau_p))
    print("       end %s" % ("becomes %.2f pp" % hi_inf if moved else "is unchanged"))
    print("  U3b: the low end (0.5 pp floor) and the centre are NOT moved by a reading whose point")
    print("       estimate is again 0.00 - see the prereg for why re-deriving the centre from an")
    print("       input that agrees with one end is not an update.")
    print("  U3c: within-study control - the SAME respondents and the SAME two passages give tau ="
          " %.2f pp" % inf["belief"]["tau"])
    print("       on the BELIEF outcomes against %.2f pp on the perception ones, and the"
          " difference is not" % inf["perception"]["tau"])
    print("       resolvable (tools/orchinik_verdicts.py: P(delta > 0) = 0.60).")
    tau_p_pub = hi_inf if moved else tau_p

    print("\nPROJECTED `pearson_r_within_outcomes` on the target"
          " (normalised skill %.2f [%.2f, %.2f], session 14)" % NORM_SKILL)
    print("  target design: k = %d message arms, Human-1 n = %.0f per arm, the card's own"
          " control SDs" % (TARGET_K, TARGET_N))
    print("  %-28s%10s%12s%22s" % ("tau", "ceiling", "expected r", "[skill interval]"))
    for lab, tv in (("low", low), ("CENTRE", centre), ("high (session 15)", tau_p),
                    ("high (TASK_16, U3a)", tau_p_pub)):
        c, e, elo, ehi = project(tv, sd.values)
        print("  %-28s%10.3f%12.2f%22s" % ("%s  %.2f pp" % (lab, tv), c, e,
                                           "[%.2f, %.2f]" % (elo, ehi)))
    print("  QUOTE: pearson_r_within_outcomes = %.2f, range %.2f-%.2f"
          % (project(centre, sd.values)[1], project(low, sd.values)[1],
             project(tau_p_pub, sd.values)[1]))
    print("\n  per-outcome ceilings at the centre tau:")
    nu = np.sqrt(sd ** 2 / TARGET_N)
    for o in sd.index:
        print("    %-24s sigma %6.1f pp  nu %.2f pp  ceiling %.3f"
              % (o, sd[o], nu[o], math.sqrt(centre ** 2 / (centre ** 2 + nu[o] ** 2))))
    out = {"tau_primary": tau_p, "tau_trust_anchor": tau_t, "low": low, "centre": centre,
           "high": tau_p, "high_task16": tau_p_pub, "infamily_orchinik2024": inf,
           "quote": {"centre_r": project(centre, sd.values)[1],
                     "range_r": [project(low, sd.values)[1], project(tau_p_pub, sd.values)[1]]}, "projection": {lab: project(tv, sd.values)
                                         for lab, tv in (("low", low), ("centre", centre),
                                                         ("high", tau_p))}}
    posthoc(codes, truth, briefs, prim, sd, low, centre, tau_p)
    (RUN / "runs/_tau/tau.json").write_text(json.dumps(out, indent=1))
    prim.to_csv(RUN / "runs/_tau/cells_primary.csv", index=False)
    print("\nwrote runs/_tau/tau.json and runs/_tau/cells_primary.csv")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true", help="recovery of a known tau, then the rest")
    a = ap.parse_args()
    main(run_selftest=a.selftest)
