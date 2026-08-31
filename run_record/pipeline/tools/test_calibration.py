#!/usr/bin/env python
"""RED-path tests for the calibration map - the stage-4 equivalent of tools/test_gates.py.

`ssb.predict.fit_calibration(pairs, by="family")` looked like per-family calibration through every
dry run and every rehearsal, and was inert: pairs.csv's `family` column holds "practice_<task>", so
`apply_calibration` looked up trust/policy/belief/behaviour, found nothing, and quietly used the
pooled slope for all 208 cells. Nothing failed. Nothing was wrong-looking. That is the shape of
standing finding 26 - a field that is present is not a field that is true.

These six cases fix the behaviour in both directions: the silent fallback is now DETECTABLE, a real
family map is proven to actually bite, and the properties the map must never lose (a null stays a
null; in_slope is respected) are asserted rather than assumed.

    /opt/kernel/venv/bin/python tools/test_calibration.py
"""
import json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402

FAM = ssb.predict.FAMILY
OUTS = list(FAM)
results = []


def check(name, got, want, detail=""):
    ok = bool(got == want) if not isinstance(want, str) else bool(got)
    results.append((name, "ok" if ok else "FAIL", detail))
    return ok


def ate(v=1.0):
    return pd.DataFrame({"condition": ["A"] * len(OUTS), "outcome": OUTS, "ate": [v] * len(OUTS)})


# 1. a map keyed on TASK names (what practice.py actually writes) silently gives pooled everywhere
lam_task = {"_pooled": 1.5, "_n": 498, "practice_bbprime2025": 1.55, "practice_voelkel2026": 1.29}
out = ssb.predict.apply_calibration(ate(), lam_task, family_of=FAM)
check("a task-keyed map applies the POOLED slope to every outcome",
      sorted(out.ate.round(6).unique().tolist()), [1.5],
      "13 outcomes, 1 distinct multiplier - the per-family argument did nothing")

# 2. and the fallback is now DETECTABLE without running a call
applied = {o: (str(FAM[o]) if str(FAM[o]) in lam_task else "_pooled") for o in OUTS}
check("the silent fallback is detectable from the map alone",
      set(applied.values()), {"_pooled"},
      "target.py records _applied_per_outcome and prints it, so pooled is a decision not an accident")

# 3. a map keyed on REAL family names does bite, and differently per family
lam_fam = {"_pooled": 1.5, "_n": 223, "behaviour": 1.578, "belief": 1.135, "policy": 1.255}
out = ssb.predict.apply_calibration(ate(), lam_fam, family_of=FAM)
got = {f: sorted(out[out.outcome.map(FAM) == f].ate.round(3).unique().tolist()) for f in set(FAM.values())}
check("a family-keyed map applies a different slope per family",
      got, {"behaviour": [1.578], "belief": [1.135], "policy": [1.255], "trust": [1.5]},
      "trust falls back to pooled because NO practice task measures trust - 0 of 1,101 cells")

# 4. a predicted null stays a null under any map (the fit is through the origin)
out = ssb.predict.apply_calibration(ate(0.0), lam_fam, family_of=FAM)
check("a null prediction stays null", out.ate.abs().max(), 0.0,
      "a shrinkage that moves a zero would invent an effect")

# 5. in_slope is respected: excluded rows cannot move the slope
n = 200
rng = np.random.default_rng(0)
good = pd.DataFrame({"pred": rng.normal(0, 1, n), "family": "f"})
good["human"] = good.pred * 1.5
bad = pd.DataFrame({"pred": rng.normal(0, 1, n), "family": "f"})
bad["human"] = bad.pred * 9.0
p = pd.concat([good.assign(in_slope=True), bad.assign(in_slope=False)], ignore_index=True)
lam = ssb.predict.fit_calibration(p, by=None)
check("in_slope=False rows do not move the fitted slope", round(lam["_pooled"], 3), 1.5,
      "200 excluded rows at slope 9.0 present and ignored; n=%d" % lam["_n"])

# 6. the live pairs.csv is in the state these tests describe - if practice.py ever starts writing
#    real family names, this case fails and the fallback note in target.py must be revisited
live = sorted(RUN.glob("runs/*/stages/calibration/pairs.csv"))
if live:
    f = pd.read_csv(live[-1])
    fams = set(f.family.astype(str).unique())
    check("the live pairs.csv family column is task-keyed, not family-keyed",
          bool(fams & set(FAM.values())), False,
          "%s has families %s" % (live[-1].parent.parent.parent.name, sorted(fams)))

# 7. STANDING FINDING 49: a scalar lambda cannot move four of the six Section-1 rows, which is most
#    of what OPEN item 18 was arguing about. Enforced here so a later session that implements a
#    NON-scalar calibration (quantile map, per-cell shrinkage, a floor) finds out that the
#    "both cards are rank-identical" reasoning no longer holds, instead of inheriting it.
from ssb import score as _S  # noqa: E402

_rng = np.random.default_rng(7)
_n = 208
_pred = np.round(_rng.normal(1.0, 1.2, _n), 1)
_hum = 1.4 * _pred + _rng.normal(0, 2.5, _n)
_df = pd.DataFrame({"condition": np.repeat([f"c{i}" for i in range(16)], 13),
                    "outcome": list(OUTS) * 16, "pred": _pred, "human": _hum})
_a = _S.ate_recovery(_df)
_b = _S.ate_recovery(_df.assign(pred=_df.pred * 1.5212356540716172))
_invariant = ["directional_agreement", "spearman_rho", "pearson_r", "pearson_r_within_outcomes"]
check("a scalar lambda leaves 4 of 6 Section-1 rows EXACTLY unchanged (finding 49)",
      all(abs(_a[k] - _b[k]) < 1e-12 for k in _invariant), True,
      "dir/rho/r/r_within identical; only RMSE and the Section-2 slope can move")
check("and it DOES move RMSE, so the test is not vacuous",
      abs(_a["rmse_pp"] - _b["rmse_pp"]) > 1e-6, True,
      "RMSE %.4f -> %.4f pp" % (_a["rmse_pp"], _b["rmse_pp"]))
# a NON-scalar transform must break the invariance, or this test proves nothing
_q = _df.assign(pred=np.sign(_df.pred) * np.abs(_df.pred) ** 1.6)
_c = _S.ate_recovery(_q)
check("a NON-scalar transform breaks it (negative control)",
      any(abs(_a[k] - _c[k]) > 1e-9 for k in _invariant), True,
      "so the invariance is a property of scalars, not of the metrics")

print("\n%-62s%-7s%s" % ("case", "result", "detail"))
for nme, r, det in results:
    print("%-62s%-7s%s" % (nme, r, det))
bad_n = sum(1 for _, r, _ in results if r != "ok")
print("\ncalibration map %s: %d cases" % ("PASS" if not bad_n else "FAIL (%d)" % bad_n, len(results)))
sys.exit(1 if bad_n else 0)
