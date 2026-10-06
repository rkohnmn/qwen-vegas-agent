# Evaluation format

No evaluation results exist yet. Milestone 0 does not run perception, planner, compiler timing, Vegas, or video quality evaluations.

Every future evaluation must report accuracy together with time and identify prompt/schema versions. Speed does not excuse an accuracy regression.

## Metrics

| Metric | Definition |
|---|---|
| Wall-clock per minute of footage | Total elapsed time and per-stage time from the run manifest, divided by source duration in minutes. |
| Cut offset error | Absolute milliseconds between each final cut and its ground-truth boundary. Report mean, median, and maximum. |
| Cut precision and recall | Expected cuts found / all emitted cuts, and expected cuts found / all ground-truth cuts. |
| Clipped-word rate | Fraction of cuts that leave a fragment of a spoken word. |
| Click rate | Fraction of joins flagged for audible discontinuity by the verifier. |
| Subtitle sync error | Mean and maximum milliseconds between caption bounds and aligned speech. |
| Speaker attribution accuracy | Correct speaker labels divided by labeled words, reported separately for multitrack and diarized modes. |
| Color correctness | Captions rendered with the configured speaker color divided by captions checked. |
| Token usage | Prompt and completion tokens per video. |
| Planner retries | Compile/schema rejection retries per run. |

## Report template

| Field | Value |
|---|---|
| Eval date | |
| Dataset / clip IDs | |
| Prompt version | |
| Schema versions (words, speakers, catalog, edl, ops) | |
| Runtime / hardware | |
| Accuracy metrics | |
| Wall-clock and per-stage time | |
| Tokens and planner retries | |
| Baseline comparison and tolerance decision | |

The eval harness and clips are deferred to [ROADMAP.md](../ROADMAP.md).
