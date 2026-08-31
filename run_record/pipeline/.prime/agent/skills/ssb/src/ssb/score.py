"""ssb.score - the frozen scoring tables, and nothing else.

Every public function here implements a named row of the scoring tables in the
frozen definitions (APPEND_SYSTEM.md). Function docstrings name the row. Per the
frozen rule "Self-scoring": when scoring a training task, use these and no others.
A metric invented to look better is not a score, so this module is deliberately
closed - adding a function here is a harness change that must be recorded.

Units: every effect passed in must already be in percentage points of its
outcome's scale range (use ssb.spec.to_pp). Cell tables carry an `outcome`
column so the within-outcome row can strip outcome fixed effects.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

from . import spec

# --------------------------------------------------------------------------
# Section 1 - ATE recovery (all tiers)
# --------------------------------------------------------------------------


def _clean(pred, human):
    p, h = np.asarray(pred, float), np.asarray(human, float)
    ok = np.isfinite(p) & np.isfinite(h)
    return p[ok], h[ok]


def directional_agreement(pred, human) -> float:
    """Row: Directional agreement. A zero prediction scores 0.5."""
    p, h = _clean(pred, human)
    s = np.where(p == 0, 0.5, np.where(np.sign(p) == np.sign(h), 1.0, 0.0))
    s = np.where(h == 0, 0.5, s)  # a zero human effect cannot be got right or wrong
    return float(s.mean())


def spearman_rho(pred, human) -> float:
    """Row: Spearman rho - do the interventions rank in the human order?"""
    p, h = _clean(pred, human)
    if np.ptp(p) == 0 or np.ptp(h) == 0:
        return float("nan")
    return float(stats.spearmanr(p, h).statistic)


def pearson_r(pred, human) -> float:
    """Row: Pearson r - are predicted effects proportional to human effects?"""
    p, h = _clean(pred, human)
    if np.ptp(p) == 0 or np.ptp(h) == 0:
        return float("nan")
    return float(stats.pearsonr(p, h).statistic)


def pearson_r_within_outcomes(df: pd.DataFrame, pred="pred", human="human", by="outcome") -> float:
    """Row: Pearson r within outcomes - outcome fixed effects removed, so the score
    reflects message-level skill and not generic knowledge of which outcome moves."""
    d = df.dropna(subset=[pred, human]).copy()
    d["_p"] = d[pred] - d.groupby(by)[pred].transform("mean")
    d["_h"] = d[human] - d.groupby(by)[human].transform("mean")
    if np.ptp(d._p) == 0 or np.ptp(d._h) == 0:
        return float("nan")
    return float(stats.pearsonr(d._p, d._h).statistic)


def rmse_pp(pred, human) -> float:
    """Row: RMSE (pp) - absolute magnitude error."""
    p, h = _clean(pred, human)
    return float(np.sqrt(np.mean((p - h) ** 2)))


def disattenuated(pred, human, se_human) -> dict:
    """Rows: r_adj, RMSE_adj - the same, disattenuated for sampling noise in the
    human reference.

    HARNESS DEFINITION (the organizers' exact formula is not published; see OPEN.md):
        reliability = 1 - mean(se^2)/var(human);  r_adj = r / sqrt(reliability)
        RMSE_adj    = sqrt(max(0, RMSE^2 - mean(se^2)))
    `se_human` is the standard error of each human effect, in pp.
    """
    p, h = _clean(pred, human)
    se = np.asarray(se_human, float)[: len(h)]
    ms = float(np.mean(se ** 2))
    var_h = float(np.var(h, ddof=1))
    rel = max(1e-9, 1.0 - ms / var_h) if var_h > 0 else np.nan
    r = pearson_r(p, h)
    return {
        "reliability": rel,
        "r_adj": float(min(1.0, r / np.sqrt(rel))) if np.isfinite(r) and np.isfinite(rel) else float("nan"),
        "rmse_adj": float(np.sqrt(max(0.0, rmse_pp(p, h) ** 2 - ms))),
    }


def ate_recovery(df: pd.DataFrame, pred="pred", human="human", se="se_human") -> dict:
    """All of Section 1 on a tidy table with columns condition, outcome, pred, human
    (and optionally se_human). Values in pp."""
    out = {
        "n_cells": int(df[[pred, human]].notna().all(axis=1).sum()),
        "directional_agreement": directional_agreement(df[pred], df[human]),
        "spearman_rho": spearman_rho(df[pred], df[human]),
        "pearson_r": pearson_r(df[pred], df[human]),
        "pearson_r_within_outcomes": pearson_r_within_outcomes(df, pred, human),
        "rmse_pp": rmse_pp(df[pred], df[human]),
    }
    if se in df:
        out.update(disattenuated(df[pred], df[human], df[se]))
    return out


# --------------------------------------------------------------------------
# Section 2 - Calibration (all tiers)
# --------------------------------------------------------------------------


def calibration(pred, human) -> dict:
    """Row: Calibration - human ATEs regressed on predicted ATEs, pooled over all
    effects. alpha = 0 and beta = 1 is perfect; beta < 1 means systematic exaggeration."""
    p, h = _clean(pred, human)
    if len(p) < 3 or np.ptp(p) == 0:
        return {"alpha": float("nan"), "beta": float("nan"), "beta_se": float("nan"), "r2": float("nan")}
    res = stats.linregress(p, h)
    return {"alpha": float(res.intercept), "beta": float(res.slope),
            "beta_se": float(res.stderr), "r2": float(res.rvalue ** 2)}


def shrinkage_factor(pred, human) -> float:
    """The single number the practice loop exists to estimate: the slope of human on
    predicted. Applying it to raw predictions is what moves the Calibration row
    towards beta = 1 and the RMSE row down. Fitted through the origin, because a
    calibration map must send a predicted null to a predicted null."""
    p, h = _clean(pred, human)
    denom = float((p * p).sum())
    return float((p * h).sum() / denom) if denom > 0 else float("nan")


# --------------------------------------------------------------------------
# Section 3 - Subgroup heterogeneity (Tiers 1-2)
# --------------------------------------------------------------------------


def subgroup_heterogeneity(df: pd.DataFrame, pred="pred", human="human") -> dict:
    """Section-1 metrics minus RMSE, on condition x moderator interactions.

    HARNESS DEFINITION (see OPEN.md): an interaction cell is the subgroup ATE minus
    the marginal ATE for the same condition x outcome, in pp. `df` must already hold
    those contrasts, one row per condition x moderator x level x outcome."""
    return {
        "n_cells": int(df[[pred, human]].notna().all(axis=1).sum()),
        "directional_agreement": directional_agreement(df[pred], df[human]),
        "spearman_rho": spearman_rho(df[pred], df[human]),
        "pearson_r": pearson_r(df[pred], df[human]),
        "pearson_r_within_outcomes": pearson_r_within_outcomes(df, pred, human),
    }


# --------------------------------------------------------------------------
# Section 4 - Distributions and demographic diagnostics (Tier 1)
# --------------------------------------------------------------------------


def _grid(outcome: str) -> np.ndarray:
    lo, hi = spec.load()["ranges"][outcome]
    if outcome == "newsletter_signup":
        return np.array([0.0, 1.0])
    return np.arange(lo, hi + 1.0)


def _pmf(x, outcome: str) -> np.ndarray:
    g = _grid(outcome)
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    idx = np.clip(np.rint(x - g[0]).astype(int), 0, len(g) - 1)
    c = np.bincount(idx, minlength=len(g)).astype(float)
    return c / c.sum() if c.sum() else c


def variance_ratio(synth, human) -> float:
    """Row: Variance ratio - headline diagnostic. synthetic/human variance per cell;
    < 1 is the documented LLM failure mode (under-dispersion)."""
    vh = float(np.var(np.asarray(human, float), ddof=1))
    vs = float(np.var(np.asarray(synth, float), ddof=1))
    return vs / vh if vh > 0 else float("nan")


def distribution_metrics(synth, human, outcome: str) -> dict:
    """Rows: Overlap (OVL), KS D, Wasserstein-1 - on the fixed grid for `outcome`."""
    g = _grid(outcome)
    ps, ph = _pmf(synth, outcome), _pmf(human, outcome)
    cs, ch = np.cumsum(ps), np.cumsum(ph)
    dg = np.diff(g, prepend=g[0])[1:] if len(g) > 1 else np.array([1.0])
    return {
        "ovl": float(np.minimum(ps, ph).sum()),
        "ks_d": float(np.max(np.abs(cs - ch))),
        "wasserstein1": float(np.sum(np.abs(cs - ch)[:-1] * dg)),
        "variance_ratio": variance_ratio(synth, human),
    }


def within_subgroup_distributions(synth: pd.DataFrame, human: pd.DataFrame, outcome: str,
                                  min_n: int = 30) -> pd.DataFrame:
    """Row: Within-subgroup distributions - the same four, within each demographic
    group with n >= 30."""
    rows = []
    for m in spec.load()["moderators"]:
        for lvl, hs in human.groupby(m):
            ss = synth[synth[m] == lvl]
            if len(hs) < min_n or len(ss) < min_n:
                continue
            r = distribution_metrics(ss[outcome], hs[outcome], outcome)
            rows.append({"moderator": m, "level": lvl, "outcome": outcome,
                         "n_human": len(hs), "n_synth": len(ss), **r})
    return pd.DataFrame(rows)


def demographic_baseline_rmse(synth: pd.DataFrame, human: pd.DataFrame, outcome: str) -> float:
    """Row: Demographic baseline RMSE - control-condition subgroup means per moderator, in pp."""
    sc, hc = synth[synth.condition == "control"], human[human.condition == "control"]
    diffs = []
    for m in spec.load()["moderators"]:
        a = sc.groupby(m)[outcome].mean()
        b = hc.groupby(m)[outcome].mean()
        for lvl in b.index.intersection(a.index):
            diffs.append(spec.to_pp(a[lvl] - b[lvl], outcome))
    return float(np.sqrt(np.mean(np.square(diffs)))) if diffs else float("nan")


def demographic_parity_gap(df: pd.DataFrame, outcome: str) -> dict:
    """Row: Demographic parity gap - worst-served minus best-served demographic group.
    Reported per moderator and pooled (max over moderators), in pp."""
    out = {}
    for m in spec.load()["moderators"]:
        g = df.groupby(m)[outcome].mean()
        out[m] = spec.to_pp(float(g.max() - g.min()), outcome) if len(g) > 1 else float("nan")
    out["max"] = float(np.nanmax(list(out.values()))) if out else float("nan")
    return out


def demographic_predictability(df: pd.DataFrame, outcome: str) -> float:
    """Row: Demographic predictability - R^2 of the outcome on the six moderators.
    Compare synthetic against human: a larger R^2 means the synthetic data
    exaggerates group differences."""
    mods = list(spec.load()["moderators"])
    d = df.dropna(subset=[outcome] + mods)
    if len(d) < 50:
        return float("nan")
    X = pd.get_dummies(d[mods], drop_first=True).astype(float).values
    X = np.column_stack([np.ones(len(X)), X])
    y = d[outcome].astype(float).values
    beta, *_ = np.linalg.lstsq(X, y, rcond=None)
    resid = y - X @ beta
    sst = float(((y - y.mean()) ** 2).sum())
    return float(1.0 - (resid ** 2).sum() / sst) if sst > 0 else float("nan")


# --------------------------------------------------------------------------
# The two scripted baselines that frame every metric
# --------------------------------------------------------------------------


def baselines(human: pd.DataFrame, human_col="human", magnitude: float = 1.0) -> pd.DataFrame:
    """The no-effect floor (every ATE zero) and the all-positive baseline (every
    intervention helps), scored on the same table. A run that does not beat both
    has not demonstrated anything.

    `magnitude` is the pp size of the all-positive baseline's effect; the organizers'
    value is not published (see OPEN.md), so it is explicit and recorded.
    """
    rows = []
    for name, p in (("no_effect_floor", np.zeros(len(human))),
                    ("all_positive", np.full(len(human), magnitude))):
        d = human.assign(pred=p)
        r = ate_recovery(d)
        r.update({f"cal_{k}": v for k, v in calibration(d.pred, d[human_col]).items()})
        rows.append({"baseline": name, **r})
    return pd.DataFrame(rows)


def scorecard(df: pd.DataFrame, pred="pred", human="human", se="se_human",
              magnitude: float = 1.0) -> dict:
    """Sections 1 + 2 on an effect table, alongside both scripted baselines."""
    d = df.rename(columns={pred: "pred", human: "human", se: "se_human"})
    out = ate_recovery(d)
    out.update({f"cal_{k}": v for k, v in calibration(d.pred, d.human).items()})
    out["shrinkage_factor"] = shrinkage_factor(d.pred, d.human)
    b = baselines(d[["condition", "outcome", "human"]], magnitude=magnitude)
    for _, r in b.iterrows():
        out[f"vs_{r.baseline}_directional"] = out["directional_agreement"] - r.directional_agreement
        out[f"vs_{r.baseline}_rmse"] = r.rmse_pp - out["rmse_pp"]
    return out
