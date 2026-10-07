# Speaker Attribution

**Status:** Deterministic attribution and artifact handling are implemented for offline fixtures. Real diarization, voice matching, and calibrated quality remain open under RV-005 and RV-006.

## Modes

The setting is speakers.mode in the ignored local config.json. The example keeps the existing single default. Set mode to auto to select a mode from audio-stream titles, documented Mic N / Track N aliases, speakers.json mappings, and per-track track_mode values.

| Mode | Selection and behavior |
|---|---|
| single | Treat the input as one unidentified speaker unless the current stage explicitly assigns a speaker. Unknown words remain low confidence and are surfaced for confirmation. |
| multitrack | Run the existing ASR interface on each audio stream, label words by the mapped track, then merge by word start time. |
| diarized | Requires a local diarization backend on a mixed track. No accepted inference backend is connected, so this mode stops safely with RV-005. |
| hybrid | Uses mapped tracks where possible and diarizes mixed or unmapped tracks. The mode is recognized, but execution stops until the local model backend is available; see RV-005. |
| Explicit override | single, multitrack, diarized, or hybrid can be set in the local config. Invalid combinations fail instead of silently changing mode. |

Track aliases are generated deterministically from stream ordinal (audio_0, Mic 1, Track 1, and audio 0) and the ffprobe title when available. A stream title can be mapped in speakers.json; do not rely on an inferred track title when two tracks share the same label.

Automatic mode selection is implemented and covered with synthetic mapping fixtures. The example default remains single because the master run rules prohibit changing defaults to auto; choose auto explicitly when the recording's tracks are mapped.

## Multitrack and bleed handling

Each stream is transcribed separately and word rows are merged by time while retaining the deterministic track key. If a mapped track has no speaker entry, its words receive Unknown N with low confidence. Duplicate normalized tokens on overlapping tracks are compared with each track's RMS energy. The lower-energy candidate is retained and marked low confidence; ambiguous candidates are also retained. This is a deterministic heuristic, not VAD and not a calibrated bleed detector. Real-speech performance is ASSUMED (RV-006).

The provisional comparisons are a likely-bleed ratio of 0.20 and an ambiguous ratio of 0.55. They are tested only with synthetic energy fixtures and must be calibrated before use on real recordings (RV-006). A report never silently removes a duplicate or changes its speaker.

## Diarization, overlap, and matching

The pure assignment helper maps each aligned word to the speaker turn with the greatest time intersection. When a word intersects turns from more than one speaker, it sets overlap: true and multiplies confidence by 0.5. Unassigned clusters remain unknown_N. These rules are synthetic-only; no diarization checkpoint or real audio was loaded (RV-005, RV-006).

Cosine matching rejects scores below the configured speakers.unknown_similarity_threshold (currently 0.65) and near ties. That threshold is inherited from the existing configuration and is not validated against enrollment samples. Real-world matching accuracy is ASSUMED (RV-005, RV-006).

## Enrollment

The local encoder interface accepts 16 kHz mono PCM samples and returns an embedding. The deterministic enrollment helper checks sample duration, estimated SNR, and consistency between windows; the profile writer saves the normalized embedding and metadata only, never the source audio. Synthetic tests cover too-short, noisy/unstable, and valid fake-encoder input.

The command python tasks.py enroll --name <speaker> --audio <approved.wav> validates a local WAV but currently stops with the G2 / RV-005 message because no accepted local embedding engine is configured. No Hugging Face token is read, no model card has been fetched for this goal, and no model weights were downloaded. Do not treat the helper thresholds as human-validated: the 3 second minimum, 10 dB SNR, and 0.82 segment-consistency values are provisional (RV-005, RV-006).

## Unknown speakers and confirmation

When attribution yields unknown_N, the perception stage writes:

- ask_user.json with an identify_speaker question, a run-relative short WAV snippet, up to three candidate names, and free-text enabled.
- speaker_report.json with low-confidence word IDs, time ranges, speaker keys, confidence values, and reasons; it contains no transcript text or media path.
- speakers.json and words.json with the unknown retained as Unknown N.

The combined dry-run stops at this point and records partial with E_SPEAKER_CONFIRMATION in run_manifest.json. Standalone planning and compilation refuse to continue while a question is pending. Run python tasks.py answer-speaker --job-dir <run-dir> --speaker-key unknown_1; the CLI displays the proposed speaker-map change and writes it only after confirmation. It updates the run artifacts and the ignored root speakers.json map while preserving confidence. After confirmation, continue with the saved words artifact, for example python tasks.py plan --words <run-dir>/words.json.

If the question is still pending after 24 hours, the next planning or compilation attempt marks it timed out, leaves the words as Unknown N, and stores a warning in ask_user.json. The timeout is checked when a command runs; there is no background scheduler. Optional enrollment of an identification snippet is not implemented.

## Speaker report

speaker_report.json groups every word below the provisional 0.65 confidence threshold into a time range and records its word ID, speaker key, confidence, and reason. Overlap, likely bleed, ambiguous bleed, unassigned, and ordinary low-confidence cases remain distinct. The threshold is a report-display choice, not a reassignment rule, and is ASSUMED until real clips are reviewed (RV-006).

## Recording advice and current limits

Separate, clean microphone tracks are preferred because they avoid clustering and make track identity explicit. Keep one speaker per track, avoid routing duplicate microphones into every track, and record a few seconds of clean speech per person for future enrollment. If only a mixed recording exists, real diarization requires G2 and an accepted local model checkpoint (RV-005). A human must inspect low-confidence ranges before subtitle coloring or other downstream decisions (RV-006).

python tasks.py eval reports a synthetic fixture score for deterministic plumbing only. It is not a model benchmark, real-speaker accuracy estimate, or evidence of laptop inference speed. See the evaluation record in EVALS.md, setup and token handling in SETUP.md, and the security boundary in SECURITY.md.