# Prompt Run Progress

Use this file to resume the attached prompt run; `REVISIT.md` is the source of open assumptions and human checks.

## Current state

- Current goal: 07 — Catalog, Transitions, Sound Effects, Effects.
- Current phase: Goal 07 phase A — deterministic catalog builder, tag policy, schema update, and disabled-key planner filter are implemented; checks passed and the phase commit is next.
- Last completed Goal 06 completion commit: b8bab7e; status follow-up 209f95c. Both are pushed; local `main` and `origin/main` matched at 209f95c after push.
- Goals completed in this run: 04, 05, and 06 — done with assumptions; origin/main includes their completion commits.
- Goals blocked: 01b–03 — source prompts and prerequisite evidence are missing (RV-003); no claim of completion.
- Retry counters: Goal 05 had one targeted timeout-test repair, one ruff repair cycle, and one mypy repair cycle; all were fixed and rerun. Goal 06 post-archive docs-check first caught two missing RV/path references; both were fixed and final docs-check/revisit-check passed. Goal 06 unit suite: 141 passed, 1 skipped (FFmpeg test).
- Next action: finish phase A verification and commit; then implement phase B, the local license-aware SFX indexer. Do not read local secret config, download tools/assets, or enable unprobed Vegas operations.

## Ten-line plan for goal 07

1. Re-read the complete Goal 07 prompt and inspect the catalog, EDL, ops, compile-report contracts, compiler, planner, executor boundary, and VQ-04/05/06/17/18 evidence.
2. Record the missing G4 SFX library/transition allowlist and absent Vegas/FFmpeg runtime evidence as RV-009/RV-010 before implementation.
3. Build deterministic collision-safe catalog keys, tag-file generation/merge, enabled filtering, full internal catalog validation, and a strict model-summary allowlist.
4. Add a local SFX indexer with format/sample-rate checks, license-required disabled entries, stable identity keys, and an injectable FFmpeg loudness adapter; never download or copy assets.
5. Add pure compiler rules for transition/SFX/effect eligibility, frame placement, gain ceilings, speech-peak avoidance, density limits, and per-item outcomes.
6. Add a capability contract and make the compiler fail closed when the executor does not advertise an operation; keep real Vegas mutation ops disabled until their VQs have E0 evidence.
7. Extend deterministic baseline planning and verification only where the existing contracts provide IDs and the safety rules allow it.
8. Add offline fixtures/tests and `HUMAN_TESTS_M7.md`; label fake FFmpeg/catalog evidence and live Vegas/SFX claims accurately.
9. Update schemas, specs, fixtures, consumers, CHANGELOG, decisions, Vegas notes, architecture, setup, README, evals, and revisit run order; run all available checks and synthetic eval.
10. Self-audit, archive the sanitized prompt, run privacy checks, commit phases A–G, push only after remote ancestry is confirmed, then start Goal 08.

## Goal 07 phase A record

- Preflight: Goal 07 prompt reread; missing G4 transition allowlist and licensed SFX directory recorded as RV-009/RV-010 before implementation. `config.local.json` was not read. `assets/sfx` is absent.
- Implementation: deterministic catalog builder/keys, full-list hash, human JSON tag template and strict merge, disabled-entry filtering in both summary and planner, safe tag/context patterns, and a C# dumper JSON comma fix without adding Vegas API calls. Catalog contract is 1.1.0.
- Synthetic CLI smoke: `python tasks.py catalog-build runs/goal07/catalog_dump.json --output-dir runs/goal07/output` created three internal entries; all were disabled and the summary was empty. The files are under ignored runs.
- `python tasks.py lint` — passed; ruff, formatting, and strict mypy.
- `python tasks.py schemas` — passed; 11 schemas and 45 fixtures.
- `python tasks.py docs-check` — passed after correcting one pseudo-path in this plan; links, paths, versions, changelog, privacy, and revisit checks agree.
- `python tasks.py revisit-check` — passed; 10 registered items.
- `.venv\Scripts\python.exe -m pytest tests\unit\test_catalog_builder.py tests\unit\test_planning_compile_eval.py::test_llm_planner_uses_loopback_fake_and_rejects_remote -q --basetemp=.pytest-temp-goal07` — passed; 11 tests. This includes the planner request filter for disabled keys.
- No Vegas, live endpoint, SFX download, or user media was used.
- Not run: `python tasks.py setup` because it may install packages and Goal 07 forbids downloads; C# compile-only check because `csc.exe` is not available on PATH.

## Ten-line plan for goal 06

1. Read the entire prompt and audit the subtitle decision, VQ-09/VQ-10 status, words/speakers/EDL/ops contracts, and architecture section 13.
2. Record missing style-interview/probe and local FFmpeg gates in REVISIT.md before implementation; do not launch Vegas or download tools/fonts.
3. Add captions 1.0.0 as a closed, frame-only output contract with source word IDs and safe confidence/style metadata.
4. Build deterministic per-speaker caption lines with configured limits, omissions, emphasis IDs, grapheme-safe splitting, and no same-track overlaps.
5. Remap source-word timing through compiled kept ranges and test cuts, gaps, and one-frame sync using rational frame rates.
6. Resolve colors solely from speakers.json; report contrast and low-confidence flags; export and round-trip safe SRT and ASS.
7. Implement a renderer interface with complete sidecar output and an ASS/FFmpeg adapter that reports missing local binaries safely; do not implement unprobed Vegas mutations.
8. Add offline verification and human checklist coverage; preserve VQ-09/VQ-10 as UNVERIFIED/PARTIAL pending their real probes.
9. Update schema, prose contract, consumers, CHANGELOG, architecture, setup, eval, README, and Progress; run available checks and synthetic eval.
10. Self-audit, archive the sanitized prompt, run final privacy checks, commit each phase, push when remote is an ancestor under the master authorization, then continue to Goal 07.

## Ten-line plan for goal 05 (historical)

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
| Standard checks | Met | setup, lint, unit (126 passed), schemas (10 schemas / 44 fixtures), docs-check, revisit-check, eval; see command record below. |
| Token privacy | Met in the current offline path | Synthetic HF-token-shaped value stays out of enrollment CLI output; child environment filters HF_TOKEN; redaction helper and artifact-shape checks pass. Final independent privacy scan remains part of the push gate. |
| Multitrack attribution and bleed | Met for synthetic fixtures | Track map and unmapped Unknown N tests; bleed fixture keeps both words and downranks the weaker candidate. |
| Diarized assignment and overlap | Met for a deterministic fixture | Turn-overlap fixture selects the dominant turn, sets overlap, halves confidence, and surfaces the range. |
| Enrollment quality and embedding-only storage | Met with fake encoder | Too-short and inconsistent samples are rejected; saved profile contains embedding metadata and no WAV. Real encoder availability remains RV-005. |
| Unknown question, confirmed answer, and timeout | Met for CLI/core flow | Question shape, confirmed map diff, confidence preservation, 24-hour timeout warning, Unknown N retention, and planning gate have unit coverage. |
| Low-confidence report | Met | Synthetic bleed and overlap cases appear as ID/time ranges with reason, without transcript text. |
| Real-model benchmark | ASSUMED (RV-005, RV-006) | G2 token/model terms/approved samples are absent; no model card was fetched or checkpoint downloaded. Exact human test is docs/HUMAN_TESTS_M5.md. |
| No tracked secrets, private paths, or voice data | Met after final gate | Root speakers.json and voices/ are ignored; prompt will be sanitized and independent scan repeated before push. |
| Contract and phase commits | Met | words=2.1.0 and speakers=1.1.0 schemas, prose specs, fixtures, consumers, and changelog agree; implementation phases A–E and documentation phase F are committed. |

## Goal 05 self-audit (self-audit, not independent)

| T3 check | Result | Evidence |
|---|---|---|
| Reproduce claims | Pass | setup, lint, 126 unit tests, schemas, docs-check, revisit-check, eval, and enroll/answer-speaker help were run. |
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
- python tasks.py test — passed; 126 unit tests.
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

## Goal 06 acceptance mapping

| Criterion | Status | Evidence or revisit |
|---|---|---|
| 1. Standard checks and Vegas behavior boundary | Met for available offline checks | `python tasks.py lint`, `test` (141 passed, 1 skipped), `schemas` (11 schemas / 45 fixtures), `docs-check`, `revisit-check`, and synthetic `eval` passed. Vegas behavior remains unverified and no Vegas was run. |
| 2. Frame-valid, single-speaker, non-overlapping captions | Met for deterministic synthetic fixtures | Caption contract and seeded layout tests cover integer frames, positive bounds, speaker grouping, and same-speaker overlap rejection. |
| 3. Cut remapping within one frame | Met for synthetic compile mappings | Tests map words through removed intervals with exact rational frame boundaries and check the first retained word alignment. |
| 4. SRT/ASS round-trip and escaping | Met | Serializer parse-back tests preserve text/timing and exercise braces, backslashes, and line breaks. |
| 5. Speaker-only colors and EDL color rejection | Met | `speakers.json` resolves colors; validator rejects unknown EDL properties, including color-like fields. |
| 6. Low contrast and low confidence reporting | Met | Unit tests cover warnings and review output. |
| 7. C# 5 executor text ops | ASSUMED / deferred under RV-007 | No Vegas text operations were added because VQ-09/VQ-10 do not provide probe evidence. This preserves the documented safety gate; a disposable-project probe and style decision are required before implementation. |
| 8. Renderer and FFmpeg generated-clip burn-in | Sidecar renderers met; burn-in ASSUMED under RV-008 | Renderer interface and sidecar-only path are implemented. Generated-clip FFmpeg test was skipped because local `ffmpeg`/`ffprobe` are unavailable. |
| 9. Human checklist | Met as a document; human execution ASSUMED under RV-007/RV-008 | `docs/HUMAN_TESTS_M6.md` includes expected outcomes and a results template; no human clip review was available. |
| 10. Contract, documentation, privacy, and phase commits | Met after final privacy gate | captions=1.0.0 schema/spec/fixture and consumers agree; phase commits A–F are recorded. Prompt archival and completion commit are this phase. |

## Goal 06 self-audit (self-audit, not independent)

| T3 check | Result | Evidence |
|---|---|---|
| Reproduce claims | Pass for available commands; setup not run | `lint`, `test`, `schemas`, `docs-check`, `revisit-check`, `eval`, and CLI help ran. `setup` was skipped because the pinned setup may install packages and the goal forbids downloads. |
| Acceptance criteria | Pass or ASSUMED; see RV-007/RV-008 | See the 10-row mapping above. |
| Hard rules | Pass | No Vegas, endpoint, download, user media, credentials, or local secret config touched; dry-run default is unchanged. |
| Contract consistency | Pass | captions 1.0.0 schema, prose, fixtures, producer, validators, and docs agree. |
| Vegas claims | Pass | VQ-09 is compile-only/partial and VQ-10 remains unverified; text operations are deferred under RV-007. |
| Diff review | Pass | No new dependency, network path, prompt instruction, loosened threshold, or validation bypass. |
| Privacy scan | Pass | `docs-check` and an independent pattern scan of 155 tracked/staged files passed after prompt archival; no private paths, token patterns, or media filenames were found. The archived prompt contains no transcript content. |
| Docs honesty | Pass | README, subtitle guide, evals, limits, revisit entries, and human checklist distinguish synthetic evidence from unrun runtime checks. |
| Human steps | Pass | `docs/HUMAN_TESTS_M6.md` documents two-speaker timing/color/readability review and performance check; not run. |
| Top risks | Pass | (1) Vegas style/text behavior unknown (RV-007); (2) FFmpeg burn-in untested locally (RV-008); (3) real-speech sync/readability/performance has no human evidence (RV-007). |

## Goal 06 command record

- `python tasks.py lint` — passed; ruff, format, and strict mypy.
- `python tasks.py test` — passed; 141 passed, 1 skipped (FFmpeg/ffprobe burn-in; RV-008).
- `python tasks.py schemas` — passed; 11 schemas and 45 fixtures.
- `python tasks.py docs-check` — passed after prompt archival; links, paths, contract versions, changelog, privacy scan, and revisit markers agree.
- `python tasks.py revisit-check` — passed; eight registered revisit items.
- `python tasks.py eval` — passed synthetic caption plumbing; 300 generated and round-tripped caption events; layout 41.107 ms and sidecar export 10.017 ms in that run. These are not Vegas or real-speech measurements.
- `python tasks.py compile --help`, `run-job --help`, and `burn-captions --help` — passed.
- `python tasks.py setup` — not run; setup may install packages and Goal 06 forbids downloads.
- Independent privacy scan — passed for 155 tracked/staged files; no target patterns or media filenames found.
- Not run: Vegas, real speech/listening, style-interview gate, FFmpeg end-to-end burn-in, and live endpoint; see RV-003, RV-007, and RV-008.
