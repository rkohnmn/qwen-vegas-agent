# Human Tests M5 — Speaker Attribution

These checks require the resources listed in RV-005 and RV-006. Do not use a source project or original media; use an approved disposable copy. No Vegas operation is part of these tests.

## Before testing

1. Complete the G2 human gate: record which gated model IDs and terms were accepted. Never put a token in this checklist or a tracked file.
2. Confirm each checkpoint's current model-card terms before downloading. Keep the token in a gitignored local secret location. No model backend is currently configured, so python tasks.py enroll is expected to stop at RV-005.
3. Prepare one labeled multitrack clip with one speaker per track, including a quiet bleed region, and one labeled mixed clip with two enrolled speakers and an overlap span.
4. Verify both clips are local and approved. Do not upload audio.

## Multitrack run

1. In the ignored local config, set speakers.mode to auto and map each audio stream title or Mic N / Track N alias in speakers.json.
2. Run python tasks.py transcribe --video <approved-copy> --max-seconds 120.
3. Inspect words.json, speaker_report.json, speakers.json, and ask_user.json without copying private transcript text into tracked docs.
4. For each pending unknown, listen to the relative WAV snippet and run python tasks.py answer-speaker --job-dir <run-dir> --speaker-key <unknown_N> --name <display-name>. Review the diff and confirm only when correct.
5. Continue with python tasks.py plan --words <run-dir>/words.json.
6. Compare labels against the supplied word-level truth. Record attribution precision/recall, bleed classification, unknown detection, time per media minute, CPU/GPU device, peak memory, and low-confidence review findings in docs/EVALS.md.

## Mixed recording

1. Enroll two speakers only after the accepted local embedding and diarization backend are configured.
2. Run the mixed clip through the local diarization stage with overlap labels and match against the enrolled profiles.
3. Confirm overlapping words carry overlap: true and reduced confidence; verify near-tie or below-threshold matches remain Unknown N.
4. Compare the result with labeled truth. Record per-speaker accuracy and overlap precision/recall, runtime, and peak memory in docs/EVALS.md.

## Record evidence

Record the date, accepted model IDs (not the token), environment, aggregate metrics, and any failed cases. Keep sample names, media filenames, local paths, raw audio, and private transcript text out of tracked files. Update RV-005 and RV-006 only when the corresponding evidence exists. Synthetic tests do not satisfy these human checks.