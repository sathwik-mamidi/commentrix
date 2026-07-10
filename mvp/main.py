"""FastAPI entry point for the local Commentrix MVP."""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response

from app.commentator import WebCommentator
from app.config import config

logger = logging.getLogger(__name__)
BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(
    title="Commentrix MVP",
    description="Local archived prototype for AI-generated sports commentary.",
    version="1.0.0",
)
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
app.mount("/public", StaticFiles(directory=BASE_DIR / "public"), name="public")

active_sessions: dict[int, WebCommentator] = {}


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(BASE_DIR / "templates" / "index.html", media_type="text/html")


@app.get("/health")
async def health() -> dict[str, Any]:
    """Report local readiness without exposing credentials."""
    return {
        "status": "ok",
        "input_video_present": config.video_path.is_file(),
        "commentary_configured": bool(config.gemini_api_key),
        "tts_enabled": config.tts_enabled,
        "active_sessions": len(active_sessions),
    }


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> FileResponse:
    return FileResponse(BASE_DIR / "static" / "favicon.png")


@app.get("/output.mp4", include_in_schema=False)
async def output_video() -> Response:
    if config.output_file.is_file():
        return FileResponse(
            config.output_file,
            media_type="video/mp4",
            filename="commentrix_output.mp4",
        )
    return HTMLResponse("<h1>Output video not found</h1>", status_code=404)


@app.get("/output.srt", include_in_schema=False)
async def output_subtitles() -> Response:
    if config.subtitle_file.is_file():
        return FileResponse(
            config.subtitle_file,
            media_type="application/x-subrip",
            filename="commentrix_subtitles.srt",
        )
    return HTMLResponse("<h1>Subtitle file not found</h1>", status_code=404)


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    await websocket.accept()
    commentator = WebCommentator(websocket)
    session_id = id(websocket)
    active_sessions[session_id] = commentator
    logger.info("WebSocket session %d connected", session_id)

    try:
        while True:
            message = await websocket.receive_json()
            if not isinstance(message, dict):
                await websocket.send_json(
                    {"type": "error", "message": "Message must be a JSON object"}
                )
                continue

            message_type = message.get("type")
            if message_type == "start":
                await commentator.start_commentary()
            elif message_type == "stop":
                await commentator.close()
                await websocket.send_json(
                    {"type": "status", "message": "Commentary stopped"}
                )
            else:
                await websocket.send_json(
                    {
                        "type": "error",
                        "message": f"Unknown message type: {message_type!r}",
                    }
                )
    except WebSocketDisconnect:
        logger.info("WebSocket session %d disconnected", session_id)
    except ValueError:
        logger.warning("WebSocket session %d sent invalid JSON", session_id)
        await websocket.close(code=1003, reason="Invalid JSON")
    except Exception:
        logger.exception("Unexpected WebSocket failure in session %d", session_id)
    finally:
        await commentator.close()
        active_sessions.pop(session_id, None)


if __name__ == "__main__":
    import uvicorn

    logging.basicConfig(level=logging.INFO)
    uvicorn.run(app, host="127.0.0.1", port=int(os.environ.get("PORT", "8000")))
