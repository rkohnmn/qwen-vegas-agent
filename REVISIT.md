# Revisit Register

This register tracks behavior implemented or described without live resources. Complete items in the dependency order in the runbook before enabling their dependent live features.

## 1. Revisit run order

1. Obtain the missing predecessor prompt artifacts and reconcile any requirements before claiming goals 01b–03 or their human gates complete.
2. Install or locate approved local FFmpeg tools and prepare disposable synthetic media; do not use user source media for executor probes.
3. Run the VEGAS probes on a disposable project using the exact steps in the applicable `docs/HUMAN_TESTS_M*.md` checklist. Record E0 evidence in `docs/VEGAS_NOTES.md` before enabling runtime-dependent paths.
4. Provide a labeled short clip and complete real-speech review; record accuracy metrics in `docs/EVALS.md` without replacing existing ground truth.
5. Turn on the self-hosted inference server only when ready, then run the recorded/live integration checks explicitly documented by their goal. No endpoint was contacted in this run.
6. Supply an HF token only if a future approved model download requires it. Never store it in the repository or pass it to child processes.
7. Complete the style interview, choose and document an asset-license decision, and provide an approved SFX library before enabling those features.
8. Run human acceptance tests and release checks on a clean checkout after all offline checks pass.

## 2. Items

### RV-001 — Goal 04 Vegas runtime and project mutation behavior

- **Feature or claim:** Marker/region transport, approval-marker cleanup, cut application, undo, gap closing, working-copy enforcement in Vegas, heartbeat/stop behavior, and Vegas-side rendering.
- **Why untested:** No human Vegas result is available; the agent must not launch Vegas. No predecessor `HUMAN_TESTS_M3.md` or `docs/VEGAS_DECISIONS.md` is present.
- **Assumption and locations:** Implement only through fakeable interfaces and sidecar review artifacts; prefer script-menu/file transport, explicit rebuild-capable edit strategy, manual render fallback, and fixed short crossfades. See `docs/VEGAS_DECISIONS.md` and `docs/PIPELINE.md`.
- **Exact test:** Follow `docs/HUMAN_TESTS_M4.md` on a disposable VEGAS Pro 17 project created from synthetic media. Exercise markers, reject/approve, execute a working copy, undo, stop/restart, render a WAV and preview, run `python tasks.py watch-render --job-dir <runs/job_id> --output final_render.mp4`, and compare before/after hashes. Do not use original projects or media.
- **Expected result and record:** No source changes; approved cuts only; undo restores the working copy; marker cleanup is scoped; renderer output is readable; stop and resume preserve state. Record Vegas build, operation outcomes, artifact hashes, join measurements, and E0 evidence IDs in the checklist and `docs/VEGAS_NOTES.md`.
- **Who:** Human with VEGAS Pro 17.
- **Severity:** blocker for enabling real Vegas execution; medium for the offline fake pipeline.
- **Related VQ IDs:** VQ-02, VQ-04, VQ-07, VQ-08, VQ-14, VQ-15, VQ-16; all remain UNVERIFIED or PARTIAL.
- **Status:** open.

### RV-002 — Goal 04 real-clip timing, sync, and listening quality

- **Feature or claim:** Real spoken-word sync, click-free joins, pacing thresholds, fix-loop quality, and final-render agreement.
- **Why untested:** No approved disposable clip, human listening result, or labeled timing ground truth was provided for this run.
- **Assumption and locations:** Offline tests use synthetic audio and deterministic fake render output; they do not establish editing quality. See `docs/EVALS.md` and `docs/HUMAN_TESTS_M4.md`.
- **Exact test:** After RV-001, run the M4 checklist on a 2–5 minute approved clip with labeled word boundaries; inspect and listen to every join, then calculate cut offset, clipped-word, click, level-step, pacing, and sync metrics using `python tasks.py eval` and the documented real-clip harness.
- **Expected result and record:** Report measured values and failures without changing thresholds to obtain a pass; record the clip identity only in ignored local artifacts, and record aggregate metrics and a redacted evidence reference in tracked docs.
- **Who:** Human reviewer; agent may calculate metrics after redacted results are supplied.
- **Severity:** high.
- **Related VQ IDs:** none; accuracy gate is independent of Vegas API questions.
- **Status:** open.

### RV-003 — Missing predecessor and reusable prompt artifacts

- **Feature or claim:** Requirements and acceptance evidence from goals 01b–03 and their interactive gates.
- **Why untested:** Those prompt files, the prompt-pack README, T1, HUMAN_GATES.md, STYLE_INTERVIEW.md, and HUMAN_TESTS_M3.md are absent from this checkout.
- **Assumption and locations:** Continue from the checked-in M1 implementation and record only the available goal results; do not backfill or claim predecessor acceptance. See `PROGRESS.md`.
- **Exact test:** Restore the exact missing prompt/reference files from the user's source pack, then compare their acceptance criteria with the completed-goal ledger and repository history. Run each missing goal's required checks before marking it done.
- **Expected result and record:** Every predecessor criterion has a concrete artifact or test and a commit; any unmet human gate has a separate RV entry.
- **Who:** Agent once the source files are available; human for human-only gates.
- **Severity:** medium.
- **Related VQ IDs:** none.
- **Status:** open.

## 3. Decisions needed from the human

- Missing predecessor prompts and gates: assumption is to proceed from the current M1 repository state and never claim unavailable goals as completed.
- Vegas transport, edit strategy, subtitle path, and render mechanism: provisional choices are recorded in `docs/VEGAS_DECISIONS.md`; confirm them with the probes before enabling runtime alternatives.
- Release license: no license is selected; a human must choose one before packaging/release work.
- Style interview and sound-effect source: absent; features depending on them remain disabled or use deterministic fakes.

## 4. Pending pushes and blockers

- Goal 04 commits `2788809`, `720b174`, and `83e892a` are not pushed yet. Push only after the prompt archival/completion commit and its privacy gate; then record the exact result.
- No implementation blocker has been confirmed yet.

## 5. Provisional decisions to confirm

- Vegas transport: script-menu/file sidecars with marker review, with runtime invocation disabled until probed.
- Edit strategy: explicit gap closing behind a rebuild-capable interface; keep linked A/V groups together.
- Subtitle path: burned-in captions plus a sidecar as the default when that goal is reached.
- Audio joins: short fixed crossfades pending human listening and click measurements.
- Rendering: manual render plus watched output as the fallback until Vegas render scripting is proven.

## 6. Human-only actions

- Run the VEGAS checks in `docs/HUMAN_TESTS_M1.md` and goal-specific `docs/HUMAN_TESTS_M*.md` on disposable projects.
- Provide and label approved short clips; review and listen to edited joins.
- Install or locate a local FFmpeg build before using the `run-job` default reference renderer (RV-004).
- Complete `STYLE_INTERVIEW.md`, choose the project license, and provide an approved SFX library.
- Enable a server or provide a token only for explicitly documented later integration tests; no such resource is assumed available.


### RV-004 — Goal 04 default reference renderer availability

- **Feature or claim:** CLI `run-job` default reference WAV render and verification path.
- **Why untested:** FFmpeg and ffprobe are not available on this machine; the closed-loop tests inject deterministic fake renderers.
- **Assumption and locations:** Local FFmpeg will be installed or located before using the default `ReferenceAudioRenderer`; this does not change Vegas rendering status. See `orchestrator/job_pipeline.py`, `README.md`, and `docs/KNOWN_LIMITS.md`.
- **Exact test:** After locating an approved local FFmpeg build, create a disposable synthetic WAV and timeline/words fixture, run `python tasks.py run-job --project <copy.veg> --media <source> --timeline <timeline.json> --words <words.json> --audio <normalized.wav>`, then confirm `preview.wav` opens and `verify_report.json` records checks from the WAV read back from disk.
- **Expected result and record:** Reference WAV is created under ignored `runs/`, parses at the declared sample rate, and verification records its checks. Record the FFmpeg version and the synthetic result; do not treat it as Vegas-render evidence.
- **Who:** Agent after local FFmpeg is available; no downloads during this run.
- **Severity:** medium.
- **Related VQ IDs:** none; this is a local media-tool prerequisite.
- **Status:** open.
