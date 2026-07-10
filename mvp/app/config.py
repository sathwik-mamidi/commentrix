"""Environment-backed settings for the local Commentrix MVP."""

from __future__ import annotations

import logging
import os
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

logger = logging.getLogger(__name__)

PROJECT_DIR = Path(__file__).resolve().parents[1]
FALSE_VALUES = {"0", "false", "no", "off"}
TRUE_VALUES = {"1", "true", "yes", "on"}


def _positive_int(environ: Mapping[str, str], name: str, default: int) -> int:
    raw_value = environ.get(name, str(default))
    try:
        value = int(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"{name} must be a positive integer, got {raw_value!r}"
        ) from exc

    if value <= 0:
        raise ValueError(f"{name} must be a positive integer, got {raw_value!r}")
    return value


def _boolean(environ: Mapping[str, str], name: str, default: bool) -> bool:
    raw_value = environ.get(name, str(default)).strip().lower()
    if raw_value in TRUE_VALUES:
        return True
    if raw_value in FALSE_VALUES:
        return False
    raise ValueError(
        f"{name} must be one of: {', '.join(sorted(TRUE_VALUES | FALSE_VALUES))}"
    )


def _project_path(base_dir: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else base_dir / path


@dataclass(frozen=True, slots=True)
class Settings:
    """Validated runtime settings loaded from environment variables."""

    base_dir: Path
    gemini_api_key: str | None
    elevenlabs_api_key: str | None
    elevenlabs_voice_id: str
    gemini_model: str
    elevenlabs_model: str
    elevenlabs_output_format: str
    elevenlabs_max_concurrent: int
    segment_duration: int
    video_path: Path
    output_file: Path
    subtitle_file: Path
    tts_enabled: bool

    @classmethod
    def from_env(
        cls,
        environ: Mapping[str, str] | None = None,
        *,
        base_dir: Path = PROJECT_DIR,
    ) -> Settings:
        values = os.environ if environ is None else environ
        gemini_api_key = values.get("GEMINI_API_KEY") or values.get("GOOGLE_API_KEY")
        elevenlabs_api_key = values.get("ELEVENLABS_API_KEY")
        tts_requested = _boolean(values, "TTS_ENABLED", True)

        settings = cls(
            base_dir=base_dir,
            gemini_api_key=gemini_api_key,
            elevenlabs_api_key=elevenlabs_api_key,
            elevenlabs_voice_id=values.get(
                "ELEVENLABS_VOICE_ID", "gU0LNdkMOQCOrPrwtbee"
            ),
            gemini_model=values.get("GEMINI_MODEL", "gemini-2.5-pro"),
            elevenlabs_model=values.get(
                "ELEVENLABS_MODEL", "eleven_multilingual_v2"
            ),
            elevenlabs_output_format=values.get(
                "ELEVENLABS_OUTPUT_FORMAT", "mp3_44100_128"
            ),
            elevenlabs_max_concurrent=_positive_int(
                values, "ELEVENLABS_MAX_CONCURRENT", 3
            ),
            segment_duration=_positive_int(values, "SEGMENT_DURATION", 30),
            video_path=_project_path(
                base_dir, values.get("VIDEO_PATH", "public/input.mp4")
            ),
            output_file=_project_path(
                base_dir, values.get("OUTPUT_FILE", "public/output.mp4")
            ),
            subtitle_file=_project_path(
                base_dir, values.get("SUBTITLE_FILE", "public/output.srt")
            ),
            tts_enabled=bool(elevenlabs_api_key) and tts_requested,
        )

        if not settings.gemini_api_key:
            logger.warning(
                "GEMINI_API_KEY or GOOGLE_API_KEY is not set; commentary generation "
                "will remain unavailable"
            )
        if tts_requested and not settings.elevenlabs_api_key:
            logger.info("ELEVENLABS_API_KEY is not set; text-to-speech is disabled")

        return settings

    def system_instruction(self, frame_count: int, segment_duration: float) -> str:
        """Build a prompt that reflects the actual number of sampled frames."""
        last_frame = max(0, frame_count - 1)
        word_budget = max(15, round(segment_duration * 3))
        return (
            "You are an energetic, concise sports commentator providing live "
            "play-by-play. The supplied frames are sampled at roughly one frame per "
            f"second from a {segment_duration:.1f}-second segment. Comment only on "
            "noteworthy action, allow natural pauses, and do not invent details that "
            "are not visible. "
            f"Keep the result under about {word_budget} words so it can be spoken "
            "during the segment. Prefix each spoken line with the zero-based frame "
            f"number where it begins, from [0] through [{last_frame}]. Return only "
            "timestamped commentary, for example: '[5] A brilliant finish!'"
        )


load_dotenv(PROJECT_DIR / ".env")
config = Settings.from_env()
