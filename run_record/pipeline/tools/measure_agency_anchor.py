#!/usr/bin/env python
"""Place EPA / NASA / NOAA between "science" and "the government" from published Pew margins.

OPEN.md item 14. `inst_trust_mean` is the mean of five institutions - EPA, NASA, NOAA,
universities/colleges and the federal government - and three of the five (the agencies) had no
measurement anywhere on the mounted data, so `tools/build_baselines.py` took them at the MIDPOINT
of the [scientific community, federal government] bracket.

This script replaces that midpoint with a number composed from published aggregate margins:
Pew ATP W149 (Jul 1-7 2024, N=9,424) AGNCYFAV, with its W123 (Mar 13-19 2023) replicate, both
read out of the vendored topline at ../datasets/pew_atp/downloads/toplines/w149_topline.txt.

Nothing here is microdata. The topline carries NO agency x party crosstab (checked: the PDF and
the text contain only the PARTY marginal 27/26/30/14), so this settles the LEVEL half of item 14
and not the party half.

    python tools/measure_agency_anchor.py     # -> inputs/measured/agency_trust_anchor.json
"""
import json, re, sys
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]
TOPLINE = Path("/workspace/datasets/pew_atp/downloads/toplines/w149_topline.txt")
PEW_TRUST = RUN / "inputs" / "measured" / "pew_atp_trust.json"

# The two named contrasts the card already carries, measured within-person in GSS 2016-2024
# (build_baselines.py recomputes them; they are copied here only to report the propagation).
GAP = 0.8                       # coarse-scale gap -> slider, measured (OPEN item 2)

# W149 AGNCYFAV item -> (label, class). "gov" = the operator's named comparators, asked of the
# SAME half-sample (Form 2) as EPA and NASA, so no form crossing is involved.
CLASS = {"JSTCE": "gov", "IRS": "gov", "HMLND": "gov",
         "EPA": "agency", "NASA": "agency",
         "CDC": "agency_form1", "NPS": "wide", "VA": "wide", "USPS": "wide", "HHS": "wide",
         "FBI": "wide", "CIA": "wide", "SSA": "wide", "FED": "wide", "ED": "wide", "TRANS": "wide"}
WAVES = {"w149_jul2024": "Jul", "w123_mar2023": "Mar"}


def parse_topline(path=TOPLINE):
    """{item: {wave: {very_fav, smwt_fav, smwt_unfav, very_unfav, not_sure, no_answer}}}."""
    txt = path.read_text(encoding="utf-8")
    out, item = {}, None
    for line in txt.splitlines():
        m = re.match(r"^\s*([A-Z]{2,5})\s+(?:The|Th e)\b", line)
        if m and m.group(1) in CLASS:
            item = m.group(1); out.setdefault(item, {})
        if item is None:
            continue
        m = re.match(r"^\s*(Jul|Mar)\s+\d+\s*-\s*\d+,?\s*\d{4}\s+(.*)$", line.strip())
        if not m:
            continue
        nums = [999.0 if t == "*" else float(t) for t in re.findall(r"\*|\d+", m.group(2))]
        # NET fav, very, somewhat | NET unfav, very, somewhat | not sure | no answer
        if len(nums) < 8:
            continue
        wave = [k for k, v in WAVES.items() if v == m.group(1)][0]
        out[item][wave] = dict(net_fav=nums[0], very_fav=nums[1], smwt_fav=nums[2],
                               net_unfav=nums[3], very_unfav=nums[4], smwt_unfav=nums[5],
                               not_sure=nums[6], no_answer=0.0 if nums[7] == 999.0 else nums[7])
    return out


def rescale(d, not_sure):
    """0-100 warmth on the same map ssb/build_baselines use for Pew's 4-point CONF items:
    (4-x)/3*100, i.e. very fav 100 / somewhat fav 66.67 / somewhat unfav 33.33 / very unfav 0.

    not_sure='exclude' renormalises over the four substantive points (the treatment the CONF
    items get, where no `not sure` option exists); not_sure='midpoint' places `not sure` at 50,
    which is what a respondent with no opinion most plausibly does on a 0-100 slider.
    """
    pts = [(d["very_fav"], 100.0), (d["smwt_fav"], 200 / 3), (d["smwt_unfav"], 100 / 3), (d["very_unfav"], 0.0)]
    if not_sure == "midpoint":
        pts.append((d["not_sure"], 50.0))
    elif not_sure != "exclude":
        raise ValueError(not_sure)
    base = sum(p for p, _ in pts)
    return sum(p * v for p, v in pts) / base


# ---------------------------------------------------------------------------------------------
# The microdata path. Nothing below runs until the operator's Pew account lands ATP_W149.sav
# (and/or ATP_W123.sav) in ../datasets/pew_atp/downloads/w149/. It is written now, against the
# published questionnaire, so that tomorrow is a drop-in re-run rather than a fresh analysis:
#     python tools/measure_agency_anchor.py            # topline only, today
#     python tools/measure_agency_anchor.py --microdata  # topline + microdata, tomorrow
# Column names are DISCOVERED, not assumed: Pew's battery suffixes vary between waves, so the
# script matches on the variable name and on the variable LABEL and reports what it found. If it
# cannot find something it says exactly which candidates it saw instead of guessing.
# ---------------------------------------------------------------------------------------------

MICRO = {"w149_jul2024": Path("/workspace/datasets/pew_atp/downloads/w149/ATP_W149.sav"),
         "w123_mar2023": Path("/workspace/datasets/pew_atp/downloads/w123/ATP_W123.sav")}
PARTY_LABELS = {1: "Republican", 2: "Democrat", 3: "Independent", 4: "Other"}


BATTERY = "AGNCYFAV"          # the battery's own name in the questionnaire; overridable for tests


def _discover(meta, want_codes):
    """{item_code: column}. Matches the battery item code in the column name first, then in the
    variable label (Pew labels read 'AGNCYFAV_b. The Central Intelligence Agency, the CIA')."""
    cols = {c: (meta.column_names_to_labels.get(c) or "") for c in meta.column_names}
    fav = {c: l for c, l in cols.items() if BATTERY in c.upper() or BATTERY in l.upper()}
    found, unmatched = {}, dict(fav)
    for code in want_codes:
        # NOT \b: `_` is a word character, so \bEPA\b never matches AGNCYFAV_EPA_W149.
        # Measured on the mounted W114 file, where \bCONF_G\b matched none of CONF_G_W114.
        pat = re.compile(r"(?<![A-Za-z0-9])" + re.escape(code) + r"(?![A-Za-z0-9])", re.I)
        hit = [c for c in fav if pat.search(c) or pat.search(fav[c])]
        if len(hit) == 1:
            found[code] = hit[0]
            unmatched.pop(hit[0], None)
    return found, unmatched, fav


def microdata(wave: str, not_sure: str = "midpoint") -> dict:
    """theta WITH a standard error, and the agency x party table the topline does not contain."""
    import numpy as np
    import pandas as pd
    import pyreadstat
    path = MICRO[wave]
    if not path.exists():
        return {"status": "ABSENT", "expected_at": str(path),
                "blocks": ["theta with an SE", "the agency x PARTY table (OPEN item 14's party half)",
                           "a within-respondent gov-comparator contrast",
                           "whether the wave carries any science referent (the bridge test)"]}
    df, meta = pyreadstat.read_sav(str(path))
    want = [c for c in CLASS if CLASS[c] in ("gov", "agency", "agency_form1")]
    if not want:
        return {"status": "NO_ITEMS_REQUESTED"}
    found, unmatched, fav = _discover(meta, want)
    missing = [c for c in want if c not in found]
    if missing:
        return {"status": "COLUMNS_NOT_FOUND", "missing": missing,
                "candidates_seen": {k: v for k, v in list(unmatched.items())[:40]},
                "hint": "add the right column names to CLASS or extend _discover; do NOT guess"}
    # The wave's OWN weight, not the first column starting with WEIGHT: Pew ships longitudinal
    # weights alongside it (W114 carries WEIGHT_W84_W114) and picking the wrong one moved a
    # known mean by 0.75 pp and its Kish n by 35% in the smoke test that found this.
    tag = re.search(r"(_W\d+)$", next(iter(found.values())))
    tag = tag.group(1) if tag else ""
    wts = [c for c in meta.column_names if c.upper().startswith("WEIGHT")]
    wcol = next((c for c in wts if c.upper() == ("WEIGHT" + tag).upper()),
                min(wts, key=len) if wts else None)
    pcol = next((c for c in meta.column_names if "PARTY_FINAL" in c.upper()), None)
    if wcol is None or pcol is None:
        return {"status": "COLUMNS_NOT_FOUND", "missing": ["weight" if not wcol else "party"],
                "candidates_seen": [c for c in meta.column_names if "WEIGHT" in c.upper()
                                    or "PARTY" in c.upper()]}
    w = pd.to_numeric(df[wcol], errors="coerce").fillna(0.0).to_numpy(float)
    party = pd.to_numeric(df[pcol], errors="coerce").map(PARTY_LABELS)

    def warm(col):
        x = pd.to_numeric(df[col], errors="coerce")
        v = x.map({1: 100.0, 2: 200 / 3, 3: 100 / 3, 4: 0.0})
        if not_sure == "midpoint":
            v = v.where(x != 5, 50.0)
        return v.where(x.isin([1, 2, 3, 4, 5] if not_sure == "midpoint" else [1, 2, 3, 4]))

    def wmean(v, ww):
        m = np.isfinite(v) & (ww > 0)
        if m.sum() == 0:
            return float("nan"), float("nan"), 0.0
        vv, wv = v[m], ww[m]
        mu = float((vv * wv).sum() / wv.sum())
        se = float(np.sqrt((wv ** 2 * (vv - mu) ** 2).sum()) / wv.sum())
        return mu, se, float(wv.sum() ** 2 / (wv ** 2).sum())

    cells, per_party = {}, {}
    for code, col in found.items():
        v = warm(col).to_numpy(float)
        mu, se, kish = wmean(v, w)
        cells[code] = {"column": col, "mean_0_100": round(mu, 3), "se": round(se, 3),
                       "kish_n": round(kish, 1)}
        per_party[code] = {}
        for lab in PARTY_LABELS.values():
            m = (party == lab).to_numpy()
            mu2, se2, k2 = wmean(np.where(m, v, np.nan), w)
            per_party[code][lab] = {"mean_0_100": round(mu2, 3), "se": round(se2, 3),
                                    "kish_n": round(k2, 1)}
    sci_label_hits = {c: l for c, l in
                      ((c, meta.column_names_to_labels.get(c) or "") for c in meta.column_names)
                      if re.search(r"scientist|scientific", l, re.I)}
    return {"status": "OK", "wave": wave, "not_sure": not_sure, "weight": wcol, "party": pcol,
            "n_rows": len(df), "items": cells, "by_party": per_party,
            "science_referent_in_wave": {k: v for k, v in list(sci_label_hits.items())[:20]},
            "bridge_becomes_fittable": bool(sci_label_hits),
            "next": "recompute theta from `items` exactly as the topline path does, now with an SE, "
                    "and hand `by_party` to tools/build_baselines.py for inst_trust_mean's party "
                    "offsets (OPEN item 14, party half)"}


def selftest_microdata() -> dict:
    """The microdata path will not be exercised until the operator's Pew account lands, so it is
    tested TODAY against a file that already exists: W114's CONF battery, whose weighted mean, SE
    and Kish n were measured independently and stored in inputs/measured/pew_atp_trust.json.

    This found two real bugs before they could cost a session:
      - `\b` boundaries never match an item code bounded by underscores (`_` is a word character),
        so column discovery silently found nothing;
      - the first column starting with WEIGHT is a LONGITUDINAL weight in W114 (WEIGHT_W84_W114),
        which moved the mean 0.75 pp and the Kish n 35%.
    """
    global BATTERY, CLASS, MICRO
    w114 = Path("/workspace/datasets/pew_atp/downloads/w114/ATP_W114.sav")
    if not w114.exists():
        return {"status": "SKIPPED", "why": "W114 not mounted"}
    keep = (BATTERY, dict(CLASS), dict(MICRO))
    try:
        BATTERY, CLASS = "CONF", {"CONF_G": "agency", "CONF_A": "gov"}
        MICRO = {"selftest": w114}
        got = microdata("selftest")
        ref = json.load(open(PEW_TRUST))["waves"]["w114"]["items"]["CONF_G_W114"]["cuts"]["overall"]["ALL"]
        g = got["items"]["CONF_G"]
        d_mean = abs(g["mean_0_100"] - ref["mean_0_100"])
        d_se = abs(g["se"] - ref["se_0_100"])
        d_kish = abs(g["kish_n"] - ref["kish_effective_n"])
        gap = got["by_party"]["CONF_G"]["Democrat"]["mean_0_100"] - \
            got["by_party"]["CONF_G"]["Republican"]["mean_0_100"]
        return {"status": "PASS" if (d_mean < 0.01 and d_se < 0.01 and d_kish < 1) else "FAIL",
                "weight_chosen": got["weight"], "mean_delta": round(d_mean, 4),
                "se_delta": round(d_se, 4), "kish_delta": round(d_kish, 2),
                "party_gap_dem_minus_rep_pp": round(gap, 2),
                "cross_check": "OPEN item 2 records W114's Dem-Rep trust gap as 21.6 pp",
                "what_it_proves": "the reader, the 4-point rescale, the weighting, the linearised SE "
                                  "and the party cut all reproduce a number measured by a different "
                                  "route; only the battery's own column names are still unverified"}
    finally:
        BATTERY, CLASS, MICRO = keep


def main():
    tl = parse_topline()
    missing = [k for k in CLASS if k not in tl]
    if missing:
        raise SystemExit(f"topline parse missed items: {missing}")

    pew = json.load(open(PEW_TRUST))
    sci = {w: pew["waves"][w]["items"][f"CONF_{'G' if w != 'w42' else 'F2'}_{w.upper()}"]["cuts"]["overall"]["ALL"]
           for w in ("w100", "w114")}
    SCI = {w: v["mean_0_100"] for w, v in sci.items()}
    sci_level = sum(SCI.values()) / 2                       # 66.9: Pew ATP confidence in *scientists*

    res = {"warmth": {}, "bridges": {}, "adopted": {}, "provenance": {}}
    for ns in ("exclude", "midpoint"):
        res["warmth"][ns] = {it: {wv: round(rescale(d, ns), 2) for wv, d in tl[it].items()} for it in tl}

    def mean_of(cls, wave, ns):
        xs = [res["warmth"][ns][it][wave] for it in tl if CLASS[it] == cls and wave in tl[it]]
        return sum(xs) / len(xs)

    for ns in ("exclude", "midpoint"):
        for wave in WAVES:
            gov = mean_of("gov", wave, ns)
            epa = res["warmth"][ns]["EPA"][wave]
            nasa = res["warmth"][ns]["NASA"][wave]
            cdc = res["warmth"][ns]["CDC"][wave]
            # NOAA has no measurement anywhere. Bracketed by the two agencies that do:
            noaa_lo, noaa_hi = min(epa, nasa), max(epa, nasa)
            noaa = (noaa_lo + noaa_hi) / 2
            agencies = {"EPA": epa, "NASA": nasa, "NOAA(bracketed)": noaa}
            mean_ag = sum(agencies.values()) / 3
            key = f"{wave}|not_sure={ns}"
            res["bridges"][key] = {
                "gov_comparators_mean": round(gov, 2), "cdc_cross_check_form1": round(cdc, 2),
                "agencies": {k: round(v, 2) for k, v in agencies.items()},
                "agencies_mean": round(mean_ag, 2),
                "sci_endpoint_pew_conf": round(sci_level, 2),
                # additive bridge: 1 pp of W149 warmth = 1 pp of the coarse-scale metric the card's
                # other two components are measured on. Needs no span rescaling; assumes only that
                # a 4-point favourability gap and a 3-point confidence gap are the same size.
                "B_additive_agency_off": round(mean_ag - sci_level, 2),
                "B_additive_per_agency": {k: round(v - sci_level, 2) for k, v in agencies.items()},
                # span bridge: rescale so that the W149 government cluster lands on the card's own
                # measured federal-government offset. theta is the fraction of the way from the
                # scientific community to the federal government.
                "theta_agencies": round((sci_level - mean_ag) / (sci_level - gov), 3),
                "theta_per_agency": {k: round((sci_level - v) / (sci_level - gov), 3) for k, v in agencies.items()},
                "gov_cluster_off_vs_sci": round(gov - sci_level, 2),
            }

    res["provenance"] = {
        "agency_margins": {
            "source": "Pew Research Center, American Trends Panel Wave 149 FINAL TOPLINE, Jul 1-7 2024, "
                      "N=9,424 (AGNCYFAV, Form 2 N=4,677 for EPA/NASA/DOJ/IRS/DHS; Form 1 N=4,747 for CDC), "
                      "with the Mar 13-19 2023 (W123) replicate printed in the same table",
            "file": str(TOPLINE), "kind": "PUBLISHED AGGREGATE MARGIN, not microdata",
            "item_text": "What is your overall opinion of each of the following agencies and departments of "
                         "the federal government? [very/somewhat favorable, somewhat/very unfavorable, not sure]",
            "party_crosstab_present": False,
            "party_note": "the vendored topline (txt AND pdf) carries only the PARTY marginal "
                          "(Rep 27 / Dem 26 / Ind 30 / else 14 / no answer 2, leaners 19/20). "
                          "There is NO agency x party table in it.",
        },
        "science_endpoint": {
            "source": "Pew ATP W100 (Sep 2021) + W114 (Mar 2022) CONF_G 'How much confidence, if any, do you "
                      "have in each of the following to act in the best interests of the public? Scientists'",
            "levels_0_100": {k: round(v, 2) for k, v in SCI.items()}, "adopted": round(sci_level, 2),
            "kind": "MICRODATA (mounted), rescaled (4-x)/3*100 - the same map applied to AGNCYFAV above",
        },
        "the_bridge_is_declared": (
            "No institution is measured in BOTH families on the mounted data - W149's 16 agencies and "
            "W100/W114's 9 confidence referents do not intersect - so the favourability->confidence map "
            "CANNOT be fitted here. It is declared, and the two bridges below bracket it."
        ),
        "noaa": "no favourability, confidence or trust measurement of NOAA exists on any mounted source or in "
                "any vendored topline. Nearest published: the National Weather Service at 76% favourable "
                "(Pew, Aug 2025 topline; microdata post-lock). NOAA is bracketed by EPA and NASA and taken at "
                "their midpoint; the bracket is reported.",
    }
    # ---- adoption ------------------------------------------------------------------------
    # PRIMARY SPEC, fixed on its own merits before any value was read:
    #   wave  = w149_jul2024  (latest, largest, and the wave whose microdata is being requested)
    #   ns    = midpoint      (the TARGET item is a 0-100 slider with no `not sure` escape, so a
    #                          respondent who has never heard of NOAA answers near the middle;
    #                          it does not drop out)
    #   bridge= B_span        (a RELATIVE POSITION inside one instrument, applied to a gap measured
    #                          in the other. B_additive is a LEVEL transfer across scale families,
    #                          which AGENTS.md standing finding 14 says does not transfer - so it is
    #                          reported as the other end of the bracket and NOT adopted.)
    PRIMARY = "w149_jul2024|not_sure=midpoint"
    theta = res["bridges"][PRIMARY]["theta_agencies"]
    span = [round(v["theta_agencies"], 3) for v in res["bridges"].values()]
    res["adopted"] = {
        "primary_spec": PRIMARY, "bridge": "B_span",
        "theta_agencies": theta,
        "theta_bracket_over_wave_x_notsure": [min(span), max(span)],
        "agency_off_formula": "agency_off = theta * fed_off, fed_off measured in GSS by build_baselines.py",
        "prior_assumption_replaced": "theta = 0.500 (the unmeasured midpoint of [scientific community, "
                                     "federal government]) adopted in run 20260815-dryrun-05",
        "b_additive_reading_same_spec": res["bridges"][PRIMARY]["B_additive_agency_off"],
        "headline": ("the three agencies sit %.0f%% of the way from the scientific community to the federal "
                     "government, not 50%%: NASA is ABOVE the science endpoint on every spec and EPA below it, "
                     "and the published margins put the whole bracket [%.3f, %.3f] strictly below the adopted "
                     "midpoint" % (100 * theta, min(span), max(span))),
        "what_the_W149_MICRODATA_will_replace": [
            "theta itself, computed from respondent-level EPA/NASA favourability instead of a published margin "
            "(and with a proper SE, which a topline cannot give)",
            "the agency x PARTY table, which the topline does NOT contain (checked in both the txt and the pdf) - "
            "this is the whole party half of OPEN item 14 and none of it is settled here",
            "the `not sure` treatment, which is a 10-23 pp share here and is currently a declared map "
            "(exclude vs midpoint moves theta from %.3f to %.3f on the primary wave)"
            % (res["bridges"]["w149_jul2024|not_sure=exclude"]["theta_agencies"], theta),
            "the gov-comparator set, which can then be a within-respondent contrast instead of a mean of margins",
            "whether W149 carries ANY science/scientist referent in-wave; if it does, the favourability->confidence "
            "bridge stops being declared and becomes fitted, which is the single largest remaining assumption",
        ],
        "what_W149_will_NOT_fix": [
            "NOAA, which is in no Pew battery at all (nearest: NWS 76% favourable, Aug 2025 topline)",
            "universities/colleges, whose card component is still GSS `coneduc` (education broadly, not "
            "higher education specifically)",
        ],
    }
    res["microdata"] = {w: microdata(w, "midpoint") for w in MICRO}
    res["microdata"]["_selftest"] = selftest_microdata()
    ready = [w for w, v in res["microdata"].items() if v.get("status") == "OK"]
    res["adopted"]["microdata_status"] = (
        "PRESENT for %s - rerun and replace theta with the microdata value" % ready if ready else
        "ABSENT: every number in this file is a PUBLISHED AGGREGATE MARGIN. Drop ATP_W149.sav into "
        "%s and rerun; the microdata path is already written and discovers its own column names."
        % MICRO["w149_jul2024"].parent)
    out = RUN / "inputs" / "measured" / "agency_trust_anchor.json"
    out.write_text(json.dumps(res, indent=1))
    print(f"wrote {out}")
    for k, v in res["bridges"].items():
        print(f"  {k:28s} gov {v['gov_comparators_mean']:5.1f}  EPA {v['agencies']['EPA']:5.1f}  "
              f"NASA {v['agencies']['NASA']:5.1f}  sci {v['sci_endpoint_pew_conf']:5.1f}  "
              f"B_add {v['B_additive_agency_off']:+6.2f}  theta {v['theta_agencies']:+.3f}")
    return res


if __name__ == "__main__":
    main()
