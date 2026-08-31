"""ssb.task - training tasks with held-out ground truth, and the leak audit.

A *training task* is shaped exactly like the target task, so practice scores are
comparable to the thing they are meant to predict and the predictor prompt is
literally the same prompt:

    task/
      brief/            EVERYTHING the predictor may read
        task.json         arms (title + full message text), outcomes + scales,
                          sample description, n per arm, control-condition means
        template.csv      condition, outcome, ate  - blank, to be filled
      sealed/           NEVER given to the predictor
        truth.csv         condition, outcome, ate, se  (pp)
        manifest.json     sha256 of truth.csv, carve parameters, git-free provenance

Blinding is enforced by construction (the predictor is handed `brief/` and only
`brief/`) and then AUDITED (`leak_audit` greps the predictor's own transcript for
the sealed path and for the sealed values). A blinding claim nobody checked is
not evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

from . import spec

ADAPTERS = spec.RUNROOT / "inputs" / "adapters"


def load_adapter(name: str) -> dict:
    """A dataset adapter is a declarative JSON file - no code per dataset.

    Required keys:
      dataset, file, reader ("csv"|"sav"|"sas7bdat"|"dta"), condition_col,
      arms {raw_value: arm_title}, control_arms [..],
      outcomes {out_name: {"col":..., "lo":..., "hi":..., "reverse":bool}},
      moderators {target_mod: {"col":..., "map":{raw: level}}},
      filters [{"col":..., "eq":...}], weight_col (nullable),
      message_texts {arm_title: "..."} or message_texts_file,
      provenance {readme_claims, verified_by, caveats}
    """
    p = ADAPTERS / f"{name}.json"
    if not p.exists():
        raise FileNotFoundError(
            f"no adapter for {name!r}. Adapters are built in the `adapters` stage "
            f"from notes/DATA_experiments.md; see AGENTS.md.")
    return json.loads(p.read_text())


def load_dataset(ad: dict) -> pd.DataFrame:
    """Read the analysis file named by an adapter, apply its filters, recode."""
    path = Path(ad["file"])
    reader = ad.get("reader", "csv")
    if reader == "csv":
        df = pd.read_csv(path, low_memory=False, **ad.get("read_kwargs", {}))
    elif reader in ("xlsx", "excel"):
        df = pd.read_excel(path, **ad.get("read_kwargs", {}))
    elif reader in ("sav", "dta", "sas7bdat"):
        import pyreadstat  # declared in pyproject only if a run needs it
        df, _ = getattr(pyreadstat, f"read_{reader}")(str(path), **ad.get("read_kwargs", {}))
    else:
        raise ValueError(f"unknown reader {reader!r}")
    for f in ad.get("filters", []):
        df = df[df[f["col"]] == f["eq"]] if "eq" in f else df[df[f["col"]].isin(f["isin"])]
    df = df[df[ad["condition_col"]].isin(ad["arms"].keys())].copy()
    df["_arm"] = df[ad["condition_col"]].map(ad["arms"])
    for m, mm in ad.get("moderators", {}).items():
        if "bins" in mm:   # numeric -> band, e.g. age -> age_band
            df[m] = pd.cut(pd.to_numeric(df[mm["col"]], errors="coerce"),
                           bins=mm["bins"], labels=mm["labels"], right=mm.get("right", True))
        else:
            df[m] = _map_codes(df[mm["col"]], mm["map"])
    # De-zero-fill: a column that stores 0 for people who never REACHED the item is not
    # missing-at-random data, it is an attrition artefact (goldwert2026's `newsletter`,
    # `letter`, `donation_bin`). `observed_if_any` names the raw columns whose presence
    # proves the respondent reached that block; everything else becomes NaN.
    for oname, o in ad.get("outcomes", {}).items():
        gate = o.get("observed_if_any")
        if gate:
            df[o["col"]] = pd.to_numeric(df[o["col"]], errors="coerce").where(
                df[gate].notna().any(axis=1))
    return df


def _norm_code(v) -> str:
    """Canonical string for a raw code, so an adapter written as {"1": ...} still
    matches a column pandas read as 1.0, b'1', or ' 1 '."""
    if isinstance(v, bytes):
        v = v.decode("utf-8", "ignore")
    s = str(v).strip()
    try:
        f = float(s)
        if np.isfinite(f) and float(f).is_integer():
            return str(int(f))
    except (TypeError, ValueError):
        pass
    return s


def _map_codes(col: pd.Series, mapping: dict) -> pd.Series:
    m = {_norm_code(k): v for k, v in mapping.items()}
    return col.map(lambda v: m.get(_norm_code(v)))


def _n(x) -> int:
    """Cell count as an int, tolerating the NaN that wm() returns for a cell of n<=2.
    A thin subgroup cell is a real fact about the data, not a reason to refuse to carve."""
    return int(x) if np.isfinite(x) else 0


def true_ates(df: pd.DataFrame, ad: dict, moderator: str | None = None) -> pd.DataFrame:
    """Arm x outcome ATEs vs the pooled control arms, in percentage points of range.

    Weighted where the adapter names a weight column, because an unweighted mean of
    a quota panel is not the estimand the source paper reports.
    """
    w = df[ad["weight_col"]].to_numpy(float) if ad.get("weight_col") else np.ones(len(df))
    ctrl_arms = set(ad["control_arms"])
    # A pooled control is wrong when the arms are not comparable to each other: tappin2023's 48
    # message arms each argue about a DIFFERENT policy issue, so arm i's counterfactual is the
    # control respondents who were asked about issue i, not the grand mean over 24 issues.
    # `control_strata` names a column whose value must match between an arm and the control rows
    # it is differenced against. Absent (every task before task 6), behaviour is unchanged.
    strata_col = ad.get("control_strata")
    strata_of = {}
    if strata_col:
        for arm, g in df.groupby("_arm"):
            vals = sorted(set(g[strata_col].dropna().astype(str)))
            if arm not in ctrl_arms and len(vals) != 1:
                raise ValueError("control_strata %r: arm %r spans %d strata (%s); an arm must sit "
                                 "in exactly one stratum or its control is ambiguous"
                                 % (strata_col, arm, len(vals), vals[:5]))
            if arm not in ctrl_arms:
                strata_of[arm] = vals[0]
    rows = []
    groups = [(None, df)] if moderator is None else list(df.groupby(moderator))
    for lvl, g in groups:
        gw = w[g.index.get_indexer_for(g.index)] if moderator else w
        gw = g[ad["weight_col"]].to_numpy(float) if ad.get("weight_col") else np.ones(len(g))
        for oname, o in ad["outcomes"].items():
            col, lo, hi = o["col"], o["lo"], o["hi"]
            v = g[col].to_numpy(float)
            if o.get("reverse"):
                v = (lo + hi) - v
            ok = np.isfinite(v)
            def wm(mask):
                m = mask & ok
                return (np.average(v[m], weights=gw[m]), gw[m].sum(), np.nanstd(v[m], ddof=1), m.sum()) if m.sum() > 2 else (np.nan,)*4
            is_ctrl = g["_arm"].isin(ctrl_arms).to_numpy()
            gstr = g[strata_col].astype(str).to_numpy() if strata_col else None
            cm, cwsum, csd, cn = wm(is_ctrl)
            for arm in sorted(set(g["_arm"]) - ctrl_arms):
                am, awsum, asd, an = wm((g["_arm"] == arm).to_numpy())
                if strata_col:                      # stratum-matched control, see above
                    cm, cwsum, csd, cn = wm(is_ctrl & (gstr == strata_of[arm]))
                scale = 100.0 / (hi - lo)
                se = np.sqrt(asd**2 / max(an, 1) + csd**2 / max(cn, 1)) * scale
                rows.append({"condition": arm, "outcome": oname,
                             "moderator_level": lvl,
                             "ate": (am - cm) * scale, "se": se,
                             "n_treat": _n(an), "n_control": _n(cn)})
    return pd.DataFrame(rows)


def attrition_bounds(df: pd.DataFrame, ad: dict) -> pd.DataFrame:
    """Lee (2009) trimming bounds on each arm-vs-control ATE, in pp of scale range.

    Differential attrition is not a nuisance to be filtered away: conditioning on
    having answered is post-treatment conditioning, so the filtered ATE is not the
    randomised contrast. Selection here is *observing the outcome at all* (after the
    adapter's `observed_if_any` de-zero-filling), measured on the full randomised
    sample. The arm with the higher observation rate is trimmed by
    q = (s_hi - s_lo) / s_hi at the top (lower bound) and at the bottom (upper bound),
    which is the worst case under the assumption that treatment moves selection in one
    direction only. The WIDTH is what the run report has to quote: a bound wider than
    the effect means the magnitude is not identified by the data, however tight its
    standard error looks.
    """
    ctrl = set(ad["control_arms"])
    cmask = df["_arm"].isin(ctrl).to_numpy()
    rows = []
    for oname, o in ad["outcomes"].items():
        v = pd.to_numeric(df[o["col"]], errors="coerce").to_numpy(float)
        if o.get("reverse"):
            v = (o["lo"] + o["hi"]) - v
        sc = 100.0 / (o["hi"] - o["lo"])
        obs = np.isfinite(v)
        s_c = obs[cmask].mean()
        vc = v[cmask & obs]
        for arm in sorted(set(df["_arm"]) - ctrl):
            am = (df["_arm"] == arm).to_numpy()
            s_a = obs[am].mean()
            va = v[am & obs]
            if s_a >= s_c:
                q = (s_a - s_c) / s_a if s_a else 0.0
                lo = (_trimmed(va, q, "top") - vc.mean()) * sc
                hi = (_trimmed(va, q, "bottom") - vc.mean()) * sc
            else:
                q = (s_c - s_a) / s_c if s_c else 0.0
                lo = (va.mean() - _trimmed(vc, q, "bottom")) * sc
                hi = (va.mean() - _trimmed(vc, q, "top")) * sc
            rows.append({"condition": arm, "outcome": oname, "lee_lo": lo, "lee_hi": hi,
                         "width": hi - lo, "trim_q": q, "obs_rate_treat": s_a,
                         "obs_rate_control": s_c, "n_randomised_treat": int(am.sum())})
    return pd.DataFrame(rows)


def _trimmed(v: np.ndarray, q: float, side: str) -> float:
    v = np.sort(v[np.isfinite(v)])
    k = int(round(q * len(v)))
    if k <= 0:
        return float(v.mean())
    return float(v[:len(v) - k].mean() if side == "top" else v[k:].mean())


def carve(name: str, task_dir, seed: int = 0, moderator: str | None = None) -> dict:
    """Build a training task from an adapter: sealed truth + a blind brief."""
    ad = load_adapter(name)
    df = load_dataset(ad)
    truth = true_ates(df, ad, moderator)
    task_dir = Path(task_dir)
    (task_dir / "brief").mkdir(parents=True, exist_ok=True)
    (task_dir / "sealed").mkdir(parents=True, exist_ok=True)

    texts = ad.get("message_texts") or json.loads(Path(ad["message_texts_file"]).read_text())
    ctrl = set(ad["control_arms"])
    arms = sorted(set(df["_arm"]) - ctrl)
    n_by_arm = df["_arm"].value_counts().to_dict()
    brief = {
        "task_id": task_dir.name,
        "study": ad["dataset"],
        "sample": ad.get("sample_description", ""),
        "n_total": int(len(df)),
        "n_by_arm": {k: int(v) for k, v in n_by_arm.items()},
        "control_arms": sorted(ctrl),
        "arms": [{"title": a, "text": texts.get(a, "")} for a in arms],
        "control_texts": {a: texts[a] for a in sorted(ctrl) if texts.get(a)},
        "outcomes": {k: {"question": v.get("question", ""), "lo": v["lo"], "hi": v["hi"],
                         "scale_range_pp": 100.0} for k, v in ad["outcomes"].items()},
        "moderator": moderator,
        "instruction": ("Predict the average treatment effect of each arm versus the pooled "
                        "control arms, for each outcome, in percentage points of that "
                        "outcome's scale range. Fill every cell of template.csv."),
    }
    (task_dir / "brief" / "task.json").write_text(json.dumps(brief, indent=1, ensure_ascii=False))
    tmpl = truth[["condition", "outcome"]].drop_duplicates().assign(ate="")
    tmpl.to_csv(task_dir / "brief" / "template.csv", index=False)

    tp = task_dir / "sealed" / "truth.csv"
    truth.to_csv(tp, index=False)
    attrition = None
    if ad.get("attrition_bounds") and moderator is None:
        ab = attrition_bounds(df, ad)
        ab.to_csv(task_dir / "sealed" / "attrition_bounds.csv", index=False)
        j = truth.merge(ab, on=["condition", "outcome"])
        attrition = {"mean_width_pp": float(ab.width.mean()),
                     "median_width_pp": float(ab.width.median()),
                     "max_width_pp": float(ab.width.max()),
                     "mean_trim_q": float(ab.trim_q.mean()),
                     "share_sign_identified": float((np.sign(j.lee_lo) == np.sign(j.lee_hi)).mean()),
                     "median_abs_ate_pp": float(j.ate.abs().median()),
                     "magnitude_identified": bool(ab.width.median() < 2 * j.ate.abs().median()),
                     "note": "Lee bounds on the arm-vs-control contrast; see ssb.task.attrition_bounds"}
    manifest = {
        "task_id": task_dir.name, "adapter": name, "seed": seed, "moderator": moderator,
        "n_cells": int(len(truth)),
        "truth_sha256": hashlib.sha256(tp.read_bytes()).hexdigest(),
        "attrition": attrition,
        "provenance": ad.get("provenance", {}),
    }
    (task_dir / "sealed" / "manifest.json").write_text(json.dumps(manifest, indent=1))
    return {"brief": str(task_dir / "brief"), "sealed": str(task_dir / "sealed"), **manifest}


# --------------------------------------------------------------------------
# leak audit
# --------------------------------------------------------------------------


def leak_audit(task_dir, transcripts: list, value_tol: int = 3) -> dict:
    """Scan a predictor's transcript for evidence it saw the sealed truth.

    Three probes: (a) the sealed path or filename appearing at all, (b) the exact
    sha256, (c) an implausible number of sealed ATE values reproduced to 2 dp.
    Probe (c) is the one that catches a leak that came in by some other route.

    Probe (c) is scored AGAINST A NULL, because a predictor writing small 2-dp effects
    onto the same grid as the truth collides with it by chance a lot. Measured on this
    harness's scripted stub - which reads nothing and knows nothing - the raw echo rate
    was 0.17-0.37, i.e. the naive rule called four of five clean tasks SUSPECT. The null
    is the same match rate against the truth vector shifted by offsets that preserve its
    2-dp grid and its magnitudes; the verdict uses the EXCESS over that null.
    """
    task_dir = Path(task_dir)
    truth = pd.read_csv(task_dir / "sealed" / "truth.csv")
    man = json.loads((task_dir / "sealed" / "manifest.json").read_text())
    ate = truth.ate.dropna()
    vals = {f"{v:.2f}" for v in ate if abs(v) > 0.05}
    blob = ""
    for t in transcripts:
        p = Path(t)
        if p.exists():
            blob += p.read_text(errors="ignore")
    # round every decimal number in the transcript to 2 dp, do not require it to be
    # WRITTEN at 2 dp: the sealed file itself stores full float precision, and the
    # original 2-dp-only regex made a verbatim copy of it invisible to this probe.
    pool = {f"{float(m):.2f}" for m in re.findall(r"-?\d+\.\d+", blob)}
    seen = pool & vals
    rate = len(seen) / max(len(vals), 1)
    rng = np.random.default_rng(int(man["truth_sha256"][:8], 16))
    null = []
    for _ in range(64):
        off = round(float(rng.uniform(-1.0, 1.0)), 2)
        shifted = {f"{v + off:.2f}" for v in ate if abs(v) > 0.05}
        null.append(len(pool & shifted) / max(len(shifted), 1))
    null_rate = float(np.mean(null))
    null_sd = float(np.std(null)) or 1e-6
    z = (rate - null_rate) / null_sd
    hits = {
        "path_mentioned": "sealed" in blob and str(task_dir.name) in blob,
        "sha_mentioned": man["truth_sha256"][:16] in blob,
        "n_truth_values_echoed": len(seen),
        "n_truth_values": len(vals),
        "echo_rate": rate,
        "echo_rate_null": null_rate,
        "echo_excess_z": z,
    }
    excess = rate - null_rate
    hits["echo_excess"] = excess
    hits["verdict"] = "LEAK" if (hits["sha_mentioned"] or excess > 0.25 or z > 8) else (
        "SUSPECT" if hits["path_mentioned"] or z > 4 or excess > 0.10 else "CLEAN")
    return hits


def score_task(task_dir, prediction_csv) -> dict:
    """Score a filled template against the sealed truth, using ssb.score only."""
    from . import score as S
    truth = pd.read_csv(Path(task_dir) / "sealed" / "truth.csv")
    pred = pd.read_csv(prediction_csv)
    d = truth.merge(pred.rename(columns={"ate": "pred"}), on=["condition", "outcome"])
    d = d.rename(columns={"ate": "human", "se": "se_human"})
    return S.scorecard(d)
