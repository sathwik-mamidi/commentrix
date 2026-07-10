<div align="center">
  <img src="assets/commentrix-logo.png" alt="Commentrix logo" width="160">
  <h1>Commentrix</h1>
  <p>AI-assisted play-by-play commentary for sports video.</p>
  <p>
    <a href="https://commentrixai.com/">Live archive</a> ·
    <a href="mvp/README.md">MVP guide</a>
  </p>
</div>

## About

Commentrix explored an automated broadcast pipeline that samples sports footage, asks a multimodal model to identify noteworthy action, generates concise timestamped commentary, and turns those lines into a synchronized voice track and subtitle file.

The project has been sunset and is published as a polished public snapshot. The [live website](https://commentrixai.com/) remains available as an informational archive; it does not run the Python MVP or accept new customers, pilots, or support requests.

## Repository layout

```text
commentrix/
├── assets/                 Archived brand assets
├── docs/                   Static Cloudflare Pages website
├── mvp/
│   ├── app/                Processing, model, audio, and orchestration modules
│   ├── public/             Local input and generated media directory
│   ├── static/             MVP browser assets
│   ├── templates/          MVP HTML shell
│   ├── tests/              Backend test suite
│   └── main.py             FastAPI entry point
└── wrangler.jsonc          Cloudflare Pages configuration
```

The two surfaces are deliberately separate:

- `docs/` is a dependency-free static archive deployed to Cloudflare Pages.
- `mvp/` is a local, single-operator FastAPI application retained as a working technical reference.

## Architecture

```text
Local MP4
   │
   ▼
OpenCV frame sampling ──► Gemini commentary generation
                              │
                              ├──► WebSocket updates in the browser
                              │
                              ▼
                       ElevenLabs speech
                              │
                              ▼
                     pydub timeline assembly
                              │
                              ▼
                       FFmpeg MP4 + SRT
```

Each video segment is sampled at approximately one frame per second. Gemini returns lines in a `[frame] commentary` format. When text-to-speech is configured, ElevenLabs renders those lines, and the MVP places them on the source timeline before writing `output.mp4` and `output.srt`.

## Quick start

### Static website

The website has no build step:

```bash
python -m http.server 8080 --directory docs
```

Open `http://localhost:8080`.

### Local MVP

Requirements:

- Python 3.11 or newer
- [FFmpeg](https://ffmpeg.org/) available on `PATH`
- A Gemini API key
- An ElevenLabs API key if voice output is required

```bash
cd mvp
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

Add credentials to `.env`, place an input video at `mvp/public/input.mp4`, then run:

```bash
python main.py
```

Open `http://127.0.0.1:8000`. API health is available at `http://127.0.0.1:8000/health`.

## Environment variables

All paths may be absolute or relative to `mvp/`.

| Variable | Required | Default | Purpose |
| --- | --- | --- | --- |
| `GEMINI_API_KEY` | Yes | — | Gemini credential. `GOOGLE_API_KEY` is accepted as an alias. |
| `GEMINI_MODEL` | No | `gemini-2.5-pro` | Gemini model used for frame analysis. |
| `ELEVENLABS_API_KEY` | For voice | — | ElevenLabs credential. Without it, TTS is disabled. |
| `ELEVENLABS_VOICE_ID` | No | Archived project voice | Voice used for narration. |
| `ELEVENLABS_MODEL` | No | `eleven_multilingual_v2` | ElevenLabs synthesis model. |
| `ELEVENLABS_OUTPUT_FORMAT` | No | `mp3_44100_128` | Requested voice-audio format. |
| `ELEVENLABS_MAX_CONCURRENT` | No | `3` | Positive request-concurrency limit. |
| `SEGMENT_DURATION` | No | `30` | Positive segment length in seconds. |
| `VIDEO_PATH` | No | `public/input.mp4` | Source video. |
| `OUTPUT_FILE` | No | `public/output.mp4` | Generated video path. |
| `SUBTITLE_FILE` | No | `public/output.srt` | Generated subtitle path. |
| `TTS_ENABLED` | No | `true` | Accepts `true/false`, `yes/no`, `on/off`, or `1/0`. |
| `PORT` | No | `8000` | Port used by `python main.py`. |

## Development commands

Install the development tools once:

```bash
cd mvp
python -m pip install -r requirements-dev.txt
```

Then run:

```bash
python -m ruff check .
python -m pytest
python -m compileall -q app main.py
```

There is no JavaScript build pipeline. The browser code is plain HTML, CSS, and JavaScript by design.

## Deployment

Cloudflare Pages should serve only `docs/`:

| Setting | Value |
| --- | --- |
| Project name | `commentrix` |
| Production branch | `main` |
| Build command | Leave blank |
| Build output directory | `docs` |
| Custom domain | `commentrixai.com` |

The checked-in `wrangler.jsonc` contains the same output-directory configuration. The MVP is not deployed by this repository configuration.

## Operational notes

- The MVP is intended for trusted local use by one operator. It has no authentication, upload boundary, persistent job queue, rate limiting, or multi-user output isolation.
- Sampled video frames are sent to Gemini. Generated commentary is sent to ElevenLabs when TTS is enabled. Review those providers' current data and billing terms before using private footage.
- The generated MP4 uses the synthesized commentary track in place of the source audio; the source video stream is copied without re-encoding.
- If TTS is disabled, generated text still appears in the browser, but the final MP4 and SRT assembly step is skipped.
- API calls already running in worker threads may finish after a browser job is stopped.
- `.env` files, local input media, generated outputs, virtual environments, caches, and Cloudflare local state are intentionally ignored by Git.

## License

No open-source license is included. The code and assets are published for archival and reference purposes; obtain permission from the repository owner before reuse or redistribution.
