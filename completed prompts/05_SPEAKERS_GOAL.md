# Prompt 05: Speaker Attribution (Multitrack, Diarization, Enrollment) (Goal Prompt)

**Prompt version:** 1.0.0
**Depends on:** Prompts 01b and 04 complete.
**Human gate before sending:** G2 done: Hugging Face account and read token; gated model terms accepted; token stored only in a gitignored location; voice samples recorded.
**Machine:** laptop (4 GB GPU, CPU fallback). Server not needed.

=== PROMPT START ===

## STANDING RULES

- Follow `AGENTS.md`; Sections 7 and 15 are inviolable. Docs are the source of truth. If sources conflict, stop and report.
- Model chooses IDs, code chooses numbers. Credentials only in the orchestrator. **The Hugging Face token is a secret**: gitignored config or environment variable only; redacted from logs, errors, run folders, and manifests.
- You never run Vegas. Never modify user media or the Vegas install directory.
- Contract changes follow `AGENTS.md` Section 8. Pin and justify dependencies. Commit per phase, no push. Report per Section 13 with an acceptance checklist.

## GOAL

Make speaker attribution reliable in both recording styles, with a single output shape, so later steps can color subtitles per speaker without caring how identity was found:

- **Multitrack:** one audio track per speaker.
- **Diarized:** one mixed track; clusters matched to enrolled voice profiles.
- **Hybrid:** per-track rules.

Unknown voices must trigger an `ask_user` question and persist the answer.

## READ FIRST

`AGENTS.md`, `ARCHITECTURE.md` (8.2, 8.3, 9.2, 9.3), the `words` and `speakers` contracts and fixtures, `docs/SECURITY.md`, `docs/EVALS.md`.

## INPUTS

```
HF_TOKEN_SOURCE = environment variable name (default HF_TOKEN) or config.local.json key
VOICE_SAMPLES_DIR = <local folder outside git with one WAV per speaker>
```

## PERMISSIONS (exact list)

1. Python packages, pinned and justified in `DECISIONS.md` (purpose, size, license): `pyannote.audio` and its requirements (or WhisperX's own diarization wrapper if it already depends on it), an embedding model package if separate.
2. **Gated model weights** from Hugging Face using the token, for the diarization pipeline and voice embedding. **Before downloading, read the current model card terms (read-only page fetch of the model card on huggingface.co) and confirm the models in use are the ones the human has accepted; list them in one message.** If a model needs terms that were not accepted, stop that part and report which page the human must visit.
3. No other downloads. No audio leaves the machine.

## SCOPE

### In scope
1. **Mode selection** (`auto`): inspect the timeline/audio streams plus `speakers.json` track mappings to choose multitrack, diarized, or hybrid; allow override in config. Document the rules and test them.
2. **Multitrack path**: transcribe each mapped track separately with the existing ASR interface; label words by track; merge by time; **bleed handling**: use VAD/energy comparison across tracks to avoid transcribing a quiet speaker's bleed into another track's words; keep both candidates when ambiguous and lower `speaker_conf`.
3. **Diarized path**: diarization on 16 kHz mono audio (CPU by default, GPU if memory allows and it is faster), assign words to speakers by overlap of aligned word time and diarization turns; handle **overlapping speech** by flagging overlapped words with reduced `speaker_conf` and an `overlap` marker in the speaker field set.
4. **Voice enrollment**: `python tasks.py enroll --name mike --audio <wav>` creates an embedding file under the gitignored `voices/`, with quality checks (duration, SNR estimate, single-speaker check). Matching with a cosine threshold in config (default from validation on your enrollment samples; state how chosen).
5. **Unknown handling**: clusters below threshold become `Unknown N` using the `unknown_palette`; **`ask_user` data path**: a typed question object (`id`, `type: identify_speaker`, short audio snippet path, up to 3 candidate names, free-text allowed) is emitted into the run folder and handled by a CLI prompt (Prompt 10 adds a nicer UI). The answer is persisted: it updates `speakers.json` (with a diff shown and confirmation) and optionally enrolls the snippet as additional voice data. A job pauses in `awaiting_user` until answered or times out into a clearly marked `Unknown` result.
6. **Confidence**: every word has `speaker_conf`; segment-level speaker is the confidence-weighted majority; low-confidence words are surfaced in a report (`speaker_report.json`: count, ranges, reasons) and never silently reassigned.
7. **Contracts**: extend `words` and `speakers` only as needed through the contract process (for example `overlap` flag, per-speaker enrollment metadata). Keep backward compatibility where possible; bump versions properly.
8. **Segment building**: segments never mix speakers unless overlap is flagged; compile and pack code updated to display speaker changes.
9. **Eval**: synthetic multitrack and mixed fixtures generated in tests (distinct tones or distinct synthetic voices via different pitch noise bursts; no committed media) plus support for labeled real clips; metrics: attribution accuracy per mode, overlap handling accuracy, unknown detection rate, time per minute of audio, peak memory.
10. **Docs**: `docs/SPEAKERS.md` (modes, thresholds, enrollment, ask_user flow, limits and recording advice: multitrack is more accurate), `SETUP.md` updates (token handling, gated model steps), `SECURITY.md` update (token handling and redaction).

### Out of scope
Colors and captions (Prompt 06), LLM work, UI beyond CLI.

## ACCEPTANCE CRITERIA

1. Standard checks pass; tests needing models or GPU are marked and skip with reasons.
2. A grep-based and runtime test proves the token never appears in logs, errors, run folders, manifests, or `speakers.json`.
3. Multitrack synthetic test: words attributed to the correct speaker, including a bleed case flagged with lowered confidence.
4. Diarized synthetic or fixture-based test: attribution by overlap logic is correct, including an overlapped span flagged.
5. Enrollment rejects too-short and multi-speaker samples (tests), and stores only embeddings (no raw audio) unless the human opts in.
6. Unknown voice produces an `ask_user` question; answering updates `speakers.json` through a confirmed diff; timeout path yields `Unknown N` and a warning (tests).
7. `speaker_report.json` lists low-confidence ranges; no word is reassigned silently (test).
8. Real-model benchmark on the laptop recorded in `docs/EVALS.md`: device, time per minute, peak memory; or the exact blocking reason.
9. No tracked file contains secrets, private paths, or voice data.
10. Contracts/docs consistent; phase commits; no push.

## HUMAN VERIFICATION AFTER

Run on one multitrack recording and one mixed recording with two known speakers. Check the speaker report for obvious errors and confirm names appear correctly. Record accuracy impressions for the eval doc.

## WORK PLAN

A: contracts and mode selection. B: multitrack with bleed handling. C: diarization and overlap. D: enrollment and matching. E: ask_user flow and persistence. F: reports, evals, docs. G: final verification and report.

## STOP AND ASK IF

A model requires terms that were not accepted; a step needs the token in a tracked file; real-model runs fail for a reason you cannot resolve (propose CPU or alternative embedding model behind the same interface).

## FINAL REPORT

Per Section 13 plus: mode-selection rules, thresholds and how chosen, accuracy table per mode, benchmark table, and recording advice for the human.

=== PROMPT END ===

---

## Completion record

- Date: 2026-10-07
- Final implementation and documentation commit: `529996a` (the separate archival/privacy completion commit follows).
- Assumptions: real diarization and voice enrollment need an accepted model and approved recordings; similarity/bleed thresholds are synthetic-only and uncalibrated; no model weights, token, private voice data, or Vegas runtime were used.
- Revisit items created for this goal: RV-005, RV-006. RV-003 remains an inherited missing-prerequisite blocker.
