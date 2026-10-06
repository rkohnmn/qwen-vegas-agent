# EDL contract

Schema version: 1.1.0

Schema: [edl.schema.json](../../schemas/edl.schema.json)

Valid example: [valid_realistic.json](../../tests/fixtures/edl/valid_realistic.json)

The EDL is the planner's complete edit-intent document. The model chooses IDs and catalog keys; deterministic code chooses every time and frame value.

## Fields

| Field | Type | Meaning and rules |
|---|---|---|
| `schema_version` | string | Required; exactly `1.1.0`. |
| `words_hash` | string | Required SHA-256 canonical hash of the exact words document. |
| `summary` | string | Bounded plain-language overview (maximum 1,000 characters). |
| `gap_actions` | array | Optional gap edits by `gap_id`, with `mode` `remove` or `shorten`; the compiler config supplies the retained length. No numeric time or duration is accepted. Each action carries a unique cut ID, reason, confidence, and `silence` category. |
| `cuts` | array | Up to 500 unique `cN` IDs. Each cut contains `remove.from_word`, `remove.to_word`, bounded `reason`, confidence 0–1, and category `filler`, `silence`, `retake`, `false_start`, `dead_air`, `tangent`, or `other`. |
| `keeps_reordered` | array | Required and empty-only in v1.1.0; schema rejects any item. Reordering is reserved for a later contract version. |
| `transitions` | array | Each transition references a cut ID, has an `offset_hint` (`before`, `at`, `after`), a transition catalog key, and a bounded reason. |
| `sfx` | array | Each item anchors to a word ID plus `offset_hint`, a catalog key, bounded gain in dB, and reason. |
| `subtitles` | object | Catalog style key, emphasis spans by word IDs, optional break hints by word ID, and omission ranges by word IDs. Speaker colors are never supplied here. |
| `tool_requests` | array | Bounded discriminated requests of type `frames`, `asset`, or `reference`. Frame requests use a typed ID anchor, not a numeric frame or time. Asset queries carry text/tags, not a path or URL. |
| `questions` | array | Bounded `ask_user` pauses, optionally anchored to an ID or speaker key; a non-empty array pauses planning. |

All objects reject undeclared fields. Thus numeric timestamp fields, hex color fields, plugin GUID fields, and filesystem path fields fail schema validation. Numeric confidence, gain, count, and bounded request fields are allowed because they are not timestamps.

## Gap handling

A `gap_actions` item names a known `gN` gap and one enum mode. `shorten` uses the compiler configuration value; the planner cannot choose a kept duration. The referential validator rejects missing or repeated gap references and IDs duplicated with a word cut.

## References and validation

Anchors can use word (`wN`), segment (`sN`), gap (`gN`), event (`eN`), or cut (`cN`) IDs with an `offset_hint`. The validator checks word, segment, gap, cut, catalog, speaker, hash, cut ordering, and overlapping-cut references. Event anchors are checked when timeline data is supplied. Ranges are inclusive by word order; equal endpoints remove one word.

All strings and arrays have explicit maximums so model output fails quickly. Error messages report a code and safe field path, never transcript text, secrets, or local absolute paths.

## Producer and consumer

| Role | Component |
|---|---|
| Produces | Planner (runtime prompt is deferred; no model calls in Milestone 1). |
| Consumes | Referential validator and later deterministic compiler. |
