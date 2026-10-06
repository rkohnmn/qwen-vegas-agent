# Words contract

Schema version: 1.0.0

Schema: [words.schema.json](../../schemas/words.schema.json)

Valid example: [valid_minimal.json](../../tests/fixtures/words/valid_minimal.json)

This contract is the perception layer's word-aligned view of one source project. Times are seconds from source-media start; compiler code later resolves IDs to frame positions.

## Fields

| Field | Type | Meaning and rules |
|---|---|---|
| `schema_version` | string | Required; exactly `1.0.0`. |
| `source_hash` | string | Required SHA-256 media identity, formatted `sha256:<64 lowercase hex>`. |
| `fps` | string | Required positive rational frame rate, such as `30000/1001`; decimals are rejected. |
| `asr` | object | Required engine metadata: `engine`, `model`, `align_model`, and `params_hash`. No undeclared keys. |
| `speaker_mode` | enum | Required: `multitrack`, `diarized`, or `single`. |
| `words` | array | Required, non-empty, at most 200,000 records. Each word has `id`, `text`, non-negative `start` and `end`, `speaker`, `speaker_conf`, and `word_conf`; `track` is optional. |
| `segments` | array | Required phrase groupings with a unique-in-document `sN` ID, one or more `wN` references, and optional speaker key. |
| `gaps` | array | Required silence/gap index. Each entry has a unique-in-document `gN` ID and non-negative `start` and `end`. This index lets EDL anchors refer to silence without sending times. |
| `audio_events` | array | Required detected non-speech events with a bounded `type` and non-negative `start`/`end` times. |

Word and segment speaker keys use `^[a-z][a-z0-9_]*$`. Confidence values are inclusive from 0 to 1. IDs remain stable for one canonical words hash; a new ASR run can produce a new set of IDs.

## Validation rules

JSON Schema enforces field types, bounds, exact keys, ID patterns, and the rational FPS syntax. `check_words` additionally rejects duplicate word or gap IDs, decreasing word starts, end-before-start ranges, and segment references to missing words. It returns short error codes without echoing transcript text.

Canonical hash: serialize the full words document as UTF-8 JSON with object keys sorted, compact separators, non-ASCII text preserved, and array order unchanged; prefix the SHA-256 hex digest with `sha256:`. The EDL's `words_hash` must equal this value.

## Producer and consumer

| Role | Component |
|---|---|
| Produces | Perception stage (ASR/alignment and silence analysis); not implemented in Milestone 0. |
| Consumes | Context packer and compiler; Milestone 0 only validates the shape and references. |

## Example

Use the linked 30-word fixture as the canonical valid example. It includes two speakers, two segments, two gaps, and an audio event.
