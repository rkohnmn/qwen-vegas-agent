# Changelog

All notable project changes are recorded here. Contract version entries are checked by `python tasks.py docs-check`.

## [Unreleased] — Milestone 1

### Changed

- Set the supported Windows development target to Python 3.12 based on the installed runtime and current WhisperX/PyTorch compatibility metadata.
- Recorded the available CPU-only inference environment and missing `ffmpeg` / `ffprobe`; the real-media smoke portion remains stopped until those tools are installed locally.
- Added timeline=1.0.0, verify_report=1.0.0, run_manifest=1.0.0; bumped compile_report=1.2.0 for join fade decisions and two-sided snap records, edl=1.2.0 for ID-only gap actions and optional subtitle style, and words=2.0.0 for explicitly unaligned transcript tokens and gap refinement metadata.
- Updated Architecture to 1.2.0 for the M1 synthetic timeline, ID-only gap intent, and report contracts.

### Added

- Added read-only ffprobe preflight, cached 16 kHz audio extraction, a lazy WhisperX adapter with CPU fallback, and fixture-backed ASR/gap-refinement coverage.
- Added ID-oriented packing, baseline and recorded planners, an isolated loopback-only LLM client for fake-server tests, and an M1 CLI guard that keeps live LLM requests disabled.
- Added rational-frame compilation with aligned-word guards, optional nearby zero-crossing snaps, measured-gap cuts, per-join fade decisions, cut-ID/category marker labels, review CSV/CMX3600/Markdown artifacts, reference WAV rendering, join/pacing/clipped-word metrics, and run integrity metadata.
- Added a one-case offline synthetic eval and M1 Vegas reflection/compile-only evidence with a human-run probe checklist.
- Updated the README, roadmap, setup, security, perception, and evaluation documentation for the actual M1 implementation and its blocked real-media smoke run.

## [Milestone 0]

### Added

- Contract schemas and specs: words=1.0.0, speakers=1.0.0, catalog=1.0.0, edl=1.0.0, ops=1.0.0.
- Local config schema and secret redaction helpers.
- Cross-platform task runner, pinned dependency lock, valid/invalid fixture set, referential checks, and Milestone 0 docs.

### Changed

- Architecture updated to version 1.1.0 to reconcile the words gap index, catalog entry kinds, and the executor operation union with the Milestone 0 contract deliverables.
- Vegas notes moved to the canonical `docs/VEGAS_NOTES.md` path and bumped to 1.0.1. No Vegas behavior was verified.
