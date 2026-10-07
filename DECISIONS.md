# Decisions

Numbered decisions capture settled design choices. The architecture remains the source of truth for system behavior; this log records rationale and Milestone 0 and Milestone 1 clarifications.

## Decisions

### D-01 — Model selects intent by ID; code selects numbers
Date: 2026-10-06

Decision: Planner output names words, segments, gaps, events, cuts, speakers, and catalog keys. Deterministic code resolves time, frame, color, plugin ID, and path values.

Rationale: Prevents model-authored timing and keeps execution constrained.

Alternatives: Let the model emit seconds or plugin settings; rejected because they are less precise and weaken the closed contract boundary.

Status: Accepted.

### D-02 — One complete plan per pass
Date: 2026-10-06

Decision: The planner emits one whole EDL per video, with bounded typed tool requests and questions.

Rationale: Keeps one structured artifact for validation and review and follows the existing architecture.

Alternatives: Emit one action per model turn; deferred.

Status: Accepted.

### D-03 — Laptop-only perception is the default topology
Date: 2026-10-06

Decision: Perception is designed to run on the editing laptop; optional CPU offload remains explicit configuration.

Rationale: The user supplies only an inference endpoint and key; video and project files stay local.

Alternatives: Require server-side workers; rejected for the default path.

Status: Accepted; hardware fit remains unbenchmarked.

### D-04 — JSON Schema is authoritative
Date: 2026-10-06

Decision: Draft 2020-12 schema files define contract shape. Python checks use those schemas plus separately named semantic/reference checks.

Rationale: Shared machine-readable contracts prevent prose, prompts, and consumers drifting.

Alternatives: Parallel hand-maintained Python models; rejected.

Status: Accepted.

### D-05 — Cross-platform tasks are implemented in Python
Date: 2026-10-06

Decision: `tasks.py` is the command interface; Makefile targets only forward to it.

Rationale: Windows is the primary development environment and should not require GNU Make.

Alternatives: Make-only tasks; rejected.

Status: Accepted.

### D-06 — Dry run remains the operating default
Date: 2026-10-06

Decision: The example config continues to use `dry-run`. M1 implements `dry-run` and offline `eval`; `--planner llm` remains disabled in the CLI until a later milestone.

Rationale: No task may imply that a pipeline stage exists before it is implemented.

Alternatives: Change the default to unattended execution or send a live planner request during M1; rejected.

Status: Accepted; M1 implementation follow-up recorded in this decision.

### D-07 — Broker and closed catalog contain the blast radius
Date: 2026-10-06

Decision: Only the orchestrator may hold the endpoint/key. Only catalog keys reach planner output; only validated ops reach the Vegas executor.

Rationale: Applies the architecture trust boundaries in code and schemas.

Alternatives: Put credentials in Vegas or expose plugin details to the planner; rejected.

Status: Accepted.

### D-08 — Contract reconciliation and canonical Vegas-notes path
Date: 2026-10-06

Decision: Milestone 0's explicit requirements add `gaps` to words, require `kind`/`params_mode` on catalog entries, and use the operation union from VEGAS_NOTES `8. Architecture was bumped to 1.1.0 to document those shapes. The existing root-level Vegas notes were moved to `docs/VEGAS_NOTES.md` and bumped to 1.0.1 without changing probe content or Vegas claims.

Rationale: The starter checkout's paths and contract descriptions did not support required gap refs, internal/model catalog separation, and the documented executor operation list.

Alternatives: Omit those required data and operation forms; rejected because referential checks and schemas could not meet the objective.

Status: Accepted.

### D-09 — Development dependencies are pinned
Date: 2026-10-06

Decision: Pin `jsonschema==4.23.0` (Draft 2020-12 validation, MIT), `pytest==8.4.2` (unit test runner, MIT), `ruff==0.12.12` (lint/format, MIT), and `mypy==1.18.2` (strict type checks, MIT).

Rationale: These small, established development tools support deterministic checks; direct versions are explicit in `requirements-dev.txt`; the complete resolved dependency set is pinned in `requirements-lock.txt`.

Alternatives: Hand-roll JSON Schema validation or leave tools unpinned; rejected.

Status: Accepted.

### D-10 — Keep task checks isolated and repeatable
Date: 2026-10-06

Decision: Schema checks re-execute under the project virtual environment, and the test task uses a temporary directory under the project root that is removed after the run.

Rationale: The task runner must use the pinned dependencies consistently and leave no test config or scratch data behind.

Alternatives: Use the caller's global packages or retain pytest temp files in the project; rejected.

Status: Accepted.

### D-11 — Python 3.12 is the Windows development target
Date: 2026-10-06

Decision: Update the project target from Python 3.11 to Python 3.12.10 on Windows. Use CPU inference when CUDA is unavailable.

Rationale: Python 3.12.10 is the installed 64-bit runtime. The current WhisperX package metadata supports Python 3.10 through 3.13, and PyTorch's Windows guidance supports Python 3.9 through 3.12. The available global PyTorch is CPU-only (`2.13.0+cpu`), so CUDA inference is not available in this environment; M1's CPU fallback remains the supported path.

Alternatives: Keep 3.11 as the target and install another Python runtime; rejected because it adds an environment requirement without improving compatibility for this milestone.

Status: Accepted. ASR was unmeasured at the initial W_VFR stop; D-30 corrected that preflight result and D-32 records the completed smoke benchmark.

### D-12 — Do not fetch ffmpeg binaries
Date: 2026-10-06

Decision: Do not fetch FFmpeg binaries. Use an existing user-installed FFmpeg only through a process-local PATH override when needed. After the configured clip's read-only preflight reports W_VFR, stop before extraction or rendering and await user direction.

Rationale: Milestone 1 explicitly excludes FFmpeg downloads. A local WinGet FFmpeg 9.0.1 package is present outside PATH; using it for read-only preflight required no download or persistent environment change. The positive VFR sample triggers the Prompt 01b stop rule because frame-based output may not be trustworthy without an approved conformity path.

Alternatives: Download a binary or substitute another media executable; rejected because the prompt permits no ffmpeg download and requires ffprobe-based inspection.

Status: The initial stop was honored. D-30 supersedes the false-positive VFR finding, and D-32 records the later approved run; no FFmpeg binary was fetched.

### D-13 — EDL silence edits use gap IDs and compile configuration
Date: 2026-10-06

Decision: Add optional `gap_actions` to EDL 1.1.0. Each action names a known gap ID and uses `remove` or `shorten`; the planner never supplies a retained length.

Rationale: This preserves compatibility with existing EDLs while giving the deterministic baseline planner a safe silence action. The compiler owns all numeric timing and configured retained-length decisions.

Alternatives: Put a duration in EDL; rejected because it lets planner output select resolved time values.

Status: Accepted.

### D-14 — M1 timeline is a linked synthetic A/V group
Date: 2026-10-06

Decision: Synthesize one zero-based timeline from the source media, with one video event, one event per selected audio stream, and a single linked A/V group. Store rational fps, integer frames, source offsets, and the source hash.

Rationale: This permits deterministic compiler and dry-run work without launching Vegas. The later Vegas dumper must emit compatible event/group semantics.

Alternatives: Require a Vegas project before planning; deferred to the Vegas executor milestone because M1 must work offline without Vegas running.

Status: Accepted.

### D-15 — Run metrics are checked from integer frame totals
Date: 2026-10-06

Decision: Treat integer frame totals as authoritative for removed-percent reporting. Estimate pack tokens as `ceil(characters / 4)` and record the estimate method in the manifest.

Rationale: Both metrics remain deterministic and do not require a tokenizer or floating-point time arithmetic.

Alternatives: Download a tokenizer or store only a floating-point percentage; rejected to keep M1 offline and auditable.

Status: Accepted.

### D-16 — Unaligned ASR tokens keep text but have no time anchors
Date: 2026-10-06

Decision: Bump the words contract to 2.0.0. Every token explicitly records `aligned` or `unaligned`; unaligned tokens retain recognized text and use null start/end values. EDL references and compiler cut ranges may use only aligned tokens.

Rationale: WhisperX alignment can fail for a segment or token. Inventing a timestamp would make later frame cuts unsafe, while discarding text would hide ASR output from review.

Alternatives: Drop unaligned words or infer their times from neighboring tokens; rejected because either loses information or fabricates timing.

Status: Accepted.

### D-17 — Refine transcript silence gaps from local PCM energy
Date: 2026-10-06

Decision: Refine candidate gaps using configurable PCM RMS windows and a robust noise-floor threshold. Record the ASR bounds, energy-refined bounds, threshold, and method in `words.json`; the compiler snaps gap removals inward and clamps to adjacent aligned word spans.

Rationale: ASR segment boundaries alone may not follow the audible silence precisely. Keeping both boundaries makes the refinement auditable and the compiler deterministic.

Alternatives: Let the planner choose times or silently replace ASR boundaries; rejected because the model must not select numeric timing and the adjustment must remain inspectable.

Status: Accepted; real-media thresholds remain unbenchmarked.

### D-18 — M1 planner network tests stay loopback-only
Date: 2026-10-06

Decision: Keep the `LlmPlanner` adapter restricted to loopback hosts and use fake local HTTP servers in tests. The M1 dry-run CLI refuses `--planner llm`; real endpoint calls are deferred.

Rationale: This validates request/response handling without sending transcripts, keys, or project data to a server during M1.

Alternatives: Test against the configured remote endpoint or enable live planning by default; rejected because that would send user content and expand M1's network boundary.

Status: Accepted.

### D-19 — Baseline evaluation stays synthetic and dependency-light
Date: 2026-10-06

Decision: Use a generated tone/silence case and fixture-backed word boundaries for the M1 eval. Report all metrics and runtime, and label the result as a plumbing check rather than real-clip accuracy.

Rationale: The smoke clip currently triggers the VFR stop rule, so the eval must remain independently runnable without real media, GPU, or model dependencies.

Alternatives: Download binaries, model weights, or an external tokenizer; rejected because those downloads are not needed for the offline acceptance path and real media setup is user-managed.

Status: Accepted.

### D-20 — Baseline pause edits retain a configured short gap
Date: 2026-10-06

Decision: The baseline planner emits `shorten` for measured pauses at least 650 ms long. The compiler keeps `compile.min_gap_after_cut_ms` of silence; it does not delete the whole pause by default.

Rationale: Removing an entire gap can leave consecutive speech words touching. Retaining a deterministic short pause is easier to review and keeps edit intent ID-only.

Alternatives: Remove every detected pause or let the planner choose a retained duration; rejected because either can create abrupt pacing or move timing decisions into the model.

Status: Accepted.

### D-21 — Measure pacing only at newly created cut joins
Date: 2026-10-06

Decision: The M1 verifier checks the mapped inter-word gap across each removed range against configured minimum and maximum thresholds, reports clipped-word boundary checks, and records a targeted suggestion for each failure.

Rationale: Pacing checks should describe joins created by this edit. Natural pauses elsewhere remain source characteristics and should not trigger a cut-specific warning.

Alternatives: Check every pair of transcript words or rely only on compile-time guards; rejected because the former flags untouched speech and the latter does not report configured join pacing.

Status: Accepted.

### D-23 — Compile outcomes are explicit and traced into final operations
Date: 2026-10-06

Decision: The compile report requires one `item_outcomes` row per EDL cut and gap action, with `applied`, `adjusted`, or `rejected` status. `adjusted` rows carry a reason and aggregate absolute boundary delta in integer frames; `rejected` rows carry an error code and reason. Each final `delete_range` operation optionally lists the EDL item IDs represented by its merged interval. The compile report is bumped to 2.0.0 because the field is required; ops is 1.1.0 for the optional trace IDs.

Rationale: Planner selection metrics alone counted a pacing-rejected filler cut as retrieved. Applied metrics must derive from emitted delete operations and preserve the planner-selection metrics separately.

Alternatives: Infer application from marker labels or leave rejection data outside the compile report; rejected because markers are review artifacts and do not identify the final deletion operation reliably.

Status: Accepted; validated by synthetic tests.

### D-24 — Keep verifier thresholds until real joins are measured
Date: 2026-10-06

Decision: Retain the existing 0.12 full-scale sample discontinuity and 8 dB level-step defaults. Add a generated speech-shaped noise fixture with smooth envelopes and room noise, and keep the fixed-tone fixture's expected level-step failures explicit. Do not calibrate from synthetic distributions.

Rationale: At the time this decision was written, the bounded preflight had reported W_VFR and the run had stopped. D-30 corrected that false positive, and the later smoke produced zero joins because it had no word-level anchors. The synthetic speech-shaped and tone fixtures still do not provide real-join distributions.

Alternatives: Raise the level-step threshold until synthetic tones pass; rejected because that would conceal real joins that may need review.

Status: Accepted; real-join calibration pending.

### D-25 — Keep ASR installation opt-in and isolated
Date: 2026-10-06

Decision: Keep plain setup dev-only. Add `requirements-asr.txt` with pinned WhisperX 3.8.6, faster-whisper 1.2.1, NumPy 2.5.3, and SoundFile 0.14.0. The optional setup installs the compatible PyTorch 2.8.0, torchaudio 2.8.0, and torchvision 0.23.0 stack from official PyTorch CUDA 12.8 wheels when a local NVIDIA device is detected, verifies CUDA inside the project venv, and falls back to official CPU wheels if needed. Model weights remain lazy and separate from package setup.

Rationale: WhisperX 3.8.6 metadata requires `torch~=2.8.0` and `torchaudio~=2.8.0`; keeping ASR packages optional preserves the offline developer setup. No model or token-gated assets are fetched during package installation.

Alternatives: Add ASR packages to the dev lock or use unpinned system/global packages; rejected because offline checks should not need ML dependencies and Vegas must not inherit those dependencies or credentials.

Status: Accepted; `python tasks.py setup --asr` exited 0. CUDA 12.8 was available in the venv on the 4095 MiB RTX 3050 Ti. WhisperX imported successfully. The complete 101-distribution version/license/purpose/installed-size inventory and retained direct wheel sizes are recorded below. Package setup itself fetched no model weights; the later approved smoke fetched only the two checkpoints recorded in D-32.

### D-26 — Bound the loopback planner boundary
Date: 2026-10-06

Decision: Keep LlmPlanner restricted to loopback hosts, disable proxy use and HTTP redirects, and cap request timeouts, retries, backoff, response size, and correction feedback. Treat 401/403 as non-retryable authentication failures; report unreachable endpoints and repeatedly malformed output with typed errors. Forward only validated error codes and bounded schema paths in correction requests, with at most eight entries. Keep live LLM planning disabled in the M1 CLI.

Rationale: A redirect could forward the Authorization header away from the loopback service. Full diagnostics can contain untrusted values or sensitive text, and unbounded retries can stall local runs. The fake-server suite can exercise these cases without contacting an inference endpoint.

Alternatives: Follow redirects, send full exception or compiler messages back to the model, or retry indefinitely; rejected because they expand the credential/data boundary and weaken bounded execution.

Status: Accepted; covered by loopback fake-server tests. No real LLM endpoint was contacted.
### D-27 — Stop processing after a positive VFR preflight
Date: 2026-10-06

Decision: For this smoke candidate, honor Prompt 01b's stop rule after W_VFR. The read-only sample covered the first 96 frames; average and real frame rates both reported 2997/100, while 1 of 95 intervals exceeded the 1 ms tolerance. Do not extract audio, download model weights, transcode the source, or claim downstream outputs are trustworthy until the user selects a compliant clip or approves a separate working-copy conformity path.

Rationale: A bounded sample is enough to raise the configured warning but does not characterize the full clip. Proceeding with frame-based edits without resolving the warning could produce untrustworthy boundaries.

Alternatives: Ignore the warning because the reported average and real rates match, or transcode the source in place; rejected by the prompt's VFR stop rule and source-read-only requirement.

Status: Superseded by D-30. The user permitted a CFR copy under ignored `runs/`; the corrected scan established the original source is already CFR, so the full smoke proceeded from the read-only source.
### D-28 — Treat Vegas metadata as candidates, not runtime proof
Date: 2026-10-06

Decision: Use the EC metadata findings to correct executor design notes while leaving runtime behavior UNVERIFIED. Keep event gain unresolved because `AudioEvent.Volume` is absent and `NormalizeGain` semantics are unknown. Prefer the explicitly named `Effects.AddEffect(PlugInNode)` call as the initial FX implementation candidate over inherited collection `Add`, subject to a Vegas probe. Record the `ICustomCommandModule` and related extension names as evidence that a route may exist, without assuming host discovery. Use `Vegas.SaveProject(...)` as the metadata-present checkpoint candidate.

Rationale: Reflection-only metadata establishes names and signatures, not behavior. Correct target and candidate method names reduce avoidable implementation errors while preserving the probe gate.

Alternatives: Treat metadata membership as proof of working behavior, choose event normalization as the gain mechanism, or assume extension discovery from the type names; rejected because no Vegas runtime operation was performed.

Status: Accepted as a design note only; no executor behavior was verified or implemented.

### D-29 — Record the VFR stop after local FFmpeg discovery
Date: 2026-10-06

Decision: Correct the Architecture status to reflect that FFmpeg 9.0.1 is installed outside the normal PATH and that a process-local PATH override enabled read-only preflight. The current real-media gate is W_VFR, which stopped processing before extraction and ASR.

Rationale: The earlier `E_MEDIA_TOOL` manifest records the initial PATH failure; the later preflight supersedes it as the current media status. Keeping both facts distinguishes the historical CLI failure from the active stop condition.

Alternatives: Continue describing the tool as absent, or proceed as though matching average/real rates clear W_VFR; rejected because the tool is installed and the bounded timestamp sample triggered Prompt 01b's stop rule.

Status at the time: no media extraction or model-weight download followed the initial VFR finding. D-30 later superseded the false positive; D-32 records the subsequent offline run. No Vegas launch or endpoint request occurred.

### D-30 — Look ahead past the ffprobe packet boundary for bounded VFR sampling
Date: 2026-10-06

Decision: For a bounded timestamp sample, request 16 packets beyond the requested sample count, then classify only the requested timestamps. Preserve the original source as read-only. If the source itself is variable-rate, use a user-approved working copy under ignored `runs/` rather than converting the source.

Rationale: The initial bounded ffprobe result contained one interval outside tolerance at its packet-count tail even though average and real rates both reported `2997/100`. A full decoded scan covered 2,354 frames and 2,353 intervals without a cadence deviation over 1 ms. The decoder can stop before all reordered frames are flushed; the lookahead removes that tail artifact while keeping the classified window bounded.

Alternatives: Ignore every `W_VFR` finding, or transcode the original source; rejected because real cadence changes still need detection and source media must remain read-only.

Status: Accepted. Regression tests distinguish a tail-only anomaly from a cadence change inside the sample. The user allowed a CFR working copy under ignored `runs/`; the corrected check proved it unnecessary for this source, and the smoke used the original read-only file.

### D-31 — Disable VAD and diarization weights in the ASR adapter
Date: 2026-10-06

Decision: Run faster-whisper `small` directly with `vad_filter=False`, pass normalized in-memory audio to avoid the installed PyAV path-decoder incompatibility, then use WhisperX only for forced alignment. Do not load diarization or VAD checkpoints in this milestone.

Rationale: The default WhisperX transcription path can invoke a VAD model that is outside the explicitly approved weight list and may need access beyond the allowed model fetch. Disabling VAD keeps the actual weight set to the approved ASR and detected-language alignment models. Normalized audio also avoids a local `TypeError` from the file decoder's unsupported `metadata_errors` argument.

Alternatives: Use WhisperX's default VAD path or skip Japanese alignment; rejected because the former could fetch an unapproved checkpoint and the latter would discard the permitted alignment stage.

Status: Accepted; unit tests assert VAD is disabled, normalized audio is passed, and alignment failure leaves words unaligned instead of inventing times.

### D-32 — Record ASR checkpoints and smoke measurements
Date: 2026-10-06

Decision: Use the approved `Systran/faster-whisper-small` ASR checkpoint at revision `536b0662742c02347bc0e980a01041f333bce120` (486,212,372 bytes in the cached snapshot; `model.bin` is 483,546,902 bytes) and the detected-language checkpoint `jonatasgrosman/wav2vec2-large-xlsr-53-japanese` at revision `cf031e020336460d15a417eba710bbc5bb43be9a` (1,271,563,035 snapshot bytes; `pytorch_model.bin` is 1,271,531,927 bytes). No license file appeared in either cached snapshot, and no token, account, or license click-through was requested. Do not redistribute these model files until their licenses are verified.

Rationale: The completed offline smoke measured CUDA `int8_float16`, 1.27 GB peak VRAM, and 37.367 seconds of ASR time for 78.545 seconds of media, for a real-time factor of 0.4757 (`ASR wall time / media duration`). Language detection returned Japanese at 0.9399 confidence. All 30 tokens were unaligned, so the baseline planner emitted zero cuts and zero gap actions. The benchmark is a pipeline measurement, not an editing-quality result.

Alternatives: Report the inverse ratio as real-time factor, infer word times for the unaligned tokens, or describe a zero-cut run as successful editing; rejected because the metric convention must be comparable, times must not be invented, and no cut was applied.

Status: Accepted. The run stayed offline from the inference endpoint, left the source hash unchanged, and fetched no VAD or diarization weights. The local snapshot metadata does not establish the model licenses; manual license review remains open.

### D-33 — Keep verifier thresholds pending human-reviewed joins
Date: 2026-10-06

Decision: Keep `max_click_delta=0.12` and `max_level_step_db=8.0` unchanged. Report real-join metrics when available, but do not recalibrate thresholds from a single unreviewed clip.

Rationale: The corrected run in D-36 has 16 joins from one unlabelled recording. Click values range from 0 to 0.033783 and all pass the 0.12 limit; level steps range from 1.215 to 42.8528 dB, with 12/16 above the 8.0 dB limit. Sixteen correlated joins from one clip are too small and unrepresentative to calibrate thresholds. The speech-like synthetic fixture is not a real-speech calibration sample; keep defaults until a larger, human-reviewed set exists.

Alternatives: Raise thresholds until the tone fixture passes or claim calibration from a zero-join sample; rejected because either would overstate verifier evidence.

Status: Accepted; defaults remain in force pending human review and a representative real-join set.


### D-34 — Keep Japanese subword times out of the word-level contract
Date: 2026-10-06

Decision: Preserve the 30 Japanese ASR phrase segments as unaligned when the aligner returns a finer set of subword rows. Do not assign those rows to the word-level transcript contract or cut between them without a Japanese lexical segmenter.

Rationale: A diagnostic run returned 298 timed subword rows for 30 ASR segments, with normalized concatenated text matching each segment. That proves alignment produced timing at a different granularity; it does not establish lexical word boundaries. The current prompt's approved dependencies do not include a Japanese tokenizer, and guessed boundaries would violate the no-cut-inside-a-word invariant.

Alternatives: Mark the whole phrase with a broad time span, treat each subword as a word, or add a tokenizer dependency; rejected because each could create unsafe edit boundaries or require an unapproved dependency.

Status: Accepted for this milestone. A language-aware segmentation stage needs a separately approved dependency and word-boundary evaluation before Japanese cuts can be trusted.


### D-35 — Continue the real-media smoke with English and an approved CFR copy
Date: 2026-10-06

Decision: Follow the user's English-only direction and run the existing offline baseline pipeline on a 120-second window of the English clip selected from the configured video directory. Its 327.169-second source is identified by SHA-256 prefix `57ce0b0d905fa8a9`; the filename and path remain unrecorded. Its source scan found one cadence interval outside the 1 ms tolerance, so create a 30/1 fps H.264 working copy under ignored `runs/` and copy its AAC audio stream. Do not modify the original. Use the WhisperX default English aligner, `WAV2VEC2_ASR_BASE_960H`, after the user approved fetching that checkpoint.

Evidence: A full source scan covered 9,815 frames and 9,814 intervals; one interval deviated from the median by 9 ms. The CFR copy retained 9,815 frames and had no interval outside tolerance. The original source hash matched before and after the copy was created, and the dry-run manifest reports the working copy unchanged. The initial run detected English at 0.9766 confidence and timed 55 of 210 words, but the positional alignment mapping was later found to mishandle WhisperX sentence splits; D-36 supersedes that timing count. No thresholds changed, no LLM endpoint was contacted, and VEGAS was not launched.

Checkpoint: `https://download.pytorch.org/torchaudio/models/wav2vec2_fairseq_base_ls960_asr_ls960.pth`, stored only in ignored `cache/asr_models/`. Size: 377,664,473 bytes. SHA-256: `488fd4f16de84438ffc945334278c1b9fb9b7159a806c1080b16111a958c945d`. The installed torchaudio 2.8.0 pipeline documentation states that this checkpoint is distributed under the MIT License. The local checkpoint is not part of the repository.

Alternatives: Process the VFR original directly, infer times for the remaining unaligned words, raise verifier thresholds to make the run pass, or enable the remote planner; rejected because frame cadence must be normalized for this smoke, word times must not be guessed, failures must remain visible, and the M1 dry-run CLI does not use the LLM endpoint.

Status: Accepted as CFR and checkpoint provenance evidence. The first-run word and join metrics are superseded by D-36.


### D-36 — Map WhisperX sentence splits back to raw ASR words
Date: 2026-10-06

Decision: Match WhisperX aligned sentence segments to raw ASR tokens in transcript order. Preserve timing only when normalized text matches the raw token sequence; keep tokens unaligned when the mapping is uncertain.

Rationale: WhisperX can return more aligned segments than faster-whisper raw segments because it splits alignment output at sentence boundaries. The original positional pairing assumed equal list lengths and caused valid English timing rows to be discarded. A corrected run produced timing anchors for all 210 English words, while the token-sequence guard prevents mismatched output from receiving times.

Evidence: Regression tests cover one raw segment split across sentence outputs, preservation of raw segment indices, and a text mismatch falling back to unaligned words. The corrected 120-second English run (`20261007T001144Z_5475d354`) produced 210/210 timing anchors and zero unaligned tokens, eight applied silence/shorten gap actions, and 16 join measurements. Duration sanity flagged 8/210 rows under 20 ms and 2/210 above 2 seconds (maximum 5.129 seconds). Verification returned `E_VERIFY`: 12 level-step checks and four pacing checks failed; 16/16 click checks and 32/32 clipped-word checks passed. A rational-frame audit found no delete range intersecting an aligned word span. An unlabeled truth template was generated under the ignored run directory. No word-level ground truth was available, so timing accuracy and editing quality remain unmeasured. Thresholds are unchanged.

Alternatives: Keep positional pairing or accept mismatched alignment rows; rejected because sentence splits shift indices and mismatched tokens must not receive times.

Status: Accepted for English alignment. Human review of the joins and an annotated timing evaluation remain open.


## Reference: browser agent patterns

Read-only review of the local sibling browser-agent repository, commit 04c788de21cded7070744c60a98048e9b2141f49. The folder contained no LICENSE, COPYING, or NOTICE file, so the license is unknown. No code was copied.

Patterns that informed this project:

- Credentials are read in a privileged background broker and do not cross into page/content-script code. Here the orchestrator remains the sole holder, while Vegas receives only validated ops.
- Settings separate endpoint, model, and key; a bounded connection test is useful later. A connection test is deferred from Milestone 0 because it would add network code.
- The reference documents a small explicit agent state machine. This project keeps the named job states in Architecture `18.3 and the emergency-stop/stop-file boundary in the executor requirements.
- It uses a typed JSON action schema and validates responses before dispatch. This project instead validates a complete EDL and closed ops union; no strings from model output are executed.
- It sends state deltas between turns. DOM-line diffing is reference-specific; no differential EDL or transcript compression was added to Milestone 0.

## Prior art

These projects informed the design; their licenses have not been checked and no code was copied:

- [video-use](https://github.com/browser-use/video-use) — license to be checked before any adaptation.
- [Smart-Cut](https://github.com/qkirara/Smart-Cut) — license to be checked before any adaptation.
- [vegas-regions-to-srt](https://github.com/kaszarobert/vegas-regions-to-srt) — license to be checked before any adaptation.

## Dependency license notes

| Package | Purpose | Pinned version | License |
|---|---|---:|---|
| jsonschema | Draft 2020-12 contract validation | 4.23.0 | MIT |
| pytest | Unit tests | 8.4.2 | MIT |
| ruff | Lint and format | 0.12.12 | MIT |
| mypy | Strict Python typing | 1.18.2 | MIT |


### D-22 — Prefer nearby zero crossings and report both boundaries
Date: 2026-10-06

Decision: When normalized PCM is available, the compiler may move each planned cut boundary to the nearest sign change within a 20 ms window, constrained to the safe adjacent silence and integer frame grid. Record both incoming and outgoing boundary resolutions, including cases with no usable crossing. The reference pipeline enables this setting; standalone compile stages use PCM only when `--audio` is supplied.

Rationale: Frame-aligned cuts remain authoritative for the VEGAS ops contract, while a nearby zero crossing can reduce audio discontinuities without allowing a cut inside aligned speech.

Alternatives: Let the planner choose the crossing time or alter cuts without retaining the word/frame guard; rejected because timing remains compiler-owned and must stay auditable.

Status: Accepted; synthetic sign-change coverage passes. Real speech behavior is unbenchmarked until the media smoke run can execute.


### ASR package installation inventory

The ASR setup added the complete non-development dependency closure below. The size column records each installed distribution footprint from wheel `RECORD` metadata; wheel archive sizes are included for the seven direct ASR/PyTorch packages where the install record retained them. Transitive archive sizes were not preserved by pip, so their installed footprints are reported rather than presented as download sizes. License values come from installed distribution metadata; an undeclared value is identified explicitly. Purpose uses each package summary, with direct package roles clarified from the setup configuration.

| Package | Version | Size | License | Purpose |
|---|---|---:|---|---|
| aiohappyeyeballs | 2.7.1 | 0.04 MiB installed | OSI Approved :: Python Software Foundation License | Happy Eyeballs for asyncio |
| aiohttp | 3.14.4 | 1.53 MiB installed | Apache-2.0 AND MIT | Async http client/server framework (asyncio) |
| aiosignal | 1.4.0 | 0.02 MiB installed | OSI Approved :: Apache Software License | aiosignal: a list of registered asynchronous callbacks |
| alembic | 1.20.0 | 1.13 MiB installed | MIT | A database migration tool for SQLAlchemy. |
| antlr4-python3-runtime | 4.9.3 | 0.45 MiB installed | BSD | ANTLR 4.9.3 runtime for Python 3.7 |
| asteroid-filterbanks | 0.4.0 | 0.08 MiB installed | OSI Approved :: MIT License | Asteroid's filterbanks |
| av | 19.0.1 | 67.47 MiB installed | BSD-3-Clause | Pythonic bindings for FFmpeg's libraries. |
| certifi | 2026.7.22 | 0.24 MiB installed | OSI Approved :: Mozilla Public License 2.0 (MPL 2.0) | Python package for providing Mozilla's CA Bundle. |
| cffi | 2.1.1 | 0.64 MiB installed | MIT-0 | Foreign Function Interface for Python calling C code. |
| charset-normalizer | 3.5.2 | 0.65 MiB installed | MIT | The Real First Universal Charset Detector. Open, modern and actively maintained alternative to Chardet. |
| click | 8.5.0 | 0.43 MiB installed | BSD-3-Clause | Composable command line interface toolkit |
| cloudpickle | 3.1.2 | 0.07 MiB installed | OSI Approved :: BSD License | Pickler class to extend the standard pickle.Pickler functionality |
| colorlog | 6.12.0 | 0.03 MiB installed | OSI Approved :: MIT License | Add colours to the output of Python's logging module. |
| contourpy | 1.4.0 | 0.60 MiB installed | BSD-3-Clause | Python library for calculating contours of 2D quadrilateral grids |
| ctranslate2 | 4.8.2 | 60.09 MiB installed | MIT | Fast inference engine for Transformer models |
| cycler | 0.12.1 | 0.02 MiB installed | OSI Approved :: BSD License | Composable style cycles |
| defusedxml | 0.7.1 | 0.06 MiB installed | OSI Approved :: Python Software Foundation License | XML bomb protection for Python stdlib modules |
| einops | 0.8.2 | 0.22 MiB installed | OSI Approved :: MIT License | A new flavour of deep learning operations |
| faster-whisper | 1.2.1 | 1.1 MB wheel download; 1.32 MiB installed | OSI Approved :: MIT License | CTranslate2 ASR backend |
| filelock | 3.32.3 | 0.33 MiB installed | MIT | A platform independent file lock. |
| flatbuffers | 25.12.19 | 0.08 MiB installed | OSI Approved :: Apache Software License | The FlatBuffers serialization format for Python |
| fonttools | 4.66.1 | 11.72 MiB installed | MIT | Tools to manipulate font files |
| frozenlist | 1.8.0 | 0.10 MiB installed | Apache-2.0 | A list-like structure which implements collections.abc.MutableSequence |
| fsspec | 2026.7.0 | 0.71 MiB installed | BSD-3-Clause | File-system specification |
| googleapis-common-protos | 1.75.5 | 0.73 MiB installed | Apache-2.0 | Common protobufs used in Google APIs |
| grpcio | 1.84.0 | 12.13 MiB installed | Apache-2.0 | HTTP/2-based RPC framework |
| huggingface-hub | 0.36.2 | 2.45 MiB installed | OSI Approved :: Apache Software License | Client library to download and publish models, datasets and other repos on the huggingface.co hub |
| idna | 3.20 | 0.43 MiB installed | BSD-3-Clause | Internationalized Domain Names in Applications (IDNA) |
| jinja2 | 3.1.6 | 0.47 MiB installed | OSI Approved :: BSD License | A very fast and expressive template engine. |
| joblib | 1.6.0 | 0.87 MiB installed | BSD-3-Clause | Lightweight pipelining with Python functions |
| julius | 0.2.8 | 0.05 MiB installed | OSI Approved :: MIT License | Nice DSP sweets: resampling, FFT Convolutions. All with PyTorch, differentiable and with CUDA support. |
| kiwisolver | 1.5.1 | 0.16 MiB installed | OSI Approved :: BSD License | A fast implementation of the Cassowary constraint solver |
| lightning | 2.6.6 | 2.88 MiB installed | OSI Approved :: Apache Software License | The Deep Learning framework to train, deploy, and ship AI products Lightning fast. |
| lightning-utilities | 0.15.3 | 0.08 MiB installed | Apache-2.0 | Lightning toolbox for across the our ecosystem. |
| mako | 1.4.3 | 0.37 MiB installed | MIT | A super-fast templating language that borrows the best ideas from the existing templating languages. |
| markdown-it-py | 4.2.0 | 0.33 MiB installed | OSI Approved :: MIT License | Python port of markdown-it. Markdown parsing, done right! |
| markupsafe | 3.0.3 | 0.03 MiB installed | BSD-3-Clause | Safely add untrusted strings to HTML/XML markup. |
| matplotlib | 3.11.2 | 22.17 MiB installed | OSI Approved :: Python Software Foundation License | Python plotting package |
| mdurl | 0.1.2 | 0.02 MiB installed | OSI Approved :: MIT License | Markdown URL utilities |
| mpmath | 1.3.0 | 1.85 MiB installed | OSI Approved :: BSD License | Python library for arbitrary-precision floating-point arithmetic |
| multidict | 6.9.1 | 0.16 MiB installed | Apache License 2.0 | multidict implementation |
| narwhals | 2.26.0 | 1.92 MiB installed | MIT | Extremely lightweight compatibility layer between dataframe libraries |
| networkx | 3.6.1 | 6.66 MiB installed | BSD-3-Clause | Python package for creating and manipulating graphs and networks |
| nltk | 3.10.3 | 6.29 MiB installed | OSI Approved :: Apache Software License | Natural Language Toolkit |
| numpy | 2.5.3 | 12.6 MB wheel download; 40.10 MiB installed | BSD-3-Clause AND 0BSD AND MIT AND Zlib AND CC0-1.0 | Numerical arrays |
| omegaconf | 2.3.1 | 0.33 MiB installed | OSI Approved :: BSD License | A flexible configuration library |
| onnxruntime | 1.30.0 | 39.99 MiB installed | OSI Approved :: MIT License | ONNX Runtime is a runtime accelerator for Machine Learning models |
| opentelemetry-api | 1.45.1 | 0.18 MiB installed | Apache-2.0 | OpenTelemetry Python API |
| opentelemetry-exporter-http-transport | 0.66b1 | 0.03 MiB installed | Apache-2.0 | OpenTelemetry Exporters HTTP transport |
| opentelemetry-exporter-otlp | 1.45.1 | 0.01 MiB installed | Apache-2.0 | OpenTelemetry Collector Exporters |
| opentelemetry-exporter-otlp-common | 0.66b1 | 0.03 MiB installed | Apache-2.0 | OpenTelemetry OTLP HTTP export utilities |
| opentelemetry-exporter-otlp-proto-common | 1.45.1 | 0.04 MiB installed | Apache-2.0 | OpenTelemetry Protobuf encoding |
| opentelemetry-exporter-otlp-proto-grpc | 1.45.1 | 0.05 MiB installed | Apache-2.0 | OpenTelemetry Collector Protobuf over gRPC Exporter |
| opentelemetry-exporter-otlp-proto-http | 1.45.1 | 0.07 MiB installed | Apache-2.0 | OpenTelemetry Collector Protobuf over HTTP Exporter |
| opentelemetry-proto | 1.45.1 | 0.24 MiB installed | Apache-2.0 | OpenTelemetry Python Proto |
| opentelemetry-sdk | 1.45.1 | 0.49 MiB installed | Apache-2.0 | OpenTelemetry Python SDK |
| opentelemetry-semantic-conventions | 0.66b1 | 0.70 MiB installed | Apache-2.0 | OpenTelemetry Semantic Conventions |
| optuna | 5.0.0 | 1.59 MiB installed | OSI Approved :: MIT License | A hyperparameter optimization framework |
| pandas | 3.0.6 | 33.16 MiB installed | OSI Approved :: BSD License | Powerful data structures for data analysis, time series, and statistics |
| pillow | 12.3.0 | 14.07 MiB installed | MIT-CMU | Python Imaging Library (fork) |
| primepy | 1.3 | 0.01 MiB installed | OSI Approved :: MIT License | This module contains several useful functions to work with prime numbers. from primePy import primes |
| propcache | 0.5.4 | 0.11 MiB installed | Apache-2.0 | Accelerated property cache |
| protobuf | 7.36.2 | 1.63 MiB installed | 3-Clause BSD License | ASR transitive runtime dependency |
| pyannote-audio | 4.0.7 | 1.74 MiB installed | Not declared in installed metadata | State-of-the-art speaker diarization toolkit |
| pyannote-core | 6.0.1 | 0.18 MiB installed | Not declared in installed metadata | Advanced data structures for handling temporal segments with attached labels |
| pyannote-database | 6.1.1 | 0.26 MiB installed | Not declared in installed metadata | Interface to multimedia databases and experimental protocols |
| pyannote-metrics | 4.1 | 0.27 MiB installed | Not declared in installed metadata | A toolkit for reproducible evaluation, diagnostic, and error analysis of speaker diarization systems |
| pyannote-pipeline | 4.0.0 | 0.17 MiB installed | Not declared in installed metadata | Tunable pipelines |
| pyannoteai-sdk | 0.4.0 | 0.02 MiB installed | Not declared in installed metadata | Official pyannoteAI Python SDK |
| pycparser | 3.0 | 0.19 MiB installed | BSD-3-Clause | C parser in Python |
| pyparsing | 3.3.3 | 0.46 MiB installed | MIT | pyparsing - Classes and methods to define and execute parsing grammars |
| python-dateutil | 2.9.0.post0 | 0.42 MiB installed | OSI Approved :: BSD License; OSI Approved :: Apache Software License | Extensions to the standard Python datetime module |
| pytorch-lightning | 2.6.6 | 2.77 MiB installed | OSI Approved :: Apache Software License | PyTorch Lightning is the lightweight PyTorch wrapper for ML researchers. Scale your models. Write less boilerplate. |
| pytorch-metric-learning | 2.9.0 | 0.32 MiB installed | OSI Approved :: MIT License | The easiest way to use deep metric learning in your application. Modular, flexible, and extensible. Written in PyTorch. |
| pyyaml | 6.0.3 | 0.45 MiB installed | OSI Approved :: MIT License | YAML parser and emitter for Python |
| regex | 2026.9.29 | 1.15 MiB installed | Apache-2.0 AND CNRI-Python | Alternative regular expression module, to replace re. |
| requests | 2.34.2 | 0.22 MiB installed | OSI Approved :: Apache Software License | Python HTTP for Humans. |
| rich | 15.0.0 | 1.18 MiB installed | OSI Approved :: MIT License | Render rich text, tables, progress bars, syntax highlighting, markdown and more to the terminal |
| safetensors | 0.8.0 | 0.81 MiB installed | OSI Approved :: Apache Software License | ASR transitive runtime dependency |
| scikit-learn | 1.9.1 | 25.92 MiB installed | BSD-3-Clause | A set of python modules for machine learning and data mining |
| scipy | 1.18.1 | 102.85 MiB installed | OSI Approved :: BSD License | Fundamental algorithms for scientific computing in Python |
| six | 1.17.0 | 0.04 MiB installed | OSI Approved :: MIT License | Python 2 and 3 compatibility utilities |
| sortedcontainers | 2.4.0 | 0.13 MiB installed | OSI Approved :: Apache Software License | Sorted Containers -- Sorted List, Sorted Dict, Sorted Set |
| soundfile | 0.14.0 | 1.0 MB wheel download; 2.37 MiB installed | OSI Approved :: BSD License | PCM audio I/O |
| sqlalchemy | 2.1.3 | 9.20 MiB installed | MIT | Database Abstraction Library |
| sympy | 1.14.0 | 25.56 MiB installed | OSI Approved :: BSD License | Computer algebra system (CAS) in Python |
| threadpoolctl | 3.7.0 | 0.09 MiB installed | BSD-3-Clause | threadpoolctl |
| tokenizers | 0.22.2 | 7.29 MiB installed | OSI Approved :: Apache Software License | ASR transitive runtime dependency |
| torch | 2.8.0+cu128 | 3461.4 MB wheel download; 7044.37 MiB installed | OSI Approved :: BSD License | CUDA tensor runtime and inference |
| torch-audiomentations | 0.12.0 | 0.14 MiB installed | OSI Approved :: MIT License | A Pytorch library for audio data augmentation. Inspired by audiomentations. Useful for deep learning. |
| torch-pitch-shift | 1.2.5 | 0.01 MiB installed | OSI Approved :: MIT License | ASR transitive runtime dependency |
| torchaudio | 2.8.0+cu128 | 4.7 MB wheel download; 22.70 MiB installed | OSI Approved :: BSD License | PyTorch audio support |
| torchcodec | 0.7.0 | 4.49 MiB installed | Not declared in installed metadata | A video decoder for PyTorch |
| torchmetrics | 1.9.0 | 3.38 MiB installed | OSI Approved :: Apache Software License | PyTorch native Metrics |
| torchvision | 0.23.0+cu128 | 7.5 MB wheel download; 18.95 MiB installed | BSD | PyTorch vision support required by ASR dependency resolution |
| tqdm | 4.70.1 | 0.32 MiB installed | MPL-2.0 AND MIT | Fast, Extensible Progress Meter |
| transformers | 4.57.6 | 49.97 MiB installed | OSI Approved :: Apache Software License | State-of-the-art Machine Learning for JAX, PyTorch and TensorFlow |
| tzdata | 2026.5 | 0.50 MiB installed | Apache-2.0 | Provider of IANA time zone data |
| urllib3 | 2.8.0 | 0.43 MiB installed | MIT | HTTP library with thread-safe connection pooling, file post, and more. |
| whisperx | 3.8.6 | 16.5 MB wheel download; 17.14 MiB installed | BSD-2-Clause | Word-timestamped ASR/alignment adapter |
| yarl | 1.25.1 | 0.31 MiB installed | Apache-2.0 | Yet another URL library |

Inventory contains 101 ASR/PyTorch-closure distributions in the project venv. Package installation alone fetched no model weights. The later approved run downloaded the two checkpoints listed in D-32; no VAD or diarization weights and no tokens were fetched.
