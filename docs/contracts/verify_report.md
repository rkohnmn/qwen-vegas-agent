# Verify report contract

Schema version: 1.0.0

Schema: [verify_report.schema.json](../../schemas/verify_report.schema.json)

A verification report contains an overall `passed` flag, per-check values and thresholds, and machine-readable fix suggestions. Checks cover click discontinuity, level step, pacing, clipped words, and removed-percent sanity. Join- and cut-scoped checks carry a target ID. Failed checks require a fix suggestion targeting that check.

`check_verify_report` confirms the overall result matches its checks and every failed check has a suggestion.
