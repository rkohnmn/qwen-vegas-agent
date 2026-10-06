# Perception

M1 provides word-level ASR behind an engine interface, a deterministic fixture engine, per-stream audio extraction, and energy-based silence refinement. `words.json` remains the shared contract; unaligned words have null times and cannot anchor cuts.

The real-media smoke used faster-whisper `small` with VAD disabled, followed by WhisperX forced alignment for the detected language. It ran on CUDA with `int8_float16`, used 1.27 GB peak VRAM, and took 37.367 seconds for 78.545 seconds of benchmark audio (real-time factor 0.4757). The detector returned Japanese at 0.9399 confidence. WhisperX returned 298 timed subword rows, but their segmentation did not match the word-level contract. All 30 phrase-level tokens remained unaligned, so the baseline planner produced no edits. No diarization or LLM call occurred.

Normalized concatenation matched each ASR segment, but the adapter kept the coarser phrases unaligned rather than guessing lexical boundaries. The two approved checkpoints are cached locally under ignored `cache/`; their exact revisions, byte sizes, and absent license files are recorded in [decisions](../DECISIONS.md#d-32-record-asr-checkpoints-and-smoke-measurements). The adapter disables VAD and diarization weight loading. See [the words contract](../docs/contracts/words.md), [setup measurements](../docs/SETUP.md), and [evaluation results](../docs/EVALS.md).
