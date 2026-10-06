# Changelog

All notable project changes are recorded here. Contract version entries are checked by `python tasks.py docs-check`.

## [Unreleased] — Milestone 1

### Changed

- Run strict mypy over both `orchestrator/` and `perception/`, matching the repository lint contract.
- Corrected the current `ops` schema version recorded in preflight-blocked and completed run manifests, with a regression test for the blocked-manifest path.
- Set the supported Windows development target to Python 3.12 based on the installed runtime and current WhisperX/PyTorch compatibility metadata.
- Recorded the venv CUDA 12.8 install and local FFmpeg 9.0.1 discovery; read-only preflight reports W_VFR, so the real-media smoke stops before audio extraction pending user direction.
- Added timeline=1.0.0, verify_report=1.0.0, and run_manifest=1.0.0; bumped compile_report=2.0.0 for required per-cut/gap outcomes and ops=1.1.0 for optional source item IDs on final delete operations. Existing versions: edl=1.2.0, words=2.0.0, speakers=1.0.0, catalog=1.0.0.
- Updated Architecture to 1.2.0 for the M1 synthetic timeline, ID-only gap intent, and report contracts.

### Added

- Added read-only ffprobe preflight, cached 16 kHz audio extraction, a lazy WhisperX adapter with CPU fallback, and fixture-backed ASR/gap-refinement coverage.
- Added ID-oriented packing, baseline and recorded planners, and a loopback-only LLM client with bounded backoff, typed failures, schema/cut-feedback retries, redirect blocking, and fake-server coverage; the M1 CLI still rejects live LLM runs.
- Added rational-frame compilation with aligned-word guards, optional nearby zero-crossing snaps, measured-gap cuts, per-item compile outcomes linked to final ops, rejected-item review context, applied evaluation metrics, per-join fade decisions, review CSV/CMX3600/Markdown artifacts, reference audio rendering, join/pacing/clipped-word metrics, and run integrity metadata.
- Added generated speech-like verifier coverage alongside the retained tone stress case, applied-metric reporting, and expanded EC-only Vegas metadata notes. Added the opt-in `setup --asr` installer while keeping plain setup dev-only.
- Updated the README, roadmap, setup, security, perception, and evaluation documentation for the actual M1 implementation and its VFR-blocked real-media smoke run.

## [Milestone 0]

### Added

- Contract schemas and specs: words=1.0.0, speakers=1.0.0, catalog=1.0.0, edl=1.0.0, ops=1.0.0.
- Local config schema and secret redaction helpers.
- Cross-platform task runner, pinned dependency lock, valid/invalid fixture set, referential checks, and Milestone 0 docs.

### Changed

- Architecture updated to version 1.1.0 to reconcile the words gap index, catalog entry kinds, and the executor operation union with the Milestone 0 contract deliverables.
- Vegas notes moved to the canonical `docs/VEGAS_NOTES.md` path and bumped to 1.0.1. No Vegas behavior was verified.
