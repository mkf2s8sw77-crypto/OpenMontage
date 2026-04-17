"""Tests for lib/providers/minimax_official_client.py.

These tests mock the network entirely and do not require a live API key.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


class TestMiniMaxOfficialClient:
    """Tests for MiniMaxOfficialClient — mocked network."""

    def test_client_uses_default_host(self):
        with patch.dict(os.environ, {}, clear=True):
            from lib.providers.minimax_official_client import (
                MiniMaxOfficialClient,
                get_host,
                DEFAULT_HOST,
            )
            assert get_host() == DEFAULT_HOST
            assert "api.minimaxi.com" in get_host()

    def test_client_uses_env_host_override(self):
        with patch.dict(os.environ, {"MINIMAX_API_HOST": "https://custom.example.com"}):
            from lib.providers.minimax_official_client import get_host
            assert get_host() == "https://custom.example.com"

    def test_client_bearer_auth_header(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key-123"}):
            from lib.providers.minimax_official_client import MiniMaxOfficialClient
            client = MiniMaxOfficialClient()
            assert "Bearer test-key-123" in client.headers["Authorization"]

    def test_client_raises_when_no_api_key(self):
        with patch.dict(os.environ, {}, clear=True):
            from lib.providers.minimax_official_client import MiniMaxOfficialClient
            client = MiniMaxOfficialClient(api_key=None)
            with pytest.raises(Exception) as exc_info:
                _ = client.headers
            assert "MINIMAX_API_KEY" in str(exc_info.value)

    def test_post_builds_correct_url(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from lib.providers.minimax_official_client import MiniMaxOfficialClient
            client = MiniMaxOfficialClient()

            mock_resp = MagicMock()
            mock_resp.ok = True
            mock_resp.json.return_value = {"data": {}}
            mock_resp.status_code = 200

            with patch.object(client._session, "request", return_value=mock_resp) as mock_req:
                client.post("/v1/test", json={"foo": "bar"})
                mock_req.assert_called_once()
                call_args = mock_req.call_args
                assert call_args[0][0] == "POST"
                assert "api.minimaxi.com/v1/test" in call_args[0][1]
                assert call_args[1]["json"] == {"foo": "bar"}
                assert "Bearer test-key" in call_args[1]["headers"]["Authorization"]

    def test_get_builds_correct_url(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from lib.providers.minimax_official_client import MiniMaxOfficialClient
            client = MiniMaxOfficialClient()

            mock_resp = MagicMock()
            mock_resp.ok = True
            mock_resp.json.return_value = {"data": {}}
            mock_resp.status_code = 200

            with patch.object(client._session, "request", return_value=mock_resp) as mock_req:
                client.get("/v1/test", params={"page": 1})
                mock_req.assert_called_once()
                call_args = mock_req.call_args
                assert call_args[0][0] == "GET"
                assert call_args[1]["params"] == {"page": 1}

    def test_error_response_raises_minimax_api_error(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from lib.providers.minimax_official_client import MiniMaxOfficialClient, MiniMaxAPIError
            client = MiniMaxOfficialClient()

            mock_resp = MagicMock()
            mock_resp.ok = False
            mock_resp.status_code = 400
            mock_resp.text = '{"base_resp": {"status_code": 10001, "status_msg": "invalid param"}}'
            mock_resp.json.return_value = {"base_resp": {"status_code": 10001, "status_msg": "invalid param"}}

            with patch.object(client._session, "request", return_value=mock_resp):
                with pytest.raises(MiniMaxAPIError) as exc_info:
                    client.post("/v1/test", json={})
                assert exc_info.value.status_code == 400
                assert exc_info.value.error_code == 10001
                assert "invalid param" in exc_info.value.message

    def test_timeout_raises_minimax_api_error(self):
        import requests
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from lib.providers.minimax_official_client import MiniMaxOfficialClient, MiniMaxAPIError
            client = MiniMaxOfficialClient()

            with patch.object(
                client._session, "request",
                side_effect=requests.exceptions.Timeout("timed out")
            ):
                with pytest.raises(MiniMaxAPIError) as exc_info:
                    client.post("/v1/test", json={})
                assert "timeout" in exc_info.value.error_code.lower()

    def test_connection_error_raises_minimax_api_error(self):
        import requests
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from lib.providers.minimax_official_client import MiniMaxOfficialClient, MiniMaxAPIError
            client = MiniMaxOfficialClient()

            with patch.object(
                client._session, "request",
                side_effect=requests.exceptions.ConnectionError("failed")
            ):
                with pytest.raises(MiniMaxAPIError) as exc_info:
                    client.post("/v1/test", json={})
                assert "connection_error" in exc_info.value.error_code.lower()

    def test_download_file_writes_bytes(self, tmp_path: Path):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from lib.providers.minimax_official_client import MiniMaxOfficialClient
            client = MiniMaxOfficialClient()

            mock_stream = MagicMock()
            mock_stream.iter_content.return_value = [b"fake audio data"]

            mock_resp = MagicMock()
            mock_resp.ok = True
            mock_resp.iter_content = mock_stream.iter_content

            output = tmp_path / "test.mp3"

            with patch.object(client._session, "get", return_value=mock_resp):
                client.download_file("https://example.com/file.mp3", output)
                assert output.read_bytes() == b"fake audio data"

    def test_download_file_creates_parent_dirs(self, tmp_path: Path):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from lib.providers.minimax_official_client import MiniMaxOfficialClient
            client = MiniMaxOfficialClient()

            mock_stream = MagicMock()
            mock_stream.iter_content.return_value = [b"data"]

            mock_resp = MagicMock()
            mock_resp.ok = True
            mock_resp.iter_content = mock_stream.iter_content

            output = tmp_path / "subdir" / "nested" / "test.mp3"

            with patch.object(client._session, "get", return_value=mock_resp):
                client.download_file("https://example.com/file.mp3", output)
                assert output.read_bytes() == b"data"

    def test_create_video_generation_task_returns_task_id(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from lib.providers.minimax_official_client import MiniMaxOfficialClient

            client = MiniMaxOfficialClient()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"task_id": "123456"}
            with patch.object(client, "post", return_value=mock_resp):
                assert client.create_video_generation_task({"prompt": "test"}) == "123456"

    def test_query_video_generation_calls_query_endpoint(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from lib.providers.minimax_official_client import MiniMaxOfficialClient

            client = MiniMaxOfficialClient()
            mock_resp = MagicMock()
            mock_resp.json.return_value = {"status": "Success", "file_id": "999"}
            with patch.object(client, "get", return_value=mock_resp) as mock_get:
                data = client.query_video_generation("abc")
            assert data["status"] == "Success"
            mock_get.assert_called_once_with("/v1/query/video_generation", params={"task_id": "abc"})

    def test_poll_video_generation_waits_for_success(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from lib.providers.minimax_official_client import MiniMaxOfficialClient

            client = MiniMaxOfficialClient()
            with patch.object(client, "query_video_generation", side_effect=[
                {"status": "Processing"},
                {"status": "Success", "file_id": "999"},
            ]):
                with patch("lib.providers.minimax_official_client.time.sleep"):
                    result = client.poll_video_generation("abc", poll_interval_seconds=0.01, timeout_seconds=1)
            assert result["file_id"] == "999"

    def test_poll_video_generation_raises_on_failure(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from lib.providers.minimax_official_client import MiniMaxOfficialClient, MiniMaxAPIError

            client = MiniMaxOfficialClient()
            with patch.object(client, "query_video_generation", return_value={"status": "Fail", "error_message": "bad prompt"}):
                with pytest.raises(MiniMaxAPIError) as exc_info:
                    client.poll_video_generation("abc", poll_interval_seconds=0.01, timeout_seconds=1)
            assert "bad prompt" in str(exc_info.value)

    def test_retrieve_file_returns_file_metadata(self):
        with patch.dict(os.environ, {"MINIMAX_API_KEY": "test-key"}):
            from lib.providers.minimax_official_client import MiniMaxOfficialClient

            client = MiniMaxOfficialClient()
            mock_resp = MagicMock()
            mock_resp.status_code = 200
            mock_resp.json.return_value = {"file": {"file_id": "1", "download_url": "https://example.com/test.mp4"}}
            with patch.object(client, "get", return_value=mock_resp) as mock_get:
                info = client.retrieve_file("1")
            assert info["download_url"] == "https://example.com/test.mp4"
            mock_get.assert_called_once_with("/v1/files/retrieve", params={"file_id": "1"})
