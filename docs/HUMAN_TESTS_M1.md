# M1 VEGAS Human Test Checklist

**Purpose:** Complete the VEGAS checks that require opening the application. No step here is part of Codex's completed read-only inspection. The three scripts have only been compiled; none has been run.

## Safety setup

1. Close any real project with unsaved work. Do not run these probes against a personal project or source media.
2. In VEGAS Pro 17, create a new empty project. Save it as a disposable scratch project under the ignored `runs/m1-vegas-metadata/scratch/` folder in this repository. If that folder is missing, create it. Do not add personal media.
3. If you want `TimelineDump` to show events, add a short built-in generated video event from VEGAS' Media Generators. A generated color/title card is enough. Do not use a real recording. Record whether you used an empty project or generated media.
4. Keep a copy of the scratch project before testing. After each probe, close without saving unless a step explicitly says otherwise.

## Prepare the Script Menu

1. Open the Windows **Documents** folder. Create `Vegas Script Menu` if it does not exist.
2. Copy `CatalogDump.cs`, `TimelineDump.cs`, and `TextProbe.cs` from this repository's `vegas/probes/` folder into that Script Menu folder. Do not copy anything into the VEGAS install folder.
3. In File Explorer, right-click each copied script, choose **Properties**, and inspect the **General** tab. If Windows shows an **Unblock** checkbox/button, use it only for these locally reviewed probe files, select **Apply**, and record that it appeared. If no Unblock control appears, record that. Do not unblock any file you cannot identify.
4. Start VEGAS and open the disposable scratch project. Choose **Tools > Scripting > Rescan Script Menu Folder**. Confirm the three script names appear under the Scripting menu. If menu wording differs, record the visible wording and do not guess at another action.

## Run `CatalogDump.cs` (VQ-04)

1. With the scratch project open, choose **Tools > Scripting > CatalogDump**.
2. If a confirmation or error appears, copy its text. The script writes `catalog_dump.json` under `Documents\VegasAgent\probes\`.
3. Inspect the JSON locally. Do not paste the full file; it may contain installed plugin names and unique IDs.
4. Record plugin counts by category (transitions, video FX, audio FX, generators), whether nested folders were found, whether the script reported an error, and whether third-party plugins appeared.

## Run `TimelineDump.cs` (VQ-12 member/runtime follow-up)

1. Keep the scratch project open. Choose **Tools > Scripting > TimelineDump**.
2. Inspect `timeline_dump.json` under `Documents\VegasAgent\probes\`.
3. Do not paste the `project_path` or any `media` path. Paste only `fps_double`, track/event counts, start and length numbers, take offsets, grouped flags, and any error text. Replace any path with `[redacted]`.
4. If you created a generated event, record whether the event appears with the expected video track kind and duration. This is observation only; it does not validate VFR or sync mapping.

## Run `TextProbe.cs` (VQ-09)

1. Use a fresh empty scratch project (or close and recreate the existing one without saving earlier changes). This probe adds a generated text event.
2. Choose **Tools > Scripting > TextProbe**. Record the generator name, whether the script reports that no Titles generator exists, the parameter count, a short list of parameter names/types, or the complete error text.
3. Confirm whether a text event appeared. Use **Undo once** and confirm whether it disappears. Close the project without saving.
4. Do not paste project paths or any private text. The probe's generated test contains no personal content.

## Try the VQ-02 command-line route

1. Close VEGAS and confirm no VEGAS process is holding a project open. Do not run this while real work is open.
2. In PowerShell, set the script path to the copied `CatalogDump.cs` and run:

   ```powershell
   $vegas = Join-Path $env:ProgramFiles 'VEGAS\VEGAS Pro 17.0\vegas170.exe'
   $script = Join-Path ([Environment]::GetFolderPath('MyDocuments')) 'Vegas Script Menu\CatalogDump.cs'
   & $vegas ('-SCRIPT:"' + $script + '"')
   ```

3. Record whether VEGAS started, whether the script ran, any dialogs/prompts, and the exact error text. Do not include a user profile path in your report. This is a manual launch test; do not automate it.

## Note VQ-03 extension feasibility

1. In File Explorer, check whether an `Application Extensions` directory exists directly under the VEGAS install folder and whether any extension SDK/sample files are already installed. Do not create or copy files into the install folder.
2. In VEGAS, inspect the visible **Tools**, **View**, and **Extensions** menus for an extension/dockable-window entry point. Do not install or build an extension.
3. Report the visible extension route, any installed sample/SDK name, and whether the extension menu exists. If none is visible, report “no local extension entry point found”; this is a feasibility note, not a negative runtime test.

## Paste this result template back

Replace unknowns with observed values. Do not paste absolute paths, project filenames, media filenames, full catalog dumps, or plugin unique IDs.

```text
VEGAS build shown in Help > About:
Scratch project: empty | generated media (describe only as “generated color” / “generated title”)
Script Menu rescan: success | failed (visible menu wording/error)
Unblock control on copied probes: present and used | present but not used | absent

CatalogDump:
  ran: yes | no
  category counts (transitions/video FX/audio FX/generators):
  nested folders found: yes | no
  third-party plugins appeared: yes | no | unknown
  error:

TimelineDump:
  ran: yes | no
  fps_double:
  track/event counts:
  grouped flags and take-offset observations:
  expected generated event visible: yes | no | not applicable
  error:

TextProbe:
  ran: yes | no
  generator found: name only, or “no Titles generator”
  parameter count and a few parameter names/types:
  text event appeared: yes | no
  one Undo removed it: yes | no | not applicable
  error:

VQ-02 -SCRIPT attempt:
  VEGAS started: yes | no
  script ran: yes | no
  dialogs/prompts:
  error:

VQ-03 extension feasibility:
  Application Extensions folder present: yes | no
  local SDK/sample found: name only | none
  visible extension/dockable UI route:
  notes:
```
