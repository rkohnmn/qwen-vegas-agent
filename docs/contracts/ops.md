# Ops contract

Schema version: 1.0.0

Schema: [ops.schema.json](../../schemas/ops.schema.json)

Valid example: [valid_realistic.json](../../tests/fixtures/ops/valid_realistic.json)

Ops is the compiler-produced executor input. This contract is not accepted from the model.

## Header fields

| Field | Type | Meaning |
|---|---|---|
| `schema_version` | string | Required; exactly `1.0.0`. |
| `header.job_id` | string | Stable bounded job identifier. |
| `header.working_copy_path` | string | Declared project-copy path; `check_ops` rejects escape from the supplied working directory. |
| `header.fps` | string | Positive rational project rate, carried with every batch. |
| `header.source_hashes` | array | Source IDs and lowercase SHA-256 digests used by this job. |

## Operation union

Each item has one discriminating `op` value. Frame positions/durations are non-negative integers; no floating-point seconds are accepted.

| Operation | Required fields after `op` | Vegas mechanism status |
|---|---|---|
| `add_marker` | `marker_id`, `frame`, `label` | `UNVERIFIED` — VQ-13 |
| `add_region` | `region_id`, `start_frame`, `end_frame`, `label` | `UNVERIFIED` — VQ-13 |
| `split` | `event_id`, `frame`, `group_ids` | `UNVERIFIED` — VQ-07, VQ-11 |
| `delete_range` | `start_frame`, `end_frame`, `track_ids`; optional `group_ids` | `UNVERIFIED` — VQ-07 |
| `close_gap` | `from_frame`, `frame_count`, `track_ids`; optional `group_ids` | `UNVERIFIED` — VQ-07 |
| `trim` | `event_id`, `start_frame`, `length_frames`; optional `take_offset_frames` | `UNVERIFIED` — VQ-07, VQ-12 |
| `set_fade` | `event_id`, `direction`, `frames`, `curve` | `UNVERIFIED` — VQ-06 |
| `add_transition` | left/right event IDs, catalog key, internal plugin ID, duration frames | `UNVERIFIED` — VQ-05 |
| `add_audio_event` | event/track IDs, SFX catalog key, confined file path, start/length frames, gain | `UNVERIFIED` — VQ-18 |
| `set_gain` | target type/ID and gain in dB | `UNVERIFIED` — VQ-18 |
| `apply_fx` | target type/ID, catalog key, internal plugin ID, bounded parameters | `UNVERIFIED` — VQ-04, VQ-17 |
| `add_text_event` | event/track IDs, start/length frames, text copied from words | `UNVERIFIED` — VQ-09 |
| `set_text_style` | event ID, text-style key, resolved hex color; optional plugin ID/parameters | `UNVERIFIED` — VQ-09, VQ-10 |
| `render_preview` | confined output path, start/end frames, template key | `UNVERIFIED` — VQ-14 |
| `render_final` | confined output path and template key | `UNVERIFIED` — VQ-14 |
| `save_checkpoint` | bounded checkpoint ID | `UNVERIFIED` — VQ-15 |
| `clear_markers_by_prefix` | bounded prefix | `UNVERIFIED` — VQ-13 |

Every Vegas API mechanism is unverified; this table maps intended operations to the open questions in [VEGAS_NOTES.md](../VEGAS_NOTES.md). No Vegas behavior is claimed by schema validation or unit tests.

## Safety and producers/consumers

The compiler is the only producer. The executor validates the schema again before applying each batch. Resolved colors, plugin IDs, and confined filesystem paths are allowed here because the compiler resolves them from validated speaker/catalog/work-directory data. Credentials, model-authored operations, or arbitrary code strings are not permitted.

| Role | Component |
|---|---|
| Produces | Deterministic frame compiler; implemented for M1 cut and gap operations. |
| Consumes | Vegas executor; deferred to M2. No ops are executed by M1. |
