# Prompt Run Progress

Use this file to resume the attached prompt run; `REVISIT.md` is the source of open assumptions and human checks.

## Current state

- Current goal: 04 — Closed-Loop Cut Pipeline Through Vegas.
- Current phase: goal 04 phase G; offline code, docs, evaluation record, and standard checks are complete. The code/schema commit and docs/completion commits remain, followed by privacy-gated push. Vegas runtime and real-speech acceptance remain open human gates.
- Last commit: `0eb9b1c` (`docs: clarify M1 status and remaining work`); goal 04 implementation has not yet been committed.
- Goals completed in this run: none yet; goal 04 is ready to archive after review and the final privacy gate.
- Goals blocked: none yet; missing prerequisites are being handled under the supplied offline-assumption rules.
- Retry counters: final check cycles 0; push attempts 0.
- Next action: create the code/schema commit, then the documentation and prompt-completion commits; run the privacy gate before pushing, then start prompt 05.


## Goal 04 acceptance mapping

| Criterion | Status | Evidence or revisit |
|---|---|---|
| Standard checks | Met | `python tasks.py setup`, `lint`, `test` (112 passed), `schemas` (10 schemas and 44 fixtures), `docs-check`, `revisit-check`, and `eval` completed. |
| End-to-end runner and artifacts | Met with fake renderer | `test_run_job_writes_review_verify_and_integrity_artifacts`; `test_approval_recompiles_exact_approved_cut_subset`; default CLI renderer end-to-end remains open because FFmpeg is absent (RV-004). |
| Exact per-cut approval subset | Met | Approved ops contain c1 and exclude c2; all-rejected case emits no delete operation. |
| Bounded crossfade repair | Met with fake signal/adapter | The synthetic join fails then passes after widening from 20 ms to 40 ms; review mode restores the pre-execution checkpoint and re-executes, cap is bounded at two, and thresholds are unchanged. |
| File-based verification | Met with fake WAV | Test confirms verifier reads a written WAV artifact from disk. |
| Source project/media hashes | Met offline | Run manifest records per-file hashes; E2E fixture checks source project, media, and audio remain unchanged. |
| Resume across stages | Met with fake adapters | Parameterized pause/resume test covers all eleven stage boundaries; a fake executor edit survives resume only when the checkpoint hash matches. |
| Human M4 acceptance | ASSUMED | Checklist and results template exist; live Vegas/render/listening observations remain open under RV-001 and RV-002. |
| Privacy and contract consistency | Met after final gate | No new dependencies; run_manifest 1.1.0 schema/spec/fixtures/consumer updated together. Repeat privacy scan after prompt archival. |
| Phase and completion commits | In progress | Code/schema commit, documentation phase, prompt footer, completion commit, and authorized push remain. |

## Goal 04 self-audit (self-audit, not independent)

| T3 check | Result | Evidence |
|---|---|---|
| Reproduce claims | Pass | Setup, lint, tests, schemas, docs-check, revisit-check, eval, and both CLI help commands were run. |
| Acceptance criteria | Pass or ASSUMED | See the mapping above; human evidence is explicitly RV-001/RV-002. |
| Hard rules | Pass | No Vegas or endpoint run; dry-run default preserved; code reads original project/media and writes only under the job directory. |
| Contract consistency | Pass | run_manifest 1.1.0 schema, prose, fixtures, referential checks, CLI producer, and changelog agree. |
| Vegas claims | Pass | Runtime is disabled; no VQ is marked VERIFIED; fake results are identified as ASSUMED (RV-001). |
| Diff review | Pass | No dependency, network call, threshold reduction, prompt change, or validation bypass was introduced. |
| Privacy scan | Pending final gate | `docs-check` includes its privacy scan; independent pattern scan runs after prompt archival and staging. |
| Documentation honesty | Pass | README, pipeline, executor guide, known limits, and roadmap distinguish sidecars/reference rendering from Vegas behavior. |
| Human steps | Pass | M4 checklist contains setup, review, approval, working-copy, stop/resume, render, metrics, and results sections. |
| Top risks | Pass | (1) Vegas mutation/undo/stop remain unverified (RV-001); (2) real-speech quality and synthetic eval failure remain open (RV-002); (3) missing predecessors remain unavailable (RV-003); default FFmpeg renderer not run (RV-004). |

## Prompt inventory

- Available in the repository: goals 04–13, T2, and T3.
- Missing from the checkout: goals 01b–03, prompt-pack README, T1, HUMAN_GATES.md, STYLE_INTERVIEW.md, HUMAN_TESTS_M3.md, `docs/VEGAS_DECISIONS.md` (added provisionally for goal 04).
- No `completed prompts/` folder or prior `PROGRESS.md` / `REVISIT.md` existed at the start. The project README is not a prompt-order README.
- Continue with available goals in numeric order. Record assumptions for unavailable predecessor artifacts; do not invent their contents or claim their gates passed.

## Ten-line plan for goal 04

1. Record absent prerequisites and Vegas runtime assumptions in `REVISIT.md` before implementation.
2. Add a provisional decision memo that selects low-dependency fallbacks and lists the probes needed to enable runtime alternatives.
3. Inspect the existing planner, compiler, verifier, artifact, CLI, and job-stage boundaries.
4. Add a resumable job state machine with hash-validated stage artifacts and typed stage failures.
5. Add dry-run review markers, per-cut approval, and deterministic recompilation of the approved subset.
6. Add fakeable executor and render interfaces with working-copy path confinement and source-integrity checks.
7. Verify rendered audio from disk and add a bounded, auditable repair loop without relaxing thresholds.
8. Add regression tests, pipeline documentation, and the M4 human-test checklist.
9. Run available standard checks, eval, and a self-audit; document unavailable live checks honestly.
10. Sanitize and archive the completed prompt, commit the goal, run the privacy gate, and attempt the authorized push.
