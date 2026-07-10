# Commentrix MVP

This directory contains the local FastAPI prototype behind the archived Commentrix concept. It samples a sports video, generates timestamped commentary with Gemini, optionally synthesizes narration with ElevenLabs, and assembles an MP4 plus SRT subtitles with pydub and FFmpeg.

See the [repository README](../README.md) for the full architecture, environment-variable reference, deployment split, and operational limitations.

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Configure at least `GEMINI_API_KEY` (or `GOOGLE_API_KEY`) in `.env`. To generate voice audio and final media, also configure `ELEVENLABS_API_KEY` and `ELEVENLABS_VOICE_ID`.

Place a local source video at `public/input.mp4`, then start the application:

```bash
python main.py
```

Open `http://127.0.0.1:8000`. The health endpoint is available at `/health`, and FastAPI's local API schema is available at `/docs`.

## Checks

```bash
python -m pip install -r requirements-dev.txt
python -m ruff check .
python -m pytest
python -m compileall -q app main.py
```

Local `.env` files, source media, generated media, subtitles, caches, and virtual environments are excluded by the root `.gitignore`.
