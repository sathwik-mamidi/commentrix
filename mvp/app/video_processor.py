"""Video metadata and frame sampling helpers."""

from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import TypedDict

import cv2
import PIL.Image

logger = logging.getLogger(__name__)


class VideoProperties(TypedDict):
    fps: float
    total_frames: int
    total_duration: float
    video_path: str


class VideoProcessor:
    """Read a local video and sample approximately one frame per second."""

    def __init__(self, video_path: str | Path) -> None:
        self.video_path = Path(video_path)
        self.video_cap: cv2.VideoCapture | None = None
        self.fps = 0.0
        self.total_frames = 0
        self.total_duration = 0.0

    def initialize_video(self) -> bool:
        self.close()
        capture = cv2.VideoCapture(str(self.video_path))
        if not capture.isOpened():
            capture.release()
            logger.error("Could not open input video: %s", self.video_path)
            return False

        fps = float(capture.get(cv2.CAP_PROP_FPS))
        total_frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
        if not math.isfinite(fps) or fps <= 0 or total_frames <= 0:
            capture.release()
            logger.error("Input video has invalid frame metadata: %s", self.video_path)
            return False

        self.video_cap = capture
        self.fps = fps
        self.total_frames = total_frames
        self.total_duration = total_frames / fps
        logger.info(
            "Loaded %s (%d frames, %.2f fps, %.2f seconds)",
            self.video_path,
            self.total_frames,
            self.fps,
            self.total_duration,
        )
        return True

    def extract_frames_from_segment(
        self, start_time: float, duration: float
    ) -> tuple[list[PIL.Image.Image], float]:
        if self.video_cap is None:
            raise RuntimeError("Video must be initialized before extracting frames")
        if start_time < 0 or duration <= 0:
            raise ValueError(
                "start_time must be non-negative and duration must be positive"
            )

        frames: list[PIL.Image.Image] = []
        sample_count = max(1, math.ceil(duration))
        for offset in range(sample_count):
            timestamp = start_time + offset
            if timestamp >= self.total_duration:
                break

            frame_number = min(int(timestamp * self.fps), self.total_frames - 1)
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            read_ok, frame = self.video_cap.read()
            if not read_ok:
                logger.warning("Could not read frame at %.2f seconds", timestamp)
                break

            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(PIL.Image.fromarray(frame_rgb))

        logger.info(
            "Extracted %d frames from %.2f-%.2f seconds",
            len(frames),
            start_time,
            start_time + duration,
        )
        return frames, start_time

    def get_video_properties(self) -> VideoProperties:
        if self.video_cap is None:
            raise RuntimeError("Video must be initialized before reading properties")
        return {
            "fps": self.fps,
            "total_frames": self.total_frames,
            "total_duration": self.total_duration,
            "video_path": str(self.video_path),
        }

    def close(self) -> None:
        if self.video_cap is not None:
            self.video_cap.release()
            self.video_cap = None
