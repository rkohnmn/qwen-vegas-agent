# Local AI Video Editing Agent for VEGAS Pro 17

**Status:** The Milestone 1 pipeline reached verification on a 120-second English real-media window using an approved CFR working copy under ignored `runs/`. The corrected adapter mapped all 210 transcript rows to timing anchors. The baseline planner emitted eight gap actions and no lexical cuts; verification failed on 12 level-step and four pacing checks. No edit-quality claim is supported. No code launches or edits VEGAS.

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

## Current limits

- The corrected English run used `small` ASR and WhisperX's `WAV2VEC2_ASR_BASE_960H` alignment checkpoint on CUDA (`int8_float16`), with 0.578 GB peak VRAM. ASR detected English at 0.9766 confidence; normalized alignment text matched all 210 transcript rows. Duration sanity flagged eight rows under 20 ms and two over 2 seconds. The baseline planner applied eight gap actions and produced 16 joins, but no lexical cuts. All 16 click checks and all 32 clipped-word checks passed; 12 level-step checks and four pacing checks failed. No human ground truth was available, so timing accuracy remains unmeasured. The home inference server remained off and no LLM endpoint was contacted.
- The earlier Japanese run remains historical evidence that timed subword pieces must not be treated as lexical words; see D-34 and [the evaluation record](docs/EVALS.md).
- The synthetic baseline eval is a one-case plumbing check, not a quality estimate for real speech.
- `--planner llm` is disabled in the CLI. The isolated client is tested only against loopback fakes; M1 makes no LLM network requests.
- Vegas-specific runtime behavior remains unverified. No Vegas application or probe was run.

The contract schemas and prose specifications are in [schemas/](schemas/) and [docs/contracts/](docs/contracts/). Remaining work and acceptance evidence are listed in [ROADMAP.md](ROADMAP.md) and [docs/EVALS.md](docs/EVALS.md).

## Hardware layout

- Editing laptop: Windows, Python 3.12, local media processing and VEGAS Pro 17. The project venv has CUDA-enabled PyTorch on the 4 GB RTX 3050 Ti; the historical Japanese `small` ASR run peaked at 1.27 GB VRAM and the latest English run peaked at 0.578 GB.
- Inference server: self-hosted Qwen through `llama-server` and Tailscale in a later milestone; M1 does not connect to it.
- Optional CPU workers and remote processing are not implemented.
