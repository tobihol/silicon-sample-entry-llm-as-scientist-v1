# inputs/texts/ — verbatim stimulus/arm texts

Tracked files come from CC-BY / MIT / CC0 sources only (tappin2023, hackenburg2025,
kim2024, altenmueller2024, vlasceanu2024).

**Nine files are deliberately disk-only** (gitignored; license scrub 2026-08-24, see
`docs/legal-review-2026-08-24.md` §4 — verbatim stimulus texts from
no-license/all-rights-reserved sources): `bbprime2025_arms.json`,
`dablander2025_arms.json`, `gligoric2025_arms.json`, `goldwert2026_arms.json`,
`koetke2024_arms.json`, `orchinik2024_arms.json`, `orchinik2024_items.json`,
`voelkel2024_arms.json`, `voelkel2026_arms.json`.

Regenerate from `data/<dataset>/downloads/` (after `fetch.sh`) via
`tools/extract_qsf_texts.py` (QSF-based: bbprime2025, vlasceanu2024) or the
dataset's `tools/build_*.py` / the extraction recipe in `inputs/adapters/<ds>.json`
(`message_texts_source` documents the exact source file per dataset).
