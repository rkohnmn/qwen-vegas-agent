# Roadmap

| Milestone | Scope | Exit evidence |
|---|---|---|
| M1 — Local-first rough cut | Implement media preflight, word-level ASR adapter, ID packing/planning, rational-frame compilation, review artifacts, reference audio rendering, verifier, and offline evaluation. Per-item compile outcomes and ops-linked applied metrics are implemented. The real-media smoke remains blocked by missing local `ffmpeg`/`ffprobe`. | Pinned checks pass; synthetic selection and applied metrics are recorded; complete the smoke run, benchmark, and real-join table after media tools are available; source hash must remain unchanged. |
| M2 — VEGAS executor | Apply validated `ops.json` only to a working copy, with per-batch undo, stop checks, operation results, and path confinement. | Human probe checklist completed; settle required Vegas questions below; executor tests on disposable Vegas projects. |
| M3 — Speaker-colored subtitles | Derive caption lines from aligned words and speaker keys, export or render subtitles, and surface low-confidence attribution. | Subtitle sync and color accuracy measured; VQ-09/VQ-10 addressed. |
| M4 — Transitions and SFX | Build the closed local catalog, apply catalog-approved transitions/SFX and safe gain, and verify fades and loudness. | Catalog checks, click/loudness metrics, and relevant Vegas API questions addressed. |
| M5 — LLM, vision, and bounded automation | Enable configured endpoint planning, bounded visual review, and later correction/automation loops behind human-review and emergency-stop gates. | LLM endpoint and structured output verified; request bounds, regression evals, stop handling, and reliability gates pass. |

## Vegas questions before M2 execution

Complete [the M1 human checklist](docs/HUMAN_TESTS_M1.md). At minimum, verify undo-block behavior (VQ-08), command-line/script invocation and working-copy safety (VQ-02/VQ-15), marker and delete-range operations (VQ-04/VQ-07), and text behavior needed by later milestones (VQ-09). The existing metadata and C# compilation evidence is marked `PARTIAL (compile-time only)` and does not settle runtime behavior.

## Remaining M1 work

- Install `ffmpeg` and `ffprobe` locally, then run the selected smoke clip without writing to the media or VEGAS installation.
- Optional ASR packages and CUDA PyTorch are installed in the project venv. After local ffmpeg/ffprobe are available, run only the small model and detected-language alignment weights through the approved local flow; record model, device, compute type, peak VRAM, and real-time factor.
- Re-run the baseline pipeline and compare source hashes before and after. Do not enable live LLM requests in M1.
