"""Per-WebSocket orchestration for the local commentary workflow."""

from __future__ import annotations

import asyncio
import logging

from fastapi import WebSocket

from .audio_processor import AudioProcessor
from .commentary_generator import (
    CommentaryGenerationError,
    CommentaryGenerator,
)
from .config import config
from .video_processor import VideoProcessor

logger = logging.getLogger(__name__)


class WebCommentator:
    """Coordinate frame sampling, model calls, TTS, and media assembly."""

    def __init__(self, websocket: WebSocket) -> None:
        self.websocket = websocket
        self.video_processor = VideoProcessor(config.video_path)
        self.audio_processor = AudioProcessor()
        self.commentary_generator = CommentaryGenerator()
        self.current_segment = 0
        self.commentary_task: asyncio.Task[None] | None = None
        self.stop_event = asyncio.Event()

    async def start_commentary(self) -> bool:
        """Validate prerequisites and start one background processing task."""
        if self.commentary_task and not self.commentary_task.done():
            await self._send_error("Commentary generation is already running")
            return False
        if not config.gemini_api_key:
            await self._send_error(
                "Set GEMINI_API_KEY or GOOGLE_API_KEY before starting"
            )
            return False
        if not config.video_path.is_file():
            await self._send_error(
                f"Input video not found at {config.video_path}"
            )
            return False
        if not await asyncio.to_thread(self.video_processor.initialize_video):
            await self._send_error("The input video could not be opened")
            return False

        self.current_segment = 0
        self.audio_processor.clear_audio_segments()
        self.commentary_generator.reset_context()
        self.stop_event.clear()
        self.commentary_task = asyncio.create_task(
            self._process_video_segments(), name="commentrix-video-processing"
        )
        return True

    async def _process_video_segments(self) -> None:
        properties = self.video_processor.get_video_properties()
        try:
            while not self.stop_event.is_set():
                start_time = self.current_segment * config.segment_duration
                if start_time >= properties["total_duration"]:
                    await self.websocket.send_json(
                        {"type": "video_processing_finished"}
                    )
                    if config.tts_enabled:
                        await self.audio_processor.create_final_video(
                            properties["video_path"],
                            properties["total_duration"],
                            self.websocket,
                        )
                    return

                duration = min(
                    config.segment_duration,
                    properties["total_duration"] - start_time,
                )
                frames, commentary_start = await asyncio.to_thread(
                    self.video_processor.extract_frames_from_segment,
                    start_time,
                    duration,
                )
                if not frames:
                    raise RuntimeError("No frames could be read from the input video")

                commentary = await self.commentary_generator.generate_commentary(
                    frames, duration
                )
                await self.websocket.send_json(
                    {
                        "type": "segment_ready",
                        "segment": self.current_segment,
                        "start_time": commentary_start,
                        "duration": duration,
                        "commentary": commentary,
                        "model": self.commentary_generator.get_current_model(),
                        "tts_enabled": config.tts_enabled,
                        "tts_voice": config.elevenlabs_voice_id,
                    }
                )

                if config.tts_enabled:
                    await self.audio_processor.generate_tts_audio(
                        commentary,
                        self.current_segment,
                        commentary_start,
                        duration,
                        self.websocket,
                    )
                self.current_segment += 1
        except asyncio.CancelledError:
            logger.info("Commentary processing was cancelled")
            raise
        except CommentaryGenerationError:
            logger.exception("Commentary model request failed")
            await self._send_error(
                "Commentary generation failed; check the server logs"
            )
        except Exception:
            logger.exception("Video processing failed")
            await self._send_error("Video processing failed; check the server logs")
        finally:
            self.video_processor.close()

    async def close(self) -> None:
        """Stop processing and release per-connection resources safely."""
        self.stop_event.set()
        task = self.commentary_task
        if task and task is not asyncio.current_task() and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        self.video_processor.close()
        self.audio_processor.clear_audio_segments()
        self.commentary_generator.reset_context()
        self.commentary_task = None

    async def _send_error(self, message: str) -> None:
        await self.websocket.send_json({"type": "error", "message": message})
