# M4 Human Test Checklist

**Purpose:** Verify the cut-only pipeline on a disposable VEGAS Pro 17 project. This checklist is not complete until a human records observed results. No Vegas behavior is verified by fake adapters or this document. See RV-001 and RV-002 in [REVISIT.md](../REVISIT.md).

## Safety and setup

1. Do not use a personal project or source recording. Make a disposable project copy from generated color/title media or an approved short clip. Keep source project and media read-only.
2. Preserve an untouched backup of the disposable project.
3. Record the Vegas build, project frame rate as a rational value, media hashes, and whether the source contains linked A/V, groups, locked tracks, envelopes, or multiple takes.
4. Confirm output paths resolve under the declared job working directory. Do not copy tools/scripts into the Vegas installation folder.
5. No API key, endpoint, profile path, project filename, media filename, transcript excerpt, or full plugin catalog belongs in the report.

## Review and approval

1. Run the offline job with a validated timeline, aligned words, declared source media, and normalized mono PCM16 audio. The run must produce timeline.json, words.json, pack.txt, edl.json, ops.json, compile_report.json, markers.csv, cutlist_preview.edl, review.md, verify_report.json, fixes.json, and run_manifest.json.
2. Open the disposable project in Vegas and compare the marker/EDL review with the planned cut IDs. Record missing, duplicated, or misplaced markers.
3. Create approved_cuts.json with one decision per planned cut/gap action. Test a mixed approve/reject set, then verify the approved operations contain exactly the approved IDs and that both refreshed review artifacts reflect every decision.
4. Test the all-rejected case. It must compile zero removals and must not mutate the project.
5. Test a missing decision and a duplicate/unknown ID. The runner must pause or reject the file with a typed error and must not execute a partial set.

## Working copy, undo, stop, and recovery

1. Hash the source project and every source media file before execution.
2. Apply the approved batch only to the disposable working copy using the provisionally selected transport.
3. Confirm linked A/V stays aligned and the original files are unchanged.
4. Undo once and confirm the full batch is undone. Record the observed undo boundary.
5. Trigger the stop file between batches. Confirm execution stops before the next batch and reports which operations completed.
6. Restart from the last saved stage. Confirm cached stage artifacts are reused only when their input and output hashes still match.
7. Change one input and confirm resume rejects it rather than reusing stale outputs.

## Render, verification, and bounded repair

1. Render an audio-only WAV and a low-resolution preview using the chosen Vegas template. If scripting remains unverified, render manually into the declared job directory, then run `python tasks.py watch-render --job-dir <runs/job_id> --output final_render.mp4 --timeout-s 3600`; it must detect a stable, non-empty file or return a typed timeout/stop/confinement error.
2. Verify that the runner reads the WAV from disk. Compare it with the reference-renderer prediction and record differences.
3. Listen at every join. Record click/discontinuity, level step, clipped-word boundary, inter-word gap, sync, and any audible artifact.
4. Include one synthetic test join known to fail the current verifier and observe whether a wider crossfade repairs it without changing thresholds.
5. Force a failure through the maximum of two repair iterations. Confirm the loop stops at the cap, records each action, and restores the pre-execution checkpoint before retrying so edits are not applied twice.
6. Render the final output, verify the sidecar markers.csv, review.md, verify_report.json, and run_manifest.json, and hash source project/media again.

## Results template

~~~text
VEGAS build:
Project frame rate:
Project type: generated-only | approved short clip
Source project unchanged: yes | no
Declared media unchanged: yes | no
Marker positions correct: yes | no | not run
Mixed approvals contain exactly approved IDs: yes | no | not run
All-rejected case leaves no edits: yes | no | not run
Undo restores working copy: yes | no | not run
Stop honored between batches: yes | no | not run
Resume reuses matching artifacts and rejects changed inputs: yes | no | not run
Preview WAV read from disk: yes | no | not run
Final render/sync result:
Join count:
Click checks passed / total:
Level-step checks passed / total:
Clipped-word checks passed / total:
Pacing checks passed / total:
Fix iterations used / configured cap:
Original and media hash comparisons:
Observed errors (redacted):
Evidence IDs to add to VEGAS_NOTES.md:
Human listening notes (no transcript excerpts):
~~~

Do not write VERIFIED until the observed result is recorded as E0 evidence in docs/VEGAS_NOTES.md. Vegas runtime remains open under RV-001; speech quality remains open under RV-002.
