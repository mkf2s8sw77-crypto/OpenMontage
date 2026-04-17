"""Tests for MiniMax official tools (TTS, Image, Music, Video).

These tests mock the network entirely and do not require a live API key.
"""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.base_tool import ToolStatus


class TestMiniMaxOfficialTTS:
    """Tests for MiniMaxOfficialTTS — mocked network."""

    def test_unavailable_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            # Force reload to pick up env state
            from tools.audio.minimax_official_tts import MiniMaxOfficialTTS
            tool = MiniMaxOfficialTTS()
            assert tool.get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_api_key(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from tools.audio.minimax_official_tts import MiniMaxOfficialTTS
            tool = MiniMaxOfficialTTS()
            assert tool.get_status() == ToolStatus.AVAILABLE

    def test_execute_returns_error_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            from tools.audio.minimax_official_tts import MiniMaxOfficialTTS
            tool = MiniMaxOfficialTTS()
            result = tool.execute({"text": "hello"})
            assert result.success is False
            assert "MINIMAX_API_KEY" in result.error

    def test_execute_success_mocks_download(self, tmp_path: Path):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from tools.audio.minimax_official_tts import MiniMaxOfficialTTS

            tool = MiniMaxOfficialTTS()
            output_file = tmp_path / "test_tts.mp3"

            # Mock the client and download
            with patch(
                "lib.providers.minimax_official_client.MiniMaxOfficialClient"
            ) as MockClient:
                mock_instance = MagicMock()
                MockClient.return_value = mock_instance

                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "data": {
                        "audio": {"file_url": "https://cdn.example.com/audio.mp3"}
                    }
                }
                mock_instance.post.return_value = mock_resp

                result = tool.execute({
                    "text": "hello world",
                    "output_path": str(output_file),
                })

                assert result.success is True
                assert result.data["provider"] == "minimax_official"
                assert result.data["model"] == "speech-2.8-hd"
                mock_instance.download_file.assert_called_once()

    def test_input_schema_contains_expected_fields(self):
        from tools.audio.minimax_official_tts import MiniMaxOfficialTTS, DEFAULT_TTS_MODEL
        tool = MiniMaxOfficialTTS()
        props = tool.input_schema["properties"]
        assert "text" in props
        assert props["model"]["default"] == DEFAULT_TTS_MODEL
        assert "voice" in props
        assert "output_path" in props

    def test_estimate_cost_scales_with_text_length(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from tools.audio.minimax_official_tts import MiniMaxOfficialTTS
            tool = MiniMaxOfficialTTS()
            cost = tool.estimate_cost({"text": "a" * 1_000_000})
            assert cost > 0


class TestMiniMaxOfficialImage:
    """Tests for MiniMaxOfficialImage — mocked network."""

    def test_unavailable_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            from tools.graphics.minimax_official_image import MiniMaxOfficialImage
            tool = MiniMaxOfficialImage()
            assert tool.get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_api_key(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from tools.graphics.minimax_official_image import MiniMaxOfficialImage
            tool = MiniMaxOfficialImage()
            assert tool.get_status() == ToolStatus.AVAILABLE

    def test_execute_returns_error_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            from tools.graphics.minimax_official_image import MiniMaxOfficialImage
            tool = MiniMaxOfficialImage()
            result = tool.execute({"prompt": "a beautiful sunset"})
            assert result.success is False
            assert "MINIMAX_API_KEY" in result.error

    def test_execute_success_mocks_download(self, tmp_path: Path):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from tools.graphics.minimax_official_image import MiniMaxOfficialImage

            tool = MiniMaxOfficialImage()
            output_file = tmp_path / "test_img.png"

            with patch(
                "lib.providers.minimax_official_client.MiniMaxOfficialClient"
            ) as MockClient:
                mock_instance = MagicMock()
                MockClient.return_value = mock_instance

                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "data": {
                        "images": [{"url": "https://cdn.example.com/image.png"}]
                    }
                }
                mock_instance.post.return_value = mock_resp

                result = tool.execute({
                    "prompt": "a beautiful sunset",
                    "output_path": str(output_file),
                })

                assert result.success is True
                assert result.data["provider"] == "minimax_official"
                assert result.data["model"] == "image-01"
                mock_instance.download_file.assert_called_once()

    def test_input_schema_contains_expected_fields(self):
        from tools.graphics.minimax_official_image import MiniMaxOfficialImage, DEFAULT_IMAGE_MODEL
        tool = MiniMaxOfficialImage()
        props = tool.input_schema["properties"]
        assert "prompt" in props
        assert props["model"]["default"] == DEFAULT_IMAGE_MODEL
        assert "aspect_ratio" in props
        assert "output_path" in props

    def test_capability_is_image_generation(self):
        from tools.graphics.minimax_official_image import MiniMaxOfficialImage
        tool = MiniMaxOfficialImage()
        assert tool.capability == "image_generation"
        assert tool.provider == "minimax_official"


class TestMiniMaxOfficialMusic:
    """Tests for MiniMaxOfficialMusic — mocked network."""

    def test_unavailable_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            from tools.audio.minimax_official_music import MiniMaxOfficialMusic
            tool = MiniMaxOfficialMusic()
            assert tool.get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_api_key(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from tools.audio.minimax_official_music import MiniMaxOfficialMusic
            tool = MiniMaxOfficialMusic()
            assert tool.get_status() == ToolStatus.AVAILABLE

    def test_execute_returns_error_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            from tools.audio.minimax_official_music import MiniMaxOfficialMusic
            tool = MiniMaxOfficialMusic()
            result = tool.execute({"prompt": "epic orchestral music"})
            assert result.success is False
            assert "MINIMAX_API_KEY" in result.error

    def test_execute_success_mocks_download(self, tmp_path: Path):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from tools.audio.minimax_official_music import MiniMaxOfficialMusic

            tool = MiniMaxOfficialMusic()
            output_file = tmp_path / "test_music.mp3"

            with patch(
                "lib.providers.minimax_official_client.MiniMaxOfficialClient"
            ) as MockClient:
                mock_instance = MagicMock()
                MockClient.return_value = mock_instance

                mock_resp = MagicMock()
                mock_resp.json.return_value = {
                    "data": {"audio_url": "https://cdn.example.com/music.mp3"}
                }
                mock_instance.post.return_value = mock_resp

                result = tool.execute({
                    "prompt": "epic orchestral music",
                    "output_path": str(output_file),
                })

                assert result.success is True
                assert result.data["provider"] == "minimax_official"
                mock_instance.download_file.assert_called_once()

    def test_input_schema_contains_expected_fields(self):
        from tools.audio.minimax_official_music import MiniMaxOfficialMusic
        tool = MiniMaxOfficialMusic()
        props = tool.input_schema["properties"]
        assert "prompt" in props
        assert "model" in props  # configurable, not hardcoded
        assert "output_path" in props

    def test_capability_is_music_generation(self):
        from tools.audio.minimax_official_music import MiniMaxOfficialMusic
        tool = MiniMaxOfficialMusic()
        assert tool.capability == "music_generation"
        assert tool.provider == "minimax_official"

    def test_default_music_model_from_env(self):
        # When MINIMAX_MUSIC_MODEL is not set, DEFAULT_MUSIC_MODEL should be "music-2.6"
        import importlib
        import tools.audio.minimax_official_music as music_module
        importlib.reload(music_module)
        assert music_module.DEFAULT_MUSIC_MODEL == "music-2.6"

    def test_default_music_model_can_be_overridden_via_env(self, monkeypatch):
        monkeypatch.setenv("MINIMAX_MUSIC_MODEL", "music-2.5")
        import importlib
        import tools.audio.minimax_official_music as music_module
        importlib.reload(music_module)
        assert music_module.DEFAULT_MUSIC_MODEL == "music-2.5"


class TestMiniMaxOfficialVideo:
    """Tests for MiniMaxOfficialVideo — mocked network."""

    def test_unavailable_without_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            from tools.video.minimax_official_video import MiniMaxOfficialVideo
            tool = MiniMaxOfficialVideo()
            assert tool.get_status() == ToolStatus.UNAVAILABLE

    def test_available_with_api_key(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from tools.video.minimax_official_video import MiniMaxOfficialVideo
            tool = MiniMaxOfficialVideo()
            assert tool.get_status() == ToolStatus.AVAILABLE

    def test_execute_returns_error_without_key(self):
        with patch.dict(os.environ, {}, clear=True):
            from tools.video.minimax_official_video import MiniMaxOfficialVideo
            tool = MiniMaxOfficialVideo()
            result = tool.execute({"prompt": "test video"})
            assert result.success is False
            assert "MINIMAX_API_KEY" in result.error

    def test_execute_text_to_video_success(self, tmp_path: Path):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from tools.video.minimax_official_video import MiniMaxOfficialVideo

            tool = MiniMaxOfficialVideo()
            output_file = tmp_path / "video.mp4"

            with patch("lib.providers.minimax_official_client.MiniMaxOfficialClient") as MockClient:
                mock_instance = MagicMock()
                MockClient.return_value = mock_instance
                mock_instance.create_video_generation_task.return_value = "123"
                mock_instance.poll_video_generation.return_value = {"status": "Success", "file_id": "456"}
                mock_instance.retrieve_file.return_value = {"file_id": "456", "download_url": "https://cdn.example.com/out.mp4"}

                with patch("tools.video._shared.probe_output", return_value={"width": 1920, "height": 1080, "duration_seconds": 6.0}):
                    result = tool.execute({
                        "prompt": "A cinematic street scene.",
                        "output_path": str(output_file),
                    })

            assert result.success is True
            assert result.data["task_id"] == "123"
            assert result.data["file_id"] == "456"
            mock_instance.download_file.assert_called_once()

    def test_build_payload_requires_first_frame_for_i2v(self):
        from tools.video.minimax_official_video import MiniMaxOfficialVideo

        tool = MiniMaxOfficialVideo()
        with pytest.raises(ValueError):
            tool._build_payload({"prompt": "test", "operation": "image_to_video"})

    def test_build_payload_requires_both_frames_for_first_last(self):
        from tools.video.minimax_official_video import MiniMaxOfficialVideo

        tool = MiniMaxOfficialVideo()
        with pytest.raises(ValueError):
            tool._build_payload(
                {
                    "prompt": "test",
                    "operation": "first_last_frame_to_video",
                    "first_frame_image": "https://example.com/a.png",
                }
            )

    def test_input_schema_contains_expected_fields(self):
        from tools.video.minimax_official_video import MiniMaxOfficialVideo, DEFAULT_VIDEO_MODEL

        tool = MiniMaxOfficialVideo()
        props = tool.input_schema["properties"]
        assert props["model"]["default"] == DEFAULT_VIDEO_MODEL
        assert "first_frame_image" in props
        assert "last_frame_image" in props
        assert "output_path" in props
