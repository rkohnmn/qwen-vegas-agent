# Evaluation results

Every result reports accuracy with runtime and identifies the contract and planner versions. Synthetic evals are plumbing checks. The corrected English real-media run produced timing anchors for all transcript rows and real join measurements, but it has no word-level ground truth and the verifier failed, so it is not an editing-quality estimate.

## Synthetic baseline sanity check

Command: `.venv\Scripts\python.exe tasks.py eval`
Date: 2026-10-06
Dataset: `synthetic-tone-silence-v1`, one generated case using fixture word boundaries and a known filler plus silence gap.
Planner: `baseline-1`
Contracts: words=2.0.0, edl=1.2.0, ops=1.1.0, compile_report=2.0.0.
Runtime: Python 3.12 on Windows; no external service or user media.

| Metric | Result |
|---|---:|
| Planner-selection precision / recall | 1.0000 / 1.0000 |
| Applied precision / recall (from final delete ops) | 1.0000 / 0.5000 |
| Proposed cuts rejected or adjusted | 1 / 2 (50.0000%) |
| Cut offset error (mean / median / max) | 0 / 0 / 0 ms |
| Clipped-word rate | 0.0000 |
| Click rate | 0.0000 |
| Audio verifier | Failed `join_1_level`, `join_2_level`; click checks passed |
| Removed duration | 19.166667% |
| Wall time | 281.055 ms total; 4.2158 s per minute of synthetic timeline |
| Estimated planner tokens | 63 |
| Compile rejections | 1 (`E_PACING_GAP`: filler removal would leave no configured pause between neighboring words) |
| Planner retries | 0 |

The labeled filler and silence are selected as expected, so planner-selection precision/recall remain 1.0. The compiler rejects the filler removal because it would leave no configured pause between neighboring words; the final delete operation contains only the silence action ID. Applied precision remains 1.0 and applied recall is 0.5 because one of the two labeled removals was not emitted. The two tone-fixture level-step failures remain expected stress-case failures: generated fixed-amplitude tones switch abruptly from silence at word boundaries. These one-case synthetic metrics do not estimate ASR accuracy or human editorial quality; runtime is a plumbing measurement, not a benchmark.

## Speech-like synthetic verifier fixture

A unit test generates band-limited noise bursts with smooth 12 ms attacks, 18 ms releases, and low-level room noise between bursts. It runs through the default verifier without changing either threshold. This generated case exercises smoother, speech-shaped amplitude variation; it is not a substitute for real speech or a calibration sample. The tone fixture remains a separate stress case with two asserted level-step failures.

## Initial English verifier run

Run `20261006T235401Z_68b01796` was the first English pass on the approved 30 fps CFR working copy. It emitted timing anchors for 55 of 210 rows and six join measurements. The verifier returned `E_VERIFY`: five level-step and two pacing checks failed; all six click checks passed. Investigation found that WhisperX split some raw ASR segments into multiple sentence-sized alignment segments, while the adapter paired results by list index. The resulting timing count is superseded by the corrected run below and D-36. This initial run did not change thresholds, contact an inference endpoint, or launch VEGAS.

The synthetic speech-shaped fixture remains a separate verifier exercise. Its smoother amplitude envelope passed under the unchanged default thresholds; the retained tone fixture still asserts two expected level-step failures. Neither fixture is a real-speech calibration sample.

## Historical Japanese real-media ASR and smoke evaluation

Run: `20261006T232642Z_d35580dd`, completed 2026-10-06 with `python tasks.py dry-run --video <selected clip> --max-seconds 120 --planner baseline`. The original source hash matched before and after the run; the test-video and VEGAS install directory listings also remained identical. The home inference server stayed off and no LLM endpoint was contacted.

The source descriptors are recorded without its filename or path: 78.553107 seconds, MOV/MP4 family, H.264 High video, AAC-LC stereo audio at 44100 Hz, and `2997/100` fps. Average and real rates match. Corrected bounded timestamp sampling and a full decoded-frame scan classify the source as CFR with no preflight warning. The old `W_VFR` came from an incomplete packet-boundary tail in ffprobe output; the fix reads 16 packets ahead and classifies only the requested sample window.

| ASR benchmark field | Result |
|---|---|
| Requested model | `small` (faster-whisper) |
| Alignment model | `jonatasgrosman/wav2vec2-large-xlsr-53-japanese` |
| Device / compute type | CUDA / `int8_float16` |
| Peak VRAM | 1.27 GB |
| ASR wall time | 37.367 seconds |
| Media duration / real-time factor | 78.545 seconds / 0.4757 (`ASR wall time / media duration`) |
| Detected language / confidence | Japanese (`ja`) / 0.9399 |
| Word timing sanity | 30 tokens; 0 aligned, 30 unaligned. Shorter-than-20-ms and longer-than-2-s rates are unavailable because there are no aligned durations. |

WhisperX produced 298 timed subword rows for 30 Japanese ASR segments, and normalized concatenation matched each segment. The rows did not match the word-level contract, so the adapter conservatively retained the 30 phrase-level tokens without time anchors rather than treating subword boundaries as lexical words. The baseline planner proposed 0 cuts and 0 gap actions. The compile report has no rejected or adjusted items and reports 0% removed. The verifier passed only the removed-percent check; click, level-step, pacing, and clipped-word measurements had no join or cut boundaries to inspect. This run proves pipeline completion and source integrity, not editing quality. No ground truth exists for the real recording.

The truth template was generated under the ignored run directory with `python tasks.py truth-template --words runs/<job_id>/words.json --output runs/<job_id>/truth_template.json`. The local model snapshots did not contain license files; revisions and exact checkpoint sizes are recorded in `DECISIONS.md` D-32. No VAD or diarization weights, tokens, or other unapproved models were fetched.

## Corrected English real-media ASR and dry-run evaluation

Run: `20261007T001144Z_5475d354`. Command: `python tasks.py dry-run --video runs/20261006T235023Z_english_cfr/source_cfr.mp4 --max-seconds 120 --planner baseline`, with the already-present ffmpeg tools supplied to that process through a temporary PATH. The selected 327.169-second source is identified by SHA-256 prefix `57ce0b0d905fa8a9`; its filename and path are omitted. The original was not modified; the run manifest's before/after SHA-256 values for the CFR working copy match. No inference endpoint or VEGAS process was used.

The source CFR copy is H.264 1280x720 with AAC stereo audio at 44,100 Hz and exactly 30/1 fps. Its bounded preflight had no warnings, and the full 9,815-frame scan found no cadence interval outside tolerance. The original source's one 9 ms cadence outlier and the CFR-copy procedure are documented above and in D-35.

| ASR and pipeline field | Result |
|---|---:|
| Processed media / source duration | 120.000 / 327.169 seconds |
| Detected language / confidence | English (`en`) / 0.9766 |
| Requested ASR / alignment model | `small` / `WAV2VEC2_ASR_BASE_960H` |
| Device / compute type / peak VRAM | CUDA / `int8_float16` / 0.578 GB |
| ASR wall time / real-time factor | 30.747 seconds / 0.2562 |
| Pipeline wall time / per media minute | 35.044 seconds / 17.522 seconds |
| Word rows / timing anchors / unaligned | 210 / 210 / 0; no human boundary labels |
| Word-duration sanity | 8/210 under 20 ms (3.81%); 2/210 over 2 s (0.95%); min 20 ms, max 5,129 ms |
| Baseline EDL | 0 lexical cuts; 8 silence/shorten gap actions |
| Compile result | 8/8 gap actions applied; 16 `delete_range` operations; 8.3611% removed |
| Verifier result | Failed `E_VERIFY`: 12/16 level-step and 4/16 pacing checks failed; 16/16 click and 32/32 clipped-word checks passed; removed-percent passed |

| Join | Click metric (limit 0.12) | Level step dB (limit 8.0) | Click | Level |
|---|---:|---:|---|---|
| join_1 | 0.000732 | 27.3668 | pass | fail |
| join_2 | 0.000000 | 36.3924 | pass | fail |
| join_3 | 0.000153 | 41.4798 | pass | fail |
| join_4 | 0.000092 | 32.8258 | pass | fail |
| join_5 | 0.000092 | 34.4418 | pass | fail |
| join_6 | 0.000031 | 1.2150 | pass | pass |
| join_7 | 0.006653 | 8.3967 | pass | fail |
| join_8 | 0.033783 | 5.9722 | pass | pass |
| join_9 | 0.000092 | 31.4512 | pass | fail |
| join_10 | 0.000610 | 42.8528 | pass | fail |
| join_11 | 0.002136 | 17.1061 | pass | fail |
| join_12 | 0.000031 | 37.2731 | pass | fail |
| join_13 | 0.000275 | 28.9100 | pass | fail |
| join_14 | 0.000397 | 16.2012 | pass | fail |
| join_15 | 0.001709 | 2.3011 | pass | pass |
| join_16 | 0.000580 | 4.0023 | pass | pass |

The 16 joins all come from one unlabelled recording, so the sample does not justify recalibrating either verifier threshold. Keep the 0.12 click and 8.0 dB level-step defaults while collecting human-reviewed real-speech evidence. The 16 compiled delete ranges had zero overlap with the 210 aligned word spans when compared on the rational 30/1 frame grid.

The corrected mapper consumes WhisperX's sentence-sized results in transcript order and retains timings only after normalized text matches. All 210 rows received timing anchors, but no word-level ground truth was available; cut precision/recall and timing accuracy remain unmeasured. The first English run's 55/210 result is a diagnosed mapping defect, not an ASR quality baseline. The latest run's `truth_template.json` is an unlabeled editing skeleton under ignored `runs/`. The aligner checkpoint provenance is recorded in D-35; the mapping correction and latest run evidence are in D-36. Verifier thresholds remain `max_click_delta=0.12` and `max_level_step_db=8.0` dB.

## Metric definitions

| Metric | Definition |
|---|---|
| Wall-clock per minute | Total elapsed time and per-stage time from the run manifest divided by source duration in minutes. |
| ASR real-time factor | ASR wall time divided by processed media duration; values below 1.0 are faster than real time. |
| Cut offset error | Absolute milliseconds between each final cut and ground-truth boundary; report mean, median, and maximum. |
| Planner-selection precision and recall | Correct planner-selected cuts divided by selected cuts, and correct selected cuts divided by ground-truth cuts. |
| Applied precision and recall | Correct selected cuts represented in final `delete_range.item_ids` divided by applied cut IDs, and correct applied cuts divided by ground-truth cuts. |
| Rejected or adjusted proposals | Count and percentage of proposed cuts/gap actions with `rejected` or `adjusted` compile status. |
| Clipped-word rate | Fraction of cut boundaries that leave a fragment of an aligned spoken word. |
| Click rate | Fraction of rendered joins flagged for audible discontinuity. |
| Subtitle sync error | Mean and maximum milliseconds between caption bounds and aligned speech. |
| Speaker attribution accuracy | Correct speaker labels divided by labeled words, reported by attribution mode. |
| Color correctness | Captions rendered with the configured speaker color divided by captions checked. |
| Token estimate and retries | Estimated planner tokens and compile/schema retries per run. |

Future real evaluations must include dataset/clip IDs, prompt and schema versions, hardware, per-stage time, accuracy metrics, retries, and the tolerance decision. The eval harness supports editable truth templates through `python tasks.py truth-template --words <words.json> --output <path-under-repo>`.
