from __future__ import annotations

import json
from pathlib import Path

from orchestrator.stages import run_compile


def test_standalone_compile_emits_caption_sidecars_and_review(tmp_path, monkeypatch) -> None:
    root = Path(__file__).resolve().parents[2]
    fixture_root = root / "tests" / "fixtures"
    words_path = fixture_root / "words" / "valid_minimal.json"
    timeline = json.loads((fixture_root / "timeline" / "valid_minimal.json").read_text())
    timeline["duration_frames"] = 300
    for event in timeline["events"]:
        event["length_frames"] = 300
    timeline_path = tmp_path / "timeline.json"
    timeline_path.write_text(json.dumps(timeline), encoding="utf-8")
    edl = json.loads((fixture_root / "edl" / "valid_minimal.json").read_text())
    edl["subtitles"]["style"] = None
    edl_path = tmp_path / "edl.json"
    edl_path.write_text(json.dumps(edl), encoding="utf-8")
    speakers_path = fixture_root / "speakers" / "valid_minimal.json"
    safe_settings = json.loads((root / "config.example.json").read_text(encoding="utf-8"))
    monkeypatch.setattr("orchestrator.stages._load_settings", lambda: safe_settings)

    output = run_compile(
        words_path,
        timeline_path,
        edl_path,
        output_root=tmp_path / "compile",
        speakers_path=speakers_path,
    )

    captions = json.loads((output / "captions.json").read_text(encoding="utf-8"))
    assert captions["captions"]
    assert (output / "captions.srt").is_file()
    assert (output / "captions.ass").is_file()
    assert "Caption review" in (output / "review.md").read_text(encoding="utf-8")
