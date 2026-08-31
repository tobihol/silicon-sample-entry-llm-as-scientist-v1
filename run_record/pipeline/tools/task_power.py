#!/usr/bin/env python
"""Does a candidate task have any signal to predict, BEFORE it is carved and paid for?

Run 20260815-practice-01 asked whether gligoric2025 could be a sixth practice task and close the
trust-family gap (standing finding 33). It is mechanically buildable - six arms, verbatim message
texts, a trust battery - and it is worthless as a scored task, because its ATEs are statistically
indistinguishable from zero. Scoring it would have measured noise, and feeding it to fit_calibration
would have dragged the pooled slope toward zero.

The test that says so, in the form standing finding 36 first wrote it:

    var(observed ATEs) = var(true effects) + mean(SE^2)     ->     var(true) = var(obs) - mean(SE^2)

**That form is biased down and is no longer the default (standing finding 79).** Every ATE table this
harness carves differences several arms against ONE control mean inside each outcome, so the cell
errors are positively correlated and mean(SE^2) over-counts the noise in the SAMPLE VARIANCE of the
cells. The covariance-aware form subtracts `trace(M V M) / (k - 1)` with M the centring matrix and

    V[i,i] = se_i^2                      V[i,j] = var_control_o / n_control_o   (i, j share outcome o)

and for the frozen table's `pearson_r_within_outcomes` row it demeans inside each outcome first,
which removes the shared-control noise entirely. A table can therefore be at chance on the marginal
ranking and carry real signal in the within-outcome contrasts - koetke2024's trust cells read a naive
-0.543 and a within-outcome ceiling of 0.648.

`sealed/truth.csv` does not store the control variance, so it is reconstructed from what is there,
assuming homoskedasticity across the arms of an outcome:

    v_i = se_i^2 / (1/n_treat_i + 1/n_control)      v_o = mean_i v_i      cov = v_o / n_control

That reconstruction is CHECKED, not assumed: `--check` compares it against the exact
individual-level computation in `tools/build_koetke.py` (marginal noise 5.416 against 5.407,
ceiling 0.850 against 0.850; within-outcome 1.837 against 1.763, 0.624 against 0.644).

    /opt/kernel/venv/bin/python tools/task_power.py                # every carved task, all 9
    /opt/kernel/venv/bin/python tools/task_power.py --run runs/<id>
    /opt/kernel/venv/bin/python tools/task_power.py --naive        # finding 36's original form
    /opt/kernel/venv/bin/python tools/task_power.py --check        # the reconstruction check
"""
import argparse, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]

# where each carved task's paid run lives (the run that holds its sealed/truth.csv)
TASK_RUNS = {
    "voelkel2026": "20260815-practice-01", "goldwert2026": "20260815-practice-01",
    "vlasceanu2024": "20260815-practice-01", "bbprime2025": "20260815-practice-01",
    "voelkel2024": "20260815-practice-01", "tappin2023": "20260817-practice-t67",
    "hackenburg2025": "20260817-practice-t67", "gligoric2025": "20260819-practice-gligoric",
    "koetke2024": "20260819-practice-koetke", "altenmueller2024": "20260820-practice-alt",
    "orchinik2024": "20260821-practice-orchinik",
    "kim2024": "20260822-practice-kimdab-main",
    "dablander2025": "20260822-practice-kimdab-main",
}


def _cov_matrix(t: pd.DataFrame) -> np.ndarray:
    """Sampling covariance of the cells of one ATE table, in pp^2, with the shared control."""
    k = len(t)
    V = np.zeros((k, k))
    for _, g in t.groupby("outcome"):
        ix = list(g.index)
        v_o = float((g.se ** 2 / (1.0 / g.n_treat + 1.0 / g.n_control)).mean())
        cov = v_o / float(g.n_control.mean())
        for i in ix:
            V[i, i] = float(t.se[i]) ** 2
            for j in ix:
                if j != i:
                    V[i, j] = cov
    return V


def power(ate, se, n_treat=None, n_control=None, outcome=None, naive=False) -> dict:
    """Deconvolved signal-to-noise for one arm x outcome ATE table.

    naive=True reproduces standing finding 36's original statistic exactly (independent cells).
    """
    t = pd.DataFrame({"ate": pd.Series(ate).astype(float), "se": pd.Series(se).astype(float)})
    if outcome is not None:
        t["outcome"] = list(outcome)
        t["n_treat"] = list(n_treat)
        t["n_control"] = list(n_control)
    t = t.dropna(subset=["ate", "se"]).reset_index(drop=True)
    k = len(t)
    var_obs = float(t.ate.var(ddof=1))
    if naive or outcome is None:
        noise = float((t.se ** 2).mean())
        within = {}
    else:
        V = _cov_matrix(t)
        M = np.eye(k) - np.ones((k, k)) / k
        noise = float(np.trace(M @ V @ M) / (k - 1))
        dev, ss_noise, df = [], 0.0, 0
        for _, g in t.groupby("outcome"):
            ix = list(g.index)
            m = len(ix)
            if m < 2:
                continue
            Mo = np.eye(m) - np.ones((m, m)) / m
            dev += list(g.ate - g.ate.mean())
            ss_noise += float(np.trace(Mo @ V[np.ix_(ix, ix)] @ Mo))
            df += m - 1
        if dev:
            # SUMS of squares on both sides. The metric is a correlation over cells, so the divisor
            # cancels - but it must be the SAME divisor. The previous form paired var(dev, ddof=1)
            # (divisor K-1) with the MEAN of the noise diagonal (divisor K) and so understated the
            # noise by K/(K-1); `tools/tau_estimate.py --selftest` is the red path that found it.
            wo, wn = float(np.sum(np.array(dev) ** 2) / df), float(ss_noise / df)
            within = {"within_var_obs": wo, "within_noise": wn, "within_var_signal": wo - wn,
                      "within_ceiling_r": float(np.sqrt(max(wo - wn, 0.0) / wo)) if wo else np.nan}
        else:
            within = {"within_var_obs": np.nan, "within_noise": np.nan,
                      "within_var_signal": np.nan, "within_ceiling_r": np.nan}
    var_true = var_obs - noise
    return {"n_cells": k, "median_abs_ate": float(t.ate.abs().median()),
            "median_se": float(t.se.median()), "var_observed": var_obs, "var_noise": noise,
            "var_signal": var_true,
            "signal_sd": float(np.sqrt(var_true)) if var_true > 0 else float("nan"),
            "signal_share": var_true / var_obs if var_obs else float("nan"),
            "max_attainable_r": (float(np.sqrt(max(var_true, 0.0) / var_obs)) if var_obs
                                 else float("nan")), **within}


def selftest(reps=300, seed=20260822, verbose=True):
    """Known-answer recovery. Standing finding 90: a reconstruction check that compares two
    implementations of the same convention cannot see the convention being wrong; only a number
    I chose in advance can.

    Builds ATE tables of a known shape (m outcomes x k treated arms against ONE shared control per
    outcome) whose TRUE effects have a chosen marginal SD and a chosen within-outcome SD, then asks
    the statistic to report them back. The naive form (finding 36) is run on the same tables as the
    red path: it must read LOW, which is the whole reason the default changed in finding 79.
    """
    rng = np.random.default_rng(seed)
    m, k, n_t, n_c, sigma = 5, 4, 400, 850, 25.0
    ok = True
    if verbose:
        print("\nSELFTEST - recovery of a KNOWN signal variance (%d reps; %d outcomes x %d arms, "
              "n_treat %d, shared n_control %d, outcome SD %.0f pp)"
              % (reps, m, k, n_t, n_c, sigma))
        print("  %9s%9s%14s%14s%14s%14s" % ("true sd", "true tau", "var_signal^", "(true)",
                                            "within_sig^", "(true)"))
    for true_sd, true_tau in ((0.0, 0.0), (1.5, 0.0), (0.0, 1.5), (2.0, 1.0)):
        marg, wit, naive = [], [], []
        for _ in range(reps):
            rows = []
            for o in range(m):
                base = rng.normal(0, true_sd)                    # outcome-level true effect
                dev = rng.normal(0, true_tau, k)
                dev = dev - dev.mean() if true_tau else np.zeros(k)
                ec = rng.normal(0, sigma / np.sqrt(n_c))         # ONE control error per outcome
                for i in range(k):
                    rows.append({"outcome": "o%d" % o, "condition": "a%d" % i,
                                 "ate": base + dev[i] + rng.normal(0, sigma / np.sqrt(n_t)) - ec,
                                 "se": sigma * np.sqrt(1 / n_t + 1 / n_c),
                                 "n_treat": n_t, "n_control": n_c})
            t = pd.DataFrame(rows)
            p_ = power(t.ate, t.se, t.n_treat, t.n_control, t.outcome)
            marg.append(p_["var_signal"])
            wit.append(p_["within_var_signal"])
            naive.append(power(t.ate, t.se, naive=True)["var_signal"])
        # What a sample variance over m*k cells is EXPECTED to be, given m outcome-level draws
        # and m*(k-1) demeaned within-outcome draws - not the population variance, which is a
        # different number and was the first thing this selftest caught about its own arithmetic.
        true_marg = (k * (m - 1) * true_sd ** 2 + m * (k - 1) * true_tau ** 2) / (m * k - 1)
        true_wit = true_tau ** 2
        tol = lambda v: max(0.15, 3 * np.std(v) / np.sqrt(len(v)))
        good = (abs(np.mean(marg) - true_marg) < tol(marg)
                and abs(np.mean(wit) - true_wit) < tol(wit)
                and np.mean(naive) < np.mean(marg) + 1e-9)
        ok &= good
        if verbose:
            print("  %9.2f%9.2f%14.3f%14.3f%14.3f%14.3f   %s   naive %+.3f (must read low)"
                  % (true_sd, true_tau, np.mean(marg), true_marg, np.mean(wit), true_wit,
                     "ok" if good else "FAIL", np.mean(naive)))
    if verbose:
        print("  VERDICT:", "OK - the covariance-aware statistic is unbiased in var_signal and in "
                            "the within-outcome term, and the naive one reads low"
              if ok else "FAIL - do not quote a ceiling from this")
    return ok


def table_for(path: Path, naive=False) -> dict:
    t = pd.read_csv(path)
    return power(t.ate, t.se, t.get("n_treat"), t.get("n_control"), t.get("outcome"), naive=naive)


def check():
    """The reconstruction against the exact individual-level computation of tools/build_koetke.py."""
    sys.path.insert(0, str(RUN / "tools"))
    import build_koetke as bk                                            # noqa: E402
    d = pd.read_csv(RUN / "inputs" / "derived" / "koetke2024_study5.csv")
    exact_t = bk.ate_table(d)
    exact_m, exact_w = bk.signal(d, exact_t, within=False), bk.signal(d, exact_t, within=True)
    got = table_for(RUN / "runs" / TASK_RUNS["koetke2024"] / "tasks" / "koetke2024" /
                    "sealed" / "truth.csv")
    print("\nRECONSTRUCTION CHECK - koetke2024, truth.csv only vs the individual-level data")
    print("  %-22s%12s%12s" % ("", "exact", "reconstructed"))
    print("  %-22s%12.3f%12.3f" % ("marginal noise", exact_m["noise"], got["var_noise"]))
    print("  %-22s%12.3f%12.3f" % ("marginal ceiling", exact_m["ceiling_r"],
                                    got["max_attainable_r"]))
    print("  %-22s%12.3f%12.3f" % ("within noise", exact_w["noise"], got["within_noise"]))
    print("  %-22s%12.3f%12.3f" % ("within ceiling", exact_w["ceiling_r"],
                                    got["within_ceiling_r"]))
    ok = (abs(exact_m["ceiling_r"] - got["max_attainable_r"]) < 0.02 and
          abs(exact_w["ceiling_r"] - got["within_ceiling_r"]) < 0.03)
    print("  VERDICT:", "OK" if ok else "MISMATCH - do not trust the reconstruction")
    return ok


def main(run=None, naive=False):
    rows = []
    if run:
        for td in sorted((Path(run) / "tasks").iterdir()):
            f = td / "sealed" / "truth.csv"
            if f.exists():
                rows.append({"task": td.name, **table_for(f, naive)})
    else:
        for task, r in TASK_RUNS.items():
            f = RUN / "runs" / r / "tasks" / task / "sealed" / "truth.csv"
            if f.exists():
                rows.append({"task": task, "run": r, **table_for(f, naive),
                             "naive_r": table_for(f, True)["max_attainable_r"]})
    d = pd.DataFrame(rows).sort_values("max_attainable_r", ascending=False)
    print("\nSIGNAL vs SAMPLING NOISE in each carved task's sealed truth (no model call involved)")
    print("statistic: %s" % ("finding 36 NAIVE (independent cells)" if naive else
                             "finding 79 COVARIANCE-AWARE (shared control) - the default"))
    hdr = ("%-15s%7s%10s%9s%11s%10s%11s%9s" %
           ("task", "cells", "med|ATE|", "med SE", "var_obs", "var_noise", "var_signal", "max r"))
    if not naive and "within_ceiling_r" in d:
        hdr += "%10s%9s" % ("naive r", "within r")
    print(hdr)
    for r in d.itertuples():
        line = ("%-15s%7d%10.2f%9.2f%11.2f%10.2f%11.2f%9.3f" %
                (r.task, r.n_cells, r.median_abs_ate, r.median_se, r.var_observed, r.var_noise,
                 r.var_signal, r.max_attainable_r))
        if not naive and hasattr(r, "within_ceiling_r"):
            line += "%10.3f%9.3f" % (getattr(r, "naive_r", float("nan")), r.within_ceiling_r)
        print(line)
    print("\nRULE: var_signal <= 0 means the table is noise and cannot be scored or calibrated on.")
    print("      max r is the ceiling on Pearson r a PERFECT predictor could reach against this")
    print("      truth; 'within r' is the same ceiling for the frozen table's")
    print("      pearson_r_within_outcomes row, which demeans inside each outcome and therefore")
    print("      loses the shared-control noise. A task can be at chance on one and not the other.")
    return d


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", default=None, help="one run directory; default = all carved tasks")
    ap.add_argument("--naive", action="store_true", help="finding 36's original statistic")
    ap.add_argument("--check", action="store_true", help="reconstruction vs individual-level data")
    ap.add_argument("--selftest", action="store_true", help="recovery of a KNOWN signal variance")
    a = ap.parse_args()
    if a.selftest:
        sys.exit(0 if selftest() else 1)
    if a.check:
        sys.exit(0 if check() else 1)
    main(a.run, a.naive)
