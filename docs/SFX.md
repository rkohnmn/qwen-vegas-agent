# Sound effects

## Local-only library

The indexer reads files and optional same-stem JSON sidecars from a local directory. It does not download, copy, rename, or modify the source samples. Do not index an unknown folder. No starter library is checked in.

A sidecar can provide a license identifier and safe tags:

~~~json
{
  "license": "CC0-1.0",
  "tags": ["whoosh", "topic_change"],
  "source": "locally supplied"
}
~~~

Missing, blank, unknown, or unlicensed metadata disables the entry and reports a warning. Disabled entries are omitted from the model-facing summary. The human remains responsible for confirming license terms. The internal index includes source paths and belongs under ignored runs; do not commit it.

## Index and measurement

Goal 07 Phase B adds the index command for common audio formats supported by local FFmpeg tools. The implementation uses ffprobe for format, duration, and sample rate, and FFmpeg ebur128 for integrated loudness and peak. The index stores a SHA-256 fingerprint and a deterministic key derived from the normalized filename and relative asset identity. It does not expose paths to the planner.

~~~powershell
python tasks.py sfx-index <approved_sfx_dir>
~~~

If FFmpeg or ffprobe is unavailable, indexing fails with a safe typed error. Do not install or download tools for this goal. Synthetic tests use an injected measurement adapter and do not count as real FFmpeg evidence.

## Placement policy

The planner selects an enabled key and an aligned word ID. The compiler chooses frame placement, gain, and any safe adjustment. It applies the configured gain ceiling, rate limit, and speech-peak avoidance. Each proposed item receives an applied, adjusted, or rejected report row. Unlicensed or disabled entries cannot become operations.

No SFX operation is enabled in VEGAS until the local index and disposable-project placement/gain checks record VQ-18 E0 evidence. See REVISIT.md RV-010 and docs/HUMAN_TESTS_M7.md.
