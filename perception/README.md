# Perception

M1 adds a word-level ASR interface, a deterministic fixture engine, a lazy WhisperX adapter with CPU fallback, per-stream audio extraction, and configurable energy refinement for silence gaps. `words.json` remains the shared contract; missing alignments are represented by null times and cannot anchor cuts.

The WhisperX package and model weights are not installed in the current environment. Real audio preflight and extraction are blocked until local `ffprobe` and `ffmpeg` are installed. The adapter has unit coverage, but no real ASR benchmark has been run. See [the words contract](../docs/contracts/words.md), [setup status](../docs/SETUP.md), and [evaluation results](../docs/EVALS.md).
