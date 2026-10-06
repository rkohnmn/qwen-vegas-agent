# Security model

This document summarizes the broker and trust-boundary design in [ARCHITECTURE.md `16](../ARCHITECTURE.md). Milestone 0 implements only local schema checks, config validation, and redaction helpers. No network, asset download, perception, or Vegas execution code is present.

## Broker invariant

The endpoint URL and API key belong only to orchestrator config and memory. The Vegas executor receives neither. `load_config()` reads a gitignored `config.json` or an explicitly supplied `QWEN_VEGAS_API_KEY` value; the environment value is copied into the orchestrator's in-memory config and is not exported to child processes. The example file contains a placeholder endpoint and no API key.

Logs must redact Authorization bearer values and configured secret patterns. The redaction filter operates on rendered log messages and structured secret fields. Config errors and validation issues do not include secret values or absolute local paths.

## Trust boundaries

| Data | Trust | Rule |
|---|---|---|
| Transcript and subtitle text | Untrusted | Data only; never parsed as instructions or executed. |
| Filenames and media metadata | Untrusted | Treat as labels. Resolve paths inside the job working directory before use. |
| Downloaded assets and fetched docs | Untrusted | No asset downloader exists in Milestone 0. Later downloads are owned by the asset manager and license-checked. |
| Planner output | Untrusted | Validate against EDL schema, catalog keys, and referential checks before compiling. |
| Config and speaker files | User-supplied | Validate on load; secret-bearing config is local and gitignored. |
| Ops files | Compiler output, still validated | Closed operation union; executor must validate again and confine all paths. |

## Asset permission policy

The design allowlists configured GitHub sources pinned to a commit and license. A source outside that allowlist requires explicit user permission before fetching. Only the asset manager may download. Milestone 0 includes no downloads and does not change the allowlist.

## Emergency stop

The planned stop file and emergency-stop control must remain honored between Vegas batches. A stop aborts pending work, records an aborted state, and leaves the original project and source media untouched. The stop-file behavior and Vegas batch boundary are `UNVERIFIED` until tested; see VQ-16 and VQ-19 in [VEGAS_NOTES.md](VEGAS_NOTES.md).

## Path and data rules

- Work only on a copy in the declared working directory.
- Reject ops paths outside that directory using a safe error code without returning the resolved absolute path.
- EDL contains IDs and closed catalog keys, never times, colors, plugin IDs, or paths.
- No model, transcript, filename, asset, or fetched document content is executed.
- No telemetry or outbound call is included in Milestone 0.
