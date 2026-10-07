# Roadmap

| Milestone | Scope | Exit evidence |
|---|---|---|
| M1 — Local-first rough cut | Implement media preflight, ASR, ID packing/planning, rational-frame compilation, review artifacts, reference audio rendering, verifier, and offline evaluation. Per-item compile outcomes and ops-linked applied metrics are implemented. The corrected English smoke mapped 210 transcript rows to timing anchors and produced 16 join measurements from an ignored CFR working copy. | Pinned checks and synthetic evaluation pass; real-media pipeline and benchmark are recorded. The baseline proposed no lexical cuts and applied eight gap actions. Verification failed 12 level-step and four pacing checks; timing accuracy still needs human ground truth. Review joins before claiming editing quality and keep current thresholds. |
| M2 — VEGAS executor | Apply validated `ops.json` only to a working copy, with per-batch undo, stop checks, operation results, and path confinement. | Human probe checklist completed; settle required Vegas questions below; executor tests on disposable Vegas projects. |
| M3 — Speaker-colored subtitles | Derive caption lines from aligned words and speaker keys, export or render subtitles, and surface low-confidence attribution. | Subtitle sync and color accuracy measured; VQ-09/VQ-10 addressed. |
| M4 — Transitions and SFX | Build the closed local catalog, apply catalog-approved transitions/SFX and safe gain, and verify fades and loudness. | Catalog checks, click/loudness metrics, and relevant Vegas API questions addressed. |
| M5 — LLM, vision, and bounded automation | Enable configured endpoint planning, bounded visual review, and later correction/automation loops behind human-review and emergency-stop gates. | LLM endpoint and structured output verified; request bounds, regression evals, stop handling, and reliability gates pass. |

## Vegas questions before M2 execution

Complete [the M1 human checklist](docs/HUMAN_TESTS_M1.md). At minimum, verify undo-block behavior (VQ-08), command-line/script invocation and working-copy safety (VQ-02/VQ-15), marker and delete-range operations (VQ-04/VQ-07), and text behavior needed by later milestones (VQ-09). The existing metadata and C# compilation evidence is marked `PARTIAL (compile-time only)` and does not settle runtime behavior.

## Remaining M1 work

- Review the 16 English join measurements; address the 12 level-step and four pacing failures without changing verifier thresholds until human-reviewed evidence supports a change. Obtain annotated word-boundary ground truth before claiming timing accuracy or relying on lexical cuts. Japanese lexical segmentation remains deferred until a dependency and boundary evaluation are approved.
- The English and Japanese ASR runs, alignment checkpoints, CUDA benchmarks, and source-integrity evidence are recorded in `DECISIONS.md` D-30 through D-36 and `docs/EVALS.md`. Do not enable live LLM requests in M1.
