#!/usr/bin/env python
"""Does the DEPOSIT reproduce the card, checked by code that did not build it?

Standing finding 46 asked whether a scoreboard row follows from the run's own pairs.csv. This is the
same question pointed at the product: gate G6 ("analyses recomputed from Tier 1 reproduce the card")
is computed inside `tools/target.py`, by the same module that wrote both sides of the comparison. A
check that shares code with the thing it checks can only find disagreements the shared code is
capable of having.

    /opt/kernel/venv/bin/python tools/verify_deposit.py runs/20260815-target-01

Recomputes every ATE straight from the deposited Tier-1 rows with plain pandas - group mean minus
control mean, nothing imported from ssb - and compares to card/ate.csv. Then checks the frozen file's
own rules directly:

  Coverage   all 17 conditions x 13 outcomes, every cell exactly once, no NA anywhere
  Tier-1floor >= 500 rows per intervention, >= 1,000 in control
  Units      donation_ams in dollars and newsletter_signup as a proportion, NOT in pp (finding 8)
  Metadata   `approach_family` and `models` are the harness's, not the template's defaults (finding 26)
  Entry      `primary` or `secondary-k`, or the filename check fails (finding 27)

Exit code is non-zero on any failure, so it can gate a deposit.
"""
import argparse, datetime as dt, glob, json, sys
from pathlib import Path

import numpy as np, pandas as pd

RUN = Path(__file__).resolve().parents[1]
SLIDERS_0_100 = 1.0
SCALE_TO_PP = {"donation_ams": 10.0, "newsletter_signup": 100.0}   # native -> pp
TOL_PP = 0.05
TEMPLATE_DEFAULTS = {"per-respondent simulation, single model", "gpt-4o-mini-2024-07-18"}
TEAM_ID = "team_31"                                  # TASK_08, the organisers' assigned id
WINDOW_OPEN, WINDOW_CLOSE = dt.date(2026, 8, 28), dt.date(2026, 8, 31)   # publish only in here


def check(label, ok, detail=""):
    print(f"  [{'PASS' if ok else 'FAIL'}] {label:52s} {detail}")
    return bool(ok)


def main(run, strict=False):
    d = RUN / run
    if not d.exists():
        raise SystemExit(f"no such run: {d}")
    ok = True
    card = pd.read_csv(d / "card/ate.csv")
    t1 = pd.read_csv(d / "stages/tier1.csv")
    outs = sorted(card.outcome.unique())
    print(f"\n{run}: {len(t1):,} deposited rows, {len(card)} card cells, {len(outs)} outcomes")

    print("\n=== G6 recomputed from the deposited rows, by code that did not build them ===")
    ctrl = t1[t1.condition == "control"]
    if ctrl.empty:
        raise SystemExit("no control condition in tier1.csv")
    rows = [{"condition": c, "outcome": o,
             "ate_rows": t1[t1.condition == c][o].mean() - ctrl[o].mean()}
            for c in sorted(set(t1.condition) - {"control"}) for o in outs]
    rc = card.merge(pd.DataFrame(rows), on=["condition", "outcome"], how="outer", indicator=True)
    ok &= check("every card cell has deposited rows behind it",
                (rc._merge == "both").all(), f"{(rc._merge == 'both').sum()}/{len(rc)} matched")
    rc["d_pp"] = (rc.ate - rc.ate_rows).abs() * rc.outcome.map(SCALE_TO_PP).fillna(SLIDERS_0_100)
    worst = rc.d_pp.max()
    ok &= check("card ATEs reproduce from rows", worst < TOL_PP,
                f"max {worst:.4f} pp, RMSE {np.sqrt((rc.d_pp ** 2).mean()):.4f} pp (tol {TOL_PP})")
    w = rc.nlargest(1, "d_pp").iloc[0]
    print(f"         worst cell: {w.condition} x {w.outcome}  card {w.ate:.6g} rows {w.ate_rows:.6g}")

    print("\n=== the frozen file's coverage rule and Tier-1 floor ===")
    n_cond = t1.condition.nunique()
    ok &= check("all 17 conditions present in Tier 1", n_cond == 17, f"{n_cond}")
    per = t1[t1.condition != "control"].condition.value_counts()
    ok &= check("Tier-1 floor: >=500 per intervention", per.min() >= 500, f"min {per.min()}")
    ok &= check("Tier-1 floor: >=1,000 in control", len(ctrl) >= 1000, f"{len(ctrl)}")
    ok &= check("no NA anywhere in Tier 1", t1.isna().sum().sum() == 0,
                f"{t1.isna().sum().sum()} NA")
    ok &= check("card: every cell exactly once",
                not card.duplicated(["condition", "outcome"]).any() and not card.ate.isna().any(),
                f"{len(card)} cells, {card.ate.isna().sum()} NA")

    for tier in (1, 2, 3):
        sub = d / f"submission_T{tier}"
        if not sub.exists():
            ok &= check(f"tier {tier} deposit exists", False, "missing")
            continue
        print(f"\n=== submission_T{tier} ===")
        for p in sorted(glob.glob(str(sub / "predictions/*.csv"))):
            df = pd.read_csv(p)
            name = Path(p).name
            ok &= check(f"{name[:44]}: no NA", df.isna().sum().sum() == 0,
                        f"{len(df)} rows x {len(df.columns)} cols")
            stem = name.rsplit("_v", 1)[0]
            ok &= check(f"{name[:44]}: entry is primary|secondary-k",
                        "_primary" in stem or "_secondary-" in stem, "")
            # The coverage rule is about ANALYSIS cells. A Tier-1 file is respondent-level, so
            # `condition` repeats by design (that is the point of it) and has no `outcome` column -
            # its outcomes are columns, not rows. Only cell-level files carry the uniqueness rule.
            keys = [c for c in ("condition", "moderator", "moderator_level", "outcome")
                    if c in df.columns]
            if "outcome" in keys:
                ok &= check(f"{name[:44]}: every cell exactly once",
                            not df.duplicated(keys).any(),
                            f"key={'+'.join(keys)}, dupes {df.duplicated(keys).sum()}")
            else:
                idc = [c for c in df.columns if c.endswith("_id")]
                ok &= check(f"{name[:44]}: respondent-level, ids unique",
                            bool(idc) and not df[idc[0]].duplicated().any(),
                            f"id={idc[0] if idc else 'NONE'}, {len(df)} rows")
        md_path = sub / "metadata.json"
        if md_path.exists():
            md = json.loads(md_path.read_text())
            af, mo = str(md.get("approach_family", "")), str(md.get("models", ""))
            ok &= check("approach_family is not the template default",
                        af and not any(t in af for t in TEMPLATE_DEFAULTS), af[:44] + "...")
            ok &= check("models is not the template default",
                        mo and not any(t in mo for t in TEMPLATE_DEFAULTS), mo[:44])
            ok &= check("entry field is primary|secondary-k",
                        md.get("entry") == "primary" or str(md.get("entry", "")).startswith("secondary-"),
                        str(md.get("entry")))
            # TASK_08: the organisers' team id is `team_31`. `check.R` only rejects the template's
            # own example id, so the placeholder this harness invented (`sodalab`) passed green for
            # eight runs. An identity is a fact, not a preference, so it is checked here and it
            # gates a real deposit.
            ok &= check(f"team_id is {TEAM_ID}", md.get("team_id") == TEAM_ID,
                        f"{md.get('team_id')!r}")
            fnames = [Path(p).name for p in glob.glob(str(sub / "predictions/*.csv"))]
            ok &= check(f"prediction filenames stamped {TEAM_ID}_",
                        bool(fnames) and all(f.startswith(TEAM_ID + "_") for f in fnames),
                        ", ".join(fnames)[:60])

    # `check.R` bounds donation_ams to [0,10] and newsletter_signup to binary, and leaves the
    # eleven 0-100 sliders UNBOUNDED. A synthesis bug that pushed one past its ceiling would ship.
    print("\n=== response ranges the validator does not bound ===")
    bounded = set(SCALE_TO_PP)
    sl = [c for c in pd.read_csv(d / "card/ate.csv").outcome.unique()
          if c in t1.columns and c not in bounded]
    bad = {c: int(((t1[c] < 0) | (t1[c] > 100)).sum()) for c in sl}
    ok &= check(f"all {len(sl)} 0-100 sliders within [0,100]", not any(bad.values()),
                f"{sum(bad.values())} out-of-range values"
                + (f"; worst {max(bad, key=bad.get)}" if any(bad.values()) else ""))

    print("\n=== units: pp -> native (finding 8) ===")
    for o, div in SCALE_TO_PP.items():
        if o not in card.outcome.values:
            continue
        v = card[card.outcome == o].ate.abs()
        ok &= check(f"{o} stored in native units, not pp", v.max() < 1.0 / div * 10,
                    f"max |ATE| {v.max():.4g} native = {v.max() * div:.3g} pp")

    # ---- the frozen file's COMPOSITE rule -------------------------------------------------
    # "Composites are scored AS SUBMITTED, never recomputed from items. A composite inconsistent
    # with its items is scored on the deviant values." So where both a composite and its items are
    # deposited, a drift between them is scored against us and is invisible to `check.R`.
    print("\n=== the frozen file's composite rule ===")
    groups = {}
    for c in t1.columns:
        parts = c.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            groups.setdefault(parts[0].rsplit("_", 1)[0], []).append(c)
    checked = 0
    for stem, its in sorted(groups.items()):
        comp = next((c for c in t1.columns if c.startswith(stem) and c not in its
                     and not c.rsplit("_", 1)[-1].isdigit()), None)
        if comp is None or len(its) < 2:
            continue
        drift = (t1[comp] - t1[its].mean(axis=1)).abs()
        ok &= check(f"composite '{comp}' consistent with its {len(its)} items",
                    drift.max() < 1e-6, f"max drift {drift.max():.8f}")
        checked += 1
    if not checked:
        print("  (no composite has its items deposited, so the rule cannot bite)")

    # ---- cross-tier agreement -------------------------------------------------------------
    # Each tier is scored separately, so three tiers can silently submit three different
    # predictions of the same 208 quantities. Nothing checked that they agree.
    print("\n=== do the three tiers submit the SAME prediction? ===")
    try:
        t2p = next(iter(glob.glob(str(d / "submission_T2/predictions/*cells_main*.csv"))), None)
        t3p = next(iter(glob.glob(str(d / "submission_T3/predictions/*.csv"))), None)
        if t2p and t3p:
            t2m = pd.read_csv(t2p)
            t3f = pd.read_csv(t3p)
            cm = t2m[t2m.condition == "control"].set_index("outcome")["mean"]
            dv = t2m[t2m.condition != "control"].copy()
            dv["ate_T2"] = dv["mean"] - dv.outcome.map(cm)
            j = t3f.merge(dv[["condition", "outcome", "ate_T2"]], on=["condition", "outcome"]) \
                   .merge(card.rename(columns={"ate": "ate_card"}), on=["condition", "outcome"])
            s = j.outcome.map(SCALE_TO_PP).fillna(SLIDERS_0_100)
            for a, b, lab in (("ate", "ate_T2", "Tier 3 == Tier 2 (cell differences)"),
                              ("ate", "ate_card", "Tier 3 == the card")):
                dd = ((j[a] - j[b]).abs() * s).max()
                ok &= check(lab, dd < 1e-9, f"n={len(j)}, max {dd:.10f} pp")
    except Exception as e:                                          # pragma: no cover
        ok &= check("cross-tier agreement computable", False, str(e)[:60])

    # ---- template placeholders and unaffirmed attestations -------------------------------
    # `check.R` validates PRESENCE for some fields and EXAMPLE-EQUALITY for others, inconsistently:
    # `team_id` is checked against the example and `.zenodo.json` creators against 'Lastname,
    # Firstname', but `team_name` and `contact` are only checked for presence, so
    # "Example Team (replace me)" and "name@institution.edu" both pass green. And
    # `blinding_attestation` is checked to EQUAL true while shipping pre-set to true in the
    # template - the validator cannot tell an affirmation from a default. Finding 26's pattern.
    tmpl = {}
    for c in (RUN.parent / "benchmark" / "metadata.json",):
        if c.exists():
            tmpl = json.loads(c.read_text())
    pending = []
    if tmpl:
        print("\n=== operator-pending: fields still identical to the template ===")
        SHARED = {"license", "tier", "entry", "coverage", "escrow_doi", "zenodo_doi",
                  "code_doi", "disclosure_class",
                  "blinding_attestation"}   # handled explicitly below, not as a generic placeholder
        md = json.loads((d / "submission_T1/metadata.json").read_text())
        for k, tv in tmpl.items():
            if k in SHARED:
                continue
            if k in md and md[k] == tv and tv not in (None, "", [], {}):
                pending.append(k)
                print(f"  [PENDING] {k:22s} still the template value: {str(tv)[:60]}")
        if not any(md.get(k) for k in ("abstract",)):
            pending.append("abstract")
            print(f"  [PENDING] {'abstract':22s} empty; `check.R` does not test it at all")
        if md.get("blinding_attestation") is True and tmpl.get("blinding_attestation") is True:
            pending.append("blinding_attestation")
            print(f"  [PENDING] {'blinding_attestation':22s} TRUE, but that is the TEMPLATE DEFAULT - "
                  "an attestation")
            print(f"  {'':33s} about HUMAN conduct that no harness can make. "
                  "`check.R` reads")
            print(f"  {'':33s} `== true` and cannot distinguish it from an affirmation.")
        if not pending:
            print("  none - every operator field has been filled")

    # ---- the deposit window (TASK_08) -----------------------------------------------------
    # The organisers ask that nothing be published before Aug 28; the prediction lock is Aug 31.
    # A build outside that window is legitimate - the harness builds and verifies whenever it
    # likes - but it must be unmistakably marked, because the artefact on disk is exactly what
    # would be uploaded. So this is a publication gate, not a harness defect.
    print("\n=== deposit window: publish only 2026-08-28 .. 2026-08-31 ===")
    md1 = json.loads((d / "submission_T1/metadata.json").read_text())
    today = dt.date.today()
    stamped = md1.get("publication_status", "")
    in_window = WINDOW_OPEN <= today <= WINDOW_CLOSE
    print(f"  built_at {md1.get('built_at', 'UNSTAMPED')} | today {today} | "
          f"window {WINDOW_OPEN} .. {WINDOW_CLOSE}")
    ok &= check("metadata records the publication window",
                bool(md1.get("not_for_publication_before")) and bool(stamped),
                stamped[:60] or "no publication_status field")
    if not in_window:
        pending.append("publication_window")
        print(f"  [NOT-FOR-PUBLICATION] today is {'before' if today < WINDOW_OPEN else 'after'} "
              f"the window - this deposit may be built and checked, not uploaded")

    # ---- license sweep (legal review 2026-08-24) ------------------------------------------
    # docs/legal-review-2026-08-24.md section 4: no Pew/CCAM (or other no-redistribution)
    # microdata may appear in any deposited file, including the raw prompt logs. Two
    # deterministic tests over everything that would be uploaded: (1) no deposited file NAME
    # matches a restricted source artefact (Pew .sav waves, the CCAM .sav, the five derived
    # extracts scrubbed from git on 2026-08-24); (2) no deposited text file CONTAINS a
    # respondent-identifier marker that exists only in real microdata exports and never in
    # our synthetic rows or aggregates (Pew's QKEY; Prolific/Qualtrics recipient fields).
    print("\n=== license sweep: no restricted microdata in the deposit ===")
    RESTRICTED_NAMES = ("ATP_W", "CCAM SPSS", "bbprime2025_analysis", "gligoric2025_trust",
                        "orchinik2024_bovitz", "koetke2024_study5", "dablander2025.csv")
    MARKERS = (b"QKEY", b"PROLIFIC_PID", b"RecipientEmail", b"RecipientFirstName",
               b"RecipientLastName", b"ExternalReference")
    dep_files = sorted({p for pat in ("submission_T*/**/*", "raw_model_logs/**/*")
                        for p in d.glob(pat) if p.is_file()})
    bad_names = [p for p in dep_files if any(m in p.name for m in RESTRICTED_NAMES)]
    ok &= check("no restricted source artefact by name",
                not bad_names,
                f"{len(dep_files)} files swept" if not bad_names
                else "; ".join(p.name for p in bad_names[:3]))
    TEXT_SUFFIX = {".csv", ".json", ".md", ".txt", ".R", ".tsv", ".Rmd", ".sha256"}
    scanned, hits = 0, []
    for p in dep_files:
        if p.suffix not in TEXT_SUFFIX:
            continue
        scanned += 1
        blob = p.read_bytes()
        hits += [(p, m.decode()) for m in MARKERS if m in blob]
    ok &= check("no microdata identifier marker in any text file",
                not hits,
                f"{scanned} text files scanned" if not hits
                else "; ".join(f"{p.name}:{m}" for p, m in hits[:3]))

    print("\nVERDICT:", "HARNESS-VERIFIED" if ok else "NOT VERIFIED",
          f"| DEPOSIT READY: {'YES' if ok and not pending else 'NO'}",
          f"({len(pending)} operator item(s) outstanding)" if pending else "")
    if pending and not strict:
        print("  The outstanding items are the operator's to fill, not harness defects, so the exit")
        print("  code stays 0. Use --strict to gate a real deposit on them.")
    return 0 if (ok and (not strict or not pending)) else 1


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("run", nargs="?", default="runs/20260815-target-01")
    a.add_argument("--strict", action="store_true",
                   help="fail if any operator field is still a template placeholder")
    n = a.parse_args()
    sys.exit(main(n.run, n.strict))
