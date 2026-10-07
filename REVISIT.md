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
8. Complete the Goal 06 style/probe gate and evaluate the local ASS burn-in path before enabling caption rendering or Vegas operations.
9. Complete the Goal 07 catalog/transition and SFX license/runtime checks (RV-009, RV-010) before enabling any corresponding executor capability.
10. Restore the runtime EDL prompt and add the optional effect/at-gap rules before enabling planner-authored catalog edits (RV-011).
11. Run human acceptance tests and release checks on a clean checkout after all offline checks pass.

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
- Goal 07 G4 transition allowlist and licensed SFX folder: assume an empty default transition allowlist and no usable SFX until an explicitly licensed local library is supplied (RV-009, RV-010).

## 4. Pending pushes and blockers

- Goal 04 commits `2788809`, `720b174`, `83e892a`, and `f7e88d0` were pushed successfully to `origin/main` after the privacy gate. Future goal commits require their own privacy-gated push.
- No push blocker is open. Goal 07 has three open gates: Vegas/runtime evidence (RV-009), local SFX tools/library (RV-010), and the absent runtime EDL prompt (RV-011); offline work continues.

## 5. Provisional decisions to confirm

- Vegas transport: script-menu/file sidecars with marker review, with runtime invocation disabled until probed.
- Edit strategy: explicit gap closing behind a rebuild-capable interface; keep linked A/V groups together.
- Subtitle path: burned-in captions plus a sidecar as the default when that goal is reached.
- Audio joins: short fixed crossfades pending human listening and click measurements.
- Goal 07 catalog: deterministic closed keys and disabled-by-default entries; no Vegas mutation capability until RV-009 probes provide E0 evidence.
- Goal 07 SFX: local-only, license-required assets; no default sample and no planner exposure until RV-010 is cleared. Planner suggestions remain opt-in.
- Rendering: manual render plus watched output as the fallback until Vegas render scripting is proven.

## 6. Human-only actions

- Run the VEGAS checks in `docs/HUMAN_TESTS_M1.md` and goal-specific `docs/HUMAN_TESTS_M*.md` on disposable projects.
- Provide and label approved short clips; review and listen to edited joins.
- Install or locate a local FFmpeg build before using the `run-job` default reference renderer (RV-004).
- Complete `STYLE_INTERVIEW.md`, choose the project license, and provide an approved SFX library.
- Provide G4's rough transition list and run M7 catalog, transition, effect, SFX placement, and level checks on disposable media (RV-009, RV-010).
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

### RV-005 — Goal 05 Hugging Face gate and voice enrollment samples

- **Feature or claim:** Real diarization and voice-embedding inference from an accepted gated checkpoint; measured similarity threshold; multi-speaker enrollment rejection; matching against the user's speakers.
- **Why untested:** This task has no verified HF read token, record of accepted model terms, or approved voice samples. No model card was fetched and no model weights were downloaded.
- **Assumption and locations:** Implement deterministic speaker logic behind model/encoder interfaces and use synthetic vectors/audio fixtures. Keep real inference disabled until the human provides approved local model files and samples. Any fixture-only similarity threshold is provisional, not validated for people.
- **Exact test:** After the human records G2 in their gate checklist, read the current model card terms for each selected checkpoint, verify the accepted model IDs, set the token only in a gitignored config or the documented environment variable, run `python tasks.py enroll --name <speaker> --audio <approved.wav>` on a local sample, then benchmark diarization and matching without uploading audio. Never store the token in artifacts or outputs.
- **Expected result and record:** Accepted model IDs and terms are recorded without the token; enrollment stores only embedding metadata and vectors under ignored `voices/`; sample duration, quality checks, matching threshold, CPU/device, runtime, and peak memory are recorded in `docs/EVALS.md`. Do not record raw audio or private paths.
- **Who:** Human supplies and accepts the gated model terms and samples; agent can run the documented local benchmark after those inputs exist.
- **Severity:** blocker for real-world diarization, enrollment, and attribution accuracy claims; offline deterministic orchestration remains available.
- **Related VQ IDs:** none.
- **Status:** open.

### RV-006 — Goal 05 real-speech attribution quality and hardware benchmark

- **Feature or claim:** Speaker attribution accuracy, overlap detection accuracy, unknown detection rate, enrollment quality rejection, wall time per minute, and peak memory on the 4 GB laptop.
- **Why untested:** No approved labeled multitrack or mixed real-speech clip and no accepted diarization/embedding model are available in this task. Synthetic data only proves deterministic logic and fixture handling.
- **Assumption and locations:** Keep reports explicit about synthetic-only evidence; use no default threshold as calibrated until reviewed against the user's enrollment samples. See `docs/SPEAKERS.md` and `docs/EVALS.md`.
- **Exact test:** Once RV-005 is complete, run one labeled multitrack recording with a bleed region and one labeled mixed recording with two enrolled speakers and an overlap span. Record per-mode attribution precision/recall, overlap accuracy, unknown detection rate, time per media minute, and peak memory; have a human inspect all low-confidence ranges.
- **Expected result and record:** Metrics and device/model details are recorded in `docs/EVALS.md`, with sample identities and paths omitted from tracked files. Threshold changes require a decision entry and new regression fixtures.
- **Who:** Human supplies and reviews the clips; agent calculates metrics from approved redacted results.
- **Severity:** high for real speaker-attribution quality claims; no impact to synthetic unit checks.
- **Related VQ IDs:** none.
- **Status:** open.

### RV-007 — Goal 06 caption style and Vegas text probes

- **Feature or claim:** The selected subtitle style and any Vegas text-event or preset renderer, including two-speaker color correctness and 300-caption performance.
- **Why untested:** `STYLE_INTERVIEW.md`, T1, and HUMAN_GATES.md are absent. VQ-09 has compile-time-only evidence; VQ-10 remains UNVERIFIED. The subtitle path in `docs/VEGAS_DECISIONS.md` is provisional ASS burn-in plus sidecars, not Vegas text events.
- **Assumption and locations:** Implement only deterministic offline caption generation and sidecars from the existing architecture defaults. Keep direct-color, preset, and executor text operations disabled until human probe evidence is recorded. See `docs/VEGAS_NOTES.md`, `docs/VEGAS_DECISIONS.md`, and `docs/HUMAN_TESTS_M6.md`.
- **Exact test:** A human completes the M6 checklist on a disposable synthetic VEGAS project, runs the VQ-09 and VQ-10 steps, decides caption style, compares two speaker colors and special text, and times 300 events. Record E0 observations in VEGAS_NOTES.md and style choices in the restored interview artifact.
- **Expected result and record:** A chosen style is explicit; any enabled Vegas mechanism passes text, per-speaker color, special-character, and 300-event checks. Until then, Vegas caption operations remain unimplemented or disabled and no Vegas claim is made.
- **Who:** Human with VEGAS Pro 17; agent can review redacted results afterward.
- **Severity:** blocker for Vegas caption rendering; no blocker for offline captions or sidecars.
- **Related VQ IDs:** VQ-09 PARTIAL (compile-time only), VQ-10 UNVERIFIED.
- **Status:** open.

### RV-008 — Goal 06 ASS burn-in runtime availability

- **Feature or claim:** End-to-end FFmpeg ASS burn-in after a final render, as selected provisionally in the subtitle decision memo.
- **Why untested:** FFmpeg/ffprobe are absent on this machine (RV-004), and Goal 06 permits no downloads. SRT/ASS generation can be verified offline, but the render integration cannot.
- **Assumption and locations:** Keep the ASS renderer behind an adapter with explicit binary discovery and typed missing-tool errors; never change the default render pipeline or install binaries. See `docs/SUBTITLES.md` and `docs/VEGAS_DECISIONS.md`.
- **Exact test:** After an approved local FFmpeg build is available, generate a synthetic 2-second video and ASS file, burn it with the configured renderer, parse the output with ffprobe, and sample caption frames for expected text/color. Record command versions and results without user media.
- **Expected result and record:** A generated output video contains the two styled caption events at the expected frames; no user media is used. Record runtime and frame inspection in docs/EVALS.md.
- **Who:** Agent when local FFmpeg is available; no download during this run.
- **Severity:** blocker for end-to-end burn-in; sidecar export remains available.
- **Related VQ IDs:** none; dependency RV-004.
- **Status:** open.

### RV-009 — Goal 07 Vegas catalog and transition/effect operations

- **Feature or claim:** Runtime catalog enumeration (including nested plugin folders/presets), transition application/duration, audio joins, and parameterizable Vegas effects; corresponding executor operations.
- **Why untested:** G4's rough transition allowlist is absent. VQ-04 has compile-time-only evidence; VQ-05, VQ-06, and VQ-17 are UNVERIFIED. The repository has no runtime executor, and AGENTS.md prohibits building on unprobed Vegas APIs.
- **Assumption and locations:** Continue with fixture/dumper-driven catalog construction and deterministic validation. Keep the default transition allowlist empty, all newly dumped entries disabled unless explicitly enabled in the human tag file, and executor mutation capabilities empty. Do not implement or advertise Vegas mutation support before probes. See `orchestrator/catalog.py`, `orchestrator/compiler.py`, `docs/VEGAS_NOTES.md`, and `docs/VEGAS_DECISIONS.md` as they are completed.
- **Exact test:** A human follows `docs/HUMAN_TESTS_M7.md` on a disposable VEGAS Pro 17 project and synthetic two-event media. Run the catalog probe; record recursion, counts, duplicate names, stable IDs, and plugin hash. Apply a dissolve and one stylized transition, control duration, inspect audio/video sync, measure short audio fades, and test one OFX parameter of each supported type. Record E0 results and update VQ-04/05/06/17 before enabling any executor capability.
- **Expected result and record:** Catalog contents and keys are repeatable after a rescan; each enabled operation is applied with measured duration and no A/V desync; unsupported FX parameters remain disabled. Record build, plugin-list hash, counts, per-operation outcomes, rendered-frame/listening checks, and E0 evidence IDs without private project paths.
- **Who:** Human with VEGAS Pro 17; agent can update the catalog/executor after redacted E0 evidence exists.
- **Severity:** blocker for Vegas catalog claims and all real transition/effect mutations; offline catalog and compiler tests continue.
- **Related VQ IDs:** VQ-04 PARTIAL (compile-time only), VQ-05 UNVERIFIED, VQ-06 UNVERIFIED, VQ-17 UNVERIFIED.
- **Status:** open.

### RV-010 — Goal 07 licensed SFX library and loudness/runtime evidence

- **Feature or claim:** Indexing approved SFX, measuring integrated loudness/peak with FFmpeg, license-aware final manifests, and precise Vegas SFX insertion/gain.
- **Why untested:** No starter SFX library or license sidecars are present (`assets/sfx` does not exist); local FFmpeg/ffprobe are unavailable. VQ-18 is UNVERIFIED. No file will be downloaded or inferred to be licensed.
- **Assumption and locations:** Implement the indexer against temporary synthetic WAV fixtures and an injectable measurement adapter; files without explicit license metadata remain disabled and are excluded from planner summaries. Do not index or modify an unknown user directory. See `orchestrator/sfx.py`, `docs/SFX.md`, and `docs/VEGAS_NOTES.md` as they are completed.
- **Exact test:** After a human supplies a local folder of approved licensed samples and local FFmpeg/ffprobe are available, run `python tasks.py sfx-index <approved_sfx_dir>`. Confirm a licensed synthetic tone's duration, sample rate, integrated loudness/true peak, fingerprint, key stability, and manifest entry; confirm a file without license metadata is disabled with a warning. Then follow `docs/HUMAN_TESTS_M7.md` to place an SFX on a word anchor in a disposable Vegas project and measure placement/gain.
- **Expected result and record:** No network access or source-file modification; keys are stable, unlicensed items are disabled, loudness agrees with a known-level tone within the documented tolerance, and a human confirms frame placement and gain behavior. Store private indexes only under ignored `runs/`; record aggregate results and license identifiers, not private paths.
- **Who:** Human supplies the approved library/licenses and runs Vegas checks; agent may run the local indexer when those tools/assets exist.
- **Severity:** high for SFX selection and real placement; no blocker for synthetic index/compiler tests.
- **Related VQ IDs:** VQ-18 UNVERIFIED; depends on VQ-06 for audio joins where applicable.
- **Status:** open.


### RV-011 — Missing runtime EDL prompt for the Goal 07 contract additions

- **Feature or claim:** Planner-authored effect selections and transitions anchored to long gaps.
- **Why untested:** This checkout contains only skills/README.md, which says the runtime EDL prompt arrives in a later milestone. Goal 07 marks runtime prompt writing out of scope, while AGENTS.md Section 8 requires updating skills/EDL_PROMPT.md whenever EDL changes.
- **Assumption and locations:** Keep EDL effects optional, preserve the ID/key-only shape, and keep baseline catalog suggestions disabled by default. No runtime prompt file was created or edited. See schemas/edl.schema.json, docs/contracts/edl.md, and skills/README.md.
- **Exact test:** Restore the exact prompt source from the prompt pack or later milestone; add a bounded effects field and cut/gap transition references without parameter values, then run eval before and after as required by AGENTS.md.
- **Expected result and record:** The prompt emits only event IDs and enabled effect keys, never plugin IDs or parameter values; all examples validate against EDL 2.0.0. Record prompt version and eval metrics.
- **Who:** Agent after the runtime prompt source is present; no Vegas behavior is required for this prompt update.
- **Severity:** blocker for planner-authored effects and baseline catalog suggestions; offline compiler policy remains testable.
- **Related VQ IDs:** none; this is a missing artifact and prompt-contract synchronization gate.
- **Status:** open.
