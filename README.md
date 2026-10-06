# Local AI Video Editing Agent for VEGAS Pro 17

**Status:** The offline Milestone 1 pipeline completed a real-media dry run. Japanese ASR returned 30 phrase-level tokens. Forced alignment produced finer subword timings that did not match the word-level contract, so the adapter kept all 30 tokens unaligned and the baseline planner emitted no cuts or gap actions. No edit-quality claim is supported by this run. No code launches or edits VEGAS.

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

- The project venv has WhisperX 3.8.6 and CUDA-enabled PyTorch. The real-media smoke used the `small` faster-whisper checkpoint and the Japanese WhisperX alignment checkpoint on CUDA (`int8_float16`), with 1.27 GB peak VRAM. ASR detected Japanese at 0.9399 confidence. WhisperX returned 298 timed subword rows whose segmentation did not match the word-level contract, so all 30 phrase-level tokens remained unaligned. The baseline planner proposed no edits, so no real joins were available to measure. The home inference server remained off and no LLM endpoint was contacted.
- The synthetic baseline eval is a one-case plumbing check, not a quality estimate for real speech.
- `--planner llm` is disabled in the CLI. The isolated client is tested only against loopback fakes; M1 makes no LLM network requests.
- Vegas-specific runtime behavior remains unverified. No Vegas application or probe was run.

The contract schemas and prose specifications are in [schemas/](schemas/) and [docs/contracts/](docs/contracts/). Remaining work and acceptance evidence are listed in [ROADMAP.md](ROADMAP.md) and [docs/EVALS.md](docs/EVALS.md).

## Hardware layout

- Editing laptop: Windows, Python 3.12, local media processing and VEGAS Pro 17. The project venv has CUDA-enabled PyTorch on the 4 GB RTX 3050 Ti; the `small` smoke ASR run peaked at 1.27 GB VRAM.
- Inference server: self-hosted Qwen through `llama-server` and Tailscale in a later milestone; M1 does not connect to it.
- Optional CPU workers and remote processing are not implemented.
