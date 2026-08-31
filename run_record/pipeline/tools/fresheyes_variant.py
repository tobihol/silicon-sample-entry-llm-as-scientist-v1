#!/usr/bin/env python
"""The `fresheyes` elicitation variant - arm `fresheyes`'s own prompt design.

Declared in runs/20260820-target-fresheyes/PREREG.md section 2 BEFORE any call:

  F1  the brief carries the CONTROL-ARM LEVEL of every outcome. An effect in percentage points
      of scale range is bounded by where the control arm already sits; the shared prompt never
      tells the predictor that. On a practice task the level is the task's own control mean,
      computed from the dataset (a LEVEL, never an effect - sealed/truth.csv holds ATEs and is
      not opened here). On the target it is this arm's anchored estimate, labelled as such.
  F2  the brief carries the study's RESOLUTION: arm size and the implied standard error of one
      ATE, so the predictor knows what the design can and cannot detect.
  F3  no reasoning channel and no ranking request; the CSV is asked for directly.

Everything else is untouched: same stimulus texts, same item wordings, same titles, same order,
same CSV contract, same frozen argv, same parser.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402

_BASE = ssb.predict.SYSTEM

SYSTEM = """You are a research analyst predicting the results of a randomised message experiment.
You reason at the level of the analysis - the average treatment effect of each message on each
outcome, against the control arm - never by imagining individual respondents.

Rules:
- Answer ONLY with CSV: a header line `condition,outcome,ate` then one row per cell. No prose.
- `ate` is the treatment effect in percentage points of that outcome's scale range (a 0-100
  slider: 1 unit = 1 pp; a $0-10 item: $1 = 10 pp; a 0/1 item: 1 percentage point of the rate
  = 1 pp).
- Every outcome is listed with the level the CONTROL arm sits at. Use it: an outcome whose
  control mean is already near the top of its scale has little room to move, and an outcome
  with a low base rate cannot move by more than its own headroom.
- Effects may be negative, and a message that plausibly backfires on an outcome should get a
  negative number. A reverse-valenced outcome (e.g. a distrust item) moves opposite to the
  construct the message pushes.
- Fill every cell. Do not omit rows, do not write NA.
- Give your honest ordering and relative magnitude. Do not inflate effects to look decisive:
  in message experiments of this size most effects are small, and some are indistinguishable
  from zero.
"""


def _fmt(x, nd=1):
    return ("%%.%df" % nd) % float(x)


def _outcome_items(brief):
    outs = brief["outcomes"]
    if isinstance(outs, dict):
        return [(k, v) for k, v in outs.items()]
    return [(o["name"], o) for o in outs]


def apply(brief: dict, levels: dict, resolution: str | None = None,
          level_note: str = "control-arm mean") -> tuple[dict, dict]:
    """(transformed brief, metadata).

    `levels` maps outcome name -> control level in the outcome's OWN native units. Any outcome
    missing from `levels` is left alone and counted in the metadata, so a partial anchor set is
    visible rather than silent.
    """
    b = json.loads(json.dumps(brief))
    n_lev = 0
    outs = b["outcomes"]
    items = outs.items() if isinstance(outs, dict) else ((o["name"], o) for o in outs)
    for name, o in items:
        if name in levels and np.isfinite(float(levels[name])):
            lo, hi = float(o.get("lo", 0)), float(o.get("hi", 100))
            nd = 2 if (hi - lo) <= 1.5 else 1
            q = str(o.get("question", "")).strip()
            o["question"] = (q + ("  " if q else "")
                             + "[%s %s]" % (level_note, _fmt(levels[name], nd)))
            n_lev += 1
    if resolution:
        b["note"] = ((b.get("note", "") or "").strip() + " " + resolution.strip()).strip()
    meta = {"variant": "fresheyes", "system_replaced": True,
            "levels_given": n_lev, "levels_missing": len(list(_outcome_items(brief))) - n_lev,
            "resolution_given": bool(resolution), "system_sha": _sha(SYSTEM)}
    return b, meta


def _sha(s: str) -> str:
    import hashlib
    return hashlib.sha256(s.encode()).hexdigest()[:12]


def control_levels_from_data(task: str) -> dict:
    """The control-arm mean of every outcome of a carved practice task, in NATIVE units.

    Computed from the source dataset the adapter names, weighted where the adapter names a
    weight column - the same estimand `ssb.task.true_ates` differences against. It reads the
    DATASET, never `sealed/`: a control level is not a treatment effect.
    """
    ad = ssb.task.load_adapter(task)
    df = ssb.task.load_dataset(ad)
    w = df[ad["weight_col"]].to_numpy(float) if ad.get("weight_col") else np.ones(len(df))
    is_ctrl = df["_arm"].isin(set(ad["control_arms"])).to_numpy()
    out = {}
    for oname, o in ad["outcomes"].items():
        v = df[o["col"]].to_numpy(float)
        if o.get("reverse"):
            v = (float(o["lo"]) + float(o["hi"])) - v
        m = is_ctrl & np.isfinite(v)
        if m.sum() > 2:
            out[oname] = float(np.average(v[m], weights=w[m]))
    return out


def resolution_note(task: str) -> str:
    """F2 for a practice task: arm size and the SE of one ATE, from the dataset's own spread."""
    ad = ssb.task.load_adapter(task)
    df = ssb.task.load_dataset(ad)
    ctrl = set(ad["control_arms"])
    arms = sorted(set(df["_arm"].dropna()) - ctrl)
    n_arm = int(np.median([int((df["_arm"] == a).sum()) for a in arms])) if arms else 0
    n_ctrl = int(df["_arm"].isin(ctrl).sum())
    ses = []
    for oname, o in ad["outcomes"].items():
        v = df[o["col"]].to_numpy(float)
        sd = float(np.nanstd(v, ddof=1)) * 100.0 / (float(o["hi"]) - float(o["lo"]))
        if np.isfinite(sd) and n_arm and n_ctrl:
            ses.append(sd * np.sqrt(1.0 / n_arm + 1.0 / n_ctrl))
    se = float(np.median(ses)) if ses else float("nan")
    return ("RESOLUTION: about %d respondents per message arm and %d in control, so the standard "
            "error of a single message x outcome effect is roughly %s percentage points. "
            "Differences smaller than that are not resolvable by this study."
            % (n_arm, n_ctrl, _fmt(se, 2)))
