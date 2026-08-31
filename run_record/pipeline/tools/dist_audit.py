#!/usr/bin/env python
"""tools/dist_audit.py - the Tier-1 DISTRIBUTIONAL surface, audited against real humans.

Section 4 of the frozen scoring table is the only section whose reference is a
DISTRIBUTION rather than a number: variance ratio (the headline diagnostic),
Overlap, KS D, Wasserstein-1, the same four within every demographic group with
n >= 30, and three demographic rows.  The target's human distributions are sealed,
so this tool substitutes the real human rows of the carved practice datasets and
scores the deposited synthetic rows against them with `ssb.score` - the frozen
reimplementation - and nothing else.

    /opt/kernel/venv/bin/python tools/dist_audit.py                       # target-01
    /opt/kernel/venv/bin/python tools/dist_audit.py --tier1 <path> --tag <name>
    /opt/kernel/venv/bin/python tools/dist_audit.py --selftest            # known-answer

THE COMPATIBILITY RULE (stated before any number, because a stand-in truth that is
not format-compatible measures the format and not the synthesis).  A human column
stands in for a target outcome only when all four hold:

  1. RESPONSE FORMAT, read off the raw data and not off the adapter's declaration:
       slider100   declared 0-100 and >= 90 distinct values in the control arm
       donation10  declared 0-10, >99% integer-valued
       binary      values in {0, 1}
  2. ITEM-COUNT CLASS.  k is inferred from the granularity of the human column (the
     smallest k for which >99.5% of values are multiples of 1/k).  A k = 1 target
     outcome matches only k = 1 human columns and a k > 1 target outcome only k > 1
     human columns, because a composite of k heaped items is a different distribution
     from an item (standing finding 2).  |k_target - k_human| is reported on every row.
  3. ITEM FAMILY.  Within slider100, `attitude` (agreement / support / intention),
     `probability` (orchinik2024's percent-chance items) and `costly` (a real
     donation slider) are separate pools.  Finding 6: the heaping RATE transfers
     across item types and the midpoint spike does not.  Finding 7: a costly-act
     outcome is a spike distribution, not a bell.  Only `attitude` is primary; the
     other two are reported and never pooled with it.
  4. ARM.  Human rows come from the CONTROL arm only, because the synthetic cell
     being compared is the control condition and a treated arm is a different cell.

Nothing here is a score of the target study.  It is a measurement of whether the
synthesis produces human-shaped rows at all, on the one format the target shares
with data we are allowed to read.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RUN = Path("/workspace/run")
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))

import ssb.score as score          # noqa: E402  the frozen metrics, and only these
import ssb.spec as spec            # noqa: E402
import ssb.task as task            # noqa: E402

SOURCES = ["voelkel2026", "vlasceanu2024", "voelkel2024", "bbprime2025",
           "hackenburg2025", "orchinik2024", "goldwert2026", "dablander2025"]

# item family by (source, column) - declared here, not inferred, because "is this a
# probability item" is a question about the questionnaire and not about the numbers.
PROBABILITY = {"orchinik2024"}                       # every outcome is a percent chance
COSTLY = {("voelkel2026", "Donation"), ("dablander2025", "donation"),
          ("goldwert2026", "donation")}


def infer_k(x: np.ndarray, kmax: int = 24) -> int | None:
    """Number of averaged items implied by the granularity of a column."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if not len(x):
        return None
    for k in range(1, kmax + 1):
        if np.mean(np.abs(x * k - np.rint(x * k)) < 1e-6) > 0.995:
            return k
    return None


def _family(source: str, colname: str, lo: float, hi: float, x: np.ndarray) -> str | None:
    xv = x[np.isfinite(x)]
    if not len(xv):
        return None
    if set(np.unique(xv)) <= {0.0, 1.0}:
        return "binary"
    if lo == 0 and hi == 10 and np.mean(xv == np.rint(xv)) > 0.99:
        return "donation10"      # goldwert2026 carries 3 off-grid values in 1,212
    if lo == 0 and hi == 100 and len(np.unique(np.rint(xv))) >= 90:
        if source in PROBABILITY:
            return "probability"
        if (source, colname) in COSTLY:
            return "costly"
        return "attitude"
    return None


# Extra raw columns pulled alongside the adapters' declared outcomes: the PRE items and
# PRE composites of the design twin, which is what `tools/build_baselines.py` actually
# anchored the card's control_mean / control_sd on.  Naming them here (rather than
# inferring) keeps the audit checkable against inputs/baselines/control_levels.csv.
ANCHOR_COLUMNS = {
    "voelkel2026": {
        "Belief_Pre": "Belief_Pre", "Belief_Pre_item1": "Belief_Pre_1_1",
        "Belief_Pre_item2": "Belief_Pre_2_1", "Belief_Pre_item3": "Belief_Pre_3_1",
        "Concern_Pre": "Concern_Pre", "Policies_Pre_3": "Policies_Pre_3",
        "IntentNp_Pre": "IntentNp_Pre", "PoliciesSp_Pre": "PoliciesSp_Pre",
        "Concern_Pre_item1": "Concern_Pre_1_1", "Policies_Pre_1": "Policies_Pre_1",
    },
}

# The CONSTRUCT twin of a target outcome: same construct AND same native response
# format, so control_mean and control_sd are matched by the card's own anchoring and
# OVL / KS / W1 then read SHAPE alone.  An outcome with no entry has no native-slider
# twin anywhere in the mounted data - which is itself one of this audit's results.
TWINS = {
    "belief_post": ["voelkel2026:Belief_Pre_item1", "voelkel2026:Belief_Pre_item2",
                    "voelkel2026:Belief_Pre_item3", "vlasceanu2024:Belief1",
                    "vlasceanu2024:Belief2", "vlasceanu2024:Belief3",
                    "vlasceanu2024:Belief4", "goldwert2026:belief_1"],
    "concern_mean": ["voelkel2026:Concern_Pre", "voelkel2026:Concern_Post"],
    "policy_general": ["voelkel2026:Policies_Pre_3", "goldwert2026:policy_1",
                       "vlasceanu2024:Policy2", "vlasceanu2024:Policy6"],
    "policy_specific_mean": ["voelkel2026:PoliciesSp_Pre", "voelkel2026:PoliciesSp_Post"],
    "behavior_mean": ["voelkel2026:IntentNp_Pre", "voelkel2026:IntentNp_Post"],
    "donation_ams": ["goldwert2026:donation"],
    "newsletter_signup": ["goldwert2026:newsletter1", "goldwert2026:newsletter2"],
}


def human_reference(sources=SOURCES, verbose=True) -> pd.DataFrame:
    """Long table of control-arm human responses on format-compatible columns."""
    mods = list(spec.load()["moderators"])
    frames = []
    for name in sources:
        ad = task.load_adapter(name)
        try:
            df = task.load_dataset(ad)
        except Exception as e:                                    # noqa: BLE001
            if verbose:
                print(f"  ! {name}: {e}", file=sys.stderr)
            continue
        ctrl = df[df["_arm"].isin(set(ad["control_arms"]))]
        for oname, o in ad["outcomes"].items():
            x = pd.to_numeric(ctrl[o["col"]], errors="coerce")
            if o.get("reverse"):
                x = (o["lo"] + o["hi"]) - x
            xv = x.to_numpy(float)
            fam = _family(name, o["col"], o["lo"], o["hi"], xv)
            if fam is None or np.isfinite(xv).sum() < 100:
                continue
            sub = pd.DataFrame({"source": name, "human_col": oname, "family": fam,
                                "value": xv})
            for m in mods:                     # all six, NaN where the source lacks one
                sub[m] = ctrl[m].to_numpy() if m in ctrl.columns else np.nan
            sub["k_human"] = infer_k(xv)
            frames.append(sub.dropna(subset=["value"]))
        for label, raw in ANCHOR_COLUMNS.get(name, {}).items():
            if raw not in ctrl.columns:
                continue
            xv = pd.to_numeric(ctrl[raw], errors="coerce").to_numpy(float)
            fam = _family(name, raw, 0, 100, xv)
            if fam is None or np.isfinite(xv).sum() < 100:
                continue
            sub = pd.DataFrame({"source": name, "human_col": label, "family": fam,
                                "value": xv})
            for m in mods:
                sub[m] = ctrl[m].to_numpy() if m in ctrl.columns else np.nan
            sub["k_human"] = infer_k(xv)
            frames.append(sub.dropna(subset=["value"]))
    out = pd.concat(frames, ignore_index=True)
    out["condition"] = "control"          # the frozen demographic rows key on this
    return out


# --------------------------------------------------------------------------
# the audit
# --------------------------------------------------------------------------


def target_outcome_table() -> pd.DataFrame:
    s = spec.load()
    comps = spec.composites()
    rows = []
    for o in s["outcomes"]:
        lo, hi = s["ranges"][o]
        k = len(comps[o]) if o in comps else 1
        fam = ("binary" if o == "newsletter_signup"
               else "donation10" if o == "donation_ams" else "attitude")
        rows.append({"outcome": o, "k_target": k, "family": fam, "lo": lo, "hi": hi})
    return pd.DataFrame(rows)


def match(tgt: pd.Series, href: pd.DataFrame, secondary=False) -> pd.DataFrame:
    """Human columns compatible with one target outcome, per the four-part rule."""
    fams = [tgt.family]
    if secondary and tgt.family == "attitude":
        fams = ["probability", "costly"]
    h = href[href.family.isin(fams)]
    if tgt.family in ("attitude", "probability", "costly"):
        h = h[(h.k_human > 1)] if tgt.k_target > 1 else h[h.k_human == 1]
    return h


def _ceiling(hv: np.ndarray, n_syn: int, outcome: str, reps=8, seed=0) -> dict:
    """What a PERFECT synthesis would score against this human column.

    Two independent draws from the column's own empirical distribution, at the two
    sample sizes actually being compared.  Every one of OVL / KS D / W1 is bounded
    away from its ideal value by sampling noise alone, and by an amount that depends
    on n_human - so an OVL of 0.70 against a 524-row column and against a 5,691-row
    column are not the same reading.  This is the frozen file's replication-ceiling
    idea applied to a distribution.
    """
    rng = np.random.default_rng(seed)
    acc = []
    for _ in range(reps):
        a = rng.choice(hv, n_syn, replace=True)
        b = rng.choice(hv, len(hv), replace=True)
        acc.append(score.distribution_metrics(a, b, outcome))
    return {f"{k}_ceiling": float(np.median([d[k] for d in acc]))
            for k in ("ovl", "ks_d", "wasserstein1", "variance_ratio")}


def audit_marginal(t1: pd.DataFrame, href: pd.DataFrame, secondary=False) -> pd.DataFrame:
    """Variance ratio, OVL, KS D, W1 for every compatible (target outcome, human column)."""
    ctrl = t1[t1.condition == "control"]
    rows = []
    for _, tgt in target_outcome_table().iterrows():
        h = match(tgt, href, secondary)
        syn = ctrl[tgt.outcome].to_numpy(float)
        for (src, col), g in h.groupby(["source", "human_col"], observed=True):
            hv = g.value.to_numpy(float)
            m = score.distribution_metrics(syn, hv, tgt.outcome)
            rows.append({"outcome": tgt.outcome, "k_target": int(tgt.k_target),
                         "source": src, "human_col": col, "k_human": int(g.k_human.iloc[0]),
                         "family": g.family.iloc[0],
                         "dk": abs(int(tgt.k_target) - int(g.k_human.iloc[0])),
                         "n_synth": len(syn), "n_human": len(g),
                         "mean_s": float(np.mean(syn)), "mean_h": float(hv.mean()),
                         "sd_s": float(np.std(syn, ddof=1)), "sd_h": float(hv.std(ddof=1)),
                         **m, **_ceiling(hv, len(syn), tgt.outcome)})
    return pd.DataFrame(rows)


def audit_twins(t1: pd.DataFrame, href: pd.DataFrame) -> pd.DataFrame:
    """The construct-twin table: the strongest test the mounted data supports.

    Level and spread are matched by the card's own anchoring, so OVL / KS D / W1
    read shape, and the variance ratio reads whether the anchor was transported
    correctly (right construct, right item count, right response format).
    """
    ctrl = t1[t1.condition == "control"]
    idx = {f"{s}:{c}": g for (s, c), g in href.groupby(["source", "human_col"], observed=True)}
    rows = []
    for outcome, refs in TWINS.items():
        syn = ctrl[outcome].to_numpy(float)
        for key in refs:
            g = idx.get(key)
            if g is None:
                rows.append({"outcome": outcome, "twin": key, "status": "MISSING"})
                continue
            hv = g.value.to_numpy(float)
            rows.append({"outcome": outcome, "twin": key, "status": "ok",
                         "k_human": int(g.k_human.iloc[0]), "n_human": len(hv),
                         "mean_s": float(np.mean(syn)), "mean_h": float(hv.mean()),
                         "sd_s": float(np.std(syn, ddof=1)), "sd_h": float(hv.std(ddof=1)),
                         **score.distribution_metrics(syn, hv, outcome),
                         **_ceiling(hv, len(syn), outcome)})
    for o in spec.load()["outcomes"]:
        if o not in TWINS:
            rows.append({"outcome": o, "twin": "NONE IN MOUNTED DATA", "status": "no twin"})
    return pd.DataFrame(rows)


def audit_subgroup(t1: pd.DataFrame, href: pd.DataFrame, min_n=30) -> pd.DataFrame:
    """Row: Within-subgroup distributions - the same four, per group with n >= 30."""
    ctrl = t1[t1.condition == "control"]
    rows = []
    for _, tgt in target_outcome_table().iterrows():
        h = match(tgt, href)
        for (src, col), g in h.groupby(["source", "human_col"], observed=True):
            hu = g.rename(columns={"value": tgt.outcome})
            r = score.within_subgroup_distributions(ctrl, hu, tgt.outcome, min_n=min_n)
            if len(r):
                r.insert(0, "human_col", col)
                r.insert(0, "source", src)
                rows.append(r)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


HEAP_COLS = ["frac_int", "p_mult5", "p_mult10", "p_at_0", "p_at_50", "p_at_100",
             "p_le4", "p_ge96", "n_unique"]


def heaping(x) -> dict:
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    r = np.rint(x)
    return {"n": len(x), "mean": float(x.mean()), "sd": float(x.std(ddof=1)),
            "frac_int": float(np.mean(x == r)), "p_mult5": float(np.mean(r % 5 == 0)),
            "p_mult10": float(np.mean(r % 10 == 0)), "p_at_0": float(np.mean(x == 0)),
            "p_at_50": float(np.mean(x == 50)), "p_at_100": float(np.mean(x == 100)),
            "p_le4": float(np.mean(x <= 4)), "p_ge96": float(np.mean(x >= 96)),
            "n_unique": int(len(np.unique(r)))}


def audit_heaping(t1: pd.DataFrame, href: pd.DataFrame) -> pd.DataFrame:
    """Not a scored row: the mechanism behind OVL/KS/W1, so a defect can be located."""
    ctrl = t1[t1.condition == "control"]
    rows = []
    for _, tgt in target_outcome_table().iterrows():
        if tgt.family != "attitude":
            continue
        rows.append({"side": "synth", "outcome": tgt.outcome, "k": int(tgt.k_target),
                     **heaping(ctrl[tgt.outcome])})
    for (src, col), g in href[href.family == "attitude"].groupby(["source", "human_col"]):
        rows.append({"side": "human", "outcome": f"{src}:{col}",
                     "k": int(g.k_human.iloc[0]), **heaping(g.value)})
    return pd.DataFrame(rows)


def human_limits(href: pd.DataFrame, outcome_for_grid="trust_post", n_splits=8,
                 seed=0, max_pairs=400) -> pd.DataFrame:
    """The two limits every distributional number needs, measured on humans only.

    CEILING  - the same human column split at random into two halves and scored
               against itself.  Nothing can do better than this; it is the frozen
               file's own "the other half's agreement with it is the replication
               ceiling", applied to a distribution instead of an effect.
    FLOOR    - two DIFFERENT human columns of the same family and item-count class.
               This is what "a plausible human-shaped distribution of the wrong
               construct" scores, and it is the number our synthesis has to beat
               to have said anything about the target's constructs.

    Both are computed on the frozen 0-100 grid via ssb.score.distribution_metrics.
    """
    rng = np.random.default_rng(seed)
    rows = []
    cols = list(href[href.family == "attitude"].groupby(["source", "human_col"]))
    for (src, col), g in cols:
        v = g.value.to_numpy(float)
        k = int(g.k_human.iloc[0])
        for _ in range(n_splits):
            p = rng.permutation(len(v))
            a, b = v[p[: len(v) // 2]], v[p[len(v) // 2:]]
            rows.append({"kind": "ceiling", "a": f"{src}:{col}", "b": f"{src}:{col}",
                         "k_a": k, "k_b": k, "n_a": len(a), "n_b": len(b),
                         **score.distribution_metrics(a, b, outcome_for_grid)})
    pairs = [(i, j) for i in range(len(cols)) for j in range(i + 1, len(cols))]
    if len(pairs) > max_pairs:
        pairs = [pairs[i] for i in rng.choice(len(pairs), max_pairs, replace=False)]
    for i, j in pairs:
        (sa, ca), ga = cols[i]
        (sb, cb), gb = cols[j]
        ka, kb = int(ga.k_human.iloc[0]), int(gb.k_human.iloc[0])
        if (ka == 1) != (kb == 1):
            continue
        rows.append({"kind": "floor", "a": f"{sa}:{ca}", "b": f"{sb}:{cb}",
                     "k_a": ka, "k_b": kb, "n_a": len(ga), "n_b": len(gb),
                     **score.distribution_metrics(ga.value.to_numpy(float),
                                                  gb.value.to_numpy(float), outcome_for_grid)})
    return pd.DataFrame(rows)


def summarise(marg: pd.DataFrame) -> pd.DataFrame:
    """Per target outcome, the median over its compatible human references."""
    g = marg.groupby("outcome")
    out = g.agg(n_ref=("human_col", "size"),
                variance_ratio=("variance_ratio", "median"),
                vr_lo=("variance_ratio", "min"), vr_hi=("variance_ratio", "max"),
                ovl=("ovl", "median"), ovl_ceil=("ovl_ceiling", "median"),
                ks_d=("ks_d", "median"), ks_ceil=("ks_d_ceiling", "median"),
                w1=("wasserstein1", "median"), w1_ceil=("wasserstein1_ceiling", "median"))
    return out.reset_index()


# --------------------------------------------------------------------------


def selftest() -> int:
    """Known answer: a copy of the human column must score VR 1, OVL 1, KS 0, W1 0,
    and a deliberately narrowed copy must score VR < 1 - the direction the frozen
    table calls the documented LLM failure mode."""
    rng = np.random.default_rng(0)
    h = np.clip(np.rint(rng.normal(60, 25, 8000)), 0, 100)
    same = score.distribution_metrics(h, h, "trust_post")
    ok = (abs(same["variance_ratio"] - 1) < 1e-9 and abs(same["ovl"] - 1) < 1e-9
          and same["ks_d"] < 1e-9 and same["wasserstein1"] < 1e-9)
    narrow = np.clip(np.rint(60 + 0.5 * (h - 60)), 0, 100)
    nm = score.distribution_metrics(narrow, h, "trust_post")
    ok2 = nm["variance_ratio"] < 0.30 and nm["ovl"] < 0.9
    shift = np.clip(h + 10, 0, 100)
    sm = score.distribution_metrics(shift, h, "trust_post")
    ok3 = abs(sm["variance_ratio"] - 1) < 0.15 and sm["wasserstein1"] > 5
    print(f"selftest identity      VR={same['variance_ratio']:.6f} OVL={same['ovl']:.6f} "
          f"KS={same['ks_d']:.2e} W1={same['wasserstein1']:.2e}  {'PASS' if ok else 'FAIL'}")
    print(f"selftest under-disp    VR={nm['variance_ratio']:.4f} OVL={nm['ovl']:.4f}"
          f"  {'PASS' if ok2 else 'FAIL'}")
    print(f"selftest pure shift    VR={sm['variance_ratio']:.4f} W1={sm['wasserstein1']:.3f}"
          f"  {'PASS' if ok3 else 'FAIL'}")
    return 0 if (ok and ok2 and ok3) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier1", default=str(RUN / "runs/20260815-target-01/stages/tier1.csv"))
    ap.add_argument("--tag", default="target-01")
    ap.add_argument("--out", default=str(RUN / "runs/_dist"))
    ap.add_argument("--min-n", type=int, default=30)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()

    out = Path(a.out) / a.tag
    out.mkdir(parents=True, exist_ok=True)
    t1 = pd.read_csv(a.tier1)
    cache = Path(a.out) / "human_ref.csv.gz"
    if cache.exists():
        href = pd.read_csv(cache)
    else:
        href = human_reference()
        cache.parent.mkdir(parents=True, exist_ok=True)
        href.to_csv(cache, index=False)
    print(f"human reference: {len(href):,} responses, "
          f"{href.groupby(['source','human_col']).ngroups} columns, "
          f"families {sorted(href.family.unique())}")

    marg = audit_marginal(t1, href)
    sec = audit_marginal(t1, href, secondary=True)
    sub = audit_subgroup(t1, href, a.min_n)
    heap = audit_heaping(t1, href)
    marg.to_csv(out / "marginal.csv", index=False)
    sec.to_csv(out / "marginal_secondary.csv", index=False)
    sub.to_csv(out / "subgroup.csv", index=False)
    heap.to_csv(out / "heaping.csv", index=False)

    tw = audit_twins(t1, href)
    tw.to_csv(out / "twins.csv", index=False)
    print("\n== CONSTRUCT TWINS (same construct AND native 0-100 format) ==")
    cols = ["outcome", "twin", "k_human", "n_human", "sd_s", "sd_h", "variance_ratio",
            "ovl", "ovl_ceiling", "ks_d", "wasserstein1"]
    print(tw.reindex(columns=cols).to_string(index=False,
          float_format=lambda v: f"{v:7.3f}"))

    lim = human_limits(href)
    lim.to_csv(out / "human_limits.csv", index=False)
    print("\n== HUMAN LIMITS (attitude family, frozen 0-100 grid) ==")
    for kind in ("ceiling", "floor"):
        d = lim[lim.kind == kind]
        for kcls, dd in (("k=1 items", d[(d.k_a == 1)]), ("k>1 composites", d[(d.k_a > 1)])):
            if not len(dd):
                continue
            print("  %-8s %-15s n=%4d  VR %.3f [%.3f, %.3f]  OVL %.3f [%.3f, %.3f]  "
                  "KS %.3f  W1 %5.2f" % (
                      kind, kcls, len(dd), dd.variance_ratio.median(),
                      dd.variance_ratio.quantile(.1), dd.variance_ratio.quantile(.9),
                      dd.ovl.median(), dd.ovl.quantile(.1), dd.ovl.quantile(.9),
                      dd.ks_d.median(), dd.wasserstein1.median()))

    s = summarise(marg)
    print("\n== MARGINAL (control arm), median over compatible human references ==")
    print(s.to_string(index=False, float_format=lambda v: f"{v:8.3f}"))
    if len(sub):
        gs = sub.groupby("outcome").agg(n=("ovl", "size"), variance_ratio=("variance_ratio", "median"),
                                        ovl=("ovl", "median"), ks_d=("ks_d", "median"),
                                        wasserstein1=("wasserstein1", "median")).reset_index()
        print(f"\n== WITHIN SUBGROUP (n >= {a.min_n}), median over group x reference ==")
        print(gs.to_string(index=False, float_format=lambda v: f"{v:8.3f}"))
    print(f"\nwrote {out}/")
    return 0




def audit_group_spread(t1: pd.DataFrame, href: pd.DataFrame, min_n=100,
                       drop_levels=("Other",)) -> pd.DataFrame:
    """Group-level mean and SD, ours and the construct twin's, for the mean-variance link.

    The frozen table scores the four distributional metrics WITHIN each demographic group
    with n >= 30, so how the within-group spread varies across groups is a scored quantity
    and not a curiosity.  On a bounded scale it varies systematically: see fit_gamma.
    """
    ctrl = t1[t1.condition == "control"]
    mods = [m for m in spec.load()["moderators"]]
    idx = {f"{s}:{c}": g for (s, c), g in href.groupby(["source", "human_col"], observed=True)}
    rows = []
    for outcome, refs in TWINS.items():
        if outcome in ("donation_ams", "newsletter_signup"):
            continue                      # not 0-100; the link is stated on the slider scale
        for key in refs:
            g = idx.get(key)
            if g is None:
                continue
            for m in mods:
                if g[m].isna().all():
                    continue
                for side, d, col in (("human", g, "value"), ("synth", ctrl, outcome)):
                    z = pd.DataFrame({"v": pd.to_numeric(d[col], errors="coerce"),
                                      "g": d[m]}).dropna()
                    for lvl, zz in z.groupby("g", observed=True):
                        if len(zz) < min_n or lvl in drop_levels:
                            continue
                        rows.append({"side": side, "twin": key, "outcome": outcome,
                                     "moderator": m, "level": lvl, "n": len(zz),
                                     "mean": float(zz.v.mean()), "sd": float(zz.v.std(ddof=1))})
    R = pd.DataFrame(rows)
    return R.drop_duplicates(subset=["side", "outcome", "moderator", "level", "twin"])


def fit_gamma(R: pd.DataFrame, side: str) -> dict:
    """log(SD_group) = outcome fixed effects + gamma * log(p(1-p)),  p = mean/100.

    gamma = 0 is a constant within-cell SD (what `ssb.synth` did before spread_gamma);
    gamma = 0.5 is a Beta of constant precision; humans read 1.0.
    """
    d = R[R.side == side].drop_duplicates(subset=["outcome", "moderator", "level"]).copy()
    if len(d) < 10:
        return {"gamma": float("nan"), "se": float("nan"), "n": len(d), "r2": float("nan")}
    p = np.clip(d["mean"].to_numpy(float) / 100.0, 1e-3, 1 - 1e-3)
    x = np.log(p * (1 - p))
    y = np.log(d["sd"].to_numpy(float))
    D = pd.get_dummies(d.outcome).astype(float).to_numpy()
    A = np.column_stack([D, x])
    b, *_ = np.linalg.lstsq(A, y, rcond=None)
    pred = A @ b
    dof = max(1, len(d) - A.shape[1])
    se = float(np.sqrt(((y - pred) ** 2).sum() / dof * np.linalg.pinv(A.T @ A)[-1, -1]))
    return {"gamma": float(b[-1]), "se": se, "n": int(len(d)),
            "r2": float(1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum())}


def audit_twin_subgroup(t1: pd.DataFrame, href: pd.DataFrame, min_n=30) -> pd.DataFrame:
    """Row: Within-subgroup distributions, against the CONSTRUCT twin rather than the
    format pool - the only version of that row in which a difference is attributable."""
    ctrl = t1[t1.condition == "control"]
    idx = {f"{s}:{c}": g for (s, c), g in href.groupby(["source", "human_col"], observed=True)}
    rows = []
    for outcome, refs in TWINS.items():
        for key in refs:
            g = idx.get(key)
            if g is None:
                continue
            hu = g.rename(columns={"value": outcome})
            r = score.within_subgroup_distributions(ctrl, hu, outcome, min_n=min_n)
            if len(r):
                r.insert(0, "twin", key)
                rows.append(r)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


if __name__ == "__main__":
    raise SystemExit(main())
