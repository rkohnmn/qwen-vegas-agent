# Executor capabilities contract

Schema version: 1.0.0

Schema: [capabilities.schema.json](../../schemas/capabilities.schema.json)

This contract is an executor-reported allowlist for optional catalog-backed M7 operations. It accepts only add_transition, add_audio_event, set_gain, and apply_fx. A capability is honored only when the document names the required E0-backed VEGAS questions:

| Operation | Required verified questions |
|---|---|
| add_transition | VQ-05 and VQ-06 |
| add_audio_event | VQ-18 |
| set_gain | VQ-18 |
| apply_fx | VQ-04 and VQ-17 |

The compiler defaults to an empty capability document. Missing, invalid, or incomplete evidence means the operation is unavailable. This repository has no runtime executor and currently advertises no M7 operation. Test-only capability fixtures do not count as VEGAS evidence.

The capability document contains no endpoint, credential, or filesystem path. A future executor must generate it from probes recorded in VEGAS_NOTES.md, and the compiler must validate it before producing a catalog-backed operation.
