# Evaluation results

Every result reports accuracy with runtime and identifies the contract and planner versions. Synthetic evals are plumbing checks; the real-media run completed the pipeline but produced no word-aligned cuts, so it does not estimate editing quality.

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

## Real-media verifier joins

The corrected preflight classified the source as CFR at `2997/100` fps. The full decoded scan covered 2,354 frames and 2,353 intervals without an interval deviating from median cadence by more than 1 ms. The completed smoke generated zero cuts and zero joins, so no real-speech join sample exists. Thresholds remain at the defaults, `max_click_delta=0.12` full-scale sample delta and `max_level_step_db=8.0` dB; the sample size is zero and does not justify calibration.

| Smoke joins | Click metric | Level step | Thresholds in force | Evidence |
|---:|---:|---:|---|---|
| 0 | N/A | N/A | 0.12 full-scale delta; 8.0 dB | No cuts or gap actions were produced. |

## Real-media ASR and smoke evaluation

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
