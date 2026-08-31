# Raw model logs for this run (registration item K.2)

**This run made ZERO model calls.** It is a baseline/offset/synthesis rebuild of
`runs/20260815-target-01`; its `card/ate.csv`, `card/responsiveness.csv` and `card/tilt.csv` are
**byte-identical** to that run's, which is asserted by `tools/build_target03.py` (assertion A1) at
every build and re-checkable in one line:

    sha256sum runs/20260815-target-01/card/ate.csv runs/20260823-target-04-main/card/ate.csv
    # both b382cd499264a6f9...

The complete unprocessed model responses that produced that ATE layer therefore live in

    runs/20260815-target-01/raw_model_logs/

- 4 prompts, 4 unprocessed completions, 4 provider JSON envelopes (model id, billed usage, timing)
- `MANIFEST.sha256`, which verifies under plain `sha256sum -c` (re-verified this session: all OK)
- a replay: parsing the three completions and taking the cell-wise median reproduces the deposited
  effect table to **0.0000000000 pp on all 208 cells**, and that table is this run's Tier 3 exactly
  (assertion A2, max |diff| 0).

**Operator decision (K.2):** one bundle covers `20260815-target-01`, `20260822-target-01b-main`,
`20260823-target-03-main` and `20260823-target-04-main`, because all four submit the same 208
predicted effects from the same four completions. `20260815-target-02-pooled` is the same
completions with the fitted multiplier 1.5212 applied deterministically. Deposit the bundle **once**
(in-repo, or as a separate linked Zenodo record - K.2 allows either) and cite it from each entry.
