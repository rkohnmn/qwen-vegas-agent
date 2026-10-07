# Local AI Video Editing Agent for VEGAS Pro 17

**Status:** Milestone 1 implementation is complete for now as an offline prototype. The pipeline reached verification on a 120-second English real-media window using an approved CFR working copy under ignored `runs/`. The corrected adapter mapped all 210 transcript rows to timing anchors. The baseline planner emitted eight gap actions and no lexical cuts; verification failed on 12 level-step and four pacing checks. The project as a whole is not complete, and no edit-quality claim is supported. No code launches or edits VEGAS.

This privacy-first project targets 4–15 minute talking-content videos. Local perception produces a word-level transcript; an ID-only edit plan is validated and compiled deterministically to frame-based operations. The M1 pipeline includes media preflight, WhisperX integration, a conservative baseline planner, review artifacts, reference audio rendering, and verification. The planner's LLM adapter is restricted to loopback and is disabled in the dry-run CLI.

## Pipeline

```mermaid
flowchart LR
  A[Source media read-only] --> B[Preflight and local ASR]
  B --> C[ID-based pack]
  C --> D[Baseline or recorded planner]
  D --> E[EDL validation]
  E --> F[Rational-frame compiler]
  F --> G[Review artifacts]
  G --> H[Reference audio render and verification]
  H --> I[Run manifest]
```

M1 does not create or modify a VEGAS project. VEGAS metadata inspection and probe compilation are compile-time evidence only; a human must run the probes on a disposable project as described in [the checklist](docs/HUMAN_TESTS_M1.md).

## Quick start

Use Python 3.12 on Windows, then run:

```powershell
python tasks.py setup
python tasks.py lint
python tasks.py test
python tasks.py schemas
python tasks.py docs-check
python tasks.py eval
```

For a media run, make local `ffmpeg` and `ffprobe` available on `PATH`, run `python tasks.py setup --asr`, then run the baseline smoke command. The opt-in setup installed pinned direct packages from PyPI plus PyTorch CUDA 12.8 from the official wheel index. WhisperX model weights are fetched only when a valid media run begins. The project does not download media binaries.

```powershell
python tasks.py dry-run --video <path> --max-seconds 120 --planner baseline
```

The command writes run artifacts beneath `runs/` and cached audio/models beneath `cache/`. It hashes the source before and after processing. See [Windows setup](docs/SETUP.md) and [security boundaries](docs/SECURITY.md).

The stages can also be run separately with `python tasks.py preflight --video <path>`, `transcribe --video <path>`, `plan --words <words.json>`, and `compile --words <words.json> --timeline <timeline.json> --edl <edl.json>`. `python tasks.py compile --words <words.json> --timeline <timeline.json> --edl <edl.json> --audio <normalized-mono.wav>` can use the optional audio input for nearby zero-crossing snaps. Without `--audio`, compilation stays frame- and silence-aligned. `python tasks.py integration` reports a skipped-by-default status; `eval` remains fully offline.

## Closed-loop job runner

`python tasks.py run-job` exercises the resumable planning, compile, review, and reference-audio verification stages from a read-only `.veg` input plus declared source media, a timeline dump, aligned words, and normalized audio. It writes outputs under ignored `runs/`; local FFmpeg is required for the default reference-audio renderer. Dry-run is the default. Vegas execution and final video rendering remain disabled pending the human checks in [docs/HUMAN_TESTS_M4.md](docs/HUMAN_TESTS_M4.md); see [the pipeline details](docs/PIPELINE.md) and [known limits](docs/KNOWN_LIMITS.md).

~~~powershell
python tasks.py run-job --project <copy.veg> --media <source-media> --timeline <timeline.json> --words <words.json> --audio <normalized-mono.wav>
python tasks.py watch-render --job-dir <runs/job_id> --output final_render.mp4 --timeout-s 3600
~~~

After a manual VEGAS render, `watch-render` waits for a confined output file to become non-empty and size-stable, honors a `STOP` file, and records its hash in `manual_render_result.json`. The offline `run-job` does not launch VEGAS or wait for the final render automatically.

## Project status

| Goal | Status | Date | Commit | Revisit items |
|---|---|---|---|---|
| 01b–03 | Blocked; prompt sources absent from this checkout | — | — | RV-003 |
| 04 — Closed-loop cut pipeline | Done with assumptions; offline scope complete | 2026-10-07 | `f7e88d0` completion (pushed) | RV-001, RV-002, RV-003, RV-004 |
| 05 — Speaker attribution | Done with assumptions; offline core complete | 2026-10-07 | `529996a` implementation and docs | RV-005, RV-006 |
| 06 — Subtitles with Speaker Colors | Done with assumptions; offline sidecars complete | 2026-10-07 | `b8bab7e` completion (pushed in `209f95c`) | RV-007, RV-008 |
| 07 — Catalog, Transitions, SFX, Effects | In progress; offline implementation | 2026-10-07 | — | RV-009, RV-010 |
| 08–13 | Not started | — | — | To be assigned as each prompt is run |

### What works today (tested)

- Offline stage runner validates supplied timeline and word artifacts, writes review sidecars, resumes hash-checked stages, and records source integrity. Tests use injected fake renderers; the CLI default renderer needs local FFmpeg (RV-004). Vegas execution is disabled. See [the pipeline](docs/PIPELINE.md).
- Per-cut approvals recompile the exact approved subset; fake executor and renderer fixtures cover review and repair behavior.
- `watch-render` detects a stable file confined to a run directory and records its hash.
- Caption compilation maps word timing through removed ranges, checks speaker color and confidence flags, and writes JSON/SRT/ASS sidecars. The local ASS burn-in command is available but awaits FFmpeg verification (RV-008); VEGAS text paths await VQ-09/VQ-10 and a human style choice (RV-007). See [the subtitle guide](docs/SUBTITLES.md).
- `python tasks.py lint`, `test`, `schemas`, `docs-check`, and `eval` are the available verification commands. Eval is synthetic and reports two level-step failures.

- Speaker-mode mapping, multitrack attribution, synthetic bleed downranking, overlap confidence, enrollment quality checks with fake encoders, low-confidence reports, question confirmation, timeout handling, and secret filtering are covered by 14 unit tests. This is fixture evidence only.

### What is assumed (not yet tested)

- VEGAS marker, edit, undo, stop, and render behavior: [RV-001](REVISIT.md#rv-001--goal-04-vegas-runtime-and-project-mutation-behavior).
- Real-speech cut timing, sync, and listening quality: [RV-002](REVISIT.md#rv-002--goal-04-real-clip-timing-sync-and-listening-quality).
- Missing predecessor prompts and human gates: [RV-003](REVISIT.md#rv-003--missing-predecessor-and-reusable-prompt-artifacts).
- Default reference rendering needs local FFmpeg: [RV-004](REVISIT.md#rv-004--goal-04-default-reference-renderer-availability).

- Real diarization, enrollment, speaker matching, bleed calibration, and laptop model benchmarks are not available without the accepted local model and labeled recordings: [RV-005](REVISIT.md#rv-005--goal-05-hugging-face-gate-and-voice-enrollment-samples) and [RV-006](REVISIT.md#rv-006--goal-05-real-speech-attribution-quality-and-hardware-benchmark).
- Real speech caption sync, visual color checks, phone-size readability, 300-event Vegas performance, and style/probe sign-off remain open: [RV-007](REVISIT.md#rv-007--goal-06-caption-style-and-vegas-text-probes) and [RV-008](REVISIT.md#rv-008--goal-06-ass-burn-in-runtime-availability).
### Quick start for the offline runner

Use Python 3.12 and provide a read-only `.veg`, its source media, validated timeline and words files, and normalized mono PCM16 WAV. The command writes to ignored `runs/`; it does not launch Vegas or ASR. See [the M4 checklist](docs/HUMAN_TESTS_M4.md).

~~~powershell
python tasks.py run-job --project <copy.veg> --media <source-media> --timeline <timeline.json> --words <words.json> --audio <normalized-mono.wav>
python tasks.py watch-render --job-dir <runs/job_id> --output final_render.mp4 --timeout-s 3600
~~~

Track open assumptions in [REVISIT.md](REVISIT.md), follow the [human test checklists](docs/HUMAN_TESTS_M4.md), and see [completed prompts](<completed prompts/>).

## Current limits

- The corrected English run used `small` ASR and WhisperX's `WAV2VEC2_ASR_BASE_960H` alignment checkpoint on CUDA (`int8_float16`), with 0.578 GB peak VRAM. ASR detected English at 0.9766 confidence; normalized alignment text matched all 210 transcript rows. Duration sanity flagged eight rows under 20 ms and two over 2 seconds. The baseline planner applied eight gap actions and produced 16 joins, but no lexical cuts. All 16 click checks and all 32 clipped-word checks passed; 12 level-step checks and four pacing checks failed. No human ground truth was available, so timing accuracy remains unmeasured. The home inference server remained off and no LLM endpoint was contacted.
- The earlier Japanese run remains historical evidence that timed subword pieces must not be treated as lexical words; see D-34 and [the evaluation record](docs/EVALS.md).
- The synthetic baseline eval is a one-case plumbing check, not a quality estimate for real speech.
- `--planner llm` is disabled in the CLI. The isolated client is tested only against loopback fakes; M1 makes no LLM network requests.
- Vegas-specific runtime behavior remains unverified. No Vegas application or probe was run.

## Remaining work

These checks remain before treating the prototype as editing-quality validated or starting Vegas execution:

- Review the 16 English joins and investigate the 12 level-step and four pacing failures using human-reviewed evidence. Keep verifier thresholds unchanged until a representative sample supports calibration.
- Label the ignored English truth template with word boundaries, then measure timing and cut accuracy. There is no real-media ground truth yet.
- Complete the click-by-click checks in [the M1 VEGAS human checklist](docs/HUMAN_TESTS_M1.md) on a disposable project. Current VEGAS evidence is metadata and compile-time only.
- Continue with Goal 07 and later transition/SFX, vision, LLM planning, automation, performance, security, and packaging prompts while the Goal 06 human caption checks remain tracked; see [the roadmap](ROADMAP.md).

The contract schemas and prose specifications are in [schemas/](schemas/) and [docs/contracts/](docs/contracts/). Remaining work and acceptance evidence are listed in [ROADMAP.md](ROADMAP.md) and [docs/EVALS.md](docs/EVALS.md).

## Hardware layout

- Editing laptop: Windows, Python 3.12, local media processing and VEGAS Pro 17. The project venv has CUDA-enabled PyTorch on the 4 GB RTX 3050 Ti; the historical Japanese `small` ASR run peaked at 1.27 GB VRAM and the latest English run peaked at 0.578 GB.
- Inference server: self-hosted Qwen through `llama-server` and Tailscale in a later milestone; M1 does not connect to it.
- Optional CPU workers and remote processing are not implemented.
