"""ssb.synth - backward synthesis: individual rows built to match a card.

The frozen definitions call a synthesis that matches means but not spread a failed
synthesis, and name the variance ratio the headline diagnostic with under-dispersion
the documented LLM failure mode. So dispersion here is a *target*, not a by-product:
the per-cell SD comes from human data (ssb.card baseline.control_sd) and the
generator solves for the latent sigma that reproduces it AFTER integer rounding
and slider heaping.

Pipeline
    1. profiles   - draw respondents from a joint demographic table (ACS x CES)
    2. assign     - allocate conditions at the preregistered per-cell sizes
    3. link       - individual linear predictor mu_i from the card, additively
                    combining the six moderator offsets and responsiveness factors
    4. rake       - a few additive passes so realised marginal cell means match
                    card.cell_means() (this is what makes Tier 1 and Tier 2 agree)
    5. respond    - draw integer responses with the target SD and human-like heaping
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from . import card as _card
from . import spec

# --------------------------------------------------------------------------
# response-format parameters (evidence: notes/DATA_format.md; edit there, not here)
# --------------------------------------------------------------------------

DEFAULT_HEAPING = {
    # MEASURED, not declared. Fitted by simulation (not algebra) against the 30 PRE
    # 0-100 item columns of voelkel2026's control arm - climate ATTITUDE items in a
    # census-quota US panel, 95,437 item responses: 41.2% on multiples of 5, 31.4% on
    # multiples of 10, 5.9% at 0, 5.2% at 50, 11.4% at 100. The evidence block and the
    # fit quality live in inputs/format_params.json; orchinik2024 and sce remain the
    # PROBABILITY-item reference (sce's 16.8% at 50 is 3x the attitude-item spike).
    "p_round10": 0.0176,
    "p_round5": 0.0311,
    "education_gradient": 0.09,   # measured across voelkel2026's 3 education strata
    "p_endpoint_lo": 0.5361,      # conditional: latent within `endpoint_window` of the floor
    "p_endpoint_hi": 0.9259,
    "endpoint_window": 4.0,
    "scale_lo": 0.0,
    "scale_hi": 100.0,
    # attraction points beyond the endpoints, [value, window, probability]:
    # the attitude slider's midpoint, and the $0/$5/$10 spikes of a real donation item
    # (goldwert2026 control arm, n=1,116: 29.7% / 28.9% / 23.7% - 82.3% on three values).
    "slider_atoms": [[50.0, 4.0, 0.8467]],
    "donation_atoms": [[0.0, 2.5, 0.8004], [5.0, 2.5, 0.7032], [10.0, 2.5, 0.7650]],
    "p_donation_zero": 0.0,
    "p_donation_max": 0.0,
}


def load_format_params(path=None) -> dict:
    """Heaping parameters, from a run's inputs/format_params.json when present."""
    p = Path(path) if path else spec.RUNROOT / "inputs" / "format_params.json"
    if p.exists():
        d = dict(DEFAULT_HEAPING)
        d.update(json.loads(p.read_text()))
        return d
    return dict(DEFAULT_HEAPING)


# --------------------------------------------------------------------------
# 1. profiles
# --------------------------------------------------------------------------


def draw_profiles(n: int, joint: pd.DataFrame, rng) -> pd.DataFrame:
    """Draw `n` respondents from a joint demographic table.

    `joint` has the six moderator columns (exact spec level strings) plus `weight`.
    Built once per run from ACS (age/gender/race/education/income) reweighted onto
    CES for party; see AGENTS.md stage `pool`.
    """
    mods = list(spec.load()["moderators"])
    missing = [m for m in mods + ["weight"] if m not in joint.columns]
    if missing:
        raise ValueError(f"joint table missing columns: {missing}")
    for m in mods:
        bad = set(joint[m]) - set(spec.load()["moderators"][m])
        if bad:
            raise ValueError(f"joint table has non-spec levels in {m}: {sorted(bad)}")
    w = joint.weight.to_numpy(float)
    idx = rng.choice(len(joint), size=n, replace=True, p=w / w.sum())
    out = joint.iloc[idx][mods].reset_index(drop=True)
    out.insert(0, "profile_id", [f"p{i:06d}" for i in range(1, n + 1)])
    return out


def assign_conditions(pool: pd.DataFrame, n_per_intervention: int, n_control: int, rng) -> pd.DataFrame:
    """Allocate conditions at the Tier-1 precision floor (frozen Coverage/Tier-1 rules)."""
    s = spec.load()
    need = n_control + n_per_intervention * len(s["interventions"])
    if len(pool) != need:
        raise ValueError(f"pool has {len(pool)} rows, need exactly {need}")
    labels = ["control"] * n_control + [c for c in s["interventions"] for _ in range(n_per_intervention)]
    out = pool.copy()
    out["condition"] = rng.permutation(labels)
    return out


# --------------------------------------------------------------------------
# 3-4. individual linear predictor, raked onto the card's cell means
# --------------------------------------------------------------------------


def _mu(df: pd.DataFrame, outcome: str, base: float, offs: dict, facs: dict, ates: dict) -> np.ndarray:
    """mu_i = base + sum_m offset[m, l_i] + ate[cond_i] * (1 + sum_m (factor[cond_i, m, l_i] - 1))

    Deviations from both the grand mean and the marginal ATE combine ADDITIVELY across
    the six moderators. Multiplying them would compound six factors into implausible
    extremes and would break the share-weighted identity the card guarantees.
    """
    mods = list(spec.load()["moderators"])
    mu = np.full(len(df), base, float)
    for m in mods:
        mu += df[m].map(lambda l, m=m: offs[(m, l, outcome)]).to_numpy(float)
    eff = df.condition.map(lambda c: ates.get((c, outcome), 0.0)).to_numpy(float)
    tilt = np.ones(len(df))
    for m in mods:
        tilt += np.array([facs.get((c, m, l), 1.0) - 1.0
                          for c, l in zip(df.condition, df[m])])
    return mu + eff * tilt


def latent_means(rows: pd.DataFrame, crd: _card.Card, rake_passes: int = 12,
                 tol: float = 0.02) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Per-respondent latent mean for every outcome, raked so the realised marginal
    cell means reproduce `crd.cell_means()`.

    Returns (mu table, rake diagnostics). The diagnostics are gate G6 evidence:
    max absolute drift between the card's cell means and what the rows actually say.
    """
    s = spec.load()
    mods = list(s["moderators"])
    target = crd.cell_means().set_index(["condition", "moderator", "level", "outcome"])["mean"]
    base = crd.baseline.set_index("outcome")["control_mean"].to_dict()
    offs = {(m, l, o): v for (m, l, o), v in
            crd.subgroup.set_index(["moderator", "level", "outcome"])["offset"].items()}
    facs = crd._factor_matrix().set_index(["condition", "moderator", "level"])["factor"].to_dict()
    ates = crd.ate.set_index(["condition", "outcome"])["ate"].to_dict()

    mu = pd.DataFrame(index=rows.index)
    diag = []
    for o in s["outcomes"]:
        lo, hi = s["ranges"][o]
        off_o = {k: v for k, v in offs.items() if k[2] == o}
        v = _mu(rows, o, base[o], off_o, facs, ates)
        for _ in range(rake_passes):
            adj = np.zeros(len(rows))
            worst = 0.0
            for m in mods:
                g = pd.DataFrame({"c": rows.condition, "l": rows[m], "v": v})
                realised = g.groupby(["c", "l"], observed=True)["v"].mean()
                for (c, l), got in realised.items():
                    want = target.get((c, m, l, o), np.nan)
                    if not np.isfinite(want):
                        continue
                    d = want - got
                    worst = max(worst, abs(d))
                    sel = (rows.condition.values == c) & (rows[m].values == l)
                    adj[sel] += d / len(mods)
            v = v + adj
            if worst < tol:
                break
        v = np.clip(v, lo, hi)
        mu[o] = v
        # final honest drift measurement, after clipping
        worst = 0.0
        for m in mods:
            realised = pd.DataFrame({"c": rows.condition, "l": rows[m], "v": v}).groupby(
                ["c", "l"], observed=True)["v"].mean()
            for (c, l), got in realised.items():
                want = target.get((c, m, l, o), np.nan)
                if np.isfinite(want):
                    worst = max(worst, abs(spec.to_pp(want - got, o)))
        diag.append({"outcome": o, "max_cell_drift_pp": worst})
    return mu, pd.DataFrame(diag)


# --------------------------------------------------------------------------
# 5. responses
# --------------------------------------------------------------------------


def _beta_draw(mu, sd, lo, hi, rng):
    """Draw on [lo, hi] with the given mean and SD via a scaled Beta (method of
    moments), shrinking the variance where the Beta is infeasible for that mean."""
    span = hi - lo
    p = np.clip((np.asarray(mu, float) - lo) / span, 1e-4, 1 - 1e-4)
    v = (np.asarray(sd, float) / span) ** 2
    v = np.minimum(v, p * (1 - p) * 0.999)
    k = np.maximum(p * (1 - p) / np.maximum(v, 1e-12) - 1, 1e-3)
    return lo + span * rng.beta(p * k, (1 - p) * k)


def _round_human(x, edu, params, rng):
    """Turn a latent slider value into the integer a human would actually leave.

    Stochastic rounding mixture: with prob `p_round10` snap to the nearest 10, with
    `p_round5` to the nearest 5, otherwise to the nearest integer; then endpoint
    atoms. The mixture weights are inverted from published heaping shares - see
    notes/DATA_format.md, which records orchinik2024 (a quota panel: 42.5% on
    multiples of 5, 13.7% at 100) and sce (75.3% on multiples of 5) verbatim.

    APPLY THIS AT ITEM LEVEL ONLY. A human composite is the mean of k heaped items
    and is therefore itself un-heaped and finely grained; heaping a composite
    directly would produce a distribution no human sample has.
    """
    x = np.asarray(x, float)
    n = len(x)
    edu_levels = spec.load()["moderators"]["education"]
    rank = pd.Series(np.asarray(edu)).map(
        {l: i / (len(edu_levels) - 1) for i, l in enumerate(edu_levels)}).to_numpy(float)
    rank = np.nan_to_num(rank, nan=0.5)
    # sce: heaping falls with education -> tilt mass from coarse rounding to integers
    g = params["education_gradient"] * (rank - 0.5)
    p10 = np.clip(params["p_round10"] * (1 - g), 0, 1)
    p5 = np.clip(params["p_round5"] * (1 - g), 0, 1)
    u = rng.random(n)
    out = np.rint(x)
    m5 = (u >= p10) & (u < p10 + p5)
    m10 = u < p10
    out[m5] = np.rint(x[m5] / 5.0) * 5.0
    out[m10] = np.rint(x[m10] / 10.0) * 10.0
    lo, hi = params["scale_lo"], params["scale_hi"]
    pull = rng.random(n)
    out[((x - lo) < params["endpoint_window"]) & (pull < params["p_endpoint_lo"])] = lo
    out[((hi - x) < params["endpoint_window"]) & (pull < params["p_endpoint_hi"])] = hi
    # explicit attraction points beyond the two endpoints: the midpoint of an attitude
    # slider (measured on voelkel2026 control-arm PRE items) and the $0/$5/$10 spikes of
    # a real donation item (measured on goldwert2026). Both are real human structure that
    # a rounding mixture alone does not produce; see inputs/format_params.json.
    for value, window, prob in params.get("atoms") or []:
        out[(np.abs(x - value) < window) & (pull < prob)] = value
    return np.clip(out, lo, hi)


def _item_sd(comp_sd: float, k: int, rho: float) -> float:
    """Item SD that yields `comp_sd` for a k-item composite with within-scale
    correlation rho:  SD_comp = SD_item * sqrt(rho + (1 - rho)/k)."""
    return float(comp_sd / np.sqrt(rho + (1.0 - rho) / k))


def _solve_scale(draw_fn, target_sd: float, iters: int = 16, hi_mult: float = 3.0) -> float:
    """Bisect on a latent SD so the SD of the FINAL, rounded, composited values equals
    the human target. Heaping and averaging both move spread; the variance-ratio row
    is the headline diagnostic, so it is solved for rather than hoped for."""
    lo_s, hi_s = 1e-3, max(1.0, target_sd * hi_mult)
    for _ in range(iters):
        mid = 0.5 * (lo_s + hi_s)
        if draw_fn(mid) < target_sd:
            lo_s = mid
        else:
            hi_s = mid
    return 0.5 * (lo_s + hi_s)


def _spread_weights(mu, lo, hi, gamma: float) -> np.ndarray:
    """Per-respondent spread multiplier, mean 1, from the mean-variance link of a
    bounded scale:  sd_i  proportional to  (p_i (1 - p_i)) ** gamma,  p = (mu - lo)/(hi - lo).

    MEASURED, not assumed (tools/dist_audit.py, runs/_dist/PREREG.md amendment 1):
    regressing log(group SD) on log(p(1-p)) over 65 control-arm demographic cells of the
    design twin, with outcome fixed effects, gives gamma = 1.003 (SE 0.073, R2 0.889) in
    humans against 0.195 in the deposited rows. gamma = 0 is a constant SD and reproduces
    the pre-amendment behaviour byte for byte, so this is a strict generalisation.
    """
    if not gamma:
        return np.ones(len(np.asarray(mu, float)))
    p = np.clip((np.asarray(mu, float) - lo) / (hi - lo), 1e-3, 1 - 1e-3)
    w = (p * (1 - p)) ** float(gamma)
    return w / float(np.mean(w))


def _draw_composite(mu, comp_sd, k, edu, params, rng, rho=0.6, want_items=False,
                    gamma: float = 0.0, scale_mask=None):
    """A k-item scale: latent respondent level -> k heaped integer items -> their mean.

    k = 1 is the single-item case and returns the heaped integer itself.

    `scale_mask` names the rows whose realised SD the solver must hit. None is the
    historical behaviour (the whole file); the control arm is what `control_sd` actually
    means, and the frozen table's variance-ratio row is stated per CELL.
    """
    n = len(mu)
    lo, hi = params["scale_lo"], params["scale_hi"]
    w = _spread_weights(mu, lo, hi, gamma)
    sel = slice(None) if scale_mask is None else np.asarray(scale_mask, bool)

    def build(sig_lat):
        rng2 = np.random.default_rng(rng.integers(1 << 62))
        s_item = _item_sd(comp_sd, k, rho) if k > 1 else comp_sd
        tau = float(np.sqrt(max(1e-6, s_item ** 2 - sig_lat ** 2))) if k > 1 else 0.0
        L = _beta_draw(mu, sig_lat * w, lo, hi, rng2)
        if k == 1:
            return [_round_human(L, edu, params, rng2)]
        return [_round_human(_beta_draw(np.clip(L, lo + 1e-6, hi - 1e-6),
                                        np.maximum(tau * w, 1e-3), lo, hi, rng2),
                             edu, params, rng2) for _ in range(k)]

    sig = _solve_scale(lambda s: float(np.std(np.mean(build(s), axis=0)[sel], ddof=1)), comp_sd)
    items = build(sig)
    comp = np.mean(items, axis=0)
    return (comp, items) if want_items else comp


def synthesize(crd: _card.Card, joint: pd.DataFrame, n_per_intervention: int = 4000,
               n_control: int = 8000, seed: int = 0, rho: float | dict = 0.6,
               format_params: dict | None = None, fit: bool = True,
               spread_gamma: float = 0.0, scale_on_control: bool = False
               ) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Build a Tier-1 table from a card. Returns (tier1, diagnostics).

    Defaults sit well ABOVE the preregistered floor on purpose: see fit_means() and
    DESIGN.md for the measurement that motivated it.

    `rho` is the within-scale item correlation used to split a composite's target SD
    into k item SDs. A float applies one value to every composite (the historical
    behaviour, 0.6). A dict {outcome: rho} applies a per-composite value and falls
    back to 0.6 - within-scale rho is a property of the SCALE and the design twin
    measures it at 0.381-0.904 across its own eight scales, so one global value is a
    declared constant where a measurement exists (tools/dist_audit.py).
    """
    rho_of = (lambda o: float(rho.get(o, 0.6))) if isinstance(rho, dict) else (lambda o: float(rho))
    # spread_gamma = 0.0 is the historical constant-SD behaviour; see _spread_weights.
    # scale_on_control=False is the historical target (the whole file); True targets the
    # control arm, which is what card.baseline.control_sd is and what the frozen
    # variance-ratio row ("per cell") asks for.
    s = spec.load()
    params = load_format_params() if format_params is None else format_params
    rng = np.random.default_rng(seed)
    n = n_control + n_per_intervention * len(s["interventions"])
    rows = assign_conditions(draw_profiles(n, joint, rng), n_per_intervention, n_control, rng)
    mu, drift = latent_means(rows, crd)
    sd = crd.baseline.set_index("outcome")["control_sd"].to_dict()
    comps = spec.composites()
    out = rows.copy()
    cmask = (rows.condition == "control").to_numpy() if scale_on_control else None
    slider = dict(params, scale_lo=0.0, scale_hi=100.0, atoms=params.get("slider_atoms"))

    for o in s["outcomes"]:
        if o == "newsletter_signup":
            out[o] = (rng.random(n) < np.clip(mu[o], 0, 1)).astype(int)
        elif o == "donation_ams":
            dp = dict(params, scale_lo=0.0, scale_hi=10.0, p_round10=0.0, p_round5=0.0,
                      p_endpoint_lo=params.get("p_donation_zero", 0.0),
                      p_endpoint_hi=params.get("p_donation_max", 0.0), endpoint_window=0.75,
                      atoms=params.get("donation_atoms"))
            out[o] = _draw_composite(mu[o].to_numpy(), sd[o], 1, out.education, dp, rng,
                                     gamma=spread_gamma, scale_mask=cmask).astype(int)
        elif o == "trust_multidimensional":
            comp, items = _draw_composite(mu[o].to_numpy(), sd[o], 12, out.education,
                                          slider, rng, rho=rho_of(o), want_items=True,
                                          gamma=spread_gamma, scale_mask=cmask)
            for name, v in zip(s["trust_items"], items):
                out[name] = v.astype(int)
            out[o] = _composite_from_items(out)  # exactly the codebook definition
        else:
            k = len(comps[o]) if o in comps else 1
            out[o] = _draw_composite(mu[o].to_numpy(), sd[o], k, out.education, slider, rng,
                                     rho=rho_of(o), gamma=spread_gamma, scale_mask=cmask)
            if k == 1:
                out[o] = out[o].astype(int)

    if fit:
        out = fit_means(out, crd, rng)

    diagnostics = drift.merge(
        pd.DataFrame([{"outcome": o, "n_items": 12 if o == "trust_multidimensional"
                       else len(comps.get(o, [1])) if o in comps else 1,
                       "target_sd": sd[o], "realised_sd": float(out[o].std(ddof=1))}
                      for o in s["outcomes"]]), on="outcome")
    diagnostics["sd_ratio"] = diagnostics.realised_sd / diagnostics.target_sd
    return out[spec.tier1_columns()], diagnostics


# --------------------------------------------------------------------------
# residual mean fitting - removing OUR OWN sampling noise from the deposit
# --------------------------------------------------------------------------


def fit_means(tier1: pd.DataFrame, crd: _card.Card, rng, passes: int = 3,
              step_slider: int = 5) -> pd.DataFrame:
    """Nudge realised cell means onto the card's predicted means.

    Why this exists (measured, see DESIGN.md): at the preregistered Tier-1 floor the
    standard error of an ATE recomputed from the rows is ~1.3 pp, which is larger
    than the ATEs themselves. Left alone, the deposited rows report the card's
    prediction PLUS 1.3 pp of our own noise, and Section-1 RMSE is scored on that sum.
    The floor is a minimum, not a target: the two remedies are a bigger pool (free,
    and preferred) and this residual fit (cheap, and keeps the file small).

    Adjustments move whole respondents by `step_slider` (5) on sliders, so the
    multiple-of-5 heaping structure survives; by 1 on donation; by a flip on the
    binary. Within a condition, adjustments are allocated to the moderator levels
    that are themselves furthest from target, so the moderator grid improves too.
    """
    s = spec.load()
    out = tier1.copy()
    mods = list(s["moderators"])
    # a composite is the mean of k integer items and is NOT itself integer-valued;
    # casting it back to int would erase the fine granularity human composites have
    integral = {o: bool(np.allclose(out[o] % 1, 0)) for o in s["outcomes"]}
    tgt_main = crd.tier2_main().set_index(["condition", "outcome"])["mean"]
    tgt_mod = crd.tier2_moderator().set_index(
        ["condition", "moderator", "moderator_level", "outcome"])["mean"]

    for o in s["outcomes"]:
        lo, hi = s["ranges"][o]
        step = 1 if o == "donation_ams" else (1 if o == "newsletter_signup" else step_slider)
        for _ in range(passes):
            for c in s["conditions"]:
                sel = np.flatnonzero((out.condition == c).to_numpy())
                if not len(sel):
                    continue
                v = np.array(out[o].to_numpy(float), copy=True)
                delta = float(tgt_main[(c, o)] - v[sel].mean())
                k = int(round(abs(delta) * len(sel) / step))
                if k == 0:
                    continue
                sign = 1.0 if delta > 0 else -1.0
                # eligible = has headroom to move in `sign` direction
                elig = sel[(v[sel] + sign * step <= hi) & (v[sel] + sign * step >= lo)]
                if not len(elig):
                    continue
                # priority: respondents in moderator cells that are themselves off-target
                pri = np.zeros(len(elig))
                for m in mods:
                    lv = out[m].to_numpy()[elig]
                    for l in s["moderators"][m]:
                        mask = lv == l
                        if not mask.any():
                            continue
                        cell = elig[mask]
                        d = float(tgt_mod.get((c, m, l, o), np.nan) - v[cell].mean())
                        if np.isfinite(d):
                            pri[mask] += sign * d
                jitter = rng.random(len(elig)) * 1e-6
                order = np.argsort(-(pri + jitter))
                pick = elig[order[: min(k, len(elig))]]
                if o == "trust_multidimensional":
                    # the composite is scored AS SUBMITTED but the validator checks it
                    # against its items, so move the items and recompute it from them
                    for it in s["trust_items"]:
                        col = np.array(out[it].to_numpy(float), copy=True)
                        col[pick] = np.clip(col[pick] + sign * step, lo, hi)
                        out[it] = col.astype(int)
                    out[o] = _composite_from_items(out)
                else:
                    v[pick] += sign * step
                    out[o] = v.astype(int) if integral[o] else v
    return out


def _composite_from_items(df: pd.DataFrame) -> np.ndarray:
    """trust_multidimensional exactly as codebook.csv defines it: the mean of the four
    subscale means. Computed from the submitted items so the two can never disagree."""
    return np.column_stack([
        np.mean([df[f"trust_{d}_{i}"].to_numpy(float) for i in (1, 2, 3)], axis=0)
        for d in ("competence", "integrity", "benevolence", "openness")]).mean(axis=1)


# --------------------------------------------------------------------------
# reconstruction: what the deposited rows actually say
# --------------------------------------------------------------------------


def recompute(tier1: pd.DataFrame) -> dict:
    """Recompute the benchmark's analyses FROM the synthetic rows.

    Gate G6 compares this against the card. If they disagree, the deposit would be
    scored on numbers the harness never predicted.
    """
    s = spec.load()
    main = tier1.groupby("condition", observed=True)[s["outcomes"]].mean()
    ctrl = main.loc["control"]
    t3 = pd.DataFrame([{"condition": c, "outcome": o, "ate": float(main.loc[c, o] - ctrl[o])}
                       for c in s["interventions"] for o in s["outcomes"]])
    t2m = pd.DataFrame([{"condition": c, "outcome": o, "mean": float(main.loc[c, o])}
                        for c in s["conditions"] for o in s["outcomes"]])
    mod = []
    for m in s["moderators"]:
        g = tier1.groupby(["condition", m], observed=True)[s["outcomes"]].mean()
        for (c, l), r in g.iterrows():
            for o in s["outcomes"]:
                mod.append({"condition": c, "moderator": m, "moderator_level": l,
                            "outcome": o, "mean": float(r[o])})
    return {"tier3": t3, "tier2_main": t2m, "tier2_moderator": pd.DataFrame(mod)}
