# Run manifest contract

Schema version: 1.2.0

Schema: [run_manifest.schema.json](../../schemas/run_manifest.schema.json)

The manifest records input IDs and hashes (never paths), contract versions, Python/media/ASR tool versions, model identifiers, per-stage wall-clock times and outcomes, a characters-based pack token estimate, source hashes before and after, and the final run outcome. A token estimate uses `ceil(pack_characters / 4)`.

`check_run_manifest` verifies the source-integrity flag matches the two hashes, the token estimate follows the documented heuristic, and input IDs are unique. Local paths and transcript contents do not belong in this contract. The optional `source_integrity.files` array records before/after hashes for the project, each declared source-media file, and normalized audio, with an `unchanged` consistency flag.


An optional sfx_used array records every planned SFX catalog key with its required license identifier. It contains no source path. The compiler keeps disabled or unlicensed entries out of operations, and the run manifest checker rejects duplicate or unlicensed records.
