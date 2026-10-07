# Prompt 04: Closed-Loop Cut Pipeline Through Vegas (Goal Prompt)

**Prompt version:** 1.0.0
**Depends on:** Prompts 01b, 02, T1, 03 complete; the Prompt 03 human test (`HUMAN_TESTS_M3.md`) passed and fed back through T1.
**Human gate before sending:** executor self-test and TP-01 cut job passed in Vegas; render mechanism decided in `docs/VEGAS_DECISIONS.md`.
**Machine:** laptop with Vegas for the human test. Baseline planner only (server not required).

=== PROMPT START ===

## STANDING RULES

- Follow `AGENTS.md`; Sections 7 and 15 are inviolable. Docs are the source of truth. If sources conflict, stop and report.
- Model chooses IDs, code chooses numbers. Credentials only in the orchestrator.
- You never run Vegas. Compile-only is `EC`; E0 needs a human result. Never write `VERIFIED` yourself.
- Never modify user media or the Vegas install directory. Local paths and secrets only in gitignored files.
- Contract changes follow `AGENTS.md` Section 8. Commit per phase, no push. Report per Section 13 with an acceptance checklist.

## GOAL

Deliver **Milestone M1 for real**: a working, verified, cut-only editing pipeline on a real Vegas project.

`Vegas project -> timeline dump -> perceive (timeline-time words) -> pack -> baseline planner -> EDL -> compile -> dry-run markers in Vegas -> approval -> execute on working copy -> Vegas render (preview) -> verify -> bounded fix loop -> final render -> report`

The result must be an edited project copy whose cut joins are measured, click-free within thresholds, and in sync.

## READ FIRST

`AGENTS.md`, `ARCHITECTURE.md` (7, 11, 12, 15, 18), `docs/EXECUTOR.md`, `docs/VEGAS_DECISIONS.md`, `docs/VEGAS_NOTES.md`, `docs/EVALS.md`, existing compiler, verifier, and renderer code.

## INPUTS

```
Reuse config.local.json (test project path or test video; scratch work dir).
SCRATCH_PROJECT = <a .veg you create from generated test media or a short real clip, kept outside git>
```

## PERMISSIONS

No downloads. Local ffmpeg only.

## SCOPE

### In scope
1. **Orchestrator job runner** `python tasks.py run-job --project <veg> [--mode dry-run|review] [--planner baseline|recorded]` implementing the full state machine from `ARCHITECTURE.md` 18.3, with typed failures at each stage and resumability from the last good state (stage artifacts are cached by hash).
2. **Dry-run markers in Vegas**: compiler output becomes `add_marker`/`add_region` ops with labeled prefixes (cut id, category, confidence); a human can review them in Vegas, then call `clear_markers_by_prefix`.
3. **Approval step** for `review` mode: reads a decisions file (`approved_cuts.json` with per-cut approve/reject) and recompiles only approved cuts. A minimal CLI prompt now; Prompt 10 adds the review UI. `review.md` and `markers.csv` stay in sync with the decisions.
4. **Execute** approved cuts on the working copy via the executor.
5. **Vegas-side preview render** using the mechanism and templates from the decision memo: an **audio-only WAV** for analysis and a low-resolution video for viewing; configurable template names in `config`. If scripted render is unavailable, implement the documented fallback (user renders manually; orchestrator watches for the output file with timeout).
6. **Verification on the Vegas render**: run the existing verifier (click/discontinuity, level step, pacing, clipped-word using the compile-time word mapping) on the **Vegas-rendered** audio; compare against the reference renderer's prediction and report differences; sync check on beep/flash if test media is used.
7. **Bounded fix loop** (default 2 iterations, config): on failure, compile adjusted ops (for example wider crossfade at a failing join, widen padding, drop a cut that fails twice), re-execute from the checkpoint, re-render, re-verify. Every fix is recorded; no fix loosens validation.
8. **Final render** via template, with sidecar `markers.csv`, `review.md`, `verify_report.json`, `run_manifest.json`.
9. **Failure handling**: executor crash, missing heartbeat, template missing, render timeout, working copy mismatch. Each produces a typed failure, leaves the working copy intact, and says what to do next.
10. **Project hygiene**: refuse non-copy projects, refuse unsaved dirty original (explain), record original hash before/after, never modify the original.

### Out of scope
LLM planner, speakers beyond single/multitrack from earlier work, subtitles, transitions, SFX, UI beyond CLI, performance optimization.

## DELIVERABLES

Runner, approval flow, Vegas render integration with fallback, verify-on-Vegas-render, fix loop, docs (`docs/PIPELINE.md` with the state machine and artifacts per stage), eval additions (applied metrics on the Vegas-rendered result), `docs/HUMAN_TESTS_M4.md` (run the pipeline on TP-01 and on a 2 to 5 minute real clip, listen at every join, compare outputs, test reject/approve, test stop and recovery), and updated `README`.

## ACCEPTANCE CRITERIA

1. Standard checks pass; Vegas-dependent steps are covered by `FakeExecutor` tests plus the human checklist.
2. `run-job` completes a dry-run end to end against `FakeExecutor` and produces every artifact; each stage's typed failure is tested.
3. Approving a subset of cuts produces ops that contain exactly that subset (test).
4. The fix loop terminates within its cap, never exceeds it, records each fix, and a test shows a failing join being repaired by a wider crossfade.
5. The verifier runs on rendered audio from a file (not only the in-memory renderer); a test uses an externally produced WAV to prove it.
6. Original project file hash and media hashes are identical before and after in every test and in the manifest.
7. Resume works: killing the run after each stage and restarting continues without recomputing cached stages (test).
8. `HUMAN_TESTS_M4.md` complete with expected measurements and a results template for T1.
9. No tracked file contains private paths or content; docs and contracts consistent.
10. Phase commits made; no push.

## HUMAN VERIFICATION AFTER THIS PROMPT

You run TP-01 and one real short clip: measured join metrics within thresholds, no audible clicks, sync correct, undo restores, kill-and-resume works. Report results through T1.

## WORK PLAN

A: state machine and resume. B: markers, approval. C: render integration with fallback. D: verify-on-render and fix loop. E: failure handling and hygiene. F: docs and human checklist. G: final verification and report.

## STOP AND ASK IF

The decision memo marks render, undo, or gap-closing as unresolved; any step would touch the original project; the fix loop would need to relax a validation rule.

## FINAL REPORT

Per Section 13 plus: pipeline diagram, failure-code table, metrics table (planner vs applied vs Vegas-rendered), and what to adjust before Prompt 05.

=== PROMPT END ===

=== COMPLETION ===
Date: 2026-10-07
Implementation commit: 2788809
Documentation commit: 720b174
Privacy-gate fix: 83e892a
Status: Done with assumptions for the available offline scope; real VEGAS execution and rendered-result acceptance remain unverified.
Summary: Added a resumable offline runner with exact per-cut approval, fakeable render/executor interfaces, checkpointed repair re-execution, disk-based WAV verification, source integrity records, and a bounded manual-render watcher. No VEGAS or LLM endpoint was run.
Assumptions and revisit items: RV-001, RV-002, RV-003, RV-004.
