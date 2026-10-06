# Decisions

Numbered decisions capture settled design choices. The architecture remains the source of truth for system behavior; this log records rationale and Milestone 0 and Milestone 1 clarifications.

## Decisions

### D-01 — Model selects intent by ID; code selects numbers
Date: 2026-10-06

Decision: Planner output names words, segments, gaps, events, cuts, speakers, and catalog keys. Deterministic code resolves time, frame, color, plugin ID, and path values.

Rationale: Prevents model-authored timing and keeps execution constrained.

Alternatives: Let the model emit seconds or plugin settings; rejected because they are less precise and weaken the closed contract boundary.

Status: Accepted.

### D-02 — One complete plan per pass
Date: 2026-10-06

Decision: The planner emits one whole EDL per video, with bounded typed tool requests and questions.

Rationale: Keeps one structured artifact for validation and review and follows the existing architecture.

Alternatives: Emit one action per model turn; deferred.

Status: Accepted.

### D-03 — Laptop-only perception is the default topology
Date: 2026-10-06

Decision: Perception is designed to run on the editing laptop; optional CPU offload remains explicit configuration.

Rationale: The user supplies only an inference endpoint and key; video and project files stay local.

Alternatives: Require server-side workers; rejected for the default path.

Status: Accepted; hardware fit remains unbenchmarked.

### D-04 — JSON Schema is authoritative
Date: 2026-10-06

Decision: Draft 2020-12 schema files define contract shape. Python checks use those schemas plus separately named semantic/reference checks.

Rationale: Shared machine-readable contracts prevent prose, prompts, and consumers drifting.

Alternatives: Parallel hand-maintained Python models; rejected.

Status: Accepted.

### D-05 — Cross-platform tasks are implemented in Python
Date: 2026-10-06

Decision: `tasks.py` is the command interface; Makefile targets only forward to it.

Rationale: Windows is the primary development environment and should not require GNU Make.

Alternatives: Make-only tasks; rejected.

Status: Accepted.

### D-06 — Dry run remains the operating default
Date: 2026-10-06

Decision: The example config uses `dry-run`; `dry-run` and `eval` task stubs return code 2.

Rationale: No task may imply that a pipeline stage exists before it is implemented.

Alternatives: Return success with a placeholder; rejected.

Status: Accepted.

### D-07 — Broker and closed catalog contain the blast radius
Date: 2026-10-06

Decision: Only the orchestrator may hold the endpoint/key. Only catalog keys reach planner output; only validated ops reach the Vegas executor.

Rationale: Applies the architecture trust boundaries in code and schemas.

Alternatives: Put credentials in Vegas or expose plugin details to the planner; rejected.

Status: Accepted.

### D-08 — Contract reconciliation and canonical Vegas-notes path
Date: 2026-10-06

Decision: Milestone 0's explicit requirements add `gaps` to words, require `kind`/`params_mode` on catalog entries, and use the operation union from VEGAS_NOTES `8. Architecture was bumped to 1.1.0 to document those shapes. The existing root-level Vegas notes were moved to `docs/VEGAS_NOTES.md` and bumped to 1.0.1 without changing probe content or Vegas claims.

Rationale: The starter checkout's paths and contract descriptions did not support required gap refs, internal/model catalog separation, and the documented executor operation list.

Alternatives: Omit those required data and operation forms; rejected because referential checks and schemas could not meet the objective.

Status: Accepted.

### D-09 — Development dependencies are pinned
Date: 2026-10-06

Decision: Pin `jsonschema==4.23.0` (Draft 2020-12 validation, MIT), `pytest==8.4.2` (unit test runner, MIT), `ruff==0.12.12` (lint/format, MIT), and `mypy==1.18.2` (strict type checks, MIT).

Rationale: These small, established development tools support deterministic checks; direct versions are explicit in `requirements-dev.txt`; the complete resolved dependency set is pinned in `requirements-lock.txt`.

Alternatives: Hand-roll JSON Schema validation or leave tools unpinned; rejected.

Status: Accepted.

### D-10 — Keep task checks isolated and repeatable
Date: 2026-10-06

Decision: Schema checks re-execute under the project virtual environment, and the test task uses a temporary directory under the project root that is removed after the run.

Rationale: The task runner must use the pinned dependencies consistently and leave no test config or scratch data behind.

Alternatives: Use the caller's global packages or retain pytest temp files in the project; rejected.

Status: Accepted.

### D-11 — Python 3.12 is the Windows development target
Date: 2026-10-06

Decision: Update the project target from Python 3.11 to Python 3.12.10 on Windows. Use CPU inference when CUDA is unavailable.

Rationale: Python 3.12.10 is the installed 64-bit runtime. The current WhisperX package metadata supports Python 3.10 through 3.13, and PyTorch's Windows guidance supports Python 3.9 through 3.12. The available global PyTorch is CPU-only (`2.13.0+cpu`), so CUDA inference is not available in this environment; M1's CPU fallback remains the supported path.

Alternatives: Keep 3.11 as the target and install another Python runtime; rejected because it adds an environment requirement without improving compatibility for this milestone.

Status: Accepted. Smoke ASR performance remains unmeasured because ffmpeg and ffprobe are missing.

### D-12 — Do not fetch ffmpeg binaries
Date: 2026-10-06

Decision: Keep preflight, extraction, and media-render smoke work stopped until the user installs `ffmpeg` and `ffprobe`. Do not fetch binaries from any source.

Rationale: Milestone 1 explicitly excludes ffmpeg downloads. Both tools are absent from PATH and the checked local tool locations. Offline contracts, planners, compiler, synthetic renderer, verifier, tests, and Vegas metadata inspection can proceed independently.

Alternatives: Download a binary or substitute another media executable; rejected because the prompt permits no ffmpeg download and requires ffprobe-based inspection.

Status: Accepted. Real-media acceptance criteria 2 and the benchmark portion of 10 are blocked pending local installation.

### D-13 — EDL silence edits use gap IDs and compile configuration
Date: 2026-10-06

Decision: Add optional `gap_actions` to EDL 1.1.0. Each action names a known gap ID and uses `remove` or `shorten`; the planner never supplies a retained length.

Rationale: This preserves compatibility with existing EDLs while giving the deterministic baseline planner a safe silence action. The compiler owns all numeric timing and configured retained-length decisions.

Alternatives: Put a duration in EDL; rejected because it lets planner output select resolved time values.

Status: Accepted.

### D-14 — M1 timeline is a linked synthetic A/V group
Date: 2026-10-06

Decision: Synthesize one zero-based timeline from the source media, with one video event, one event per selected audio stream, and a single linked A/V group. Store rational fps, integer frames, source offsets, and the source hash.

Rationale: This permits deterministic compiler and dry-run work without launching Vegas. The later Vegas dumper must emit compatible event/group semantics.

Alternatives: Require a Vegas project before planning; deferred to the Vegas executor milestone because M1 must work offline without Vegas running.

Status: Accepted.

### D-15 — Run metrics are checked from integer frame totals
Date: 2026-10-06

Decision: Treat integer frame totals as authoritative for removed-percent reporting. Estimate pack tokens as `ceil(characters / 4)` and record the estimate method in the manifest.

Rationale: Both metrics remain deterministic and do not require a tokenizer or floating-point time arithmetic.

Alternatives: Download a tokenizer or store only a floating-point percentage; rejected to keep M1 offline and auditable.

Status: Accepted.

## Reference: browser agent patterns

Read-only review of the local sibling browser-agent repository, commit 04c788de21cded7070744c60a98048e9b2141f49. The folder contained no LICENSE, COPYING, or NOTICE file, so the license is unknown. No code was copied.

Patterns that informed this project:

- Credentials are read in a privileged background broker and do not cross into page/content-script code. Here the orchestrator remains the sole holder, while Vegas receives only validated ops.
- Settings separate endpoint, model, and key; a bounded connection test is useful later. A connection test is deferred from Milestone 0 because it would add network code.
- The reference documents a small explicit agent state machine. This project keeps the named job states in Architecture `18.3 and the emergency-stop/stop-file boundary in the executor requirements.
- It uses a typed JSON action schema and validates responses before dispatch. This project instead validates a complete EDL and closed ops union; no strings from model output are executed.
- It sends state deltas between turns. DOM-line diffing is reference-specific; no differential EDL or transcript compression was added to Milestone 0.

## Prior art

These projects informed the design; their licenses have not been checked and no code was copied:

- [video-use](https://github.com/browser-use/video-use) — license to be checked before any adaptation.
- [Smart-Cut](https://github.com/qkirara/Smart-Cut) — license to be checked before any adaptation.
- [vegas-regions-to-srt](https://github.com/kaszarobert/vegas-regions-to-srt) — license to be checked before any adaptation.

## Dependency license notes

| Package | Purpose | Pinned version | License |
|---|---|---:|---|
| jsonschema | Draft 2020-12 contract validation | 4.23.0 | MIT |
| pytest | Unit tests | 8.4.2 | MIT |
| ruff | Lint and format | 0.12.12 | MIT |
| mypy | Strict Python typing | 1.18.2 | MIT |
