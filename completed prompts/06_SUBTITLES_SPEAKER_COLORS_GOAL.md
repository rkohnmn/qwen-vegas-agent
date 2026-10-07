# Prompt 06: Subtitles with Speaker Colors (Goal Prompt)

**Prompt version:** 1.0.0
**Depends on:** Prompts 04 and 05 complete; `docs/VEGAS_DECISIONS.md` records the subtitle path.
**Human gate before sending:** the text/preset probes (VQ-09, VQ-10) were run and fed through T1; speaker colors and caption style decided (`STYLE_INTERVIEW.md` sections 5 and 6, even if rough).
**Machine:** laptop; Vegas for human verification.

=== PROMPT START ===

## STANDING RULES

- Follow `AGENTS.md`; Sections 7 and 15 are inviolable. Docs are the source of truth. If sources conflict, stop and report.
- Model chooses IDs, code chooses numbers. **The model never sees or sets colors**; colors come from `speakers.json` and are applied by code.
- You never run Vegas. Never modify user media or the Vegas install directory. Compile-only is `EC`; E0 needs a human result.
- Contract changes follow `AGENTS.md` Section 8. Commit per phase, no push. Report per Section 13 with an acceptance checklist.

## GOAL

Produce **speaker-colored, frame-synced subtitles** after cuts, through the path chosen in `docs/VEGAS_DECISIONS.md`, with always-available sidecar exports (SRT and ASS) and a verified sync and color check.

## READ FIRST

`AGENTS.md`, `ARCHITECTURE.md` (13), `docs/VEGAS_DECISIONS.md` (**subtitle path is authoritative**), `docs/VEGAS_NOTES.md` VQ-09/10, `docs/SPEAKERS.md`, `words`, `speakers`, `edl`, `ops` contracts.

## INPUTS

```
Reuse config.local.json.
CAPTION_STYLE = defaults from STYLE_INTERVIEW.md answers, if provided, else the defaults in ARCHITECTURE.md 13.2
```

## PERMISSIONS

No downloads. Fonts: use only fonts already installed or free fonts the human places in a local `assets/fonts/` with license noted. ffmpeg local for burn-in fallback.

## SCOPE

### In scope
1. **New contract `captions` 1.0.0**: caption id, speaker key, text, start/end **frames in the edited timeline**, style key, emphasis spans by word id, confidence flags (for example `low_speaker_conf`), source word ids. Contract process applies.
2. **Line builder** (pure code, deterministic): split at speaker changes; max characters per line, max lines, reading-speed ceiling (CPS), minimum duration, hold time; prefer breaks at punctuation and clause boundaries; honor EDL `break_hints` and `omit_ranges`; handle filler-word display policy from config; profanity policy from config; emphasis from EDL by word ids; non-Latin and right-to-left safe splitting (no breaking inside grapheme clusters); never overlap captions of the same track.
3. **Time remapping**: build captions in **source time then map through the compiled cuts** to the edited timeline using the compile mapping, snapping to frames; captions spanning a removed gap are split or trimmed predictably; a test proves sync to the aligned word within one frame after cuts.
4. **Color assignment**: from `speakers.json` only; contrast check against configured outline/box; warnings for low contrast; unknown speakers use `unknown_palette`; low-confidence attribution is rendered but flagged in the report and `review.md`.
5. **Sidecar exports**: `.srt` (no color, plain), `.ass` (speaker colors as styles, emphasis as override tags, safe escaping), optional `.vtt`. Round-trip tests parse the files back.
6. **Vegas path per decision memo**, behind one interface `CaptionRenderer`:
   - `DirectColor`: create text events and set text/color via the mechanism proven in VQ-09 (RTF or parameter).
   - `PresetPerSpeaker`: apply per-speaker presets by name (a setup step generates a `presets_needed.md` listing the preset names, fonts, sizes and colors for the human to create once in Vegas).
   - `AssBurnIn`: after the final render, burn captions with ffmpeg using the generated ASS (config for font dir and hardware encoder if any).
   - `SidecarOnly`.
   The chosen renderer is configured; the others remain available and tested to the extent possible offline.
7. **Executor ops**: implement `add_text_event` and `set_text_style` in the executor (batched, undo-wrapped, heartbeat), compile-checked as `EC`; scale to 300+ events with measured batch sizes from the probes.
8. **Verification**: subtitle sync error (re-align audio of the rendered/edited result and compare caption bounds, report mean and max ms), speaker/color consistency (caption speaker equals majority speaker of its words), caption density and CPS violations, readable-contrast warnings. If a frame can be rendered, sample frames at caption times and check the expected color is present in the caption region (best effort, documented tolerance).
9. **Pack and planner interplay**: EDL `subtitles` section validated (style key exists, emphasis ids exist, `omit_ranges` ids exist); no color or time fields.
10. **Docs**: `docs/SUBTITLES.md`, setup steps (fonts, presets), updates to `ARCHITECTURE.md` 13, `HUMAN_TESTS_M6.md` (create presets if needed; run on a clip with two speakers; check colors, timing, readability on a phone-size preview; compare Vegas-rendered captions to ASS burn-in; test 300 captions performance).

### Out of scope
LLM prompt changes, transitions, SFX, vision.

## ACCEPTANCE CRITERIA

1. Standard checks pass; Vegas-dependent behavior covered by fakes plus the human checklist.
2. No caption line contains two speakers; no caption overlaps another on the same track; every caption has start < end; all times are integer frames (tests, including property tests with seeded random inputs).
3. After synthetic cuts, caption starts land within one frame of the aligned first word (test).
4. SRT and ASS files parse back to the same text and timings; ASS escapes special characters (braces, backslashes, newlines) correctly (tests).
5. Colors come only from `speakers.json`; a test proves an EDL containing a color-like field is rejected.
6. Low-contrast and low-confidence cases appear in the report (tests).
7. The executor ops compile in C# 5 mode (`EC`) and contain no network code.
8. Renderer interface has at least the decided path plus `SidecarOnly` fully implemented; `AssBurnIn` works end to end with ffmpeg on a generated clip (marked ffmpeg test).
9. `HUMAN_TESTS_M6.md` complete with expected outcomes and a results template for T1.
10. Contracts/docs consistent; no private data in tracked files; phase commits; no push.

## HUMAN VERIFICATION AFTER

Captions visible, correct color per speaker, synced after cuts, readable at small size; Vegas-rendered result matches the sidecar; 300-caption job completes without freezing Vegas.

## WORK PLAN

A: `captions` contract, line builder, remap. B: colors, contrast, exports. C: renderer interface and decided path, burn-in. D: executor ops. E: verification. F: docs, human checklist. G: final verification, report.

## STOP AND ASK IF

The decision memo has no subtitle path; the only workable path needs a download; per-event color is `DISPROVED` and presets are also unavailable and ffmpeg is not installed.

## FINAL REPORT

Per Section 13 plus: path used, limits discovered, sync and color check results, performance numbers, and what to adjust before Prompt 07.

=== PROMPT END ===

---

## Completion record

- Date: 2026-10-07
- Final implementation and documentation commit: `44b9221`; the separate archival/privacy completion commit follows.
- Assumptions: VQ-09 has compile-time evidence only, VQ-10 remains UNVERIFIED, and local FFmpeg/ffprobe are unavailable; see RV-007/RV-008. No Vegas, real speech, endpoint, download, or user media was used.
- Revisit items created: RV-007, RV-008. RV-003 remains inherited.
