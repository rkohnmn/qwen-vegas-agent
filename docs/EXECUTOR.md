# VEGAS Executor Contract and Status

This page describes the intended boundary for a future VEGAS Pro executor. The repository currently contains probe scripts only; it does not contain a runtime executor that applies operations. No code in `orchestrator/job_pipeline.py` launches Vegas. Its `DisabledVegasExecutor` fails closed unless a test supplies a fake adapter.

## Data flow

The deterministic compiler is the only producer of `ops.json`. The file follows the closed operation union in [the ops contract](contracts/ops.md) and the machine schema at `../schemas/ops.schema.json`. Model output, transcript text, arbitrary paths, and executable strings are never executor input. The planned executor must validate the complete batch again before applying it.

The orchestrator owns endpoint credentials. The Vegas process receives only a validated operation batch and a declared working-copy path. All project mutations must stay under the job's working directory; source media and the original project remain read-only. Each mutation batch must be undoable when VQ-08 is confirmed. Unknown operations fail closed. The stop signal is checked between bounded batches.

## Current implementation status

| Capability | Status |
|---|---|
| Compiler emits frame-based cut/gap operations | Implemented and unit-tested offline |
| Review sidecars (markers CSV, cutlist EDL, review report) | Implemented offline; no Vegas markers are written |
| Per-cut approval and exact subset recompilation | Implemented and unit-tested offline |
| Runtime executor and Vegas project mutation | Not implemented; blocked on human probes, see RV-001 |
| M7 optional operations | Capability contract and compiler gates are implemented; default capability set is empty, and no executor advertises support |
| Undo, linked-event handling, stop-file behavior inside Vegas | Unverified; see VQ-07, VQ-08, VQ-11, and VQ-16 |
| Vegas preview/final rendering | Not implemented; manual render remains a human step |

## Enablement gate

Do not add an executor implementation that depends on an API member or transport without recording its evidence in [VEGAS_NOTES.md](VEGAS_NOTES.md). Run the applicable disposable-project checklist, record E0 observations, then update the relevant VQ status and this page. The API map and safety protocol are in [the architecture](../ARCHITECTURE.md#12-the-vegas-executor) and [VEGAS_NOTES.md](VEGAS_NOTES.md).
