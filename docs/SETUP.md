# Setup

This guide covers Milestone 0 only: local Python contract checks on Windows. It does not configure ASR, the model server, Tailscale, or VEGAS.

## Prerequisites

- Windows 10 or later.
- Python 3.11 available as `python` or the Windows `py` launcher.
- No GPU, Vegas installation, LLM endpoint, or network service is needed by the checks.

## Install and validate

From the repository root in PowerShell:

```powershell
python tasks.py setup
python tasks.py lint
python tasks.py test
python tasks.py schemas
python tasks.py docs-check
```

The setup task creates `.venv` and installs the direct development tools from `requirements-dev.txt`, constrained by the complete transitive lock in `requirements-lock.txt`. Pip needs access to its configured package index only when a pinned package is not already cached. The checks make no network requests. Activate the environment only if you want to run Python commands directly:

```powershell
.\\.venv\\Scripts\\Activate.ps1
```

The schema, unit, and documentation checks are local. The `dry-run` and `eval` entry points currently print that they are not implemented in Milestone 0 and exit with code 2.

## Later milestones — not yet exercised

Everything below is design guidance only and must be checked on the target system before use.

- **WhisperX:** planned ASR/alignment path; model size, CUDA build, and 4 GB VRAM fit are `UNVERIFIED`.
- **`llama-server`:** planned flags include `--mmproj`, a context setting of at least 32k, and JSON Schema constrained output. Compatibility with the selected build and Qwen model is `UNVERIFIED`.
- **Tailscale:** planned private route from the editing laptop to the user's inference endpoint; authentication, HTTPS certificate, and endpoint reachability are not tested here.
- **VEGAS Pro 17 script paths:** `Documents\\Vegas Script Menu` and an install-folder `Script Menu` are expected locations; the exact Script Menu folder must be recorded in [VEGAS_NOTES.md `3](VEGAS_NOTES.md). An `Application Extensions` folder under the VEGAS install is also expected for extensions. All locations and extension loading behavior are `UNVERIFIED` until VQ-01/VQ-03 are tested on a throwaway project.

No probe has been run. The three scripts in `vegas/probes/` are untested drafts and must only be used with the safety protocol in `VEGAS_NOTES.md`.
