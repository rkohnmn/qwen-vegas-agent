# Goal 06 Human Tests: Subtitles and Speaker Colors

**Status:** Not run. This checklist requires a human with VEGAS Pro 17 and a disposable synthetic project. The agent must not launch VEGAS. Record results without user media, personal paths, or transcript text.

## Preconditions

- Use a new disposable `.veg` project and generated synthetic media. Never use an original project or source recording.
- Restore `STYLE_INTERVIEW.md`, T1, and `HUMAN_GATES.md` from the original prompt pack if available. They are absent from this checkout (RV-003/RV-007); do not claim those gates passed.
- Review `docs/VEGAS_NOTES.md` VQ-09 and VQ-10, and `docs/VEGAS_DECISIONS.md`. The selected provisional path is ASS burn-in plus SRT/ASS sidecars.
- Ensure the two synthetic speaker entries have distinct colors in `speakers.json`. Do not put colors or times in an EDL.
- If a local FFmpeg build is already available, record its version. Do not download tools or fonts for this check.

## A. Probe Vegas text behavior

Follow the exact probe steps in `docs/VEGAS_NOTES.md`:

1. Run TextProbe on the disposable project. Record generator parameter names and CLR types; do not infer runtime behavior from compilation.
2. Attempt a plain text event, render one frame, and record whether text appears.
3. Test a per-event color parameter or RTF color table only if exposed by the probe. Compare two speaker colors, line breaks, braces, backslashes, non-Latin text, and emoji.
4. Time creation of 300 test events and record UI responsiveness, event/track counts, and any freeze or crash.
5. If direct per-event color is unavailable, manually create the per-speaker presets and run VQ-10. Confirm the preset color persists after text changes. Do not enable either code path without E0 evidence.
6. Record exactly which outcomes were observed. A failed probe leaves the Vegas text path disabled.

## B. Check generated sidecars and sync

1. Create a small synthetic timeline with two speakers, aligned word IDs, one planned removal, one retained word after the removal, one emphasis span, and punctuation. Include a special-character string in a synthetic word fixture.
2. Run `python tasks.py compile` against those synthetic artifacts and the matching speaker map. Confirm the compile directory contains `captions.json`, `.srt`, `.ass`, `captions_report.json`, and `review.md`.
3. Inspect the JSON frame bounds before and after the cut. The first retained post-cut word must map within one project frame. Confirm words intersecting the removed interval are reported and do not leak into a caption.
4. Parse SRT and ASS back to text and timings. Confirm SRT is plain text and ASS carries the expected speaker styles and emphasis while escaping braces, backslashes, and line breaks.
5. Check that each caption contains one speaker, same-speaker captions do not overlap, low-confidence ranges are flagged, and colors match `speakers.json` / `unknown_palette`. Record contrast warnings without changing colors automatically.
6. View a generated preview at phone size. Record readability, line count, CPS warnings, and any style choices. Do not call a synthetic visual result human speech-quality evidence.

## C. Compare final paths and stress count

1. If VQ-09 or VQ-10 produced a usable Vegas method, create a manual Vegas preview with two speakers and compare it against the ASS burn-in. Otherwise record “Vegas comparison unavailable; text mechanism remains disabled.”
2. Render a synthetic final video manually into the run directory. If FFmpeg is already installed, run:

   ```powershell
   python tasks.py burn-captions --job-dir runs/<job_id> --video final_render.mp4 --ass captions.ass --output final_captioned.mp4
   ```

   Confirm the new file is readable and the source render remains unchanged. Record FFmpeg and ffprobe versions and sample caption frames for both text and color. If FFmpeg is missing, record that sidecars remain usable and leave RV-008 open.
3. Repeat with 300 caption events. Record generation/export wall time, Vegas event-creation wall time when available, maximum observed UI pause, and whether the application remained responsive. Do not extrapolate from the 200-word offline unit fixture.

## Results template

```text
Date and reviewer:
Vegas edition/build:
Project/media: generated synthetic only (describe recipe, no path)
Style interview reference / version:
T1 reference / result (restore exact T1 before claiming this gate):
VQ-09: pass / fail / unavailable; observations:
VQ-10: pass / fail / unavailable; observations:
Selected style: font / size / outline / position / line limits:
Speaker-color correctness: checked / total; mismatches:
Unknown-palette correctness: checked / total; mismatches:
Contrast warnings:
Post-cut sync error: mean / max milliseconds; project fps; frame offset:
SRT parse-back: pass / fail; ASS parse-back: pass / fail:
Special characters: pass / fail; examples by code point only:
Phone-size readability: pass / fail; observations:
300-caption generation/export time:
300 Vegas event creation time / maximum UI pause:
ASS burn-in: pass / fail / skipped; FFmpeg/ffprobe versions:
Source render unchanged: yes / no:
E0 evidence IDs recorded in VEGAS_NOTES.md:
Open issues and RV IDs:
```

Until results are recorded, keep VQ-09 at its existing compile-only status, VQ-10 UNVERIFIED, and Vegas text-event operations disabled. This checklist does not itself verify Vegas or resolve the missing style/T1 gate.
