# Setup

**Document version:** 1.1.2

This guide covers the local Milestone 1 rough-cut pipeline on Windows. It never starts VEGAS or contacts an inference endpoint.

## Prerequisites

- Windows 10 or later.
- Python 3.12 available as `python` or the Windows `py` launcher.
- `ffmpeg` and `ffprobe` on `PATH` for media preflight, extraction, and reference rendering. They are not bundled or downloaded by this project.
- Local ASR is optional. `python tasks.py setup --asr` installs the pinned optional packages from `requirements-asr.txt` and a pinned PyTorch stack; plain `setup` remains dev-only. The `small` ASR and detected-language alignment weights are fetched lazily when a valid media run begins; VAD filtering and diarization are disabled in this adapter.
- VEGAS Pro 17 is only needed for the later human checks; M1 does not launch or modify it.
- The LLM endpoint remains disabled in M1. Planner tests use a loopback fake only.

## Install and validate

From the repository root in PowerShell:

```powershell
python tasks.py setup
python tasks.py lint
python tasks.py test
python tasks.py schemas
python tasks.py docs-check
python tasks.py eval
```

The setup task creates `.venv` and installs the pinned development dependencies from the project requirements. Checks and synthetic evals make no network requests. `setup --asr` additionally installs WhisperX 3.8.6, faster-whisper 1.2.1, NumPy 2.5.3, SoundFile 0.14.0, their declared dependencies, and PyTorch 2.8.0 with torchaudio 2.8.0 and torchvision 0.23.0. It tries the official CUDA 12.8 wheel index when `nvidia-smi` finds a GPU, verifies `torch.cuda.is_available()` inside `.venv`, and falls back to the official CPU wheel index if CUDA installation or verification fails. This path does not download model weights. Activate the environment only if you want to run Python commands directly:

```powershell
.\.venv\Scripts\Activate.ps1
```

`python tasks.py eval` runs synthetic fixtures and requires no media, model weights, GPU, or network. A real `python tasks.py dry-run --video <path> --max-seconds 120 --planner baseline` requires local `ffmpeg`, `ffprobe`, WhisperX, and the approved ASR/alignment weights. The real-media smoke completed end to end. Corrected bounded VFR sampling and a full decoded-frame scan classified the selected source as CFR; the original source stayed read-only. ASR detected Japanese. The aligner returned finer subword timings that did not match the contract’s word units, so the adapter retained all 30 phrase-level tokens without time anchors; the run produced no cuts and no real joins.

## Measured on dev laptop

| Item | Observation |
|---|---|
| OS | Windows 10, build 19045 |
| Python | 3.12.10, 64-bit |
| CPU | AMD Ryzen 7 5800U with Radeon Graphics; 16 logical processors |
| RAM | 15.4 GiB available to Windows |
| GPU | NVIDIA GeForce RTX 3050 Ti Laptop GPU, 4 GiB VRAM; driver 595.71 |
| CUDA in the global Python | Unavailable; global PyTorch remains CPU-only (`2.13.0+cpu`). |
| CUDA in the project venv | Available; PyTorch `2.8.0+cu128` reports CUDA 12.8 and `torch.cuda.is_available()` is true. Detected GPU memory is 4095 MiB; the real smoke ASR peak was 1.27 GB. |
| VEGAS | Pro 17.0, build 284; `ScriptPortal.Vegas.dll` and `vegas170.exe` are present |
| `ffmpeg` / `ffprobe` | Version 9.0.1 is installed in a local WinGet package outside PATH. The smoke used a process-local PATH override; this project did not download binaries or change persistent PATH settings. |

WhisperX and PyTorch support the active Python 3.12 runtime. The opt-in ASR setup installed CUDA PyTorch in the project venv and verified CUDA availability. The adapter selects CUDA when available and falls back to CPU int8 when CUDA is unavailable or an out-of-memory retry is needed. See [WhisperX package metadata](https://pypi.org/project/whisperx/) and [PyTorch Windows installation guidance](https://docs.pytorch.org/get-started/locally/).

The selected smoke candidate is identified in tracked documentation only by its SHA-256 prefix; the source path and filename stay in ignored local configuration.

| Candidate field | Observation |
|---|---|
| SHA-256 prefix | `690caa6e14f57674` |
| Duration | 78.553107 seconds by ffprobe; 78.545 seconds in the frame-aligned ASR benchmark. |
| Frame rate | `2997/100` fps. Average and real rates match. |
| VFR status | CFR. The corrected bounded check reads 16 packets beyond the requested timestamp window and evaluates only the requested sample. A full decoded scan covered 2,354 frames and 2,353 intervals with no interval more than 1 ms from the median cadence. |
| Container / video codec / audio codec | MOV/MP4 family; H.264 High video; AAC-LC audio. |
| Audio layout | One AAC-LC stream, 44100 Hz, stereo. |
| Preflight warnings | None. |
| Detected language / confidence | Japanese (`ja`), 0.9399. |

The earlier `W_VFR` came from an incomplete ffprobe packet-boundary tail, not a cadence change in the clip. Regression tests cover tail lookahead and still detect a cadence change inside the requested sample. A CFR working copy was permitted under ignored `runs/`; the corrected scan established that the source itself is CFR, so the completed smoke used the original read-only source.

The real-media dry run completed as `20261006T232642Z_d35580dd`. Its manifest records equal before/after source hashes. The test-video and VEGAS install directory listings also matched before and after. All transcript, render, benchmark, review, and truth-template outputs remain under ignored `runs/`.

## ASR benchmark and run outputs

| Field | Smoke result |
|---|---|
| ASR model | `small` (faster-whisper) |
| Alignment model | `jonatasgrosman/wav2vec2-large-xlsr-53-japanese` |
| Device / compute type | CUDA / `int8_float16` |
| Peak VRAM | 1.27 GB |
| ASR wall time | 37.367 seconds |
| Real-time factor | 0.4757 (ASR wall time divided by 78.545 seconds of media) |
| Language / confidence | Japanese (`ja`) / 0.9399 |
| Word timing | 30 tokens; 0 aligned and 30 unaligned. Short/long duration rates are not measurable with zero aligned tokens. |

The local model snapshots did not include license files. The approved run fetched only the small ASR checkpoint and the language-selected alignment checkpoint; no VAD or diarization weights, tokens, or LLM endpoint were used. Checkpoint revisions, byte sizes, and the unresolved license metadata are recorded in `DECISIONS.md` D-32. Verify redistribution terms before packaging these weights.

WhisperX produced 298 timed subword rows for 30 Japanese ASR segments, and normalized concatenated text matched every segment. The rows did not match the word-level contract, so the adapter retained the original phrase-level tokens without time anchors instead of treating subword boundaries as lexical word boundaries. The baseline planner produced zero cuts and zero gap actions. The verifier passed the removed-percent check at 0%; there were no joins for click or level-step measurement. Keep thresholds at the existing defaults until real joins are available. The truth template is available under the smoke run directory for manual labeling.

## M1 review artifacts and verifier

- markers.csv contains frame, timecode, label, category, and confidence. Each label contains an M1 prefix, cut ID, category, and IN/OUT suffix.
- cuts.edl is a CMX3600-style record EDL for the source intervals kept after the planned removals. It is an interchange view only; it does not contain Vegas effects, titles, transitions, or audio fades, and fractional frame rates may require a compatible importer.
- review.md lists cut IDs, categories, confidence, reasons, nearby transcript context, a count/removed-frame/removed-percent summary, and a **Proposed but not applied** section for rejected actions. The compiler report gives every proposed cut and gap action an explicit status; final delete operations carry their source item IDs for applied metrics.
- verify_report.json measures rendered join clicks and level steps, pacing at joins created by cuts, clipped-word boundaries, and removed-percent limits. Pacing uses compile.min_gap_after_cut_ms and compile.max_gap_after_cut_ms from the validated config.

## Later milestones

- **`llama-server`:** M1 never contacts the inference endpoint. A future configured server must use schema-constrained output and a bounded context.
- **Tailscale:** M1 has no remote worker or endpoint route.
- **VEGAS Pro 17:** M1 only inspects installation metadata and compiles probes; a human must run probes on a throwaway project. Vegas behavior remains `UNVERIFIED`.
