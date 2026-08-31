#!/usr/bin/env python
"""tools/tau_sensitivity.py - the one line the operator will be asked about. 0 model calls.

    /opt/kernel/venv/bin/python tools/tau_sensitivity.py
    /opt/kernel/venv/bin/python tools/tau_sensitivity.py --selftest

TASK_17 direction 2, and session 16's own second-ranked next step. The campaign quotes
`pearson_r_within_outcomes` = 0.45, range 0.25-0.53, and that number is a FUNCTION of tau - the SD
of the target's true within-outcome-demeaned message effects, which is sealed. Three things were
missing and all three are cheap:

  1. the MAP, not three points on it: tau -> ceiling -> expected score, on a grid, so a reader can
     put the quote anywhere;
  2. the INVERSE: what would tau have to be for the quote to be wrong? A range is only a claim if
     something could falsify it;
  3. the DIRECTION of every reading that fed the range. `runs/_trusttask4/PREREG.md` U4 says the
     in-family orchinik2024 reading is a LOWER bound on the target's tau (two arms, both
     pro-science passages differing only in which warrant they give, against sixteen deliberately
     diverse messages) - and U3a used the same reading's interval to lower the range's HIGH end.
     Those two uses point opposite ways. This tool prints both readings side by side and says
     which is quoted and why, instead of leaving the tension inside a pre-registration.

Nothing here is a new estimate of tau. Every input is `runs/_tau/tau.json` and the deposited card's
own control SDs; the arithmetic is `tools/tau_estimate.py:project`, unchanged.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / "tools"))
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
from tau_estimate import NORM_SKILL, TARGET_K, TARGET_N, project   # noqa: E402


def target_sd() -> pd.Series:
    base = pd.read_csv(RUN / "runs/20260815-target-01/card/baseline.csv")
    sd = base.set_index("outcome").control_sd.copy()
    sd["donation_ams"] *= 10.0          # $0-10 -> pp
    sd["newsletter_signup"] *= 100.0    # 0/1  -> pp
    return sd


def invert(r_target: float, sd: np.ndarray, which: int = 1,
           lo: float = 1e-4, hi: float = 60.0) -> float:
    """The tau that produces a given expected score. `which`: 1 = point, 0 = ceiling,
    2/3 = the ends of the skill interval. Monotone in tau, so bisection is exact enough."""
    f = lambda t: project(t, sd)[which]
    if f(hi) < r_target:
        return float("inf")
    if f(lo) > r_target:
        return 0.0
    for _ in range(200):
        mid = 0.5 * (lo + hi)
        if f(mid) < r_target:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


# --------------------------------------------------------------------------------- self-test
def selftest(reps: int = 400, seed: int = 20260822) -> None:
    """Standing finding 90: make the projection recover a tau CHOSEN IN ADVANCE.

    Simulate the target's own design - k = 16 message arms, n per arm from the Human-1 half, one
    outcome with a chosen respondent SD - with true within-outcome-demeaned effects of a known
    tau, hand an ORACLE predictor the true effects, and score it exactly as the frozen table's
    `pearson_r within outcomes` row does. The realised correlation must land on `project`'s
    CEILING, which is the half of the quote that is arithmetic. (The other half, the 0.66 skill
    normalisation, is an empirical constant from runs/_decomp and is not testable here.)"""
    rng = np.random.default_rng(seed)
    n, sigma = int(TARGET_N), 25.0
    print("  target-shaped simulation: k = %d arms, n = %d per arm (Human 1), sigma = %.0f pp"
          % (TARGET_K, n, sigma))
    ok = True
    for tau in (0.5, 1.14, 2.58, 5.0):
        rs = []
        for _ in range(reps):
            t = rng.normal(0, tau, TARGET_K)
            t = t - t.mean()                                   # demeaned within the outcome
            obs = t + rng.normal(0, sigma / math.sqrt(n), TARGET_K)
            obs = obs - obs.mean()
            rs.append(np.corrcoef(t, obs)[0, 1])
        got, want = float(np.mean(rs)), project(tau, np.array([sigma]))[0]
        # the k-1 demeaning inflates the noise slightly relative to the k-arm formula
        bad = abs(got - want) > 0.05
        ok &= not bad
        print("     tau %.2f pp -> ceiling predicted %.3f, simulated %.3f   %s"
              % (tau, want, got, "FAIL" if bad else "OK"))
    assert ok, "the projection does not reproduce a simulated ceiling"
    # and the inverse must round-trip
    sd = target_sd().values
    for r in (0.25, 0.45, 0.53):
        t = invert(r, sd)
        back = project(t, sd)[1]
        assert abs(back - r) < 1e-3, (r, t, back)
    print("     inverse round-trips at r = 0.25 / 0.45 / 0.53 to < 1e-3")
    print("  selftest OK")


# -------------------------------------------------------------------------------------- main
def main() -> int:
    tau = json.loads((RUN / "runs/_tau/tau.json").read_text())
    sd = target_sd()
    v = sd.values
    low, centre, high15, high16 = tau["low"], tau["centre"], tau["high"], tau["high_task16"]
    prim, infam = tau["tau_primary"], tau["infamily_orchinik2024"]["perception"]

    print(__doc__.split("TASK_17 direction 2")[0])
    print("TARGET DESIGN (frozen): %d message arms, Human-1 n = %.0f per arm, the deposited card's"
          " own control SDs" % (TARGET_K, TARGET_N))
    print("SKILL NORMALISATION: %.2f [%.2f, %.2f] of the ceiling (runs/_decomp, session 14)"
          % NORM_SKILL)

    # ---------------------------------------------------------------- 1. the map
    print("\n1. THE MAP  tau -> ceiling -> expected `pearson_r_within_outcomes`")
    print("   %-10s %9s %11s %18s   %s" % ("tau (pp)", "ceiling", "expected r", "[skill interval]",
                                           "what sits here"))
    marks = {round(low, 2): "LOW end (substituted 0.5 pp floor; the trust anchor reads 0.00)",
             round(centre, 2): "CENTRE - the QUOTE",
             round(high16, 2): "HIGH end as published (TASK_16 U3a)",
             round(prim, 2): "primary climate x message x slider stratum (session 15 high end)"}
    grid = sorted(set([round(x, 2) for x in np.arange(0.0, 6.01, 0.25)]
                      + [round(low, 2), round(centre, 2), round(high16, 2), round(prim, 2)]))
    for t in grid:
        c, e, elo, ehi = project(t, v)
        print("   %-10.2f %9.3f %11.2f %18s   %s"
              % (t, c, e, "[%.2f, %.2f]" % (elo, ehi), marks.get(t, "")))

    # ---------------------------------------------------------------- 2. the inverse
    print("\n2. THE INVERSE - what would tau have to be for the quote to be wrong?")
    r_lo, r_c, r_hi = tau["quote"]["range_r"][0], tau["quote"]["centre_r"], tau["quote"]["range_r"][1]
    t_lo, t_c, t_hi = invert(r_lo, v), invert(r_c, v), invert(r_hi, v)
    print("   the published quote is r = %.2f, range %.2f-%.2f, which inverts to"
          % (r_c, r_lo, r_hi))
    print("   tau = %.2f pp, range %.2f-%.2f pp." % (t_c, t_lo, t_hi))
    print()
    print("   >>> ONE LINE: the quoted range 0.25-0.53 is wrong only if the target's true tau is")
    print("   >>> below %.2f pp or above %.2f pp - and the entire evidence base is a set of"
          % (t_lo, t_hi))
    print("   >>> readings between 0.00 and %.2f pp, so the range's LOW end is the one that can"
          % prim)
    print("   >>> fail: every in-family reading on disk (0.00, 0.00, 0.53, 0.70 pp) sits BELOW")
    print("   >>> %.2f pp." % t_lo)
    print()
    print("   the asymmetry, stated as a slope rather than a boundary:")
    for t in (0.25, 0.5, 1.0, 2.0, 4.0):
        d = project(t + 0.25, v)[1] - project(t, v)[1]
        print("     at tau = %.2f pp, +0.25 pp of tau buys %+0.3f of expected r" % (t, d))
    print("   the map is steepest exactly where the in-family evidence sits, which is why a range")
    print("   whose low end is a SUBSTITUTED floor is the fragile part of the quote.")

    # ---------------------------------------------------------------- 3. direction of evidence
    print("\n3. WHICH WAY EACH READING BOUNDS TAU  (the in-family lower-bound argument, attached)")
    rows = [
        ("primary climate x message x slider", prim, "UPPER-ish",
         "4 climate studies, 34 slider cells, message arms - out of family (belief/policy), and"
         " these studies' arms differ in topic as well as tone"),
        ("bbprime2025 alone (post-hoc)", 6.51, "UPPER",
         "its News Comments arms manipulate the relevance of the very headlines the outcomes ask"
         " about - proximal cells no target outcome resembles"),
        ("design twin voelkel2026 alone", 0.60, "neither",
         "same panel and slider format as the target, climate belief/policy outcomes"),
        ("orchinik2024 perception (in family, in format)", infam["tau"], "LOWER",
         "PREREG U4: 2 arms, both pro-science passages differing only in which warrant they give."
         " 16 deliberately diverse messages must differ by at least this much"),
        ("orchinik2024 belief, same respondents", tau["infamily_orchinik2024"]["belief"]["tau"],
         "LOWER", "the within-study control; the difference from the perception reading is not"
         " resolvable (P = 0.60)"),
        ("koetke2024 trust outcomes (post-hoc, k=3)", 0.70, "LOWER",
         "3 arms differing in a rhetorical move inside one paragraph - finding 85's shape"),
    ]
    print("   %-46s %7s %-10s %s" % ("reading", "tau pp", "bounds", "why"))
    for name, t, d, why in rows:
        print("   %-46s %7.2f %-10s %s" % (name, t, d, why[:70]))
        if len(why) > 70:
            print("   %-46s %7s %-10s %s" % ("", "", "", why[70:]))

    print("\n   THE TENSION, NAMED. `runs/_trusttask4/PREREG.md` uses the orchinik reading twice and")
    print("   in opposite directions: U3a takes its 95%% upper bound (%.2f pp) as the new HIGH end"
          % high16)
    print("   of the range, while U4 says the same reading is a LOWER bound on the target's tau.")
    print("   A reading cannot cap a range it is a floor for. Under U4 read alone the high end")
    print("   reverts to the primary stratum:")
    for lab, t in (("published (U3a caps the high end at the in-family CI)", high16),
                   ("U4 read alone (in-family reading is a floor, not a cap)", prim)):
        print("     %-56s high tau %.2f pp -> r %.2f, range %.2f-%.2f"
              % (lab, t, project(t, v)[1], project(low, v)[1], project(t, v)[1]))
    print("   THE PUBLISHED QUOTE IS KEPT AND IS THE CONSERVATIVE ONE: it is the narrower range and")
    print("   the lower top end, it was fixed in a pre-registration before the number existed, and")
    print("   RUNBOOK 2a forbids widening a published interval after seeing what would widen it.")
    print("   What changes is that the report now says the high end is a CAP TAKEN FROM A FLOOR,")
    print("   so a target that scores above 0.53 is not a surprise the harness failed to predict.")

    # ---------------------------------------------------------------- 4. what else moves it
    print("\n4. WHAT ELSE MOVES THE QUOTE, at the centre tau = %.2f pp" % centre)
    c, e, elo, ehi = project(centre, v)
    print("   ceiling %.3f x skill %.2f [%.2f, %.2f] = r %.2f [%.2f, %.2f]"
          % (c, NORM_SKILL[0], NORM_SKILL[1], NORM_SKILL[2], e, elo, ehi))
    print("   the skill normalisation contributes +-%.3f of width; tau over its own published"
          % ((ehi - elo) / 2))
    print("   range contributes +-%.3f. The two are the same size, so a session that pins tau"
          % ((project(high16, v)[1] - project(low, v)[1]) / 2))
    print("   further and leaves the skill factor alone halves nothing.")
    print("\n   and the FLOOR beneath all of it (tools/null_audit.py, this session): on a target of")
    print("   16 arms x 13 outcomes the permutation null is far tighter than on the small practice")
    print("   tasks, but the quote is a point prediction of a score, not a claim of significance -")
    print("   the two limits answer different questions and both belong in the report.")

    out = {"map": [{"tau": t, **dict(zip(("ceiling", "r", "r_lo", "r_hi"), project(t, v)))}
                   for t in grid],
           "quote": {"r": r_c, "range": [r_lo, r_hi], "tau": t_c, "tau_range": [t_lo, t_hi]},
           "readings": [{"name": n, "tau": t, "bounds": d} for n, t, d, _ in rows],
           "high_end_published": high16, "high_end_u4_alone": prim}
    (RUN / "runs/_tau/sensitivity.json").write_text(json.dumps(out, indent=1))
    print("\nwritten: runs/_tau/sensitivity.json")
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        selftest()
        raise SystemExit(0)
    raise SystemExit(main())
