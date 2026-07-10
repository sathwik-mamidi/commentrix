"""Text-to-speech, subtitle, and final media assembly helpers."""

from __future__ import annotations

import asyncio
import base64
import io
import logging
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any

import requests
from pydub import AudioSegment

from .config import config

logger = logging.getLogger(__name__)

COMMENTARY_LINE_PATTERN = re.compile(r"\[(\d+)]\s*([^[]+?)(?=\s*\[\d+]|$)")


class AudioProcessor:
    """Generate narration audio and place it on the source-video timeline."""

    def __init__(self) -> None:
        self.tts_enabled = config.tts_enabled
        self.collected_audio_segments: dict[int, list[dict[str, Any]]] = {}
        self.elevenlabs_semaphore = asyncio.Semaphore(
            config.elevenlabs_max_concurrent
        )

    def parse_commentary_lines(
        self, commentary_text: str, *, max_frame: int | None = None
    ) -> list[dict[str, Any]]:
        """Extract non-empty ``[frame] text`` entries within segment bounds."""
        lines: list[dict[str, Any]] = []
        for frame_value, raw_text in COMMENTARY_LINE_PATTERN.findall(
            commentary_text.strip()
        ):
            frame_number = int(frame_value)
            text = raw_text.strip()
            if text and (max_frame is None or frame_number <= max_frame):
                lines.append({"frame": frame_number, "text": text})
        return lines

    async def _generate_elevenlabs_tts(
        self, line_text: str, frame_number: int
    ) -> dict[str, Any]:
        async with self.elevenlabs_semaphore:
            logger.info(
                "Generating ElevenLabs audio for frame %d: %s",
                frame_number,
                line_text[:50],
            )
            url = (
                "https://api.elevenlabs.io/v1/text-to-speech/"
                f"{config.elevenlabs_voice_id}"
            )
            try:
                response = await asyncio.to_thread(
                    requests.post,
                    f"{url}?output_format={config.elevenlabs_output_format}",
                    headers={
                        "xi-api-key": config.elevenlabs_api_key,
                        "Content-Type": "application/json",
                    },
                    json={
                        "text": line_text.strip(),
                        "model_id": config.elevenlabs_model,
                        "voice_settings": {
                            "stability": 0.5,
                            "similarity_boost": 0.75,
                            "style": 0.0,
                            "use_speaker_boost": True,
                        },
                    },
                    timeout=30,
                )
                response.raise_for_status()
            except requests.RequestException:
                logger.exception(
                    "ElevenLabs request failed for frame %d", frame_number
                )
                raise

            audio_data = response.content
            return {
                "frame": frame_number,
                "text": line_text,
                "audio_base64": base64.b64encode(audio_data).decode("ascii"),
                "audio_data": audio_data,
            }

    async def generate_tts_audio(
        self,
        text: str,
        segment_num: int,
        commentary_start: float,
        segment_duration: float,
        websocket: Any,
    ) -> list[dict[str, Any]] | None:
        """Generate and stream each valid commentary line for one segment."""
        if not self.tts_enabled or len(text.strip()) < 3:
            return None

        max_frame = max(0, int(segment_duration - 0.000001))
        commentary_lines = self.parse_commentary_lines(
            text, max_frame=max_frame
        )
        if not commentary_lines:
            logger.warning("No timestamped commentary lines were returned")
            return None

        async def generate_line(line: dict[str, Any]) -> dict[str, Any] | None:
            try:
                return await self._generate_elevenlabs_tts(
                    line["text"], line["frame"]
                )
            except requests.RequestException:
                return None

        results = await asyncio.gather(
            *(generate_line(line) for line in commentary_lines)
        )
        valid_results = [result for result in results if result is not None]
        if not valid_results:
            await websocket.send_json(
                {
                    "type": "audio_segment_error",
                    "segment": segment_num,
                    "error": "Voice generation failed for this segment",
                }
            )
            return None

        segment_lines = self.collected_audio_segments.setdefault(segment_num, [])
        for result in valid_results:
            segment_lines.append(
                {
                    "frame": result["frame"],
                    "text": result["text"],
                    "audio_data": result["audio_data"],
                    "segment_start_time": commentary_start,
                }
            )
            await websocket.send_json(
                {
                    "type": "audio_line",
                    "data": result["audio_base64"],
                    "segment": segment_num,
                    "frame": result["frame"],
                    "text": result["text"],
                }
            )
        return valid_results

    @staticmethod
    def _format_srt_timestamp(seconds: float) -> str:
        """Convert seconds to the ``HH:MM:SS,mmm`` SRT format."""
        total_milliseconds = max(0, round(seconds * 1000))
        hours, remainder = divmod(total_milliseconds, 3_600_000)
        minutes, remainder = divmod(remainder, 60_000)
        whole_seconds, milliseconds = divmod(remainder, 1000)
        return (
            f"{hours:02d}:{minutes:02d}:{whole_seconds:02d},"
            f"{milliseconds:03d}"
        )

    def _generate_subtitles(self, audio_segments: list[dict[str, Any]]) -> str:
        entries = []
        for index, segment in enumerate(audio_segments, 1):
            start = self._format_srt_timestamp(segment["start_ms"] / 1000)
            end = self._format_srt_timestamp(segment["end_ms"] / 1000)
            entries.append(f"{index}\n{start} --> {end}\n{segment['text']}\n")
        return "\n".join(entries)

    async def create_final_video(
        self, video_path: str, total_duration: float, websocket: Any
    ) -> None:
        """Create subtitles and mux the collected narration with the source video."""
        if not self.collected_audio_segments:
            logger.info("No narration audio collected; skipping final media assembly")
            return

        temp_audio_path: Path | None = None
        try:
            await websocket.send_json(
                {"type": "status", "message": "Generating final video..."}
            )
            duration_ms = max(1, round(total_duration * 1000))
            combined_audio = AudioSegment.silent(duration=duration_ms)

            timeline: list[dict[str, Any]] = []
            for segment_num in sorted(self.collected_audio_segments):
                for line in self.collected_audio_segments[segment_num]:
                    try:
                        audio = AudioSegment.from_mp3(
                            io.BytesIO(line["audio_data"])
                        )
                    except Exception:
                        logger.exception(
                            "Could not decode narration in segment %d", segment_num
                        )
                        continue

                    start_ms = round(
                        (line["segment_start_time"] + line["frame"]) * 1000
                    )
                    timeline.append(
                        {
                            "start_ms": start_ms,
                            "end_ms": start_ms + len(audio),
                            "audio": audio,
                            "text": line["text"],
                        }
                    )

            timeline.sort(key=lambda item: item["start_ms"])
            processed = self._process_audio_segments_for_overlap(timeline)
            clipped: list[dict[str, Any]] = []
            for segment in processed:
                if segment["start_ms"] >= duration_ms:
                    continue
                available_ms = duration_ms - segment["start_ms"]
                audio = segment["audio"][:available_ms]
                if not audio:
                    continue
                segment = {
                    **segment,
                    "audio": audio,
                    "end_ms": segment["start_ms"] + len(audio),
                }
                combined_audio = combined_audio.overlay(
                    audio, position=segment["start_ms"]
                )
                clipped.append(segment)

            if not clipped:
                raise RuntimeError("No valid narration audio could be assembled")

            await self._create_subtitle_file(clipped, websocket)
            with tempfile.NamedTemporaryFile(
                suffix=".mp3", delete=False
            ) as temp_audio_file:
                temp_audio_path = Path(temp_audio_file.name)
            await asyncio.to_thread(
                combined_audio.export, temp_audio_path, format="mp3"
            )
            await self._merge_video_with_audio(video_path, temp_audio_path)
            await websocket.send_json(
                {
                    "type": "final_video_ready",
                    "output_file": "/output.mp4",
                    "subtitle_file": "/output.srt",
                    "message": "Final video and subtitles are ready",
                }
            )
        except Exception:
            logger.exception("Final media assembly failed")
            await websocket.send_json(
                {
                    "type": "error",
                    "message": "Final video generation failed; check the server logs",
                }
            )
        finally:
            if temp_audio_path is not None:
                temp_audio_path.unlink(missing_ok=True)

    @staticmethod
    def _process_audio_segments_for_overlap(
        audio_segments: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Trim earlier lines so only one narration line plays at a time."""
        processed: list[dict[str, Any]] = []
        for current in audio_segments:
            while processed and current["start_ms"] < processed[-1]["end_ms"]:
                previous = processed[-1]
                new_duration = current["start_ms"] - previous["start_ms"]
                if new_duration <= 0:
                    processed.pop()
                    continue
                previous["audio"] = previous["audio"][:new_duration]
                previous["end_ms"] = current["start_ms"]
                break
            processed.append(dict(current))
        return processed

    async def _create_subtitle_file(
        self, audio_segments: list[dict[str, Any]], websocket: Any
    ) -> None:
        await websocket.send_json(
            {"type": "status", "message": "Generating subtitle file..."}
        )
        config.subtitle_file.parent.mkdir(parents=True, exist_ok=True)
        config.subtitle_file.write_text(
            self._generate_subtitles(audio_segments), encoding="utf-8"
        )
        logger.info("Saved subtitles to %s", config.subtitle_file)

    async def _merge_video_with_audio(
        self, video_path: str, audio_path: Path
    ) -> None:
        config.output_file.parent.mkdir(parents=True, exist_ok=True)
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            video_path,
            "-i",
            str(audio_path),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-movflags",
            "+faststart",
            "-shortest",
            "-y",
            str(config.output_file),
        ]
        try:
            await asyncio.to_thread(
                subprocess.run,
                command,
                capture_output=True,
                text=True,
                check=True,
            )
        except FileNotFoundError as exc:
            raise RuntimeError("FFmpeg is not installed or is not on PATH") from exc
        except subprocess.CalledProcessError as exc:
            logger.error("FFmpeg failed: %s", exc.stderr.strip())
            raise RuntimeError("FFmpeg could not create the output video") from exc

    def clear_audio_segments(self) -> None:
        self.collected_audio_segments.clear()
