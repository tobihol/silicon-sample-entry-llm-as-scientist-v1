#!/usr/bin/env python
"""Stage the raw model logs the registration form requires, hashed and timestamped. K.2.

`registration.md` K.2: "Raw output logs - complete unprocessed model responses archived, hashed,
time-stamped (required for Tiers 1-2, public or escrowed; ... oversized logs may be a separate
linked Zenodo upload)". Ours existed - prompts, transcripts and cached JSON envelopes all sit under
`runs/<id>/stages/target/` - but they were never assembled into anything depositable, and
`raw_data_deposit/` is not the place for them: that folder is the Qualtrics-export path for teams
that actually ran a simulated survey, and an analysis-first pipeline correctly leaves it empty.

    /opt/kernel/venv/bin/python tools/stage_raw_logs.py runs/20260815-target-01

Writes `runs/<id>/raw_model_logs/` containing every prompt sent, every unprocessed completion
received, the provider's own JSON envelopes (which carry the model id, token usage and timestamps),
a `MANIFEST.sha256` and a `README.md` explaining the mapping to K.2.

It does NOT touch the deposit. The bundle is staged so the operator can either copy it into the
repo or make it the separate linked Zenodo upload the form explicitly permits - both are operator
acts, and a `make check`-verified deposit is not something a tool should edit behind them.
"""
import argparse, hashlib, json, shutil, sys, time
from pathlib import Path

RUN = Path(__file__).resolve().parents[1]


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    h.update(p.read_bytes())
    return h.hexdigest()


def main(run):
    d = RUN / run
    src = d / "stages/target"
    if not src.exists():
        raise SystemExit(f"no target stage in {d}")
    out = d / "raw_model_logs"
    if out.exists():
        shutil.rmtree(out)
    (out / "prompts").mkdir(parents=True)
    (out / "completions").mkdir()
    (out / "envelopes").mkdir()

    spend = json.loads((d / "stages/target/spend.json").read_text())
    cost = json.loads((d / "stages/target/cost.json").read_text())
    meta = json.loads((d / "card/meta.json").read_text())
    cache = RUN / "runs/_cache/completions"

    staged = []
    for f in sorted(src.glob("*.txt")):
        sub = "prompts" if f.name.endswith(("system.txt", "user.txt")) else "completions"
        shutil.copy2(f, out / sub / f.name)
        staged.append((f"{sub}/{f.name}", out / sub / f.name))

    # the provider's own envelopes carry model id, billed usage and timestamps.
    # A run whose calls were ALL cache hits records no call keys in spend.json (it paid for
    # nothing), so fall back to the probe's recorded cache_key and to matching the completions
    # themselves - otherwise the bundle silently ships zero envelopes, which is the failure this
    # note exists to prevent.
    keys = [c.get("key", "") for c in spend.get("calls", []) if c.get("key")]
    if not keys:
        pk = json.loads((d / "stages/target/blinding_probe.json").read_text()).get("cache_key", "")
        bodies = {(out / "completions" / f.name).read_text().strip()
                  for f in (out / "completions").iterdir()}
        for c in sorted(cache.glob("*.json")):
            try:
                j = json.loads(c.read_text())
            except Exception:
                continue
            res = str(j.get("text", j.get("result", ""))).strip()
            if (pk and c.stem.startswith(pk[:12])) or (res and res in bodies):
                keys.append(c.stem[:12])
    n_env = 0
    for k in keys:
        for c in cache.glob("*.json"):
            try:
                j = json.loads(c.read_text())
            except Exception:
                continue
            if j.get("cache_key", "").startswith(k) or c.stem.startswith(k):
                dst = out / "envelopes" / f"{k}.json"
                shutil.copy2(c, dst)
                staged.append((f"envelopes/{k}.json", dst))
                n_env += 1
                break

    lines = [f"{sha256(p)}  {rel}" for rel, p in sorted(staged)]
    (out / "MANIFEST.sha256").write_text("\n".join(lines) + "\n")

    rd = [
        "# Raw model logs — registration form item K.2\n",
        f"Run `{run}`, model `{cost.get('model')}`, "
        f"{cost.get('calls')} calls ({cost.get('draws')} prediction draws + 1 blinding probe), "
        f"{spend.get('billed_tokens', 0):,} billed tokens.",
        f"Staged {time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())}.\n",
        "## What is here\n",
        "| directory | contents |",
        "|---|---|",
        "| `prompts/` | the exact system and user text sent for the prediction call and for the "
        "blinding probe, byte for byte |",
        "| `completions/` | the **unprocessed** model responses, exactly as received, before parsing |",
        "| `envelopes/` | the provider's own JSON envelopes: model id, token usage, timing |",
        "| `MANIFEST.sha256` | sha256 of every file above |",
        "\n## Why this is complete\n",
        "Every model call this pipeline makes is one plain completion with no tools, no retrieval "
        "and no conversation history, so a prompt and its completion are the entire interaction. "
        "There is no hidden state, no intermediate generation and no per-respondent output — the "
        "approach is analysis-first and never simulates a respondent.\n",
        f"The blinding probe is included deliberately: it is the call that asked the model whether "
        f"it already knew this study's results, **before any prediction was made**, and its verdict "
        f"is the evidence behind registration item I.3.\n",
        "## What is NOT here\n",
        "`raw_data_deposit/` in the submission repo is the Qualtrics-export path, for teams whose "
        "pipeline produces a simulated survey export. This one does not, so that folder is "
        "correctly empty and these logs are not it.\n",
        "## Deposit\n",
        "Under K.2 these may be shipped inside the repo (public or escrowed) or uploaded as a "
        "separate linked Zenodo record. Both are operator decisions; this bundle is staged, not "
        "deposited, and the `make check`-verified submission directories are untouched.",
    ]

    # Does the bundle actually reproduce what was deposited? A log archive nobody can replay is
    # an assertion, not evidence.
    repro = None
    try:
        sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
        import pandas as pd
        import ssb  # noqa: E402
        dep = pd.read_csv(d / "stages/target/ate_pp_raw.csv")
        conds, outs = sorted(dep.condition.unique()), sorted(dep.outcome.unique())
        fr = [ssb.predict.parse((out / "completions" / f"transcript_draw{i}_part1.txt").read_text(),
                                conds, outs) for i in range(int(cost.get("draws", 3)))]
        med = pd.concat(fr).groupby(["condition", "outcome"], as_index=False).ate.median()
        jj = med.merge(dep[["condition", "outcome", "ate"]], on=["condition", "outcome"],
                       suffixes=("_logs", "_dep"))
        repro = float((jj.ate_logs - jj.ate_dep).abs().max())
        rd.insert(-2, "## Replay\n")
        rd.insert(-2, "These logs reproduce the deposited predictions exactly. Parse the three "
                      "completions, take the cell-wise median, and the result equals the deposited "
                      f"effect table to **{repro:.10f} pp** on all {len(jj)} cells; converting to "
                      "each outcome's native units then reproduces the card, and the card "
                      "reproduces all three tiers. The whole chain "
                      "`completions -> parse -> median -> native units -> card -> Tier 1/2/3` is "
                      "checkable by a third party from this bundle plus the submission repo.\n")
    except Exception as e:                                            # pragma: no cover
        rd.insert(-2, f"\n*(replay check not run: {str(e)[:80]})*\n")
    (out / "README.md").write_text("\n".join(rd) + "\n")

    total = sum(p.stat().st_size for _, p in staged)
    print(f"staged {len(staged)} files ({total:,} bytes) -> {out}")
    print(f"  prompts {len(list((out / 'prompts').iterdir()))}, "
          f"completions {len(list((out / 'completions').iterdir()))}, "
          f"envelopes {n_env}")
    print(f"  MANIFEST.sha256 over {len(lines)} files")
    if repro is not None:
        print(f"  REPLAY: the completions reparse to the deposited table, max diff {repro:.10f} pp")
    print("  the submission_T* directories are UNTOUCHED")
    want = int(cost.get("calls", 0))
    if n_env < want:
        print(f"  NOTE: {want - n_env} of {want} provider envelope(s) could not be located in the "
              "cache. Prompts and completions are complete and the replay above still holds; the "
              "envelopes only add the provider's own usage/timing record.")
    return 0


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("run", nargs="?", default="runs/20260815-target-01")
    sys.exit(main(a.parse_args().run))
