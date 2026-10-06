# Compile report contract

Schema version: 1.0.0

Schema: [compile_report.schema.json](../../schemas/compile_report.schema.json)

The compiler report records the total removed frames and percentage, warnings, rejected items, and every cut-boundary snap. Each snap names a cut ID, its original word time, the final integer frame, the millisecond delta, and the reason. The frame totals are authoritative; `removed_percent` is a display metric checked against those totals.

Warnings and rejected items use stable codes and bounded safe messages. They do not include absolute paths, secrets, or transcript text. `check_compile_report` checks the frame totals, percentage, and unique snap IDs.
