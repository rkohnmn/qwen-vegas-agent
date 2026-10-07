from __future__ import annotations

import random

from orchestrator.captions import CaptionConfig, build_captions, grapheme_clusters
from orchestrator.compiler import FrameInterval
from orchestrator.contracts import check_captions, validate


def _inputs(word_frames: list[tuple[str, str, int, int]]) -> tuple[dict, dict, dict]:
    words = {
        "schema_version": "2.1.0",
        "fps": "25/1",
        "words": [
            {
                "id": word_id,
                "text": text,
                "start": start / 25,
                "end": end / 25,
                "speaker": speaker,
                "speaker_conf": 0.95,
                "word_conf": 0.95,
                "alignment_status": "aligned",
            }
            for word_id, text, start, end, speaker in word_frames
        ],
    }
    edl = {"subtitles": {"style": None, "emphasis": [], "break_hints": [], "omit_ranges": []}}
    timeline = {
        "fps": "25/1",
        "duration_frames": max((end for _, _, _, end, _ in word_frames), default=0) + 120,
    }
    return words, edl, timeline


def test_source_word_start_maps_through_cut_and_split() -> None:
    words, edl, timeline = _inputs(
        [("w1", "before", 5, 10, "host"), ("w2", "after", 45, 50, "host")]
    )
    document, report = build_captions(
        words,
        edl,
        timeline,
        [FrameInterval(20, 40, ("c1",), "silence")],
        config=CaptionConfig(max_cps=100, min_duration_ms=1, hold_ms=0),
    )
    assert [row["start_frame"] for row in document["captions"]] == [5, 25]
    assert [row["text"] for row in document["captions"]] == ["before", "after"]
    assert report["caption_count"] == 2
    assert check_captions(document, words) == []


def test_omissions_emphasis_and_speaker_changes_are_respected() -> None:
    words, edl, timeline = _inputs(
        [("w1", "we", 1, 4, "host"), ("w2", "um", 5, 7, "host"), ("w3", "agree", 8, 12, "guest")]
    )
    edl["subtitles"]["omit_ranges"] = [{"from_word": "w2", "to_word": "w2"}]
    edl["subtitles"]["emphasis"] = [{"word_ids": ["w1"], "mode": "bold"}]
    document, report = build_captions(
        words,
        edl,
        timeline,
        [],
        config=CaptionConfig(max_cps=100, min_duration_ms=1, hold_ms=0),
    )
    assert [caption["speaker_key"] for caption in document["captions"]] == ["host", "guest"]
    assert document["captions"][0]["text"] == "we"
    assert document["captions"][0]["emphasis"][0]["word_ids"] == ["w1"]
    assert report["omitted_edl_word_count"] == 1
    assert check_captions(document, words) == []


def test_edl_break_hint_splits_same_speaker_caption() -> None:
    words, edl, timeline = _inputs([("w1", "First", 1, 4, "host"), ("w2", "second", 6, 10, "host")])
    edl["subtitles"]["break_hints"] = [{"before_word": "w2"}]
    document, _report = build_captions(
        words,
        edl,
        timeline,
        [],
        config=CaptionConfig(max_cps=100, min_duration_ms=1, hold_ms=0),
    )
    assert [caption["text"] for caption in document["captions"]] == ["First", "second"]


def test_grapheme_clusters_keep_combining_emoji_and_flags_together() -> None:
    assert grapheme_clusters("e\u0301👩‍👩‍👦🇺🇸") == ["e\u0301", "👩‍👩‍👦", "🇺🇸"]


def test_seeded_caption_batches_never_mix_speakers_or_overlap_same_track() -> None:
    rng = random.Random(606)
    rows: list[tuple[str, str, int, int, str]] = []
    cursor = 0
    for index in range(1, 201):
        length = rng.randint(1, 5)
        rows.append(
            (f"w{index}", f"word{index}", cursor, cursor + length, "host" if index % 2 else "guest")
        )
        cursor += length + rng.randint(1, 3)
    words, edl, timeline = _inputs(rows)
    document, _report = build_captions(
        words,
        edl,
        timeline,
        [],
        config=CaptionConfig(
            max_chars_per_line=18, max_lines=2, max_cps=100, min_duration_ms=1, hold_ms=0
        ),
    )
    assert document["captions"]
    speaker_by_id = {row["id"]: row["speaker"] for row in words["words"]}
    for caption in document["captions"]:
        source_speakers = {speaker_by_id[word_id] for word_id in caption["source_word_ids"]}
        assert source_speakers == {caption["speaker_key"]}
        lines = caption["text"].split("\n")
        assert len(lines) <= 2
        assert all(len(grapheme_clusters(line)) <= 18 for line in lines)
    assert check_captions(document, words) == []


def test_edl_rejects_model_supplied_caption_color() -> None:
    import json
    from pathlib import Path

    edl = json.loads(Path("tests/fixtures/edl/valid_realistic.json").read_text(encoding="utf-8"))
    edl["subtitles"]["color"] = "#FFFFFF"
    assert any(issue.code.value == "E_SCHEMA" for issue in validate("edl", edl))


def test_caption_contract_rejects_same_speaker_overlap() -> None:
    words, _edl, _timeline = _inputs([("w1", "one", 1, 10, "host"), ("w2", "two", 5, 12, "host")])
    document = {
        "schema_version": "1.0.0",
        "fps": "25/1",
        "duration_frames": 120,
        "captions": [
            {
                "id": "cap1",
                "speaker_key": "host",
                "text": "one",
                "start_frame": 1,
                "end_frame": 10,
                "style_key": None,
                "emphasis": [],
                "confidence_flags": [],
                "source_word_ids": ["w1"],
            },
            {
                "id": "cap2",
                "speaker_key": "host",
                "text": "two",
                "start_frame": 5,
                "end_frame": 12,
                "style_key": None,
                "emphasis": [],
                "confidence_flags": [],
                "source_word_ids": ["w2"],
            },
        ],
    }
    assert any(issue.code.value == "E_CAPTION_OVERLAP" for issue in check_captions(document, words))
    assert not validate("captions", document)


def test_caption_contract_rejects_mixed_speaker_source_words() -> None:
    words, _edl, _timeline = _inputs([("w1", "one", 1, 5, "host"), ("w2", "two", 6, 10, "guest")])
    document = {
        "schema_version": "1.0.0",
        "fps": "25/1",
        "duration_frames": 120,
        "captions": [
            {
                "id": "cap1",
                "speaker_key": "host",
                "text": "one two",
                "start_frame": 1,
                "end_frame": 10,
                "style_key": None,
                "emphasis": [],
                "confidence_flags": [],
                "source_word_ids": ["w1", "w2"],
            }
        ],
    }
    assert any(issue.code.value == "E_CAPTION_SPEAKER" for issue in check_captions(document, words))
