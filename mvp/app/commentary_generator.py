"""Gemini-backed commentary generation."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Sequence

import PIL.Image
from google import genai

from .config import config

logger = logging.getLogger(__name__)


class CommentaryGenerationError(RuntimeError):
    """Raised when the configured model cannot produce commentary."""


class CommentaryGenerator:
    """Generate timestamped sports commentary while carrying brief context forward."""

    def __init__(self) -> None:
        self.gemini_client = (
            genai.Client(api_key=config.gemini_api_key)
            if config.gemini_api_key
            else None
        )
        self.previous_commentary = ""

    async def generate_commentary(
        self, frames: Sequence[PIL.Image.Image], segment_duration: float
    ) -> str:
        if not self.gemini_client:
            raise CommentaryGenerationError("Gemini API key is not configured")
        if not frames:
            raise CommentaryGenerationError("No video frames were supplied")

        prompt = config.system_instruction(len(frames), segment_duration)
        if self.previous_commentary:
            prompt += (
                "\n\nUse this previous segment only for continuity; do not repeat it: "
                f"{self.previous_commentary}"
            )

        try:
            response = await asyncio.to_thread(
                self.gemini_client.models.generate_content,
                model=config.gemini_model,
                contents=[prompt, *frames],
            )
        except Exception as exc:
            logger.exception("Gemini commentary generation failed")
            raise CommentaryGenerationError(
                "The commentary model request failed"
            ) from exc

        commentary = (response.text or "").strip()
        if not commentary:
            raise CommentaryGenerationError("The commentary model returned no text")

        self.previous_commentary = commentary
        return commentary

    def get_current_model(self) -> str:
        return config.gemini_model

    def reset_context(self) -> None:
        self.previous_commentary = ""
