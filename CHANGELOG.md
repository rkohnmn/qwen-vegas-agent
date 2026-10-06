# Changelog

All notable project changes are recorded here. Contract version entries are checked by `python tasks.py docs-check`.

## [Unreleased] — Milestone 1

### Changed

- Set the supported Windows development target to Python 3.12 based on the installed runtime and current WhisperX/PyTorch compatibility metadata.
- Recorded the available CPU-only inference environment and missing `ffmpeg` / `ffprobe`; the real-media smoke portion remains stopped until those tools are installed locally.
- Added timeline=1.0.0, compile_report=1.0.0, verify_report=1.0.0, run_manifest=1.0.0; bumped edl=1.1.0 for ID-only gap actions.
- Updated Architecture to 1.2.0 for the M1 synthetic timeline, ID-only gap intent, and report contracts.

## [Milestone 0]

### Added

- Contract schemas and specs: words=1.0.0, speakers=1.0.0, catalog=1.0.0, edl=1.0.0, ops=1.0.0.
- Local config schema and secret redaction helpers.
- Cross-platform task runner, pinned dependency lock, valid/invalid fixture set, referential checks, and Milestone 0 docs.

### Changed

- Architecture updated to version 1.1.0 to reconcile the words gap index, catalog entry kinds, and the executor operation union with the Milestone 0 contract deliverables.
- Vegas notes moved to the canonical `docs/VEGAS_NOTES.md` path and bumped to 1.0.1. No Vegas behavior was verified.
