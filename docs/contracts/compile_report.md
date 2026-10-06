# Compile report contract

Schema version: 1.2.0

Schema: [compile_report.schema.json](../../schemas/compile_report.schema.json)

The compiler report records the total removed frames and percentage, warnings, rejected items, and every cut-boundary snap. Each incoming/outgoing snap names its cut ID and boundary, the original word time (or measured silence frame time), final integer frame, exact rational `final_time` in seconds, millisecond delta, and reason. When PCM is available and configured, the reason records whether the selected frame followed a nearby zero crossing. The frame totals are authoritative; `removed_percent` is a display metric checked against those totals.

Warnings and rejected items use stable codes and bounded safe messages. They do not include absolute paths, secrets, or transcript text. `check_compile_report` checks the frame totals, percentage, and unique snap IDs.


`fade_decisions` is an optional M1 field. When present it records the crossfade policy and frame count for every compiled join.
