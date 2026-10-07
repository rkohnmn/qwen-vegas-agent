# Security model

This document records the M1 trust boundaries. Media is read-only input; generated artifacts live under the repository's ignored `runs/` and `cache/` directories. M1 does not launch VEGAS or call an inference endpoint.

## Broker and credentials

The endpoint URL and API key belong only to orchestrator config and memory. Vegas code and child processes receive neither. Any future network client must live in the orchestrator, redact Authorization headers and configured secret patterns, and use bounded timeouts. M1's LLM adapter is restricted to loopback addresses and is used only with fake local test servers; `--planner llm` is disabled in the CLI.

## Trust boundaries

| Data | Trust | Rule |
|---|---|---|
| Transcript and subtitle text | Untrusted | Data only; quote/escape it in packs; never parse it as instructions or execute it. |
| Filenames and media metadata | Untrusted | Treat as labels. Read the input media without modifying it; write generated results only into the job output/cache directories. |
| Downloaded assets and fetched docs | Untrusted | M1 has no downloader. Future asset fetches belong only to the asset manager and must follow the allowlist and license policy. |
| Planner output | Untrusted | Validate EDL schema, catalog keys, hash, and referential constraints before compiling. |
| Config and speaker files | User-supplied | Validate on load; `config.local.json` and `config.json` are gitignored. |
| Ops files | Compiler output, still validated | Closed operation union; future executor must validate again and confine paths to the declared working copy. |
| Environment variables | Untrusted and potentially secret-bearing | Remove secret-like names before starting ffmpeg, ffprobe, compiler/test child processes; never forward configured keys. |

## Asset permission policy

Only allowlisted GitHub sources pinned to a commit and license may be fetched without another permission step. Any other source requires explicit user permission. No assets or binaries were downloaded for M1; ffmpeg binaries and ASR weights remain user-managed prerequisites.

## Stop and source integrity

M1 never writes source media or the VEGAS installation. The dry-run hashes source media before and after the pipeline and records both values in the run manifest. Vegas batch stop behavior is a later executor requirement and remains unverified until tested on a throwaway project.

## Data rules

- Keep model credentials in the orchestrator only; do not pass them to Vegas or child processes.
- Keep EDL intent ID-only: no numeric times/durations, colors, plugin IDs, file paths, or executable strings.
- Reject unaligned words as cut anchors; preserve their transcript text without fabricated timestamps.
- Never execute content from a model, transcript, filename, asset, or fetched document.
- Do not add telemetry or unrelated outbound calls.

## Hugging Face and speaker data

HF read tokens are credentials. The current speaker path does not read HF_TOKEN or a token from local config because no accepted diarization or embedding backend is configured. The enrollment command validates the local WAV and stops with the G2 / RV-005 explanation. Do not pass a token on the command line, write it to a tracked file, or copy it into an error, run artifact, transcript, speakers.json, or voice profile.

When a backend is added, keep the token only in the orchestrator's secret-bearing process/config boundary, redact it from errors and request records, and remove token-like variables from every child process environment. Model-card terms and accepted model IDs may be recorded; token values may not. Voice profiles under ignored voices/ contain embeddings and metadata only. The root speakers.json is also gitignored because it holds user-maintained identities and track assignments.
