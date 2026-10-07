# Subtitles and Caption Sidecars

**Document version:** 1.0.0

This guide describes the deterministic caption pipeline added for Goal 06. It creates frame-resolved captions after compilation and exports SRT and ASS. The provisional renderer decision is ASS burn-in after a manually completed final render, with sidecars always available. Vegas text events and presets remain disabled until VQ-09 and VQ-10 receive human E0 evidence.

## Generate captions

The standalone compile command accepts the same `words.json`, `timeline.json`, and `edl.json` artifacts as the compiler. It also needs the validated `speakers.json` created by transcription, by default beside `words.json`:

```powershell
python tasks.py compile --words <words.json> --timeline <timeline.json> --edl <edl.json>
```

If the speaker map is elsewhere, pass `--speakers <speakers.json>`. The output directory contains `captions.json`, `captions.srt`, `captions.ass`, `captions_report.json`, `ops.json`, `compile_report.json`, and `review.md`.

`python tasks.py run-job` uses the speaker map beside the word file or the optional `--speakers` path. Candidate captions are generated from the compiled kept ranges. In review mode, approved cuts are compiled again and their caption sidecars are written under `approved_captions/`; those sidecars match the approved edit set.

## Layout and timing rules

The caption builder uses rational frame arithmetic and integer half-open frame ranges. It maps retained word intervals through the compiler's kept ranges. A word intersecting a removed interval is omitted and counted; captions split at a speaker change, EDL break hint, or removed source gap. Captions on one speaker track cannot overlap. Different speakers can overlap to preserve simultaneous speech.

Line layout uses the configured maximum characters, maximum lines, characters per second, minimum duration, and hold time. It prefers punctuation and clause boundaries, and never splits Unicode combining sequences, emoji joiner sequences, regional-indicator flags, or Hangul composition clusters. Filler and profanity handling are local configuration options. EDL can refer only to emphasis word IDs, omissions, and break hints; it cannot carry colors, filesystem paths, or caption timestamps.

## Color and sidecars

Known speaker colors come only from `speakers.json`. Unmapped speakers use its `unknown_palette`. The captions contract has no color field, and EDL color-like fields fail validation. The ASS exporter writes one style per speaker and escapes braces, backslashes, and line breaks before adding emphasis overrides. SRT is plain text and has no color semantics.

The contrast report compares the speaker foreground color with the configured outline color. `captions_report.json` contains counts, reason codes, word IDs, speaker keys, and frame ranges; it does not copy caption text or media paths. `review.md` adds warning codes and low-confidence ranges without exposing the transcript.

Defaults are the deterministic architecture values unless local `subtitles` settings override them: 42 graphemes per line, 2 lines, 20 CPS, 700 ms minimum duration, 100 ms hold, 0.65 low-confidence threshold, Arial at 48 points, black 2-point outline, and 48-point vertical margin. The default font name is provisional; the adapter does not install or download fonts. Use only fonts already installed or locally provided with a recorded license.

## ASS burn-in

After a final video has been rendered manually into an ignored run directory, burn the ASS sidecar into a new file:

```powershell
python tasks.py burn-captions --job-dir runs/<job_id> --video final_render.mp4 --ass captions.ass --output final_captioned.mp4
```

For approved review output, use `--ass approved_captions/captions.ass`. All paths must remain inside the declared job directory. The adapter invokes local FFmpeg without a shell, refuses to overwrite, and reports missing or failed FFmpeg support without deleting the sidecars. No executable or font is downloaded. FFmpeg/ffprobe were unavailable on the Goal 06 machine, so the generated-clip end-to-end burn-in check remains skipped under [RV-008](../REVISIT.md#rv-008--goal-06-ass-burn-in-runtime-availability).

## Verification and open limits

Offline checks cover schema and word references, no same-speaker overlaps, exact kept-range mapping, SRT/ASS parse-back, special-character escaping, map-only colors, contrast warnings, and low-confidence flags. The seeded layout test exercises 200 words. Rendered caption re-alignment, rendered pixel/color sampling, real-speech sync, phone-size readability, and 300-event VEGAS performance have not been measured.

The human procedure is in [HUMAN_TESTS_M6.md](HUMAN_TESTS_M6.md). It records the missing style interview and T1 evidence rather than inventing either. See [RV-007](../REVISIT.md#rv-007--goal-06-caption-style-and-vegas-text-probes) for style/Vegas probes and [RV-008](../REVISIT.md#rv-008--goal-06-ass-burn-in-runtime-availability) for the local FFmpeg gate.
