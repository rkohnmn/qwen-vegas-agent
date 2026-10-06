# Timeline contract

Schema version: 1.0.0

Schema: [timeline.schema.json](../../schemas/timeline.schema.json)

The M1 timeline represents one source file in a synthetic, frame-based A/V sequence. It contains one video event, one or more audio events (one per selected audio stream), and exactly one linked group. Every event begins at timeline frame zero and carries its source offset and integer frame length. `fps` is a positive rational string; all frame positions are integers.

| Field | Meaning |
|---|---|
| `source_hash` | SHA-256 identity of the read-only source media. |
| `fps` | Rational frame rate used for M1 frame conversion. |
| `duration_frames` | Positive source duration in frames. |
| `tracks` | Typed audio/video tracks with stable IDs and indices. |
| `groups` | One linked A/V group listing every event ID. |
| `events` | Track/group references, timeline start frame, source offset, and length. |

`check_timeline` verifies uniqueness, track/group/event references, complete group membership, source-range bounds, and the presence of exactly one video event plus at least one audio event. The later Vegas dumper must emit this same shape; this synthetic contract does not claim any Vegas behavior.
