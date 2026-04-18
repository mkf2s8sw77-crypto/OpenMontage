"""Tests for the local MiniMax Studio API."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from studio_api.main import app


client = TestClient(app)


def test_health_endpoint():
    response = client.get("/api/studio/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_project_uses_slug():
    response = client.post("/api/studio/projects", json={"title": "MiniMax Studio Smoke"})
    assert response.status_code == 200
    assert response.json()["project"]["project_id"] == "minimax-studio-smoke"


def test_config_status_does_not_leak_key(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "secret-key")
    response = client.get("/api/studio/config/status")
    payload = response.json()
    assert response.status_code == 200
    assert payload["minimax"]["configured"] is True
    assert "secret-key" not in str(payload)


def test_generate_tts_route(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    fake_result = type(
        "Result",
        (),
        {
            "success": True,
            "data": {"output": "projects/test/assets/audio/tts.mp3"},
            "artifacts": ["projects/test/assets/audio/tts.mp3"],
        },
    )()
    with patch("studio_api.main.MiniMaxOfficialTTS.execute", return_value=fake_result):
        response = client.post("/api/studio/tts", json={"project_id": "studio-api-tts", "text": "hello"})
    assert response.status_code == 200
    assert response.json()["project_id"] == "studio-api-tts"


def test_generate_image_route(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    fake_result = type(
        "Result",
        (),
        {
            "success": True,
            "data": {"output": "projects/test/assets/images/image.png"},
            "artifacts": ["projects/test/assets/images/image.png"],
        },
    )()
    with patch("studio_api.main.MiniMaxOfficialImage.execute", return_value=fake_result):
        response = client.post("/api/studio/image", json={"project_id": "studio-api-image", "prompt": "a sunset"})
    assert response.status_code == 200
    assert response.json()["category"] == "images"


def test_generate_music_route(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    fake_result = type(
        "Result",
        (),
        {
            "success": True,
            "data": {"output": "projects/test/assets/music/music.mp3"},
            "artifacts": ["projects/test/assets/music/music.mp3"],
        },
    )()
    with patch("studio_api.main.MiniMaxOfficialMusic.execute", return_value=fake_result):
        response = client.post(
            "/api/studio/music",
            json={"project_id": "studio-api-music", "prompt": "ambient piano", "lyrics": "[Verse]\nhello"},
        )
    assert response.status_code == 200
    assert response.json()["category"] == "music"


def test_generate_music_route_requires_lyrics():
    response = client.post("/api/studio/music", json={"project_id": "studio-api-music", "prompt": "ambient piano"})
    assert response.status_code == 422


def test_create_video_job_and_query(monkeypatch):
    monkeypatch.setenv("MINIMAX_API_KEY", "test-key")
    fake_result = type(
        "Result",
        (),
        {
            "success": True,
            "data": {"task_id": "123", "file_id": "456", "output": "projects/test/assets/video/video.mp4"},
            "artifacts": ["projects/test/assets/video/video.mp4"],
            "error": None,
        },
    )()
    with patch("studio_api.main.MiniMaxOfficialVideo.execute", return_value=fake_result):
        response = client.post(
            "/api/studio/video/jobs",
            json={"project_id": "studio-api-video", "prompt": "cinematic alley"},
        )
    assert response.status_code == 200
    job = response.json()["job"]
    assert job["status"] in {"queued", "success"}

    detail = client.get(f"/api/studio/jobs/{job['job_id']}?project_id=studio-api-video")
    assert detail.status_code == 200
    assert detail.json()["job"]["job_id"] == job["job_id"]


def test_api_allows_local_vite_origin_via_cors():
    response = client.options(
        "/api/studio/tts",
        headers={
            "Origin": "http://127.0.0.1:5173",
            "Access-Control-Request-Method": "POST",
        },
    )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://127.0.0.1:5173"
