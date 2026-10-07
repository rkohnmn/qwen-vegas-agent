# Prompt 07: Catalog, Transitions, Sound Effects, Effects (Goal Prompt)

**Prompt version:** 1.0.0
**Depends on:** Prompt 04 complete (06 helpful but not required). `docs/VEGAS_DECISIONS.md` covers transitions (VQ-05), SFX gain (VQ-18), OFX params (VQ-17).
**Human gate before sending:** G4 done: starter SFX folder with licenses noted; list of acceptable and unacceptable Vegas transitions (rough).
**Machine:** laptop; Vegas for human verification.

=== PROMPT START ===

## STANDING RULES

- Follow `AGENTS.md`; Sections 7 and 15 are inviolable. Docs are the source of truth. If sources conflict, stop and report.
- **Model chooses by catalog key; code chooses placement, durations, gains, and GUIDs.** Plugin GUIDs and file paths never reach the model or EDL.
- You never run Vegas. Never modify user media or the Vegas install directory. Compile-only is `EC`; E0 needs a human result.
- Contract changes follow `AGENTS.md` Section 8. Pin and justify dependencies. Commit per phase, no push. Report per Section 13 with an acceptance checklist.

## GOAL

Give the planner a **real, closed vocabulary** of transitions, effects, and sound effects, and let the compiler and executor apply them precisely and safely.

## READ FIRST

`AGENTS.md`, `ARCHITECTURE.md` (8.5, 14, 11.2), `docs/VEGAS_DECISIONS.md`, `docs/VEGAS_NOTES.md` (VQ-04, 05, 06, 17, 18), the `catalog`, `edl`, `ops` contracts, `docs/EXECUTOR.md`.

## INPUTS

```
SFX_LIBRARY_DIR = <local folder outside git: audio files plus optional sidecar .json with tags and license>
DEFAULT_ALLOWED_TRANSITIONS = taken from the human's rough list in config.local.json, else the baseline set in the decision memo
```

## PERMISSIONS

- No downloads. ffmpeg local for loudness measurement (`ebur128`).
- Optional text-embedding model for semantic SFX search is **not** pre-approved; use tag/keyword search unless the human approves a specific model in a follow-up.

## SCOPE

### In scope
1. **Catalog dumper (C#)**: finalize from probe `P`-series and `CatalogDump`: transitions, video FX, audio FX, text presets, with name, unique ID, OFX flag, parameter schema where proven (VQ-17), preset names; plugin list hash; recursion over folders. Compile-checked (`EC`).
2. **Catalog builder (Python)**: ingest dumper output, assign **deterministic collision-safe keys** (`category.normalized_name.shorthash`), merge with a **human-editable tag file** `catalog_tags.yaml` (or JSON): tags like `soft`, `hard`, `dialogue_safe`, `stylized`, default duration, allowed contexts, `params_mode` (`params`, `preset_only`, `defaults_only`), `enabled`. First run **generates a starter tag file** from names and marks everything `enabled: false` except the allowed list so the human opts in. Produce the full internal catalog and the **model-facing summary** (keys, tags, durations; no GUIDs, no paths).
3. **SFX library indexer** (`python tasks.py sfx-index <dir>`): scan, validate formats and sample rate, measure integrated loudness and peak with ffmpeg, duration, fingerprint hash, **require license metadata** (missing license marks the file `disabled` with a warning), tags from sidecar or filename conventions, generate keys `sfx.<name>`, write `sfx_index.json` (gitignored if it contains private info). Keyword/tag search function for the planner's tool rounds.
4. **Compiler rules** for transitions, SFX, and effects, all configurable and tested:
   - Transitions: only where the EDL requests them at a cut id or gap id; allowed only if the entry is `dialogue_safe` for cuts inside continuous speech (unless the style config permits); minimum clip length; maximum per minute; duration clamp from catalog defaults; refuse overlap that would require changing audio sync (use the method from the decision memo); audio join stays a short crossfade unless otherwise justified.
   - SFX: position from `at_word` plus `offset_hint`; gain relative to local loudness (config), ceiling, **avoid speech peaks** by default (shift within a small window or reduce gain, recorded in compile report); ducking optional via envelope if the decision memo supports it; maximum per minute; no overlap of two SFX unless allowed.
   - Effects: apply only catalog entries with proven parameter support; reject parameters not in the entry's schema.
   - Everything is snapped to frames; every placement and every rejection appears in `compile_report` with `applied/adjusted/rejected`.
5. **Executor ops** (`add_transition`, `add_audio_event`, `set_gain`, `apply_fx`) per the decision memo; batching, undo, heartbeat, stop file; unsupported mechanisms return typed `unsupported_op` and the compiler must not emit them (capability handshake: the executor reports supported ops in a `capabilities.json` that the compiler reads).
6. **Baseline planner extension** (deterministic, for testing and fallback): propose transitions at long-gap topic boundaries using allowed keys, and SFX at configured triggers (for example topic changes) with rate limits; label confidence low; fully optional by config.
7. **Verification**: transition frame checks (sample frames across a transition render for glitches via simple luminance/continuity metrics, best effort), loudness and headroom check of SFX against speech, density limits, license check in the final manifest (list every SFX used with its license).
8. **Docs**: `docs/CATALOG.md` (key rules, tag file format, how to enable transitions), `docs/SFX.md`, `HUMAN_TESTS_M7.md` (dump catalog, enable a handful of transitions, run a cut job with transitions, run SFX placement, listen and watch; test every enabled transition once on TP media; verify no A/V desync; verify SFX level).

### Out of scope
LLM prompt writing, vision, online asset downloads, music beds.

## ACCEPTANCE CRITERIA

1. Standard checks pass; Vegas-dependent behavior covered by fakes plus the human checklist.
2. Catalog keys are deterministic across runs and collision-free on a fixture with duplicate display names (test); GUIDs and paths never appear in the model-facing summary (test).
3. EDL referencing a disabled, missing, or non-dialogue-safe entry in a disallowed context is rejected or adjusted with a typed code (tests per case).
4. SFX indexer rejects unlicensed files by default, measures loudness within tolerance on generated tones of known level (test), and produces stable keys.
5. SFX placement avoids speech peaks on a synthetic case and records the adjustment (test); gain never exceeds the configured ceiling (property test).
6. Compiler never emits an op the executor's `capabilities.json` does not list (test).
7. All new executor code compiles in C# 5 mode (`EC`) with no network code.
8. `HUMAN_TESTS_M7.md` complete with expected outcomes and a results template for T1.
9. Contracts/docs versioned and consistent; no private data in tracked files; phase commits; no push.

## HUMAN VERIFICATION AFTER

Each enabled transition applies cleanly with correct duration and no desync; SFX positions and levels are right; nothing crashes Vegas.

## WORK PLAN

A: contracts, catalog builder, tag file. B: SFX indexer. C: compiler rules and tests. D: executor ops and capabilities. E: baseline planner extension, verification. F: docs and human checklist. G: final verification, report.

## STOP AND ASK IF

The decision memo marks transitions or gain as `DISPROVED` without a fallback; a rule would require the model to supply a number; SFX licenses cannot be recorded.

## FINAL REPORT

Per Section 13 plus: catalog statistics, enabled/disabled counts, parameterizable entries, SFX index summary, limits found, and prompt adjustments for 08.

=== PROMPT END ===

## Completion record

- Completed: 2026-10-07
- Status: Offline implementation complete with assumptions. No runtime executor operation is enabled; Vegas event-pair evidence, local FFmpeg/SFX evidence, and the runtime EDL prompt remain open under RV-009, RV-010, and RV-011.
- Phase commits: `037bb73`, `a169518`, `1a25cba`. See PROGRESS.md and the Git history for the Goal 07 documentation/completion commit.
- Checks: `python tasks.py lint`, `python tasks.py schemas` (12 schemas, 50 fixtures), `python tasks.py test` (174 passed, 2 skipped), `python tasks.py docs-check`, `python tasks.py revisit-check`, `python tasks.py eval` (synthetic only).
- Human verification: `docs/HUMAN_TESTS_M7.md` is complete; VEGAS, licensed-library, real FFmpeg tone, and C# compile-only checks were not run.
- Source prompt SHA-256 (UTF-8 text): `8ab88c338a47c9a592553f3c0a255f96f412fc2117bce5ac7b6daa39822385ef`
