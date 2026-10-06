# Speakers contract

Schema version: 1.0.0

Schema: [speakers.schema.json](../../schemas/speakers.schema.json)

Valid example: [valid_minimal.json](../../tests/fixtures/speakers/valid_minimal.json)

This user-maintained document maps stable speaker keys to display labels and subtitle palette colors. The model sees keys, not color values or voice-profile paths.

## Fields

| Field | Type | Meaning and rules |
|---|---|---|
| `schema_version` | string | Required; exactly `1.0.0`. |
| `speakers` | object | Required map of 1–64 speaker keys. Keys match `^[a-z][a-z0-9_]*$`. |
| `speakers.<key>.display` | string | Required non-empty display label, maximum 80 characters. |
| `speakers.<key>.color` | string | Required literal hex color matching `#RRGGBB`. |
| `speakers.<key>.track` | string | Optional multitrack source label, maximum 120 characters. |
| `speakers.<key>.voice_profile` | string | Optional local profile reference used by diarized matching, maximum 260 characters. Keep profile files under the ignored `voices/` directory. |
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
