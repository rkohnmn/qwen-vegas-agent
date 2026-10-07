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

The index command supports WAV, MP3, FLAC, OGG, M4A, AAC, AIFF, and AIF inputs when the local FFmpeg tools can decode them. The implementation uses ffprobe for format, duration, and sample rate, and FFmpeg ebur128 for integrated loudness and peak. The index writes runs/sfx-index/sfx_index.json by default. It stores a SHA-256 fingerprint and a deterministic key derived from the normalized filename, relative asset identity, and content fingerprint. Catalog build can merge the index with --sfx-index; generated catalog tags keep those entries disabled until human opt-in. It does not expose paths to the planner.

~~~powershell
python tasks.py sfx-index <approved_sfx_dir>
~~~

If FFmpeg or ffprobe is unavailable, indexing fails with a safe typed error. Do not install or download tools for this goal. Synthetic tests generate a PCM tone and use an injected measurement adapter to test indexing; a parser fixture tests FFmpeg ebur128 output. Neither counts as a real FFmpeg measurement. At this workstation ffmpeg and ffprobe were not found, so real loudness evidence is pending under RV-010.

## Placement policy

When explicitly enabled, the deterministic baseline planner can suggest an enabled key at a configured long-gap trigger with low confidence. The planner selects an enabled key and an aligned word ID. The compiler chooses frame placement, gain, and any safe adjustment. It applies the configured gain ceiling, rate limit, and speech-peak avoidance. Each proposed item receives an applied, adjusted, or rejected report row. Unlicensed or disabled entries cannot become operations.

No SFX operation is enabled in VEGAS: the executor is absent and the default capability set is empty. No operation can be emitted until the local index, disposable-project placement/gain checks, and VQ-18 E0 evidence exist. See REVISIT.md RV-010 and docs/HUMAN_TESTS_M7.md.
