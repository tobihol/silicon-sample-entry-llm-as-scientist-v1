# run_record/ — the run's recorded output

The loop's start state (frozen definitions, first session brief, launcher) is in the code
repository (registration K.1). This folder holds the pipeline the agent designed under the
frozen rules and the record of the run that produced the entry
(`20260823-target-04-main`):

- `pipeline/` — the pipeline the agent built: code (`tools/`, the `ssb` package), inputs, dataset
  notes, harness definitions, runbook, development ledger.
- `card/` — the target card the pipeline assembled: effect table (`ate.csv`), control
  levels (`baseline.csv`), subgroup offsets, response shapes, tilt.
- `prompts/` — the verbatim predictor and probe prompts (`system.txt`, `user.txt`,
  `probe_system.txt`, `probe_user.txt`), the blinding-probe verdict
  (`blinding_probe.json`), and the spend records (`cost.json`, `spend.json`).
- `run.json` — the run's pre-registered parameters (including the three baseline-layer
  changes of target-04); `gates.json` — the deposit gates and their results.
- `frozen.sha256` — signature of the frozen definitions at run time.
- `registration_draft.md` — the harness-generated registration draft with per-item
  sources.
