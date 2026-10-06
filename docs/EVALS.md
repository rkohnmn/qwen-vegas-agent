# Evaluation results

Every result reports accuracy with runtime and identifies the contract and planner versions. The current offline result is a synthetic plumbing check only; it does not estimate real editing quality.

## Synthetic baseline sanity check

Command: `.venv\Scripts\python.exe tasks.py eval`
Date: 2026-10-06
Dataset: `synthetic-tone-silence-v1`, one generated case using fixture word boundaries and a known filler plus silence gap.
Planner: `baseline-1`
Contracts: words=2.0.0, edl=1.2.0, ops=1.0.0.
Runtime: Python 3.12 on Windows; no external service or user media.

| Metric | Result |
|---|---:|
| Cut precision / recall | 1.0000 / 1.0000 |
| Cut offset error (mean / median / max) | 0 / 0 / 0 ms |
| Clipped-word rate | 0.0000 |
| Click rate | 0.0000 |
| Audio verifier | Failed `join_1_level`, `join_2_level`; click checks passed |
| Removed duration | 19.166667% |
| Wall time | 137.805 ms total; 2.0671 s per minute of synthetic timeline |
| Estimated planner tokens | 63 |
| Compile rejections | 1 (`E_PACING_GAP`: filler removal would leave no configured pause between neighboring words) |
| Planner retries | 0 |

The labeled filler and silence are selected as expected. The compiler rejects the filler removal because it would leave no configured pause between neighboring words; it shortens the long silence while retaining a pause. The two level-step checks fail because the generated tone bursts switch between silence and a fixed-amplitude sine wave at word boundaries. This synthetic waveform is deliberately simple and cannot establish real-speech join quality. The verifier result is retained as a failure rather than tuned to pass the fixture. These one-case selection metrics do not estimate ASR accuracy, human editorial quality, or performance on real footage; the runtime is a plumbing measurement, not a benchmark.

## Real-media ASR and smoke evaluation

Not run. `ffmpeg` and `ffprobe` are absent from PATH and the checked local tool locations, so media inspection and audio extraction cannot start. WhisperX and ASR weights are also not installed. No binaries, Python packages, or model weights were downloaded. Once local prerequisites are available, `python tasks.py dry-run --video <path> --max-seconds 120 --planner baseline` writes an `asr_benchmark.json` with model, device, compute type, peak VRAM when available, elapsed time, and real-time factor.

## Metric definitions

| Metric | Definition |
|---|---|
| Wall-clock per minute | Total elapsed time and per-stage time from the run manifest divided by source duration in minutes. |
| Cut offset error | Absolute milliseconds between each final cut and ground-truth boundary; report mean, median, and maximum. |
| Cut precision and recall | Correct predicted cuts divided by predicted cuts, and correct predicted cuts divided by ground-truth cuts. |
| Clipped-word rate | Fraction of cut boundaries that leave a fragment of an aligned spoken word. |
| Click rate | Fraction of rendered joins flagged for audible discontinuity. |
| Subtitle sync error | Mean and maximum milliseconds between caption bounds and aligned speech. |
| Speaker attribution accuracy | Correct speaker labels divided by labeled words, reported by attribution mode. |
| Color correctness | Captions rendered with the configured speaker color divided by captions checked. |
| Token estimate and retries | Estimated planner tokens and compile/schema retries per run. |

Future real evaluations must include dataset/clip IDs, prompt and schema versions, hardware, per-stage time, accuracy metrics, retries, and the tolerance decision. The eval harness supports editable truth templates through `python tasks.py truth-template --words <words.json> --output <path-under-repo>`.
