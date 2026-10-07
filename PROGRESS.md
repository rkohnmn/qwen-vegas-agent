# Prompt Run Progress

Use this file to resume the attached prompt run; `REVISIT.md` is the source of open assumptions and human checks.

## Current state

- Current goal: 05 — Speaker Attribution and Profiles.
- Current phase: phase A committed as d52f812; phase B multitrack and pause integration is ready for its commit. Phases C–G follow.
- Last commit: d52f812 (goal 05 phase A contracts and attribution core); origin/main was updated through goal 04.
- Goals completed in this run: 04 — done with assumptions; completion commit f7e88d0, pushed to origin/main. Goal 05 acceptance is mapped below and still needs its phase/archive commits.
- Goals blocked: 01b–03 — source prompts and prerequisite evidence are missing (RV-003); no claim of completion.
- Retry counters: Goal 05 had one targeted timeout-test repair, one ruff repair cycle, and one mypy repair cycle; all were fixed and rerun. Final unit suite: 125 passed. Push attempts for goal 05: 0.
- Next action: commit phase B integration, then complete overlap/reporting, CLI enrollment and confirmation, documentation, and final archive/privacy/push phases.
## Ten-line plan for goal 05

1. Re-read the full goal and inspect architecture, word/speaker contracts, security, setup, evaluation, config, ASR, and CLI boundaries.
2. Record the missing predecessor and G2 model/token/sample gates in `REVISIT.md` before implementation; do not read local secret config or download model files.
3. Add automatic mode selection for mapped, mixed, partial, and single audio tracks with explicit overrides.
4. Add multitrack word labeling and conservative cross-track energy comparison so likely bleed stays visible at reduced confidence.
5. Add a pluggable diarization-turn matcher with overlap marking, confidence reduction, and no implicit reassignment.
6. Add local-only profile quality checks, cosine matching, unknown IDs, and a CLI enrollment entry point that fails safely when its encoder is unavailable.
7. Add typed `ask_user` question creation, confirmed speaker-map updates, timeout handling, and low-confidence reporting.
8. Update contracts only where needed, with schemas, fixtures, consumers, changelog, decisions, architecture, setup, security, and speaker docs in sync.
9. Run setup, lint, unit, schemas, docs-check, revisit-check, and eval; record exact results and unavailable real-model evidence.
10. Self-audit against T3, archive the sanitized goal prompt, privacy-gate, commit, push when origin is an ancestor, and continue to goal 06.


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
| Phase and completion commits | Met | Implementation 2788809, docs 720b174, privacy fix 83e892a, and completion/push commit f7e88d0 are recorded; origin/main was an ancestor and push succeeded. |

## Goal 04 self-audit (self-audit, not independent)

| T3 check | Result | Evidence |
|---|---|---|
| Reproduce claims | Pass | Setup, lint, tests, schemas, docs-check, revisit-check, eval, and both CLI help commands were run. |
| Acceptance criteria | Pass or ASSUMED | See the mapping above; human evidence is explicitly RV-001/RV-002. |
| Hard rules | Pass | No Vegas or endpoint run; dry-run default preserved; code reads original project/media and writes only under the job directory. |
| Contract consistency | Pass | run_manifest 1.1.0 schema, prose, fixtures, referential checks, CLI producer, and changelog agree. |
| Vegas claims | Pass | Runtime is disabled; no VQ is marked VERIFIED; fake results are identified as ASSUMED (RV-001). |
| Diff review | Pass | No dependency, network call, threshold reduction, prompt change, or validation bypass was introduced. |
| Privacy scan | Pass; repeat before push | `docs-check` and an independent scan passed after prompt archival; one pre-existing dummy bearer string was split into fragments and committed as 83e892a. |
| Documentation honesty | Pass | README, pipeline, executor guide, known limits, and roadmap distinguish sidecars/reference rendering from Vegas behavior. |
| Human steps | Pass | M4 checklist contains setup, review, approval, working-copy, stop/resume, render, metrics, and results sections. |
| Top risks | Pass | (1) Vegas mutation/undo/stop remain unverified (RV-001); (2) real-speech quality and synthetic eval failure remain open (RV-002); (3) missing predecessors remain unavailable (RV-003); default FFmpeg renderer not run (RV-004). |

## Goal 05 acceptance mapping

| Criterion | Status | Evidence or revisit |
|---|---|---|
| Standard checks | Met | setup, lint, unit (125 passed), schemas (10 schemas / 44 fixtures), docs-check, revisit-check, eval; see command record below. |
| Token privacy | Met in the current offline path | Synthetic HF-token-shaped value stays out of enrollment CLI output; child environment filters HF_TOKEN; redaction helper and artifact-shape checks pass. Final independent privacy scan remains part of the push gate. |
| Multitrack attribution and bleed | Met for synthetic fixtures | Track map and unmapped Unknown N tests; bleed fixture keeps both words and downranks the weaker candidate. |
| Diarized assignment and overlap | Met for a deterministic fixture | Turn-overlap fixture selects the dominant turn, sets overlap, halves confidence, and surfaces the range. |
| Enrollment quality and embedding-only storage | Met with fake encoder | Too-short and inconsistent samples are rejected; saved profile contains embedding metadata and no WAV. Real encoder availability remains RV-005. |
| Unknown question, confirmed answer, and timeout | Met for CLI/core flow | Question shape, confirmed map diff, confidence preservation, 24-hour timeout warning, Unknown N retention, and planning gate have unit coverage. |
| Low-confidence report | Met | Synthetic bleed and overlap cases appear as ID/time ranges with reason, without transcript text. |
| Real-model benchmark | ASSUMED (RV-005, RV-006) | G2 token/model terms/approved samples are absent; no model card was fetched or checkpoint downloaded. Exact human test is docs/HUMAN_TESTS_M5.md. |
| No tracked secrets, private paths, or voice data | Met after final gate | Root speakers.json and voices/ are ignored; prompt will be sanitized and independent scan repeated before push. |
| Contract and phase commits | Met for contract consistency; phase commits pending | words=2.1.0 and speakers=1.1.0 schemas, prose specs, fixtures, consumers, and changelog agree; commits are the remaining goal work. |

## Goal 05 self-audit (self-audit, not independent)

| T3 check | Result | Evidence |
|---|---|---|
| Reproduce claims | Pass | setup, lint, 125 unit tests, schemas, docs-check, revisit-check, eval, and enroll/answer-speaker help were run. |
| Acceptance criteria | Pass or ASSUMED | Mapping above; only real-model/hardware claims remain under RV-005 and RV-006. |
| Hard rules | Pass | No Vegas, LLM endpoint, model download, or user media run; dry-run default remains; auto speaker selection stays opt-in. |
| Contract consistency | Pass | words=2.1.0 and speakers=1.1.0 schemas, specs, examples, fixtures, producers, consumers, and changelog agree. |
| Vegas claims | Pass | No Vegas-facing code changed and no VQ is marked VERIFIED. |
| Diff review | Pass with repair | Found and repaired an invalid run_compile insertion and strict typing/test issues; final lint, tests, and docs checks pass. |
| Privacy scan | Pass; repeat before push | docs-check passed; HF token runtime sentinel and child-environment checks pass. Sanitize Prompt 05 and run independent tracked/staged scan before push. |
| Documentation honesty | Pass | Speaker guide, setup/security, known limits, eval, architecture, roadmap, changelog, and README identify synthetic-only evidence and open model gates. |
| Human steps | Pass | docs/HUMAN_TESTS_M5.md specifies G2, one multitrack clip, one mixed clip, and aggregate metrics. |
| Top risks | Pass | (1) no accepted local model/backend (RV-005); (2) bleed, similarity, overlap, and enrollment thresholds are not calibrated (RV-006); (3) timeout is checked on the next CLI plan/compile invocation rather than a background scheduler. |

## Goal 05 command record

- python tasks.py setup — passed; all pinned development packages were already installed.
- python tasks.py lint — passed; ruff, formatting, and strict mypy clean.
- python tasks.py test — passed; 125 unit tests.
- python tasks.py schemas — passed; 10 schemas and 44 fixtures.
- python tasks.py docs-check — passed; links, paths, versions, changelog, privacy scan, and revisit marker check.
- python tasks.py revisit-check — passed; all six registered items resolve.
- python tasks.py eval — passed as an offline synthetic run; speaker fixture scores are 2/2 multitrack, 1/1 diarized, 1/1 overlap, 1/1 bleed flag, and 1/1 unknown detection. This is not a model benchmark.
- CLI help for dry-run, enroll, and answer-speaker — passed.
- Not run: real-model benchmark, labeled real-speech review, Vegas, and endpoint integration; see RV-001, RV-002, RV-005, and RV-006.

## Prompt inventory

- Available in the repository: goals 05–13, T2, and T3; goal 04 is under `completed prompts/`.
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
