# Roadmap

## Current completion status

The offline M1 pipeline and deterministic cores for Prompts 05–07 are implemented. Prompt 04 adds an offline resumable job runner; Prompt 05 adds fixture-backed speaker attribution helpers; Prompt 06 adds caption sidecars; Prompt 07 adds the closed catalog builder, local SFX index, and fail-closed compiler policy. No M7 runtime operation is enabled. No accepted diarization backend or licensed M7 SFX library is configured; real-speech review and VEGAS runtime checks remain open. The overall project is not complete: later prompts remain future work, and M1 verification did not pass all quality checks.

| Milestone | Scope | Exit evidence |
|---|---|---|
| M1 — Local-first rough cut | Implemented offline: media preflight, ASR, ID packing/planning, rational-frame compilation, review sidecars, reference audio rendering, verifier, offline evaluation, and a resumable job runner that consumes precomputed perception artifacts. Per-item compile outcomes, ops-linked applied metrics, approval, and a manual-render watcher are implemented. | Unit, schema, lint, docs, and synthetic checks pass. Real-media pipeline and benchmark are recorded. The synthetic fixture verifier still flags two level-step checks; the real-media smoke verifier failed 12 level-step and four pacing checks. Vegas execution, Vegas-rendered metrics, and real-speech accuracy are not established. |
| Prompt 05 — Speaker attribution | Offline deterministic helpers and fixture tests implemented; mixed-mode inference and real quality remain untested. | Synthetic tests plus G2/model and labeled-clip results under RV-005/RV-006. |
| M2 — VEGAS executor | Apply validated `ops.json` only to a working copy, with per-batch undo, stop checks, operation results, and path confinement. | Human probe checklist completed; settle required Vegas questions below; executor tests on disposable Vegas projects. |
| M3 — Speaker-colored subtitles | Derive caption lines from aligned words and speaker keys, export or render subtitles, and surface low-confidence attribution. | Subtitle sync and color accuracy measured; VQ-09/VQ-10 addressed. |
| Prompt 07 — Catalog, transitions, SFX, effects | Offline catalog/tag builder, license-aware local SFX indexing, and capability-gated compiler policy. Runtime mutation operations remain disabled. | Standard offline checks; licensed-tone measurement; post-cut event mapping; C# compile-only check; disposable-project transition/SFX/effect review and VQ-04/05/06/17/18 E0 evidence (RV-009/RV-010/RV-011). |
| M5 — LLM, vision, and bounded automation | Future endpoint planning, bounded visual review, and correction loops behind human-review and emergency-stop gates. Prompt 08 covers runtime planner instructions and is next. | LLM endpoint and structured output verified; request bounds, regression evals, stop handling, and reliability gates pass. |

## Vegas questions before M2 execution

Complete the [M1 human checklist](docs/HUMAN_TESTS_M1.md) and the [M4 closed-loop checklist](docs/HUMAN_TESTS_M4.md). At minimum, verify undo-block behavior (VQ-08), command-line/script invocation and working-copy safety (VQ-02/VQ-15), marker and delete-range operations (VQ-04/VQ-07), and text behavior needed by later milestones (VQ-09). The existing metadata and C# compilation evidence is marked `PARTIAL (compile-time only)` and does not settle runtime behavior. Goal 07 also depends on restoring the runtime EDL prompt before its optional `effects` and `at_gap` intent can be enabled (RV-011).

## Remaining M1 work

- Review the 16 English join measurements; investigate the 12 level-step and four pacing failures without changing verifier thresholds until human-reviewed evidence supports a change.
- Label the ignored truth template with word boundaries and evaluate timing/cut accuracy. No real-media ground truth currently exists.
- Run the human VEGAS checklist on a disposable project. Do not treat metadata or compile-only results as runtime verification.
- Japanese lexical segmentation remains deferred until a dependency and boundary evaluation are approved.
- The English and Japanese ASR runs, alignment checkpoints, CUDA benchmarks, and source-integrity evidence are recorded in `DECISIONS.md` D-30 through D-37 and `docs/EVALS.md`. Do not enable live LLM requests in M1.
