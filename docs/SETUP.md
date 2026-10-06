# Setup

**Document version:** 1.1.0

This guide covers the local Milestone 1 rough-cut pipeline on Windows. It never starts VEGAS or contacts an inference endpoint.

## Prerequisites

- Windows 10 or later.
- Python 3.12 available as `python` or the Windows `py` launcher.
- `ffmpeg` and `ffprobe` on `PATH` for media preflight, extraction, and reference rendering. They are not bundled or downloaded by this project.
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
```

The setup task creates `.venv` and installs pinned dependencies from the project requirements. Pip uses PyPI only. The checks and synthetic evals make no network requests. Activate the environment only if you want to run Python commands directly:

```powershell
.\.venv\Scripts\Activate.ps1
```

`python tasks.py dry-run --video <path> --max-seconds 120 --planner baseline` runs the offline pipeline. `python tasks.py eval` runs synthetic fixtures and requires no media, model weights, GPU, or network.

## Measured on dev laptop

| Item | Observation |
|---|---|
| OS | Windows 10, build 19045 |
| Python | 3.12.10, 64-bit |
| CPU | AMD Ryzen 7 5800U with Radeon Graphics; 16 logical processors |
| RAM | 15.4 GiB available to Windows |
| GPU | NVIDIA GeForce RTX 3050 Ti Laptop GPU, 4 GiB VRAM; driver 595.71 |
| CUDA in the active Python | Unavailable; the installed global PyTorch is CPU-only (`2.13.0+cpu`) and `torch.cuda.is_available()` is false |
| VEGAS | Pro 17.0, build 284; `ScriptPortal.Vegas.dll` and `vegas170.exe` are present |
| `ffmpeg` / `ffprobe` | Missing from PATH and the checked local tool locations. No version is available; binaries were not downloaded. |

WhisperX metadata permits Python 3.12, and PyTorch's Windows support currently covers Python 3.9 through 3.12. The project therefore targets the installed Python 3.12 runtime. Because CUDA is unavailable in the active Python, ASR must use its CPU fallback unless a supported CUDA build is installed later. See the [WhisperX package metadata](https://pypi.org/project/whisperx/) and [PyTorch Windows installation guidance](https://docs.pytorch.org/get-started/locally/).

The selected smoke candidate is identified in tracked documentation only by its SHA-256 prefix and generic metadata: `690caa6e14f57674`, 78.55 seconds, approximately 29.97 fps as reported by Windows media properties, stereo audio. Codecs and VFR status are unverified because `ffprobe` is unavailable. No pipeline run was performed on the video.

The missing `ffmpeg` and `ffprobe` stop the real-media portion of M1. Install them locally, then rerun preflight, extraction, and the smoke benchmark. The project does not fetch binaries.

## Later milestones

- **`llama-server`:** M1 never contacts the inference endpoint. A future configured server must use schema-constrained output and a bounded context.
- **Tailscale:** M1 has no remote worker or endpoint route.
- **VEGAS Pro 17:** M1 only inspects installation metadata and compiles probes; a human must run probes on a throwaway project. Vegas behavior remains `UNVERIFIED` until observed.
