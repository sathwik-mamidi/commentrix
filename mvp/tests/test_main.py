import asyncio

from main import health, output_subtitles, output_video


def test_health_does_not_expose_credentials() -> None:
    response = asyncio.run(health())

    assert response["status"] == "ok"
    assert "gemini_api_key" not in response
    assert "elevenlabs_api_key" not in response


def test_missing_outputs_return_not_found() -> None:
    assert asyncio.run(output_video()).status_code == 404
    assert asyncio.run(output_subtitles()).status_code == 404
