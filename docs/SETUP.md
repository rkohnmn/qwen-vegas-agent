# Setup

**Document version:** 1.1.0

This guide covers the local Milestone 1 rough-cut pipeline on Windows. It never starts VEGAS or contacts an inference endpoint.

## Prerequisites

- Windows 10 or later.
- Python 3.12 available as `python` or the Windows `py` launcher.
- `ffmpeg` and `ffprobe` on `PATH` for media preflight, extraction, and reference rendering. They are not bundled or downloaded by this project.
- Local ASR is optional. `python tasks.py setup --asr` installs the pinned optional packages from `requirements-asr.txt` and a pinned PyTorch stack; plain `setup` remains dev-only. Model weights are fetched lazily by WhisperX only when a valid media run begins.
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

`python tasks.py eval` runs synthetic fixtures and requires no media, model weights, GPU, or network. A real `python tasks.py dry-run --video <path> --max-seconds 120 --planner baseline` requires local `ffmpeg`, `ffprobe`, WhisperX, and its model weights. In the current environment it stops at preflight because `ffprobe` is unavailable; no source-media run has been performed.

## Measured on dev laptop

| Item | Observation |
|---|---|
| OS | Windows 10, build 19045 |
| Python | 3.12.10, 64-bit |
| CPU | AMD Ryzen 7 5800U with Radeon Graphics; 16 logical processors |
| RAM | 15.4 GiB available to Windows |
| GPU | NVIDIA GeForce RTX 3050 Ti Laptop GPU, 4 GiB VRAM; driver 595.71 |
| CUDA in the global Python | Unavailable; global PyTorch remains CPU-only (`2.13.0+cpu`). |
| CUDA in the project venv | Available; PyTorch `2.8.0+cu128` reports CUDA 12.8 and `torch.cuda.is_available()` is true. Detected GPU memory is 4095 MiB; model peak VRAM is unmeasured. |
| VEGAS | Pro 17.0, build 284; `ScriptPortal.Vegas.dll` and `vegas170.exe` are present |
| `ffmpeg` / `ffprobe` | Missing from PATH and the checked local tool locations. No version is available; binaries were not downloaded. |

WhisperX and PyTorch support the active Python 3.12 runtime. The opt-in ASR setup installed CUDA PyTorch in the project venv and verified CUDA availability. The adapter will choose CUDA when available and falls back to CPU int8 when CUDA is unavailable or an out-of-memory retry is needed. See [WhisperX package metadata](https://pypi.org/project/whisperx/) and [PyTorch Windows installation guidance](https://docs.pytorch.org/get-started/locally/).

The selected smoke candidate is identified in tracked documentation only by its SHA-256 prefix; the source path and filename stay in ignored local configuration.

| Candidate field | Observation |
|---|---|
| SHA-256 prefix | `690caa6e14f57674` |
| Duration | 78.55 seconds (Windows media properties) |
| Frame rate | Approximately 29.97 fps (Windows media properties); rational rate not measured |
| Container / video codec / audio codec | Not measured; `ffprobe` unavailable |
| VFR status | Not determined; no timestamp sampling was possible |
| Audio layout | Stereo per Windows media properties; stream count not measured |
| Preflight warnings | No warning codes emitted; preflight stopped with `ffprobe is not installed or not available on PATH` |
| Detected language / confidence | Not measured; ASR did not start |

No pipeline run was performed on the video. Its SHA-256 was identical before and after the read-only preflight attempt.

The current shell still lacks `ffmpeg` and `ffprobe`; preflight stops before audio extraction. The source hash was unchanged. Install both locally, then rerun preflight, extraction, and the smoke benchmark. The project does not fetch binaries.

## ASR benchmark and run outputs

The dry-run records per-stream model, alignment model, device, compute type, wall time, peak VRAM when CUDA metrics are available, and real-time factor in `asr_benchmark.json`. The 4 GiB laptop GPU is the measured VRAM ceiling; peak model-run VRAM remains unmeasured until the media smoke runs. With the default `compile.snap_zero_crossing` setting, normalized PCM is also passed to the compiler so it can prefer a nearby zero crossing within 20 ms while respecting safe speech bounds. The standalone `compile` task accepts `--audio <normalized-mono.wav>` for the same optional snap. Run artifacts are written under `runs/<job_id>/`; extracted PCM audio and model cache files are written under `cache/`. Both locations are gitignored. The source file is hashed before and after the run, and both hashes are stored in `run_manifest.json`.

## M1 review artifacts and verifier

- markers.csv contains frame, timecode, label, category, and confidence. Each label contains an M1 prefix, cut ID, category, and IN/OUT suffix.
- cuts.edl is a CMX3600-style record EDL for the source intervals kept after the planned removals. It is an interchange view only; it does not contain Vegas effects, titles, transitions, or audio fades, and fractional frame rates may require a compatible importer.
- review.md lists cut IDs, categories, confidence, reasons, nearby transcript context, a count/removed-frame/removed-percent summary, and a **Proposed but not applied** section for rejected actions. The compiler report gives every proposed cut and gap action an explicit status; final delete operations carry their source item IDs for applied metrics.
- verify_report.json measures rendered join clicks and level steps, pacing at joins created by cuts, clipped-word boundaries, and removed-percent limits. Pacing uses compile.min_gap_after_cut_ms and compile.max_gap_after_cut_ms from the validated config.

## Later milestones

- **`llama-server`:** M1 never contacts the inference endpoint. A future configured server must use schema-constrained output and a bounded context.
- **Tailscale:** M1 has no remote worker or endpoint route.
- **VEGAS Pro 17:** M1 only inspects installation metadata and compiles probes; a human must run probes on a throwaway project. Vegas behavior remains `UNVERIFIED`.
