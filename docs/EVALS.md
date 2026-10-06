# Evaluation results

Every result reports accuracy with runtime and identifies the contract and planner versions. The current offline result is a synthetic plumbing check only; it does not estimate real editing quality.

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
| Wall time | 177.525 ms total; 2.6629 s per minute of synthetic timeline |
| Estimated planner tokens | 63 |
| Compile rejections | 1 (`E_PACING_GAP`: filler removal would leave no configured pause between neighboring words) |
| Planner retries | 0 |

The labeled filler and silence are selected as expected, so planner-selection precision/recall remain 1.0. The compiler rejects the filler removal because it would leave no configured pause between neighboring words; the final delete operation contains only the silence action ID. Applied precision remains 1.0 and applied recall is 0.5 because one of the two labeled removals was not emitted. The two tone-fixture level-step failures remain expected stress-case failures: generated fixed-amplitude tones switch abruptly from silence at word boundaries. These one-case synthetic metrics do not estimate ASR accuracy or human editorial quality; runtime is a plumbing measurement, not a benchmark.

## Speech-like synthetic verifier fixture

A unit test generates band-limited noise bursts with smooth 12 ms attacks, 18 ms releases, and low-level room noise between bursts. It runs through the default verifier without changing either threshold. This generated case exercises smoother, speech-shaped amplitude variation; it is not a substitute for real speech or a calibration sample. The tone fixture remains a separate stress case with two asserted level-step failures.

## Real-media verifier joins

No real joins were measured: read-only preflight reported W_VFR from bounded timestamp sampling, so processing stopped before audio extraction. Thresholds remain at the existing defaults, `max_click_delta=0.12` full-scale sample delta and `max_level_step_db=8.0` dB, pending a larger real-join sample.

| Smoke join | Click metric | Level step | Thresholds in force | Evidence |
|---|---:|---:|---|---|
| Not measured | N/A | N/A | 0.12 full-scale delta; 8.0 dB | W_VFR detected in the first 96 sampled frames; no audio was extracted. |

## Real-media ASR and smoke evaluation

No full pipeline run completed. A baseline dry-run was attempted and stopped at preflight with `E_MEDIA_TOOL` because ffprobe was not on PATH. It wrote only a preflight-blocked `run_manifest.json`, containing matching before/after source hashes and preflight-stage timing. A subsequent read-only preflight using the installed FFmpeg 9.0.1 binaries reported W_VFR: average and real frame rates matched at 2997/100, but one of 95 sampled intervals exceeded the 1 ms tolerance. Under Prompt 01b, processing stopped before audio extraction. The bounded sample is sufficient to trigger the stop rule but does not characterize every frame in the clip. Optional ASR setup completed with WhisperX 3.8.6 and CUDA PyTorch (`2.8.0+cu128`; CUDA available in the venv, 4095 MiB device capacity). No ASR model/alignment weights or LLM endpoint were used.

| ASR benchmark field | Result |
|---|---|
| Requested model | `small`; weights not fetched |
| Alignment model | Not selected; no language detection run |
| Device / compute type | No inference run; CUDA available in the project venv / N/A |
| Peak VRAM | Not measured; device capacity is 4095 MiB |
| ASR wall time / real-time factor | Not measured |
| Timing sanity | No words processed; short/long/unaligned counts unavailable |

The candidate duration is 78.553107 seconds. Preflight reports the MOV/MP4 family, H.264 High video, AAC-LC stereo audio at 44100 Hz, and rational average/real frame rates of 2997/100. It flags W_VFR because 1 of 95 sampled intervals exceeded the 1 ms tolerance. Language and confidence remain unmeasured. Await direction on a different CFR clip or a working-copy conformity workflow before running dry-run or ASR.

No `words.json` exists for the blocked smoke, so a truth template was not generated. After a successful run, use `python tasks.py truth-template --words runs/<job_id>/words.json --output runs/<job_id>/truth_template.json`, then open it with `notepad runs/<job_id>/truth_template.json`.

## Metric definitions

| Metric | Definition |
|---|---|
| Wall-clock per minute | Total elapsed time and per-stage time from the run manifest divided by source duration in minutes. |
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
