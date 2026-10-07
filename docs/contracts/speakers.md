# Speakers contract

Schema version: 1.1.0

Schema: [speakers.schema.json](../../schemas/speakers.schema.json)

Valid example: [valid_minimal.json](../../tests/fixtures/speakers/valid_minimal.json)

This user-maintained document maps stable speaker keys to display labels, subtitle palette colors, and optional track and local voice-profile metadata. Version 1.1.0 is a backward-compatible minor addition. The model sees keys, not color values or voice-profile paths.

## Fields

| Field | Type | Meaning and rules |
|---|---|---|
| `schema_version` | string | Required; exactly `1.1.0`. |
| `speakers` | object | Required map of 1–64 speaker keys. Keys match `^[a-z][a-z0-9_]*$`. |
| `speakers.<key>.display` | string | Required non-empty display label, maximum 80 characters. |
| `speakers.<key>.color` | string | Required literal hex color matching `#RRGGBB`. |
| `speakers.<key>.track` | string | Optional multitrack source label, maximum 120 characters; matches a stream title or documented Mic N/Track N alias. |
| `speakers.<key>.track_mode` | enum | Optional per-track rule: `single_speaker` for one mapped voice or `mixed` when diarization is required. |
| `speakers.<key>.voice_profile` | string | Optional local profile reference used by diarized matching, maximum 260 characters. Keep profile files under the ignored `voices/` directory. |
| `speakers.<key>.voice_profile_metadata` | object | Optional model ID, embedding dimension, 16 kHz sample rate, sample duration, and passed/assumed quality status. Contains no audio or credential. |
| `unknown_palette` | array | Required 1–16 hex colors used when attribution remains unknown. |

## Validation rules

JSON Schema rejects malformed keys, colors, excess entries, missing fields, and undeclared properties. It does not silently assign an unknown speaker a known speaker's color. Low-confidence attribution must remain visible to later reports.

## Producer and consumer

| Role | Component |
|---|---|
| Produces | User/editor; the example is a template, not an enrolled voice profile. |
| Consumes | Perception, compiler, and subtitle renderer; only speaker keys are exposed to the planner. |

## Example

See the linked valid fixture for two speakers with separate tracks and a three-color unknown palette.
