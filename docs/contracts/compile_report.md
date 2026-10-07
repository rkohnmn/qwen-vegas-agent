# Compile report contract

Schema version: 2.1.0

Schema: [compile_report.schema.json](../../schemas/compile_report.schema.json)

The compiler report records total removed frames and percentage, warnings, rejected items, an explicit outcome for every EDL cut and gap action, and every cut-boundary snap. Each incoming/outgoing snap names its cut ID and boundary, the original word time (or measured silence frame time), final integer frame, exact rational `final_time` in seconds, millisecond delta, and reason. When PCM is available and configured, the reason records whether the selected frame followed a nearby zero crossing. The frame totals are authoritative; `removed_percent` is a display metric checked against those totals.

Each `item_outcomes` row identifies a cut, gap action, transition, SFX, or effect as `applied`, `adjusted`, or `rejected`. Adjustments require a plain-language reason and positive aggregate `delta_frames` (the sum of absolute boundary shifts from the proposed safe frame ranges). Rejections require a stable error code and reason. Applied rows do not carry adjustment or rejection fields. `rejected_items` remains a compatibility summary of rejected outcomes.

Warnings and rejected items use stable codes and bounded safe messages. They do not include absolute paths, secrets, or transcript text. `check_compile_report` checks the frame totals, percentage, and unique snap IDs.


`fade_decisions` is an optional M1 field. When present it records the crossfade policy and frame count for every compiled join.


The optional sfx_used list carries catalog keys and license identifiers for each emitted SFX operation. The job run manifest copies this list so the final record includes the license without exposing local asset paths.
