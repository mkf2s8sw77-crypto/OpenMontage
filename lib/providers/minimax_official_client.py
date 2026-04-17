"""MiniMax Official API client.

Provides a shared HTTP client for all MiniMax official direct-connect tools.
Default host: https://api.minimaxi.com (CN node).
The host is configurable via MINIMAX_API_HOST env var for future flexibility.
"""

from __future__ import annotations

import os
from pathlib import Path
import time
from typing import Any

import requests


DEFAULT_HOST = "https://api.minimaxi.com"
DEFAULT_TTS_MODEL = "speech-2.8-hd"
DEFAULT_IMAGE_MODEL = "image-01"
DEFAULT_MUSIC_MODEL = "music-2.6"
DEFAULT_VIDEO_MODEL = "MiniMax-Hailuo-2.3"


def get_api_key() -> str | None:
    return os.environ.get("MINIMAX_API_KEY")


def get_host() -> str:
    return os.environ.get("MINIMAX_API_HOST", DEFAULT_HOST)


class MiniMaxAPIError(Exception):
    """Raised when the MiniMax API returns an error response."""

    def __init__(self, status_code: int, error_code: str | None, message: str):
        self.status_code = status_code
        self.error_code = error_code
        self.message = message
        super().__init__(f"MiniMax API error {status_code} ({error_code}): {message}")


class MiniMaxOfficialClient:
    """Thread-safe requests session for MiniMax Official API."""

    def __init__(
        self,
        api_key: str | None = None,
        host: str | None = None,
        timeout: int = 120,
    ):
        self.api_key = api_key or get_api_key()
        self.host = host or get_host()
        self.timeout = timeout
        self._session = requests.Session()

    @property
    def headers(self) -> dict[str, str]:
        key = self.api_key
        if not key:
            raise MiniMaxAPIError(0, None, "MINIMAX_API_KEY is not set")
        return {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        }

    def _request(
        self,
        method: str,
        path: str,
        *,
        json: dict | None = None,
        params: dict | None = None,
    ) -> requests.Response:
        url = f"{self.host}{path}"
        try:
            resp = self._session.request(
                method,
                url,
                headers=self.headers,
                json=json,
                params=params,
                timeout=self.timeout,
            )
        except requests.exceptions.Timeout:
            raise MiniMaxAPIError(0, "timeout", f"Request to {url} timed out after {self.timeout}s")
        except requests.exceptions.ConnectionError as exc:
            raise MiniMaxAPIError(0, "connection_error", f"Could not connect to {url}: {exc}")

        if not resp.ok:
            err_code = None
            err_msg = resp.text or "Unknown error"
            try:
                body = resp.json()
                err_code = body.get("base_resp", {}).get("status_code") or body.get("error_code")
                err_msg = body.get("base_resp", {}).get("status_msg") or body.get("error_msg") or err_msg
            except Exception:
                pass
            raise MiniMaxAPIError(resp.status_code, err_code, err_msg)

        return resp

    def get(self, path: str, *, params: dict | None = None) -> requests.Response:
        return self._request("GET", path, params=params)

    def post(self, path: str, json: dict | None = None) -> requests.Response:
        return self._request("POST", path, json=json)

    def create_video_generation_task(self, payload: dict[str, Any]) -> str:
        """Submit a video generation task and return its task_id."""
        response = self.post("/v1/video_generation", json=payload)
        data = response.json()
        task_id = data.get("task_id")
        if not task_id:
            raise MiniMaxAPIError(
                response.status_code,
                None,
                f"Video generation response missing task_id: {data}",
            )
        return str(task_id)

    def query_video_generation(self, task_id: str) -> dict[str, Any]:
        """Query a MiniMax video generation task by task_id."""
        response = self.get("/v1/query/video_generation", params={"task_id": task_id})
        return response.json()

    def poll_video_generation(
        self,
        task_id: str,
        *,
        poll_interval_seconds: float = 10.0,
        timeout_seconds: float = 900.0,
    ) -> dict[str, Any]:
        """Poll until a video task reaches success or fail."""
        deadline = time.time() + timeout_seconds
        latest: dict[str, Any] | None = None
        while time.time() < deadline:
            latest = self.query_video_generation(task_id)
            status = str(latest.get("status", "")).lower()
            if status == "success":
                return latest
            if status in {"fail", "failed"}:
                message = (
                    latest.get("error_message")
                    or latest.get("base_resp", {}).get("status_msg")
                    or "Unknown error"
                )
                raise MiniMaxAPIError(
                    200,
                    latest.get("base_resp", {}).get("status_code"),
                    f"Video generation failed: {message}",
                )
            time.sleep(poll_interval_seconds)
        raise MiniMaxAPIError(0, "timeout", f"Timed out waiting for video task {task_id}")

    def retrieve_file(self, file_id: str | int) -> dict[str, Any]:
        """Retrieve file metadata, including its temporary download URL."""
        response = self.get("/v1/files/retrieve", params={"file_id": file_id})
        data = response.json()
        file_info = data.get("file")
        if not isinstance(file_info, dict):
            raise MiniMaxAPIError(
                response.status_code,
                None,
                f"File retrieve response missing file object: {data}",
            )
        return file_info

    def fetch_download_url(self, file_id: str | int) -> str:
        """Resolve a file ID to a downloadable URL."""
        file_info = self.retrieve_file(file_id)
        download_url = file_info.get("download_url")
        if not download_url:
            raise MiniMaxAPIError(200, None, f"File metadata missing download_url: {file_info}")
        return str(download_url)

    def download_file(self, url: str, output_path: str | os.PathLike) -> None:
        """Download a file from a given URL to output_path."""
        resp = self._session.get(url, headers=self.headers, timeout=self.timeout, stream=True)
        resp.raise_for_status()
        path = Path(output_path) if not isinstance(output_path, Path) else output_path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        with open(path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
