# Catalog

## Closed vocabulary and safety

The internal catalog combines a VEGAS plug-in dump with the local SFX index. It may contain plug-in IDs, parameter metadata, license metadata, and local SFX paths. Keep it under the ignored runs directory. The planner receives only the allowlisted summary: enabled keys, kinds, safe tags, parameter mode, default transition frames, and SFX duration. It never receives plug-in IDs, paths, or arbitrary parameter values.

The Python builder uses category, normalized display name, and the first eight SHA-256 hex characters of a stable identity. Duplicate display names therefore remain distinct. The full plug-in list hash is stable when input rows are reordered. Catalog validation rejects duplicate keys.

## Build from a dump

The CatalogDump source is a compile-only probe. It has not been run in VEGAS. Read it before any human runs it, and use a disposable empty project.

The builder reads a JSON dump and writes catalog.json, catalog_summary.json, and catalog_tags.json beneath runs/catalog by default. The first tag file leaves every item disabled. The builder does not read local configuration or enable a transition from an assumed baseline. If a tag file already exists, it is preserved; derived outputs require the explicit overwrite flag.

~~~powershell
python tasks.py catalog-build <catalog_dump.json> --output-dir runs/catalog --vegas-version 17.x
~~~

The current dump labels generators generically. The builder does not assume that every generator is a text preset; unclassified rows are omitted with a warning until a human or later probe classifies them.

## Human tag file

The tag file is JSON with a schema version and an entries array. Each row contains the catalog key, tags, allowed contexts, parameter mode, and enabled flag. Transition rows also include default_duration_frames.

~~~json
{
  "schema_version": "1.0.0",
  "entries": [
    {
      "key": "tr.crossfade-short.a1b2c3d4",
      "tags": ["soft", "dialogue_safe"],
      "allowed_contexts": ["topic_boundary"],
      "params_mode": "defaults_only",
      "enabled": true,
      "default_duration_frames": 12
    }
  ]
}
~~~

Keys and tag values are identifiers, not free text. Tags and contexts use lowercase letters, digits, underscores, and hyphens. Unknown fields and keys fail closed. A first run uses an empty transition allowlist, so nothing becomes planner-visible until the human enables specific entries. A parameters mode is rejected until a VQ-17-backed schema and evidence exist.

## Transition policy

Only enabled catalog keys are eligible. A human must add a transition to the tag file and choose its contexts. Continuous-speech cuts default to no visual transition unless a safe tag and style configuration allow one. Default duration and per-minute limits are compiler policy, not planner-supplied numbers. Minimum clip length cannot be verified until the timeline identifies post-cut event pairs; the current compiler rejects eligible transitions with `E_TRANSITION_BOUNDARY_UNRESOLVED` rather than using word duration as a proxy.

No Vegas transition operation is enabled until the M7 disposable-project checks provide E0 evidence for VQ-04, VQ-05, and VQ-06. OFX parameters remain disabled until VQ-17 is resolved. See REVISIT.md RV-009 and docs/HUMAN_TESTS_M7.md.


## Add a local SFX index

Run python tasks.py sfx-index <approved_sfx_dir> to create an ignored local index. Review license sidecars, then pass the resulting JSON to the builder with --sfx-index runs/sfx-index/sfx_index.json. The first generated tag file still disables every entry. Internal paths, measured peak/loudness, fingerprint, and license stay out of the model-facing summary.
