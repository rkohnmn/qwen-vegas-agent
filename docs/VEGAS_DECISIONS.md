# VEGAS Decisions

**Status: PROVISIONAL / ASSUMED (RV-001).** No decision below has E0 evidence. No Vegas runtime behavior is claimed, and no item enables an unverified path by default.

| Area | Provisional choice | Why this depends least on unverified runtime behavior | Evidence needed to enable an alternative |
|---|---|---|---|
| Transport | Review through sidecar files and marker/EDL export; use a script-menu action only after the human probe confirms it. Keep extension polling and command-line script launch disabled. | Files can be produced and validated without loading Vegas or assuming an extension host. A human can inspect the CSV/EDL before applying it. | Run `docs/HUMAN_TESTS_M4.md` transport steps on a disposable project; record E0 evidence for VQ-02 and VQ-13. |
| Edit strategy | Rebuild a disposable working-copy timeline from explicit kept ranges; preserve a gap-closing adapter for transport paths that support it. Keep linked audio/video groups together. | Rebuild avoids relying on undocumented ripple selection state. It still requires a human to validate project/take/automation fidelity before use. | Compare source and rebuilt project on linked A/V, envelopes, locked tracks, and undo using the M4 checklist; record VQ-07, VQ-08, and VQ-15 evidence. |
| Subtitles | Use ASS burn-in with a sidecar caption file as the default path. Vegas text events remain disabled until text generator behavior is probed. | Sidecar text can be generated and checked offline; burn-in can be delegated to the already bounded render path. | Run the goal 06 human checklist on a disposable project and compare rendered timing/color; record VQ-09 and VQ-10 evidence. |

The offline compile stage now emits caption JSON, SRT, and ASS sidecars, and `python tasks.py burn-captions` invokes the selected local FFmpeg adapter on a render confined to a run directory. This implements sidecar generation; the renderer has not been exercised end to end because FFmpeg is unavailable (RV-008). The decision remains provisional until the M6 human comparison is recorded.
| Audio joins | Use short fixed crossfades at joins. Do not rely on project-default fades. | A deterministic fixed duration is auditable in compiled reports and can be tested with synthetic audio, although the Vegas curve and resulting click rate are unknown. | Render synthetic boundary signals in Vegas, inspect every join, and record samples/thresholds for VQ-05/VQ-06. |
| Preview/final render | Use manual rendering with a confined output path and a bounded output-file watcher as the fallback. Scripted preview and final render remain disabled. | This avoids assuming render-template enumeration, script invocation, or render completion semantics. | Run the M4 checklist render steps and record template, output, timeout, and cancellation behavior for VQ-14. |

## Implementation boundary

The offline runner may produce validated review artifacts, use fake executor/renderer adapters, and verify a WAV read back from disk. Fake results are test plumbing only. They do not count as Vegas execution, render evidence, or acceptance on a real project. Every runtime alternative stays behind an interface and disabled by default until the corresponding E0 result is recorded in `docs/VEGAS_NOTES.md`.

## Confirmation

The human should confirm or replace these choices after the listed probes. A blank project license remains a separate human decision; this memo does not select one.
