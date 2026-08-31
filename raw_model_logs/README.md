# Raw model logs — registration form item K.2

Run `runs/20260815-target-01`, model `claude-opus-5`, 4 calls (3 prediction draws + 1 blinding probe), 123,276 billed tokens.
Staged 2026-08-15T22:31:54Z.

## What is here

| directory | contents |
|---|---|
| `prompts/` | the exact system and user text sent for the prediction call and for the blinding probe, byte for byte |
| `completions/` | the **unprocessed** model responses, exactly as received, before parsing |
| `envelopes/` | the provider's own JSON envelopes: model id, token usage, timing |
| `MANIFEST.sha256` | sha256 of every file above |

## Why this is complete

Every model call this pipeline makes is one plain completion with no tools, no retrieval and no conversation history, so a prompt and its completion are the entire interaction. There is no hidden state, no intermediate generation and no per-respondent output — the approach is analysis-first and never simulates a respondent.

The blinding probe is included deliberately: it is the call that asked the model whether it already knew this study's results, **before any prediction was made**, and its verdict is the evidence behind registration item I.3.

## What is NOT here

`raw_data_deposit/` in the submission repo is the Qualtrics-export path, for teams whose pipeline produces a simulated survey export. This one does not, so that folder is correctly empty and these logs are not it.

## Replay

These logs reproduce the deposited predictions exactly. Parse the three completions, take the cell-wise median, and the result equals the deposited effect table to **0.0000000000 pp** on all 208 cells; converting to each outcome's native units then reproduces the card, and the card reproduces all three tiers. The whole chain `completions -> parse -> median -> native units -> card -> Tier 1/2/3` is checkable by a third party from this bundle plus the submission repo.

## Deposit

Under K.2 these may be shipped inside the repo (public or escrowed) or uploaded as a separate linked Zenodo record. Both are operator decisions; this bundle is staged, not deposited, and the `make check`-verified submission directories are untouched.
