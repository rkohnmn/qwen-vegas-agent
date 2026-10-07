# Human acceptance checks: Goal 07

Run only on a disposable VEGAS Pro 17 project built from synthetic media. Do not use original projects, source media, production SFX, or user content. Never run a downloaded or community script. Read the checked-in CatalogDump probe before use. Record results without private paths or transcript text.

## Prerequisites

- VEGAS Pro 17 and a disposable test project with two short linked A/V events.
- A local .NET Framework C# 5 compiler for compile-only checks.
- An approved local FFmpeg/ffprobe installation for real SFX loudness measurements.
- A local sample folder whose license terms have been confirmed by a human. Keep this folder outside Git.
- A rough transition allowlist from G4.

If a prerequisite is absent, mark that section not run and keep the dependent operation disabled. Do not infer a license or substitute a downloaded asset.

## Catalog dump and build

1. Inspect vegas/probes/CatalogDump.cs and confirm it writes only the probe JSON. Compile it in C# 5 mode if the compiler and reference assembly are available; do not launch VEGAS from a command line.
2. Open the disposable project and run the probe using the human-approved method. Do not open a production project.
3. Confirm the JSON parses and contains category, display name, unique ID, OFX flag, and depth. Record the plugin-list hash, counts, duplicate display names, folders, and generator entries.
4. Run the local builder with the generated dump. Confirm a first-run tag file is created and every entry is disabled. Confirm the planner summary contains no disabled keys, GUIDs, paths, or arbitrary parameters.
5. Rebuild from the same dump and confirm keys and plugin-list hash remain stable.

Expected: the dump parses, duplicate display names have distinct keys, and no item becomes planner-visible without a human tag-file opt-in.

## Transition and effect checks

Do not attempt these steps until RV-009 probes pass and a later executor implementation advertises the operation.

1. Enable a small, named set of transitions in the tag file and record the human's allowed contexts and default durations.
2. Apply every enabled transition once to synthetic two-event TP media. Check the requested duration, preview frames around the boundary, and linked audio/video sync.
3. Test the transition on a cut created by the pipeline, including a short clip that should be rejected.
4. Listen to each audio join at normal and amplified volume. Record click, continuity, and level observations.
5. For each effect enabled with parameter mode, confirm its parameter schema matches the actual type/range in VEGAS and test one value of each supported type. Until VQ-17 passes, keep all effects at defaults-only.

Expected: no unsupported key or parameter is applied, no transition exceeds the safe overlap, and there is no A/V desync. Record each enabled transition once.

## SFX index and level checks

1. Create a short synthetic 1 kHz tone with a known digital level using the already installed local FFmpeg, then add an explicit test-only sidecar license label. Do not put generated audio in the repository.
2. Index the licensed tone and a second file without license metadata. Confirm the latter is disabled with a warning.
3. Compare measured integrated loudness and peak with the known tone expectation; use the tolerance documented by the indexer. Confirm sample rate, duration, SHA-256 fingerprint, and stable key after a second index.
4. After VQ-18 and capability support are implemented, add the licensed tone to a disposable SFX track at an aligned word anchor. Check frame placement, gain ceiling, speech-peak avoidance, and playback level.
5. Review the final manifest and confirm every used sound has its license identifier.

Expected: missing-license files never enter the planner summary; gain stays under the configured ceiling; placement and loudness are measured rather than assumed.

## Results template

| Check | Result: pass / fail / not run | Evidence or notes |
|---|---|---|
| Catalog dump compiled in C# 5 | | |
| Runtime catalog enumeration and plugin hash | | |
| Duplicate-name key stability | | |
| Transition duration and A/V sync | | |
| Audio join listening and measurements | | |
| OFX parameter types and ranges | | |
| Licensed SFX index and loudness tolerance | | |
| Unlicensed SFX disabled | | |
| SFX placement, gain ceiling, and peak avoidance | | |
| Final manifest lists license identifiers | | |

Record VEGAS build, local tool versions, aggregate plugin counts, enabled/disabled counts, tested keys, sample rate, loudness/peak deltas, frame offset, and E0 evidence IDs. Omit private paths, filenames, media, and transcripts.

## Current status

The repository has no runtime executor for transition/effect/SFX operations. VQ-04 is compile-time-only; VQ-05, VQ-06, VQ-17, and VQ-18 remain unverified. Do not run mutation checks until the relevant probe evidence and capability support exist. Track these gates in REVISIT.md RV-009 and RV-010.
