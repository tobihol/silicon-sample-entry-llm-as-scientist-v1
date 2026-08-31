"""ssb.card - the prediction card: one object, three tiers.

A *card* is a directory of small CSV/JSON files holding every number the harness
predicts. Tier 1, Tier 2 and Tier 3 are all *derived* from it, so the three
deposited files cannot disagree with each other by construction.

    card/
      meta.json         provenance: run id, model, stage, notes, damping switch
      baseline.csv      outcome, control_mean, control_sd          (native units)
      subgroup.csv      moderator, level, outcome, offset, share   (native units)
      ate.csv           condition, outcome, ate                    (native units, 16x13)
      responsiveness.csv moderator, level, factor                  (27 numbers)
      tilt.csv          condition, moderator, level, factor        (sparse, default 1.0)

Subgroup ATE model (deliberately low-rank; see DESIGN.md choice 3):

    ate[i, o, m, l] = ate[i, o] * r[m, l] * t[i, m, l] / Z[i, m]

`Z[i, m]` is the share-weighted mean of `r * t` over the levels of moderator m, so
subgroup ATEs always average back to the marginal ATE. Without it the Tier-2
moderator file would silently contradict the Tier-2 main file.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd

from . import spec

FILES = ("meta.json", "baseline.csv", "subgroup.csv", "ate.csv", "responsiveness.csv", "tilt.csv")


@dataclass
class Card:
    meta: dict
    baseline: pd.DataFrame          # outcome, control_mean, control_sd
    subgroup: pd.DataFrame          # moderator, level, outcome, offset, share
    ate: pd.DataFrame               # condition, outcome, ate
    responsiveness: pd.DataFrame    # moderator, level, factor
    tilt: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(columns=["condition", "moderator", "level", "factor"]))

    # ---------------- io ----------------
    @classmethod
    def load(cls, path) -> "Card":
        p = Path(path)
        tilt_p = p / "tilt.csv"
        return cls(
            meta=json.loads((p / "meta.json").read_text()),
            baseline=pd.read_csv(p / "baseline.csv"),
            subgroup=pd.read_csv(p / "subgroup.csv"),
            ate=pd.read_csv(p / "ate.csv"),
            responsiveness=pd.read_csv(p / "responsiveness.csv"),
            tilt=pd.read_csv(tilt_p) if tilt_p.exists() else pd.DataFrame(columns=["condition", "moderator", "level", "factor"]),
        )

    def save(self, path) -> Path:
        p = Path(path)
        p.mkdir(parents=True, exist_ok=True)
        (p / "meta.json").write_text(json.dumps(self.meta, indent=1, sort_keys=True))
        for name in ("baseline", "subgroup", "ate", "responsiveness", "tilt"):
            getattr(self, name).to_csv(p / f"{name}.csv", index=False)
        return p

    # ---------------- construction helpers ----------------
    @classmethod
    def skeleton(cls, shares: dict[tuple[str, str], float] | None = None, meta: dict | None = None) -> "Card":
        """An all-zero, structurally complete card. Every predicted number is 0/neutral,
        which is exactly the no-effect floor of the frozen scoring table."""
        s = spec.load()
        base = pd.DataFrame({"outcome": s["outcomes"], "control_mean": np.nan, "control_sd": np.nan})
        sub = pd.DataFrame(
            [
                {"moderator": m, "level": l, "outcome": o, "offset": 0.0,
                 "share": (shares or {}).get((m, l), np.nan)}
                for m, l in s["moderator_levels"]
                for o in s["outcomes"]
            ]
        )
        ate = pd.DataFrame(
            [{"condition": c, "outcome": o, "ate": 0.0} for c in s["interventions"] for o in s["outcomes"]]
        )
        resp = pd.DataFrame([{"moderator": m, "level": l, "factor": 1.0} for m, l in s["moderator_levels"]])
        return cls(meta=meta or {}, baseline=base, subgroup=sub, ate=ate, responsiveness=resp)

    # ---------------- validation ----------------
    def validate(self) -> list[str]:
        """Return a list of problems. Empty list == card is complete and internally sane."""
        s = spec.load()
        bad: list[str] = []
        exp_out = set(s["outcomes"])
        if set(self.baseline.outcome) != exp_out:
            bad.append(f"baseline: outcomes {sorted(exp_out ^ set(self.baseline.outcome))} mismatched")
        if self.baseline[["control_mean", "control_sd"]].isna().any().any():
            bad.append("baseline: NA in control_mean/control_sd")
        want_ate = {(c, o) for c in s["interventions"] for o in s["outcomes"]}
        got_ate = set(map(tuple, self.ate[["condition", "outcome"]].values))
        if got_ate != want_ate:
            bad.append(f"ate: {len(want_ate - got_ate)} missing, {len(got_ate - want_ate)} unexpected cells")
        if self.ate.ate.isna().any():
            bad.append("ate: NA present")
        want_sub = {(m, l, o) for m, l in s["moderator_levels"] for o in s["outcomes"]}
        got_sub = set(map(tuple, self.subgroup[["moderator", "level", "outcome"]].values))
        if got_sub != want_sub:
            bad.append(f"subgroup: {len(want_sub - got_sub)} missing, {len(got_sub - want_sub)} unexpected cells")
        if self.subgroup.offset.isna().any():
            bad.append("subgroup: NA offset")
        sh = self.subgroup.drop_duplicates(["moderator", "level"]).groupby("moderator")["share"].sum()
        off = sh[(sh - 1.0).abs() > 1e-6]
        if len(off):
            bad.append(f"subgroup: shares do not sum to 1 for {list(off.index)}")
        if set(map(tuple, self.responsiveness[["moderator", "level"]].values)) != set(s["moderator_levels"]):
            bad.append("responsiveness: moderator levels mismatched")
        for _, r in self.baseline.iterrows():
            lo, hi = s["ranges"][r.outcome]
            if not (lo <= r.control_mean <= hi):
                bad.append(f"baseline: {r.outcome} control_mean {r.control_mean} outside [{lo},{hi}]")
            if r.control_sd < 0:
                bad.append(f"baseline: {r.outcome} negative sd")
        return bad

    # ---------------- derivation ----------------
    def _factor_matrix(self) -> pd.DataFrame:
        """condition x (moderator, level) -> normalised r*t factor."""
        s = spec.load()
        shares = self.subgroup.drop_duplicates(["moderator", "level"]).set_index(["moderator", "level"])["share"]
        r = self.responsiveness.set_index(["moderator", "level"])["factor"]
        t = self.tilt.set_index(["condition", "moderator", "level"])["factor"] if len(self.tilt) else pd.Series(dtype=float)
        rows = []
        for i in s["interventions"]:
            for m, levels in s["moderators"].items():
                raw = np.array([r[(m, l)] * float(t.get((i, m, l), 1.0)) for l in levels])
                w = np.array([shares[(m, l)] for l in levels])
                z = float((w * raw).sum())
                if abs(z) < 1e-9:
                    raise ValueError(f"degenerate normaliser for {i}/{m}")
                for l, f in zip(levels, raw / z):
                    rows.append({"condition": i, "moderator": m, "level": l, "factor": f})
        return pd.DataFrame(rows)

    def tier3(self) -> pd.DataFrame:
        """condition, outcome, ate - 208 rows, native units, no control row."""
        s = spec.load()
        d = self.ate.copy()
        d["condition"] = pd.Categorical(d.condition, s["interventions"], ordered=True)
        d["outcome"] = pd.Categorical(d.outcome, s["outcomes"], ordered=True)
        return d.sort_values(["condition", "outcome"]).astype({"condition": str, "outcome": str}).reset_index(drop=True)

    def tier2_main(self) -> pd.DataFrame:
        """condition, outcome, mean - 221 rows, native units, clipped to scale."""
        s = spec.load()
        base = self.baseline.set_index("outcome")["control_mean"]
        rows = [{"condition": "control", "outcome": o, "mean": float(base[o])} for o in s["outcomes"]]
        for _, r in self.ate.iterrows():
            lo, hi = s["ranges"][r.outcome]
            rows.append({"condition": r.condition, "outcome": r.outcome,
                         "mean": float(np.clip(base[r.outcome] + r.ate, lo, hi))})
        d = pd.DataFrame(rows)
        d["condition"] = pd.Categorical(d.condition, s["conditions"], ordered=True)
        d["outcome"] = pd.Categorical(d.outcome, s["outcomes"], ordered=True)
        return d.sort_values(["condition", "outcome"]).astype({"condition": str, "outcome": str}).reset_index(drop=True)

    def cell_means(self) -> pd.DataFrame:
        """condition x moderator x level x outcome -> mean (native units, clipped).

        This is the Tier-2 moderator grid AND the target that backward synthesis
        writes rows against, so the two can never drift apart.
        """
        s = spec.load()
        base = self.baseline.set_index("outcome")["control_mean"]
        off = self.subgroup.set_index(["moderator", "level", "outcome"])["offset"]
        fac = self._factor_matrix().set_index(["condition", "moderator", "level"])["factor"]
        ate = self.ate.set_index(["condition", "outcome"])["ate"]
        rows = []
        for m, levels in s["moderators"].items():
            for l in levels:
                for o in s["outcomes"]:
                    lo, hi = s["ranges"][o]
                    ctrl = base[o] + off[(m, l, o)]
                    rows.append({"condition": "control", "moderator": m, "level": l,
                                 "outcome": o, "mean": float(np.clip(ctrl, lo, hi))})
                    for i in s["interventions"]:
                        eff = ate[(i, o)] * fac[(i, m, l)]
                        rows.append({"condition": i, "moderator": m, "level": l,
                                     "outcome": o, "mean": float(np.clip(ctrl + eff, lo, hi))})
        d = pd.DataFrame(rows)
        d["condition"] = pd.Categorical(d.condition, s["conditions"], ordered=True)
        d["outcome"] = pd.Categorical(d.outcome, s["outcomes"], ordered=True)
        return d.sort_values(["condition", "moderator", "level", "outcome"]).astype(
            {"condition": str, "outcome": str}).reset_index(drop=True)

    def tier2_moderator(self) -> pd.DataFrame:
        """condition, moderator, moderator_level, outcome, mean - 5,967 rows."""
        d = self.cell_means().rename(columns={"level": "moderator_level"})
        return d[["condition", "moderator", "moderator_level", "outcome", "mean"]]

    def clipping_report(self) -> pd.DataFrame:
        """Cells whose predicted mean hit a scale boundary. A long report means the
        card is asking for effects the scale cannot deliver - fix the card, not the clip."""
        s = spec.load()
        base = self.baseline.set_index("outcome")["control_mean"]
        off = self.subgroup.set_index(["moderator", "level", "outcome"])["offset"]
        fac = self._factor_matrix().set_index(["condition", "moderator", "level"])["factor"]
        ate = self.ate.set_index(["condition", "outcome"])["ate"]
        rows = []
        for m, levels in s["moderators"].items():
            for l in levels:
                for o in s["outcomes"]:
                    lo, hi = s["ranges"][o]
                    for i in s["interventions"]:
                        raw = base[o] + off[(m, l, o)] + ate[(i, o)] * fac[(i, m, l)]
                        if raw < lo - 1e-9 or raw > hi + 1e-9:
                            rows.append({"condition": i, "moderator": m, "level": l,
                                         "outcome": o, "raw": raw, "lo": lo, "hi": hi})
        return pd.DataFrame(rows)


def from_inputs(ate: pd.DataFrame, meta: dict | None = None, inputs=None) -> "Card":
    """Assemble a card from the built inputs plus a predicted ATE table (native units).

    Reads `inputs/pool/joint.csv` for the moderator shares and
    `inputs/baselines/{control_levels,subgroup_offsets}.csv` for the human-anchored
    control levels and subgroup offsets, so stage 6 is a function of files on disk
    rather than of whatever was in a notebook. `ate` must already be in NATIVE units -
    use ssb.predict.to_native on a predictor's percentage-point output first.

    Responsiveness is left at 1.0 everywhere (the honest no-moderation floor); a run
    that believes in differential responsiveness overwrites it after this call.
    """
    inputs = Path(inputs) if inputs else spec.RUNROOT / "inputs"
    s = spec.load()
    pool = pd.read_csv(inputs / "pool" / "joint.csv")
    shares = {(m, l): float(pool[pool[m] == l].weight.sum()) / float(pool.weight.sum())
              for m in s["moderators"] for l in s["moderators"][m]}
    crd = Card.skeleton(shares=shares, meta=meta or {})
    lv = pd.read_csv(inputs / "baselines" / "control_levels.csv")
    crd.baseline = lv[["outcome", "control_mean", "control_sd"]].copy()
    off = pd.read_csv(inputs / "baselines" / "subgroup_offsets.csv")
    crd.subgroup = crd.subgroup.drop(columns=["offset"]).merge(
        off[["moderator", "level", "outcome", "offset"]], on=["moderator", "level", "outcome"], how="left")
    crd.subgroup["offset"] = crd.subgroup.offset.fillna(0.0)
    crd.subgroup = crd.subgroup[["moderator", "level", "outcome", "offset", "share"]]
    crd.ate = ate[["condition", "outcome", "ate"]].copy()
    return crd
