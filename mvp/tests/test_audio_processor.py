from pydub import AudioSegment

from app.audio_processor import AudioProcessor


def test_commentary_parser_extracts_and_bounds_lines() -> None:
    processor = AudioProcessor()

    lines = processor.parse_commentary_lines(
        "Intro [0] Kick-off! [4] A quick break. [12] Out of range.",
        max_frame=10,
    )

    assert lines == [
        {"frame": 0, "text": "Kick-off!"},
        {"frame": 4, "text": "A quick break."},
    ]


def test_srt_timestamp_rounds_milliseconds() -> None:
    assert AudioProcessor._format_srt_timestamp(3661.9996) == "01:01:02,000"
    assert AudioProcessor._format_srt_timestamp(-3) == "00:00:00,000"


def test_subtitles_are_numbered_and_separated() -> None:
    processor = AudioProcessor()

    subtitles = processor._generate_subtitles(
        [
            {"start_ms": 1000, "end_ms": 2250, "text": "Opening line"},
            {"start_ms": 3000, "end_ms": 4500, "text": "Second line"},
        ]
    )

    assert "1\n00:00:01,000 --> 00:00:02,250\nOpening line" in subtitles
    assert "2\n00:00:03,000 --> 00:00:04,500\nSecond line" in subtitles


def test_overlap_trims_the_earlier_audio_line() -> None:
    segments = [
        {
            "start_ms": 0,
            "end_ms": 2000,
            "audio": AudioSegment.silent(duration=2000),
            "text": "First",
        },
        {
            "start_ms": 1500,
            "end_ms": 2500,
            "audio": AudioSegment.silent(duration=1000),
            "text": "Second",
        },
    ]

    processed = AudioProcessor._process_audio_segments_for_overlap(segments)

    assert processed[0]["end_ms"] == 1500
    assert len(processed[0]["audio"]) == 1500
    assert processed[1]["start_ms"] == 1500
