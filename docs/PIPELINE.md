# Closed-Loop Pipeline

**Status: offline implementation with assumptions.** The current runner consumes a read-only VEGAS project, declared source-media files, a timeline dump, aligned words, and normalized audio. It does not open VEGAS, create the timeline dump, or run ASR. Those adapters depend on the missing human VEGAS probes. Fake executor and reference-render results are marked ASSUMED (RV-001); speech quality and render accuracy are not measured (RV-002).

## Flow

~~~mermaid
flowchart LR
  A[Project and source hashes] --> B[Copy project into run directory]
  B --> C[Load validated timeline]
  C --> D[Load aligned words and speakers]
  D --> E[Pack] --> F[Baseline or recorded planner]
  F --> G[Compile frame operations and captions]
  G --> H[Markers, EDL, review, SRT, ASS]
  H --> I{Review mode?}
  I -->|No| J[Reference WAV]
  I -->|Yes| K[Per-cut decisions] --> L[Recompile approved cuts] --> M[Executor interface]
  M --> J
  J --> N[Verify WAV read from disk]
  N --> O[At most two crossfade repairs]
  O --> P[Final render request and run manifest]
~~~

The runtime Vegas executor is disabled. Review mode without an injected executor fails closed with E_EXECUTOR_DISABLED; tests inject a clearly named FakeExecutor. The current renderer writes a reference audio preview, not a Vegas render. Final video rendering stays a manual step and the manifest says so. After rendering to the declared run directory, `python tasks.py watch-render --job-dir <runs/job_id> --output final_render.mp4 --timeout-s 3600` waits for a confined, non-empty, size-stable file and writes its SHA-256 record. The watcher does not launch Vegas or verify video contents.

## State and artifacts

Each stage stores its input key, output paths relative to the run directory, and output SHA-256 hashes in ignored job_state.json. Resume reuses a stage only when its key and every recorded output hash still match. After the injected executor completes, the working-copy hash is checkpointed; resume preserves later edits only when the file still matches that checkpoint. The source project and each declared media/audio input are rehashed at the end. No paths are recorded in run_manifest.json.

| Stage | Main artifacts | Failure codes |
|---|---|---|
| Project copy | working_copy/project.veg | E_PROJECT_INPUT, E_COPY_MISMATCH, E_RUN_EXISTS |
| Ingest / perceive | timeline.json, words.json, speakers.json | E_TIMELINE_INVALID, E_MEDIA_HASH_MISMATCH, E_WORDS_INVALID, E_WORDS_TIMELINE_MISMATCH |
| Pack / plan | pack.txt, edl.json | E_PLAN_FAILED, E_EDL_INVALID |
| Compile / dry run | ops.json, compile_report.json, captions.json, captions.srt, captions.ass, captions_report.json, markers.csv, cutlist_preview.edl, review.md | E_COMPILE_INVALID, E_STAGE_OUTPUT |
| Approval | approved_cuts.template.json or approved_cuts.json, approved EDL/ops/captions, pre-execution project checkpoint, refreshed markers and review | E_APPROVAL_SHAPE, E_APPROVAL_INVALID, E_APPROVAL_COVERAGE |
| Execute | execution_result.json | E_EXECUTOR_DISABLED, E_EXECUTOR_INPUT_INVALID, E_EXECUTOR_RESULT |
| Preview / verify | preview.wav, verify_report.json, fixes.json | E_PREVIEW_VERIFY |
| Final render | final_render_status.json, optional manual_render_result.json | Vegas rendering remains manual and unverified |

Errors are recorded by stage in job_state.json and in the run manifest. Messages avoid paths and raw exception output. Failed runs retain the copied project and completed artifacts for inspection.

| Failure stage | Stable error codes |
|---|---|
| Project copy / resume | E_PROJECT_INPUT, E_RUN_EXISTS, E_COPY_MISMATCH, E_RESUME_STATE, E_RESUME_INPUT_CHANGED |
| Ingest / perception | E_INPUT_MISSING, E_INPUT_READ, E_TIMELINE_INVALID, E_MEDIA_HASH_MISMATCH, E_WORDS_INVALID, E_WORDS_TIMELINE_MISMATCH |
| Plan / compile | E_PLAN_FAILED, E_EDL_INVALID, E_COMPILE_INVALID, E_STAGE_OUTPUT |
| Approval | E_APPROVAL_SHAPE, E_APPROVAL_INVALID, E_APPROVAL_COVERAGE, E_APPROVED_COMPILE_INVALID |
| Execute | E_EXECUTOR_DISABLED, E_EXECUTOR_RESULT |
| Preview / verify | E_PREVIEW_VERIFY, E_STAGE_FAILED |
| Manual render watcher | E_PATH_CONFINEMENT, E_RENDER_TIMEOUT_CONFIG, E_RENDER_STOPPED, E_RENDER_TIMEOUT |
| Integrity / manifest | E_SOURCE_CHANGED, E_MANIFEST_INVALID |

## Approval and repairs

Review decisions must include exactly one approve or reject for every EDL cut and gap action. Missing decisions write a template and pause. Approved items alone are recompiled; markers.csv, review.md, and `approved_captions/` sidecars are regenerated from that approved set and include the decision audit. The candidate caption sidecars remain available at the run root.

The default repair cap is two iterations. Only failed click or level-step checks can request a wider configured crossfade. The verifier thresholds remain unchanged. Every repair records the triggering check IDs and old/new duration in fixes.json. In review mode the runner restores the pre-execution checkpoint and re-executes the adjusted operations before rendering again; fake adapters test this path. The fixed-width behavior is ASSUMED (RV-001) until a real Vegas render and listening review establish that the same repair improves the result.

## Measurement record

| View | Metrics |
|---|---|
| Planner | EDL intent and cut IDs from baseline or recorded output |
| Applied | Compiled frame ranges and per-item outcomes |
| Reference-rendered | WAV-based click, level-step, clipped-word, pacing, and removed-percent checks |
| Vegas-rendered | Not measured (ASSUMED; RV-001) |
| Real-speech accuracy | Not measured in this run (RV-002) |

See the [human checklist](HUMAN_TESTS_M4.md), [caption checklist](HUMAN_TESTS_M6.md), [subtitle guide](SUBTITLES.md), [provisional Vegas decisions](VEGAS_DECISIONS.md), and [REVISIT.md](../REVISIT.md) before enabling any runtime path.
