#!/usr/bin/env python
"""Re-measure the billed-token estimator's factors from a run's own calls. Makes no model call.

    /opt/kernel/venv/bin/python tools/billing_factors.py [--runs runs/A runs/B ...]

Finding 28 measured three numbers once, on the climate briefs, and tools/practice.py and
tools/target.py have carried them as constants since:

    tokenizer factor 1.574   CLI second pass +73.2%   output 19 tokens/cell

Session 10's first batch on two NEW tasks landed at 0.77x its estimate. The ledger was right (it
counts what the provider reported); the PRICE quoted to the operator was wrong, and this says
which factor moved.

Method: a run's cost.json states exactly which payloads it planned and how many times each would
be called, all counted by `ssb.predict.n_tokens`. Where the run paid for every planned call (no
cache hits), sum(provider context tokens) / sum(planned payload tokens) is an exact measurement
of the factor for THAT corpus. Where some calls were cache hits the mapping is ambiguous and this
prints SKIPPED rather than a number - a factor derived from a guessed mapping is how finding 52
happened.
"""
import argparse, glob, json, sys
from pathlib import Path

import pandas as pd

RUN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RUN / ".prime/agent/skills/ssb/src"))
import ssb  # noqa: E402

CACHE = RUN / "runs" / "_cache" / "completions"


def planned(run: Path):
    """(planned payload tokens, planned calls, planned cells) from the run's own cost.json."""
    cost = json.loads((run / "stages" / "practice" / "cost.json").read_text())
    tok = calls = cells = 0
    for t, p in cost["plans"].items():
        row = next(r for r in cost["per_task"] if r["task"] == t)
        tok += sum(p["tokens_per_part"]) * cost["draws"] + (p["probe_tokens"] if cost["probe"] else 0)
        calls += row["calls"]
        cells += p["n_cells"] * cost["draws"]
    return tok, calls, cells


def measure(run: Path):
    sp = json.loads((run / "stages" / "practice" / "spend.json").read_text())
    tok, calls, cells = planned(run)
    made = sp["paid_calls"]
    ctx = haiku = out = 0
    model = None
    for c in sp["calls"]:
        f = glob.glob(str(CACHE / (c["key"] + "*.json")))
        if not f:
            return None
        j = json.loads(Path(f[0]).read_text())
        model = j["model"]
        mu = j["payload"].get("modelUsage") or {}
        for k, v in mu.items():
            n_in = (v.get("inputTokens", 0) + v.get("cacheReadInputTokens", 0)
                    + v.get("cacheCreationInputTokens", 0))
            if "haiku" in k:
                haiku += n_in + v.get("outputTokens", 0)
            else:
                ctx += n_in
                out += v.get("outputTokens", 0)
    ok = made == calls
    return {"run": run.name, "model": model, "paid_calls": made, "planned_calls": calls,
            "complete": ok, "planned_payload_tokens": tok, "provider_context_tokens": ctx,
            "tokenizer_factor": (ctx / tok) if ok else float("nan"),
            "chars_per_token": (4 * tok / ctx) if ok else float("nan"),
            "cli_overhead": haiku / ctx if ctx else float("nan"),
            "out_tokens_per_cell": (out / cells) if ok else float("nan"),
            "billed": sp["billed_tokens"]}


def main(runs):
    rows = [r for r in (measure(RUN / x) for x in runs) if r]
    d = pd.DataFrame(rows)
    print("%-38s%-16s%7s%10s%12s%12s%11s%10s" % ("run", "model", "calls", "complete", "factor",
                                                 "chars/tok", "CLI extra", "out/cell"))
    for r in d.itertuples():
        print("%-38s%-16s%7d%10s%12s%12s%11s%10s"
              % (r.run, r.model, r.paid_calls, "yes" if r.complete else "SKIPPED (cache hits)",
                 "%.3f" % r.tokenizer_factor if r.complete else "-",
                 "%.2f" % r.chars_per_token if r.complete else "-",
                 "%+.1f%%" % (100 * r.cli_overhead), 
                 "%.1f" % r.out_tokens_per_cell if r.complete else "-"))
    print("\nThe constants in tools/practice.py: factor 1.574, CLI +73.2%, 19 tokens/cell.")
    print("`ssb.predict.n_tokens` has no tiktoken here and falls back to len/4, so `factor` is a "
          "CHARACTERS-PER-TOKEN ratio\nand a property of the CORPUS: re-measure it on the first "
          "batch of any new task family and re-price from there.")
    (RUN / "runs" / "_scratch" / "billing_factors.csv").write_text(d.to_csv(index=False))
    return d


if __name__ == "__main__":
    a = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--runs", nargs="*", default=[
        "runs/20260815-practice-01", "runs/20260817-practice-t67",
        "runs/20260817-promptexp-reason-t67", "runs/20260817-practice-fable-t67",
        "runs/20260817-promptexp-fable-reason-t67"])
    main(a.parse_args().runs)
