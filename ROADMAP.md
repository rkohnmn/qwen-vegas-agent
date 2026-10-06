# Roadmap

Milestone 0 is the contract and validation foundation. Runtime editing is not implemented.

| Milestone | Scope | Exit evidence |
|---|---|---|
| M1 — Transcript-driven rough cut | Ingest a project copy; produce word-aligned transcripts; pack one pass; plan cuts; compile exact frames; show a dry run. Keep human review as the default. | Unit/schema checks, labeled clip evals, and Vegas executor tests on throwaway projects. |
| M2 — Speaker-colored subtitles | Map speaker keys to user colors, build subtitle lines deterministically, render or export SRT/ASS, report low-confidence attribution. | Subtitle sync and color accuracy, VQ-09/VQ-10 evidence, and fixture-backed verification. |
| M3 — Transitions and SFX | Build a closed local catalog, add catalog-approved transitions/SFX and explicit fades, apply safe gain. | Catalog key checks, loudness/click metrics, VQ-05/VQ-06/VQ-18 evidence, license records. |
| M4 — Vision review | Add bounded frame requests, visual checks, and preview verification without giving the model filesystem access. | Measured review accuracy, request bounds, and VQ-14 evidence for preview rendering. |
| M5 — Full auto mode | Add bounded correction loops, thresholds, stop/abort handling, and unattended execution only after human-reviewed reliability gates. | Regression evals, emergency-stop tests, path confinement, and all blocking Vegas questions resolved. |

Deferred items from this milestone: perception engines, endpoint client and connection test, compiler timing/snapping, Vegas executor/extension, prompt files, eval clips/harness, and asset downloads. Implement them only under the corresponding repository and Vegas safety rules.
