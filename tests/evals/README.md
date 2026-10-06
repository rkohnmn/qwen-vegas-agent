# M1 evaluation assets

M1 generates its audio-like tone/silence timeline in code and uses fixture word boundaries; it does not store rendered clips. The deterministic baseline sanity run is available with python tasks.py eval and is documented in docs/EVALS.md.

For a real clip, create an editable *.truth.json with this shape:

- schema_version: 1.0.0
- source_hash: SHA-256 of the source file
- expected_cuts: list of expected boundaries with from_text, to_text, approximate_start_s, approximate_end_s, and category; gap cuts may also identify before_text and after_text
- speaker_labels: list of word_text and expected speaker key records
- notes: short evaluation comments

Ground truth may contain approximate times because it is labeled human data. Planner EDL output remains ID-only. Use python tasks.py truth-template --words <words.json> --output <path-under-repo> to generate an editable transcript index, then fill expected_cuts, speaker_labels, and notes. Keep media files local; do not add private clips to version control.
