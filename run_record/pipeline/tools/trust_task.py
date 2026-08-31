#!/usr/bin/env python
"""The first trust-outcome practice task, graded against its pre-registration - and what it says
about the card's trust cells.

    /opt/kernel/venv/bin/python tools/trust_task.py

Pre-registration: `runs/_trusttask/PREREG.md`, written before any call. Task input:
`tools/build_gligoric.py`. Nothing here calls a model; every transcript is already paid for.

The task is gligoric2025's own randomised experiment: five trust-raising messages against a bare
control, 6,690 US self-identified conservatives, trust in scientists on 7-point bipolar items.
Standing finding 33 says zero of 1,489 scored practice cells are in the target's `trust` family, so
this is the first in-family evidence the harness has ever had. It is also a task with NO signal to
rank (var_true < 0), which is why the pre-registration grades MAGNITUDE against the published
equivalence bound and refuses to read any ranking row as skill.
"""
import argparse, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402

TASK = "gligoric2025"
LINES = [("20260819-practice-gligoric", "claude-opus-5", 3),
         ("20260819-practice-gligoric-fable-5", "claude-fable-5", 1),
         ("20260819-practice-gligoric-sonnet-5", "claude-sonnet-5", 1)]
CARD = RUN / "runs" / "20260815-target-01" / "card"          # the deposited primary candidate
LAMBDA_POOLED = 1.5212                                        # the practice-fitted multiplier
SEED = 20260819


def deltas() -> dict:
    """Equivalence bound per outcome: d = 0.1 of the CONTROL-arm SD, in pp of the 1-7 range.

    d = 0.1 is the bound the published paper's equivalence test reports; the SD is measured on the
    control arm of the randomised (conservative) sample. Both are fixed in the PREREG before any
    call, and the HUMAN table is 40 of 40 inside them.
    """
    d = pd.read_csv(RUN / "inputs" / "derived" / "gligoric2025_trust.csv")
    c = d[(d.conservative == 1) & (d.Condition == "Control")]
    ad = ssb.task.load_adapter(TASK)
    return {o: 0.1 * c[o].std(ddof=1) / (v["hi"] - v["lo"]) * 100 for o, v in ad["outcomes"].items()}


def frame(run_id):
    d = RUN / "runs" / run_id / "tasks" / TASK
    tr = pd.read_csv(d / "sealed" / "truth.csv")
    pr = pd.read_csv(d / "prediction.csv")
    m = (tr.merge(pr, on=["condition", "outcome"], suffixes=("_h", "_p"))
           .rename(columns={"ate_h": "human", "ate_p": "pred"}))
    sm = json.loads((RUN / "runs" / run_id / "stages" / "practice" / "summary.json").read_text())
    return m, sm


def beta_ci(m, n_boot=2000):
    """Slope of human on predicted, with a bootstrap CLUSTERED ON THE ARM (finding 42)."""
    b = float(np.polyfit(m.pred, m.human, 1)[0])
    rng = np.random.default_rng(SEED)
    arms = m.condition.unique()
    out = []
    for _ in range(n_boot):
        s = pd.concat([m[m.condition == a] for a in rng.choice(arms, len(arms), replace=True)])
        if s.pred.std() > 0:
            out.append(float(np.polyfit(s.pred, s.human, 1)[0]))
    return b, float(np.percentile(out, 2.5)), float(np.percentile(out, 97.5))


def main(n_boot=2000):
    D = deltas()
    print("EQUIVALENCE BOUNDS (d = 0.1 x control SD, pp of the 1-7 range)")
    print("  " + "  ".join("%s %.3f" % (k, v) for k, v in D.items()))

    rows = []
    for run_id, line, draws in LINES:
        if not (RUN / "runs" / run_id).exists():
            continue
        m, sm = frame(run_id)
        m["inside"] = m.pred.abs() <= m.outcome.map(D)
        ov = m[m.outcome == "trust_overall"]
        pb = sm["recognition"][0]
        rows.append({"line": line, "draws": draws, "probe": pb["verdict"],
                     # raw, referent undefined under probe v1 (OPEN 36); printed for provenance
                     "conf_raw_uninterpretable": pb["self_report_confidence"],
                     "P1_of_5": int(ov.inside.sum()), "P2": float(m.inside.mean()),
                     "med_abs_pred": float(m.pred.abs().median()),
                     "max_abs_pred": float(m.pred.abs().max()),
                     "share_positive": float((m.pred > 0).mean()),
                     "rmse_pp": float(np.sqrt(((m.pred - m.human) ** 2).mean())),
                     "billed": sm["spend"]["batch_billed_tokens"]})
    t = pd.DataFrame(rows)
    m0, _ = frame(LINES[0][0])
    floor = float(np.sqrt((m0.human ** 2).mean()))
    print("\nPER LINE (P1: of the 5 message arms on trust_overall, |pred| <= 1.963 pp; "
          "P2: share of all 40 cells inside their own bound)")
    print(t.to_string(index=False, float_format=lambda x: "%.3f" % x))
    print("\nhuman table: median |ATE| %.2f pp, max %.2f pp, 40 of 40 inside; no-effect floor RMSE "
          "%.3f pp" % (m0.human.abs().median(), m0.human.abs().max(), floor))
    print("PRE-REGISTERED VERDICTS")
    for r in rows:
        v = ("QUARANTINED (recognised) - not scored, see runs/_trusttask/PREREG.md"
             if r["probe"] == "RECOGNISED" else
             "P1 %s (%d of 5), P2 %s (%.3f)"
             % ("PASS" if r["P1_of_5"] == 5 else "PARTIAL" if r["P1_of_5"] == 4 else "FAIL",
                r["P1_of_5"], "PASS" if r["P2"] >= 0.80 else "FAIL", r["P2"]))
        print("  %-18s %s" % (r["line"], v))

    # S2 - the trust-family slope, declared uninformative before it was computed
    b, lo, hi = beta_ci(m0, n_boot)
    print("\nS2 trust-family calibration slope (claude-opus-5, 40 cells)")
    print("  beta %.3f  [%.3f, %.3f]  (%d resamples clustered on the arm)" % (b, lo, hi, n_boot))
    print("  var_true < 0 on this table, so this is a regression on noise: the interval contains "
          "every value any other task has produced. It may not shrink or stretch any card.")
    print("  for comparison, the per-task slopes already on the board:")
    for run in ["20260815-practice-01", "20260817-practice-t67"]:
        p = RUN / "runs" / run / "stages" / "calibration" / "pairs.csv"
        if p.exists():
            for k, g in pd.read_csv(p).groupby("task"):
                print("    %-16s %.3f" % (k, float(np.polyfit(g.pred, g.human, 1)[0])))
    print("  NOTE the confound this task cannot break: it is the harness's first TRUST task and "
          "only its second COARSE-LIKERT task, and the two coarse-Likert slopes (0.845 here, "
          "0.865 tappin2023) sit together below 1 while every slider task is 1.11-2.31. Finding 69 "
          "predicts exactly that from the scale format alone, so a trust slope and a format slope "
          "are not separable on the mounted data.")

    # Direction 3 - what this implies for the card's trust cells (MEASUREMENT ONLY)
    fam = json.loads((RUN / "inputs" / "outcome_families.json").read_text())
    trust = fam["target_families"]["trust"]
    ate = pd.read_csv(CARD / "ate.csv")
    ct = ate[ate.outcome.isin(trust)]
    dlt = D["trust_overall"]
    print("\nTHE CARD'S TRUST CELLS (%d = 4 trust outcomes x 16 interventions), native units = pp"
          % len(ct))
    print(ct.groupby("outcome").ate.agg(["min", "median", "max"]).round(2).to_string())
    print("\n%-22s%10s%10s%12s%12s" % ("multiplier", "median|", "max|", ">1.963pp", ">2pp"))
    for lam, what in [(1.0, "deposited (unshrunk)"), (LAMBDA_POOLED, "pooled practice lambda"),
                      (b, "this task's beta")]:
        v = (ct.ate * lam).abs()
        print("%-22s%10.2f%10.2f%12.3f%12.3f"
              % ("%.4f %s" % (lam, ""), v.median(), v.max(), (v > dlt).mean(), (v > 2).mean()))
        print("   %s" % what)
    print("\nThe same predictor, same model, same prompt shape, on a REAL randomised trust "
          "experiment: median |pred| %.2f pp, max %.2f pp, %.0f%% positive - inside the published "
          "equivalence bound on 40 of 40 cells. On the target's trust outcomes it writes a median "
          "of %.2f pp and a max of %.2f pp, %.0f%% of them outside that same bound."
          % (m0.pred.abs().median(), m0.pred.abs().max(), 100 * (m0.pred > 0).mean(),
             ct.ate.abs().median(), ct.ate.abs().max(), 100 * (ct.ate.abs() > dlt).mean()))
    print("Measurement only: TASK_12 item 3 forbids a card change, and RUNBOOK 2a forbids editing a "
          "deposited prediction because a diagnostic looked bad.")
    return t


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--bootstrap", type=int, default=2000)
    a = ap.parse_args()
    main(a.bootstrap)
