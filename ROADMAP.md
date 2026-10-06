# Roadmap

| Milestone | Scope | Exit evidence |
|---|---|---|
| M1 — Local-first rough cut | Implement media preflight, ASR, ID packing/planning, rational-frame compilation, review artifacts, reference audio rendering, verifier, and offline evaluation. Per-item compile outcomes and ops-linked applied metrics are implemented. The real-media dry run completed with an unchanged source hash; Japanese subword alignment did not match word-level units, so no cuts or joins were emitted. | Pinned checks and synthetic evaluation pass; real-media pipeline and benchmark are recorded. Word-boundary quality and verifier thresholds on real joins remain unvalidated because the smoke produced no word-level anchors. |
| M2 — VEGAS executor | Apply validated `ops.json` only to a working copy, with per-batch undo, stop checks, operation results, and path confinement. | Human probe checklist completed; settle required Vegas questions below; executor tests on disposable Vegas projects. |
| M3 — Speaker-colored subtitles | Derive caption lines from aligned words and speaker keys, export or render subtitles, and surface low-confidence attribution. | Subtitle sync and color accuracy measured; VQ-09/VQ-10 addressed. |
| M4 — Transitions and SFX | Build the closed local catalog, apply catalog-approved transitions/SFX and safe gain, and verify fades and loudness. | Catalog checks, click/loudness metrics, and relevant Vegas API questions addressed. |
| M5 — LLM, vision, and bounded automation | Enable configured endpoint planning, bounded visual review, and later correction/automation loops behind human-review and emergency-stop gates. | LLM endpoint and structured output verified; request bounds, regression evals, stop handling, and reliability gates pass. |

## Vegas questions before M2 execution

Complete [the M1 human checklist](docs/HUMAN_TESTS_M1.md). At minimum, verify undo-block behavior (VQ-08), command-line/script invocation and working-copy safety (VQ-02/VQ-15), marker and delete-range operations (VQ-04/VQ-07), and text behavior needed by later milestones (VQ-09). The existing metadata and C# compilation evidence is marked `PARTIAL (compile-time only)` and does not settle runtime behavior.

## Remaining M1 work

- Add an approved Japanese lexical segmenter or select speech in a language with supported word segmentation; prove boundaries before enabling cuts from this clip.
- Collect a real-media run that emits reviewable joins before calibrating click and level-step thresholds; keep current defaults until then.
- The small ASR and Japanese alignment weights, CUDA benchmark, and source-integrity comparison are recorded in `DECISIONS.md` D-30 through D-34 and `docs/EVALS.md`. Do not enable live LLM requests in M1.
