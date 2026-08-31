# inputs/derived/ — dataset extracts used by the harness

Tracked files here come only from CC-BY / MIT / CC0 sources (tappin2023,
hackenburg2025, kim2024, altenmueller2024) and are redistributable with attribution.

**Five files are deliberately disk-only** (gitignored; license scrub 2026-08-24,
see `docs/legal-review-2026-08-24.md` §4 — their sources declare no license /
no-redistribution, so respondent-level extracts must not be published):
`bbprime2025_analysis.csv`, `dablander2025.csv`, `gligoric2025_trust.csv`,
`koetke2024_study5.csv`, `orchinik2024_bovitz.csv`.

To regenerate them from a fresh clone: fetch the raw sources
(`data/<dataset>/fetch.sh` → `data/<dataset>/downloads/`), then run the matching
builder in `tools/`: `build_dablander.py`, `build_gligoric.py`, `build_koetke.py`,
`build_orchinik.py`; `bbprime2025_analysis.csv` is the study's own analysis file
subset per `inputs/adapters/bbprime2025.json` (provenance in `notes/DATA_*.md`).
