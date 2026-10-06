# Catalog contract

Schema version: 1.0.0

Schema: [catalog.schema.json](../../schemas/catalog.schema.json)

Valid example: [valid_realistic.json](../../tests/fixtures/catalog/valid_realistic.json)

The catalog is the closed set of transitions, effects, text presets, and sound effects that a plan may select. The internal file retains identifiers and paths needed by deterministic code. The planner receives only a derived allowlisted summary.

## Fields

| Field | Type | Meaning and rules |
|---|---|---|
| `schema_version` | string | Required; exactly `1.0.0`. |
| `vegas_version` | string | Required source application version label. Vegas behavior remains `UNVERIFIED` unless a VQ entry has recorded evidence. |
| `plugin_list_hash` | string | Required SHA-256 identity of the enumerated plugin list. |
| `transitions`, `video_fx`, `audio_fx`, `text_presets`, `sfx` | arrays | Required category groups. Every entry has `key`, `kind`, `tags`, and `params_mode`. Group and `kind` must agree. |
| `key` | string | Category-prefixed deterministic key, such as `tr.crossfade-short.a1b2c3`. |
| `kind` | enum | `transition`, `video_fx`, `audio_fx`, `text_preset`, or `sfx`. |
| `tags` | string array | Up to 32 unique descriptive tags. |
| `params_mode` | enum | `params`, `preset_only`, or `defaults_only`; it states what the compiler may apply. |
| `plugin_unique_id` | string | Internal plugin identifier. Permitted in the catalog and ops contract only; never included in planner summaries. |
| `params` | object | Internal extensible plugin parameter map. It is an extension point for installed plugin names/types and is never sent to the model. |
| `presets`, `supports_color_override`, `default_duration_frames` | optional typed fields | Preset choices and transition/text capabilities, according to the entry kind. |
| `path`, `duration`, `loudness_lufs`, `license`, `source` | SFX metadata | Internal local asset path, duration seconds, loudness, license, and provenance. Paths are not exposed in the model summary. |

## Deterministic key construction

Choose the category prefix (`tr`, `vfx`, `afx`, `txt`, `sfx`); normalize the display name with Unicode NFKD, lowercase it, replace each run of non-ASCII alphanumeric characters with `-`, and trim hyphens. Append the first 6–12 lowercase hexadecimal characters of SHA-256 over the stable plugin UID or asset identity. If the normalized name is empty, use `item`. This makes same-name plugins collision-safe and stable for the same catalog source.

`check_catalog` rejects duplicate keys across every category group.

## Planner summary

`catalog_summary` derives:

```json
{
  "schema_version": "1.0.0",
  "entries": [
    {"key": "tr.crossfade-short.a1b2c3", "kind": "transition",
     "tags": ["soft"], "params_mode": "params",
     "default_duration_frames": 12}
  ]
}
```

The summary uses an explicit field allowlist. It excludes `plugin_unique_id`, `path`, and arbitrary `params` values so filesystem paths or plugin internals cannot leak through nested metadata.

## Producer and consumer

| Role | Component |
|---|---|
| Produces | Vegas catalog dumper plus the local asset index; neither is implemented in Milestone 0. |
| Consumes | Planner receives the derived summary; compiler validates keys against the full catalog. |
