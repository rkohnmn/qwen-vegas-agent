# Words contract

Schema version: 2.1.0

Schema: [words.schema.json](../../schemas/words.schema.json)

Valid example: [valid_minimal.json](../../tests/fixtures/words/valid_minimal.json)

This contract is the perception layer's transcript view of one source project. Aligned times are seconds from source-media start; compiler code later resolves IDs to frame positions. Version 2.0.0 is a breaking change because it represents forced-alignment failures explicitly. Version 2.1.0 is a backward-compatible minor addition: it adds the optional overlap marker and the hybrid mode value.

## Fields

| Field | Type | Meaning and rules |
|---|---|---|
| `schema_version` | string | Required; exactly `2.1.0`. |
| `source_hash` | string | Required SHA-256 media identity, formatted `sha256:<64 lowercase hex>`. |
| `fps` | string | Required positive rational frame rate, such as `30000/1001`; decimals are rejected. |
| `asr` | object | Required engine metadata: `engine`, `model`, `align_model`, and `params_hash`; detected language, confidence, device, compute type, and CPU-fallback reason are optional. No undeclared keys. |
| `speaker_mode` | enum | Required: `multitrack`, `diarized`, `hybrid`, or `single`. |
| `words` | array | Required, non-empty, at most 200,000 records. Each word has `id`, `text`, `alignment_status`, `start`, `end`, `speaker`, `speaker_conf`, and `word_conf`; `track` and `overlap` are optional. `overlap: true` marks an aligned word whose time intersects another speaker turn. Aligned words have non-negative numeric times. Unaligned words have null times and `alignment_status: unaligned`. |
| `segments` | array | Required phrase groupings with a unique-in-document `sN` ID, one or more `wN` references, and optional speaker key. |
| `gaps` | array | Required silence/gap index. Each entry has a unique-in-document `gN` ID and non-negative `start` and `end`. Optional `refinement` records original ASR bounds and energy-refined bounds plus the RMS threshold method. |
| `audio_events` | array | Required detected non-speech events with a bounded `type` and non-negative `start`/`end` times. |

Word and segment speaker keys use `^[a-z][a-z0-9_]*$`. Confidence values are inclusive from 0 to 1. IDs remain stable for one canonical words hash; a new ASR run can produce a new set of IDs.

## Validation rules

JSON Schema enforces field types, bounds, exact keys, ID patterns, and the rational FPS syntax. `check_words` additionally rejects duplicate word or gap IDs, decreasing aligned-word starts, invalid aligned/un-aligned timing combinations, end-before-start ranges, and segment references to missing words. EDL references to unaligned words are rejected. It returns short error codes without echoing transcript text.

Canonical hash: serialize the full words document as UTF-8 JSON with object keys sorted, compact separators, non-ASCII text preserved, and array order unchanged; prefix the SHA-256 hex digest with `sha256:`. The EDL's `words_hash` must equal this value.

## Producer and consumer

| Role | Component |
|---|---|
| Produces | Perception stage (ASR/alignment and silence analysis); implemented in Milestone 1. |
| Consumes | Context packer and compiler; The context packer omits timing for unaligned words; the compiler requires aligned word IDs for any cut. |

## Example

Use the linked fixture as the canonical valid example. It includes two speakers, two segments, two gaps, and an audio event.
