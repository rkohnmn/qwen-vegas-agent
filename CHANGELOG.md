# Changelog

All notable project changes are recorded here. Contract version entries are checked by `python tasks.py docs-check`.

## [Unreleased] — Milestone 1

### Changed

- Run strict mypy over both `orchestrator/` and `perception/`, matching the repository lint contract.
- Corrected the current `ops` schema version recorded in preflight-blocked and completed run manifests, with a regression test for the blocked-manifest path.
- Bumped Architecture to 1.2.1 to replace the stale missing-FFmpeg status; D-29 recorded the initial W_VFR stop and D-30 supersedes it with corrected CFR evidence.
- Set the supported Windows development target to Python 3.12 based on the installed runtime and current WhisperX/PyTorch compatibility metadata.
- Recorded the venv CUDA 12.8 install and local FFmpeg 9.0.1 discovery. The corrected bounded VFR scan classifies the selected source as CFR and the real-media smoke completed.
- Recorded the corrected English real-media smoke: 210 of 210 transcript rows received timing anchors, duration sanity flags, eight gap actions emitted 16 joins, and the verifier surfaced 12 level-step and four pacing failures without changing thresholds. An unlabeled truth template is saved under the ignored run directory.
- Recorded the user-approved 30 fps CFR working copy and the PyTorch-hosted English alignment checkpoint with its byte size, checksum, source, and stated MIT license.
- Added timeline=1.0.0, verify_report=1.0.0, and run_manifest=1.0.0; bumped compile_report=2.0.0 for required per-cut/gap outcomes and ops=1.1.0 for optional source item IDs on final delete operations. Existing versions: edl=1.2.0, words=2.0.0, speakers=1.0.0, catalog=1.0.0.
- Updated Architecture to 1.2.0 for the M1 synthetic timeline, ID-only gap intent, and report contracts.

### Added

- Fixed bounded ffprobe VFR sampling by looking ahead 16 packets while classifying only the requested timestamp window; regression tests cover tail artifacts and in-window cadence changes.
- Completed the approved real-media dry run with unchanged source hash and protected-directory listings; recorded ASR checkpoint revisions, sizes, benchmark, and license metadata limitation.
- Changed ASR real-time factor reporting to elapsed ASR time divided by media duration.
- Fixed WhisperX sentence-split alignment mapping with regression coverage for split segments and safe fallback on text mismatch.
- Added regression coverage proving Japanese subword timing is not relabeled as word timing when segmentation does not match the word-level contract.

- Added read-only ffprobe preflight, cached 16 kHz audio extraction, a lazy WhisperX adapter with CPU fallback, and fixture-backed ASR/gap-refinement coverage.
- Added ID-oriented packing, baseline and recorded planners, and a loopback-only LLM client with bounded backoff, typed failures, schema/cut-feedback retries, redirect blocking, and fake-server coverage; the M1 CLI still rejects live LLM runs.
- Added rational-frame compilation with aligned-word guards, optional nearby zero-crossing snaps, measured-gap cuts, per-item compile outcomes linked to final ops, rejected-item review context, applied evaluation metrics, per-join fade decisions, review CSV/CMX3600/Markdown artifacts, reference audio rendering, join/pacing/clipped-word metrics, and run integrity metadata.
- Added generated speech-like verifier coverage alongside the retained tone stress case, applied-metric reporting, and expanded EC-only Vegas metadata notes. Added the opt-in `setup --asr` installer while keeping plain setup dev-only.
- Completed the read-only VEGAS metadata follow-ups in VEGAS_NOTES 1.0.4 and recorded D-28; metadata continues to count as compile-time evidence only. Strengthened compiler coverage to assert each cut and gap action has exactly one outcome.
- Updated the README, roadmap, setup, security, perception, and evaluation documentation for the real-media smoke. All 30 Japanese tokens were unaligned, so no cuts or joins were available for quality calibration.

## [Milestone 0]

### Added

- Contract schemas and specs: words=1.0.0, speakers=1.0.0, catalog=1.0.0, edl=1.0.0, ops=1.0.0.
- Local config schema and secret redaction helpers.
- Cross-platform task runner, pinned dependency lock, valid/invalid fixture set, referential checks, and Milestone 0 docs.

### Changed

- Architecture updated to version 1.1.0 to reconcile the words gap index, catalog entry kinds, and the executor operation union with the Milestone 0 contract deliverables.
- Vegas notes moved to the canonical `docs/VEGAS_NOTES.md` path and bumped to 1.0.1. No Vegas behavior was verified.
