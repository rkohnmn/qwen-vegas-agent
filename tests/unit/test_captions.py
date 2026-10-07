from __future__ import annotations

import pytest

from orchestrator.caption_renderers import (
    AssBurnInRenderer,
    CaptionRenderUnavailable,
    SidecarOnlyRenderer,
    parse_ass,
    parse_srt,
    serialize_ass,
    serialize_srt,
)
from orchestrator.captions import (
    CaptionConfig,
    build_captions,
    contrast_ratio,
    grapheme_clusters,
    resolve_speaker_color,
)


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


def _caption_document(text: str = "Hello {user} \\ path\nnext") -> dict:
    return {
        "schema_version": "1.0.0",
        "fps": "30000/1001",
        "duration_frames": 180,
        "captions": [
            {
                "id": "cap1",
                "speaker_key": "host",
                "text": text,
                "start_frame": 30,
                "end_frame": 90,
                "style_key": "txt.default.a1b2c3",
                "emphasis": [
                    {"word_ids": ["w1"], "mode": "bold", "start_codepoint": 0, "end_codepoint": 5}
                ],
                "confidence_flags": [],
                "source_word_ids": ["w1"],
            }
        ],
    }


def _speaker_document(color: str = "#FF0000") -> dict:
    return {
        "schema_version": "1.1.0",
        "speakers": {"host": {"display": "Host", "color": color}},
        "unknown_palette": ["#888888", "#BBBBBB"],
    }


def test_srt_and_ass_round_trip_text_and_frame_grid() -> None:
    document = _caption_document()
    speakers = _speaker_document()
    srt = serialize_srt(document)
    ass = serialize_ass(document, speakers, CaptionConfig())
    assert parse_srt(srt, document["fps"]) == [
        {"start_frame": 30, "end_frame": 90, "text": document["captions"][0]["text"]}
    ]
    assert parse_ass(ass, document["fps"]) == [
        {"start_frame": 30, "end_frame": 90, "text": document["captions"][0]["text"]}
    ]
    assert "&H000000FF" in ass
    assert "color" not in document["captions"][0]


def test_rtl_combining_marks_survive_ass_round_trip() -> None:
    text = "مَرْحَبًا שלום"
    document = _caption_document(text)
    ass = serialize_ass(document, _speaker_document(), CaptionConfig())
    assert parse_ass(ass, document["fps"]) == [{"start_frame": 30, "end_frame": 90, "text": text}]
    assert grapheme_clusters("مَرْحَبًا") == ["مَ", "رْ", "حَ", "بً", "ا"]


def test_unknown_colors_and_low_contrast_use_only_speaker_map() -> None:
    speakers = _speaker_document("#111111")
    assert resolve_speaker_color(speakers, "host") == "#111111"
    speakers["speakers"]["unknown_2"] = {"display": "Unknown", "color": "#FFFFFF"}
    assert resolve_speaker_color(speakers, "unknown_2") == "#BBBBBB"
    assert contrast_ratio("#111111", "#000000") < 3
    words, edl, timeline = _inputs([("w1", "hello", 2, 10, "host")])
    words["words"][0]["speaker_conf"] = 0.2
    document, report = build_captions(
        words,
        edl,
        timeline,
        [],
        config=CaptionConfig(max_cps=100, min_duration_ms=1, hold_ms=0),
        speakers_document=speakers,
    )
    caption = document["captions"][0]
    assert "low_speaker_conf" in caption["confidence_flags"]
    assert any(item["code"] == "W_CAPTION_LOW_CONTRAST" for item in report["warnings"])
    assert report["low_confidence"][0]["source_word_ids"] == ["w1"]


def test_filler_and_profanity_policy_is_local_config_only() -> None:
    words, edl, timeline = _inputs([("w1", "um", 1, 3, "host"), ("w2", "damn", 4, 8, "host")])
    config = CaptionConfig(
        max_cps=100,
        min_duration_ms=1,
        hold_ms=0,
        show_fillers=False,
        profanity_policy="mask",
        profanity_words=("damn",),
    )
    document, report = build_captions(words, edl, timeline, [], config=config)
    assert document["captions"][0]["text"] == "****"
    assert "profanity_masked" in document["captions"][0]["confidence_flags"]
    assert report["omitted_filler_count"] == 1
    assert report["masked_profanity_count"] == 1


def test_sidecar_renderer_writes_text_free_report(tmp_path) -> None:
    document = _caption_document("private transcript text")
    report = {"caption_count": 1, "warnings": [], "low_confidence": []}
    paths = SidecarOnlyRenderer().write_sidecars(
        tmp_path, document, report, _speaker_document(), CaptionConfig()
    )
    assert all(path.is_file() for path in paths)
    assert "private transcript text" not in paths[3].read_text(encoding="utf-8")
    assert (
        parse_ass(paths[2].read_text(encoding="utf-8"), document["fps"])[0]["text"]
        == document["captions"][0]["text"]
    )


def test_ass_burn_in_fails_safely_when_ffmpeg_is_missing(tmp_path, monkeypatch) -> None:
    renderer = AssBurnInRenderer()
    video = tmp_path / "input.mp4"
    ass = tmp_path / "captions.ass"
    video.write_bytes(b"synthetic placeholder")
    ass.write_text("[Events]\n", encoding="utf-8")
    monkeypatch.setattr("orchestrator.caption_renderers.shutil.which", lambda _name: None)
    with pytest.raises(CaptionRenderUnavailable, match="sidecars remain usable"):
        renderer.burn_in(video, ass, tmp_path / "output.mp4", allowed_root=tmp_path)


@pytest.mark.skipif(
    __import__("shutil").which("ffmpeg") is None or __import__("shutil").which("ffprobe") is None,
    reason="local FFmpeg and ffprobe are required for the generated-clip burn-in check (RV-008)",
)
def test_ass_burn_in_generated_clip_end_to_end(tmp_path) -> None:
    import json
    import shutil
    import subprocess

    from orchestrator.childenv import safe_child_environment

    ffmpeg, ffprobe = shutil.which("ffmpeg"), shutil.which("ffprobe")
    assert ffmpeg is not None and ffprobe is not None
    source = tmp_path / "synthetic.mp4"
    output = tmp_path / "burned.mp4"
    ass_path = tmp_path / "captions.ass"
    document = _caption_document("TEST CAPTION")
    document["fps"] = "25/1"
    document["captions"][0]["start_frame"] = 10
    document["captions"][0]["end_frame"] = 40
    ass_path.write_text(
        serialize_ass(document, _speaker_document(), CaptionConfig()), encoding="utf-8"
    )
    subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-nostdin",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "color=c=black:s=640x360:d=2:r=25",
            "-c:v",
            "libx264",
            str(source),
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        shell=False,
        env=safe_child_environment(),
    )
    AssBurnInRenderer().burn_in(source, ass_path, output, allowed_root=tmp_path)
    probe = subprocess.run(
        [ffprobe, "-v", "error", "-show_streams", "-of", "json", str(output)],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
        shell=False,
        env=safe_child_environment(),
    )
    assert output.is_file() and output.stat().st_size > 0
    assert any(row.get("codec_type") == "video" for row in json.loads(probe.stdout)["streams"])
    frame = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostdin",
            "-i",
            str(output),
            "-ss",
            "1.0",
            "-frames:v",
            "1",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "rgb24",
            "pipe:1",
        ],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        shell=False,
        env=safe_child_environment(),
    )
    red_pixels = sum(
        red > 100 and green < 90 and blue < 90
        for red, green, blue in zip(
            frame.stdout[0::3], frame.stdout[1::3], frame.stdout[2::3], strict=True
        )
    )
    assert red_pixels > 100
