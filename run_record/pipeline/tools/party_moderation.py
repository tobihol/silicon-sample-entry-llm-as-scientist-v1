#!/usr/bin/env python
"""TASK_13 item 2: is the card's ZERO condition x moderator interaction consistent with the
polarization evidence in altenmueller2024?

    /opt/kernel/venv/bin/python tools/party_moderation.py

The comparison rule was fixed in runs/_trusttask2/PREREG.md section 4 BEFORE any of this was
computed. Three quantities, all in pp of each outcome's scale range, all local, no model call:

 1. IDENTITY-LABEL interaction - altenmueller2024 Study 1 (an institute described as politically
    liberal vs conservative) and Study 4b (sociological vs economic institute, i.e. discipline as
    a stereotyped proxy for the same thing), split at the sample median of the study's own averaged
    conservatism variable;
 2. MESSAGE-STRATEGY interaction - koetke2024 Study 5, the task carved this session, party from
    the survey's own party-ID item. This is the like-for-like comparator: the target's 16 arms are
    message strategies, not manipulations of who the scientist is;
 3. whether either replicates, by finding 53's arbiter (split the respondents in half at random,
    recompute, correlate the two halves' interaction vectors) rather than by a p-value.

Verdict rule, pre-registered:
  CONSISTENT   identity-label interaction large and replicable AND message-strategy interaction
               not distinguishable from zero at this precision
  INCONSISTENT message-strategy interaction itself large and replicating
  UNRESOLVED   otherwise; the width of the interval is then the result
"""
import sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
ALT = Path("/workspace/datasets/altenmueller2024/downloads/Data & Code/Data")
KOETKE = RUN / "inputs" / "derived" / "koetke2024_study5.csv"
METI14 = ["competent", "intelligent", "educated", "professional", "experienced", "qualified",
          "honest", "sincere", "just", "fair", "moral", "ethical", "responsible", "considerate"]
SEED = 20260819


def alt_study(name, skip, treat, control, drop=None):
    df = pd.read_csv(ALT / f"rawdata_{name}.csv", low_memory=False).iloc[skip:].copy()
    for c in METI14 + ["attention_check", "pol_orientation", "pol_preference"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[df.attention_check == 1]
    if drop:
        df = df[df.condition != drop]
    df["conservative"] = df[["pol_orientation", "pol_preference"]].mean(axis=1)
    df["trust14"] = df[METI14].mean(axis=1)
    df["polgroup"] = np.where(df.conservative > df.conservative.median(),
                              "conservative-half", "liberal-half")
    return df[df.condition.isin([treat, control])].reset_index(drop=True)


def interaction(df, cond, treat, control, ycol, rng, group="polgroup",
                hi="conservative-half", lo="liberal-half"):
    out = {}
    for g in (hi, lo):
        s = df[df[group] == g]
        t = s[s[cond] == treat][ycol].dropna()
        c = s[s[cond] == control][ycol].dropna()
        if len(t) < 3 or len(c) < 3:
            return None
        out[g] = ((t.mean() - c.mean()) / rng * 100,
                  np.sqrt(t.var(ddof=1) / len(t) + c.var(ddof=1) / len(c)) / rng * 100)
    return {"ate_" + hi: out[hi][0], "ate_" + lo: out[lo][0],
            "interaction": out[hi][0] - out[lo][0],
            "se": float(np.sqrt(out[hi][1] ** 2 + out[lo][1] ** 2))}


def snr(r):
    """Complementary halves partition the sample, so for a mean-based estimator the two halves'
    errors are EXACTLY opposite (mean_A + mean_B = 2 mean_full). Writing the across-cell signal
    variance S and error variance N, vec_A = t + e and vec_B = t - e, so

        r = (S - N) / (S + N)   ->   S/N = (1 + r) / (1 - r)

    (verified by simulation). The split-half r is therefore a monotone read-out of the
    signal-to-noise ratio, r = 0 is exactly S = N, and a NEGATIVE r is not anti-replication - it
    is noise larger than signal. finding 53's +0.024 on the target-shaped moderator vectors reads
    S/N = 1.05 under the same identity."""
    return (1 + r) / (1 - r)


def split_half(df, vec, n=200, seed=SEED):
    """finding 53's arbiter: correlate the two halves' vectors of cell estimates."""
    rng = np.random.default_rng(seed)
    rs = []
    for _ in range(n):
        ix = rng.permutation(len(df))
        a, b = df.iloc[ix[: len(df) // 2]], df.iloc[ix[len(df) // 2:]]
        va, vb = vec(a), vec(b)
        ok = np.isfinite(va) & np.isfinite(vb)
        if ok.sum() > 2 and np.std(va[ok]) > 0 and np.std(vb[ok]) > 0:
            rs.append(np.corrcoef(va[ok], vb[ok])[0, 1])
    return float(np.mean(rs)), float(np.std(rs)), len(rs)


def main():
    print("=" * 78)
    print("1. IDENTITY-LABEL interaction (altenmueller2024)")
    s1 = alt_study("study1", 8, "liberal research institute", "conservative research institute")
    r1 = interaction(s1, "condition", "liberal research institute",
                     "conservative research institute", "trust14", 6)
    print("  Study 1 (liberal vs conservative institute), n = %d" % len(s1))
    print("     liberal-half ATE %+7.2f | conservative-half ATE %+7.2f | interaction %+7.2f pp "
          "(SE %.2f, z %.1f)" % (r1["ate_liberal-half"], r1["ate_conservative-half"],
                                 r1["interaction"], r1["se"], r1["interaction"] / r1["se"]))
    s4 = alt_study("study4b", 7, "sociological research institute", "economic research institute",
                   drop="economic and sociological research institute")
    r4 = interaction(s4, "condition", "sociological research institute",
                     "economic research institute", "trust14", 6)
    print("  Study 4b (sociological vs economic institute), n = %d" % len(s4))
    print("     liberal-half ATE %+7.2f | conservative-half ATE %+7.2f | interaction %+7.2f pp "
          "(SE %.2f, z %.1f)" % (r4["ate_liberal-half"], r4["ate_conservative-half"],
                                 r4["interaction"], r4["se"], r4["interaction"] / r4["se"]))

    print("\n2. MESSAGE-STRATEGY interaction (koetke2024 Study 5, the task carved this session)")
    k = pd.read_csv(KOETKE)
    k["polgroup"] = k.party.map({1: "liberal-half", 2: "conservative-half"})
    k = k[k.polgroup.notna()]
    outs = {"trust_meti": 6, "belief_research": 6, "perceived_humility": 4}
    rows = []
    for y, rng in outs.items():
        for arm in ["Limits of Methods", "Limits of Results", "Personal Humility"]:
            r = interaction(k, "IHCondition", arm, "Control", y, rng)
            rows.append({"outcome": y, "arm": arm, **r})
    ki = pd.DataFrame(rows)
    print(ki.round(2).to_string(index=False))
    tm = ki[ki.outcome == "trust_meti"]
    print("  trust: |interaction| max %.2f pp, mean SE %.2f -> this sample cannot rule out an "
          "interaction larger than about %.1f pp"
          % (tm.interaction.abs().max(), tm.se.mean(), 1.96 * tm.se.mean()))

    print("\n3. DOES EITHER REPLICATE (finding 53's arbiter, %d random splits)" % 200)
    v1 = lambda d: np.array([  # noqa: E731  - the 14 METI items as the cell vector
        (interaction(d, "condition", "liberal research institute",
                     "conservative research institute", it, 6) or {"interaction": np.nan}
         )["interaction"] for it in METI14])
    m1 = lambda d: np.array([  # noqa: E731  - main effects on the same splits, as the reference
        ((d[d.condition == "liberal research institute"][it].mean()
          - d[d.condition == "conservative research institute"][it].mean()) / 6 * 100)
        for it in METI14])
    r, s, n = split_half(s1, v1)
    print("  altenmueller Study 1  interaction vector (14 METI items): r = %+.3f (SD %.3f, %d "
          "splits)  -> signal/noise %.2f" % (r, s, n, snr(r)))
    r, s, n = split_half(s1, m1)
    print("                        MAIN EFFECT vector, same splits:      r = %+.3f (SD %.3f)" % (r, s))

    def vk(d):
        out = []
        for y, rng in outs.items():
            for arm in ["Limits of Methods", "Limits of Results", "Personal Humility"]:
                r = interaction(d, "IHCondition", arm, "Control", y, rng)
                out.append(np.nan if r is None else r["interaction"])
        return np.array(out)

    def mk(d):
        out = []
        for y, rng in outs.items():
            for arm in ["Limits of Methods", "Limits of Results", "Personal Humility"]:
                t = d[d.IHCondition == arm][y].dropna()
                c = d[d.IHCondition == "Control"][y].dropna()
                out.append((t.mean() - c.mean()) / rng * 100)
        return np.array(out)

    r, s, n = split_half(k, vk)
    print("  koetke Study 5        interaction vector (9 cells):        r = %+.3f (SD %.3f, %d "
          "splits)  -> signal/noise %.2f" % (r, s, n, snr(r)))
    r, s, n = split_half(k, mk)
    print("                        MAIN EFFECT vector, same splits:      r = %+.3f (SD %.3f)" % (r, s))

    print("\n4. WHAT THE TARGET ITSELF COULD RESOLVE")
    print("  ~18,000 respondents over 17 conditions is ~1,000 per arm and ~2,000 control; a party")
    print("  half is ~500/1,000. On a 0-100 slider with SD 25 that is SE(ATE|party) ~ 1.37 pp and")
    print("  SE(interaction) ~ 1.94 pp, so the target study itself cannot resolve a party x message")
    print("  interaction below about 4 pp - the same order as the bound koetke leaves open.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
