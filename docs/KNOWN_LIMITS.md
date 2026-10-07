# Known Limits

## VEGAS runtime

The repository has no runtime executor. The offline runner writes review sidecars and exercises fake adapters; it does not open VEGAS, apply edits, create Vegas markers, or render a preview in Vegas. The `watch-render` task only observes a confined file and records its hash; it does not launch VEGAS or validate media contents. Keep all Vegas-dependent behavior disabled until the disposable-project checks in [HUMAN_TESTS_M4.md](HUMAN_TESTS_M4.md) produce E0 evidence. See [RV-001](../REVISIT.md#rv-001--goal-04-vegas-runtime-and-project-mutation-behavior).

## Speech and audio quality

The job runner consumes precomputed timeline and word artifacts. It does not run ASR. Its default reference audio renderer requires local FFmpeg, and the fake renderer tests use synthetic signals. Neither establishes real-speech edit quality or Vegas-rendered results. FFmpeg was not available during the goal 04 run, so the CLI's default reference renderer was not run end to end (RV-004). The offline eval still reports level-step failures. See [RV-002](../REVISIT.md#rv-002--goal-04-real-clip-timing-sync-and-listening-quality) and [RV-004](../REVISIT.md#rv-004--goal-04-default-reference-renderer-availability).

## Captions and subtitle rendering

The offline compile stage maps captions to edited integer frames and writes JSON, SRT, and ASS sidecars. Unit fixtures verify frame mapping through cuts, SRT/ASS round trips, speaker-map color use, contrast warnings, and low-confidence flags. No rendered-caption re-alignment, pixel sampling, or real-speech readability review has been completed. The ASS burn-in adapter needs a local FFmpeg build; the generated-clip end-to-end check is skipped when FFmpeg/ffprobe are absent (RV-008). Direct Vegas text and preset renderers remain disabled pending VQ-09/VQ-10 human results and the M6 style gate (RV-007).

## Missing predecessor evidence

Goals 01b–03 and their human-gate artifacts were absent when this prompt run started. Their completion is not claimed. Restore the exact source prompts and reconcile acceptance evidence before treating those prerequisites as complete. See [RV-003](../REVISIT.md#rv-003--missing-predecessor-and-reusable-prompt-artifacts).

## Planner and credentials

The current CLI does not contact the configured LLM endpoint. The endpoint client is outside this offline runner's goal. API credentials remain confined to orchestrator configuration and memory; no credential is passed to the Vegas executor.

## Speaker attribution

Mapped-track attribution and bleed comparisons have synthetic fixture coverage only. The checked-in example defaults to single-speaker mode; automatic mode is an explicit config choice. Mixed/hybrid attribution and enrollment stop because no accepted local model backend is configured. The 0.65 similarity and report thresholds plus bleed/overlap/enrollment thresholds are not calibrated on real speech. See the [speaker guide](SPEAKERS.md), [RV-005](../REVISIT.md#rv-005--goal-05-hugging-face-gate-and-voice-enrollment-samples), and [RV-006](../REVISIT.md#rv-006--goal-05-real-speech-attribution-quality-and-hardware-benchmark).
