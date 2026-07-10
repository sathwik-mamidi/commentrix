from pathlib import Path

import pytest

from app.config import Settings


def test_defaults_resolve_paths_from_project_directory(tmp_path: Path) -> None:
    settings = Settings.from_env({}, base_dir=tmp_path)

    assert settings.segment_duration == 30
    assert settings.video_path == tmp_path / "public/input.mp4"
    assert settings.output_file == tmp_path / "public/output.mp4"
    assert settings.tts_enabled is False


def test_google_key_alias_and_tts_configuration(tmp_path: Path) -> None:
    settings = Settings.from_env(
        {
            "GOOGLE_API_KEY": "gemini-key",
            "ELEVENLABS_API_KEY": "voice-key",
            "TTS_ENABLED": "yes",
            "SEGMENT_DURATION": "15",
        },
        base_dir=tmp_path,
    )

    assert settings.gemini_api_key == "gemini-key"
    assert settings.tts_enabled is True
    assert settings.segment_duration == 15


@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("SEGMENT_DURATION", "0"),
        ("SEGMENT_DURATION", "thirty"),
        ("ELEVENLABS_MAX_CONCURRENT", "-1"),
        ("TTS_ENABLED", "sometimes"),
    ],
)
def test_invalid_environment_values_fail_fast(
    name: str, value: str, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match=name):
        Settings.from_env({name: value}, base_dir=tmp_path)


def test_system_instruction_uses_actual_segment_shape(tmp_path: Path) -> None:
    settings = Settings.from_env({}, base_dir=tmp_path)

    prompt = settings.system_instruction(frame_count=12, segment_duration=11.5)

    assert "11.5-second segment" in prompt
    assert "[0] through [11]" in prompt
