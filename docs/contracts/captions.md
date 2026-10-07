# Captions contract

Schema version: 1.0.0

Schema: [captions.schema.json](../../schemas/captions.schema.json)

Valid example: [valid_minimal.json](../../tests/fixtures/captions/valid_minimal.json)

This code-produced contract stores caption text and integer frame bounds in the edited timeline. It carries stable word IDs and optional emphasis metadata. It never stores a resolved speaker color; the renderer resolves every color from the validated `speakers.json` document.

## Fields

| Field | Type | Meaning and rules |
|---|---|---|
| `schema_version` | string | Required; exactly `1.0.0`. |
| `fps` | rational string | Required; the edited timeline frame rate, such as `30000/1001`. |
| `duration_frames` | integer | Required positive duration of the edited timeline. |
| `captions` | array | Ordered caption events with unique `capN` IDs. |
| `captions[].speaker_key` | key | Required speaker identity; each speaker key is a separate render layer/track for overlap checks. Unknown keys remain unknown. |
| `captions[].text` | string | Required display text with explicit newline line breaks; no model-authored markup. |
| `start_frame`, `end_frame` | integers | Required half-open frame range in the edited timeline; semantic validation requires start < end. |
| `style_key` | key or null | Optional EDL text-preset intent; it does not contain font parameters, colors, paths, or Vegas plugin identifiers. |
| `emphasis` | array | Word-ID spans and mode plus codepoint bounds used to place ASS overrides safely. |
| `confidence_flags` | enum array | May include low speaker confidence, overlap, unknown speaker, and profanity masking. |
| `source_word_ids` | ID array | Ordered source transcript words represented by this caption; semantic validation rejects missing IDs, multiple speaker identities within one caption, and speaker mismatch. |

## Timing and overlap

The builder converts source word times to frames with rational arithmetic, then maps fully retained words through the compiled half-open keep ranges. Words intersecting a removed range are omitted and reported rather than rendered with a clipped boundary. Captions split at speaker changes and removed source gaps. `speaker_key` is the caption track key: captions on the same speaker track may not overlap; different speakers may overlap to preserve simultaneous speech. Semantic validation rejects bounds beyond the edited timeline duration.

SRT timestamps round to milliseconds and ASS timestamps round to centiseconds. Parsing them back and rounding to the contract frame grid must recover the same frames; the JSON contract remains the exact timing source.

## Color and serialization

The contract rejects undeclared fields, so an EDL color or a caption color is invalid. SRT remains uncolored plain text. ASS styles use only each mapped speaker color or an entry from `unknown_palette`; outline/box colors are style settings, never speaker colors. Transcript braces, backslashes, and line breaks are escaped before ASS override blocks are added.

The renderer also writes `captions_report.json`, which contains only counts, IDs, frame ranges, and reason codes—not transcript text or media paths. It reports contrast warnings, low-confidence ranges, timing-density violations, and words intersecting removed ranges.

## Producer and consumer

| Role | Component |
|---|---|
| Produces | Deterministic caption builder after EDL compilation. |
| Consumes | SRT/ASS sidecar writers, ASS burn-in adapter, and future Vegas renderer behind the `CaptionRenderer` interface. |
