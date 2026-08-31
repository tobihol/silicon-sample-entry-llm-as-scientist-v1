# team_31 secondary-1 entry (llm-as-scientist-v1)

Tier-1 **secondary-1** entry of team_31 for the
[Silicon Sample Benchmark](https://janpfander.github.io/llm_predictions_megastudy/):
`predictions/team_31_T1_secondary-1_v1.csv`, 43,200 synthetic respondents
(16 interventions × 13 outcomes), with the completed `registration.md` and `metadata.json`.

**Method.** Dataset acquisition → [prime-agent](https://github.com/PrimeIntellect-ai/prime-agent) loop → derivation of
individual-level rows. The predictions are analysis-first: the study's published analysis
table is predicted directly and the individual-level rows are synthesized backwards from
it. The loop has a prescribed strategy and self-administered testing. The start state
fixes the strategy and the materials: predict analysis-first, improve by practicing on
tasks built from published data, and build the entry from nothing but that data plus plain
model completions (`claude-opus-5`, fixed prompts, no tools, no agent runtime, thinking
off). The deposited entry is therefore independent of the building agent's own reasoning:
it reproduces from code, data, and a handful of cached completions. Testing was
self-administered: practice ground truth sat in the loop's own filesystem, held out only
by its own discipline, with no external rules. The loop's start state is in the code
repository. The pipeline it built and the run's records are deposited under
`run_record/`.

## What is where

| path | what |
|---|---|
| `predictions/` | the scored prediction file (sha256 in `metadata.json`) |
| `registration.md` | the completed 39-item method registration |
| `run_record/pipeline/` | the pipeline the agent built: code (`tools/`, the `ssb` package), inputs, dataset notes, harness definitions, runbook, development ledger |
| `run_record/` | the run's recorded output: the target card, verbatim prompts, run and gate records |
| `raw_model_logs/` | registration item K.2: the 4 prompts and 4 unprocessed completions behind the effect table, with provider envelopes and manifest |

The campaign **environment and start state** (container launcher, frozen definitions,
first session brief) are in the team's code repository,
[silicon-sample-submission](https://github.com/tobihol/silicon-sample-submission) (registration K.1).

## Template provenance

This repository is a clone of the organizers' submission template
([janpfander/silicon-sample-submission](https://github.com/janpfander/silicon-sample-submission)
@ `546f928`), which provides `Makefile`, `scripts/`, `survey/`, `codebook.csv`, `FAQ.md`, and
`README.qmd`. The template's example data were replaced by this entry. Validation: `make check`
(the organizers' validator) passes with no failures.

## Licensing of the shipped survey materials

Your Zenodo license (default `CC-BY-4.0` in `metadata.json`) applies to **your** contribution:
your code, predictions, and documentation. The shipped `survey/` folder is different: several
intervention stimulus texts adapt previously published journalism and other copyrighted material,
included here for scholarly research use. Keep `survey/` in your deposit unchanged (it documents
what your respondents saw), but your license grant does not and cannot re-license those
underlying texts.

## Team

Registered team **team_31**: Tobias Holtdirk, Bolei Ma (LMU Munich, SODA Lab).
Contributor: Haiwen Huang. Contact: tobias.holtdirk@lmu.de.
