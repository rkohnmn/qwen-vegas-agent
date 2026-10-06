# Perception

M1 adds a word-level ASR interface, a deterministic fixture engine, a lazy WhisperX adapter with CPU fallback, per-stream audio extraction, and configurable energy refinement for silence gaps. `words.json` remains the shared contract; missing alignments are represented by null times and cannot anchor cuts.

The optional WhisperX 3.8.6 and faster-whisper 1.2.1 packages are installed in the project venv with CUDA PyTorch 2.8.0+cu128; no model weights were fetched. Local FFmpeg 9.0.1 tools were found outside the normal PATH, and a process-local PATH override enabled read-only preflight. That preflight reported `W_VFR`, so audio extraction and ASR remain stopped under Prompt 01b. The adapter has unit coverage, but no real ASR benchmark has been run. See [the words contract](../docs/contracts/words.md), [setup status](../docs/SETUP.md), and [evaluation results](../docs/EVALS.md).
