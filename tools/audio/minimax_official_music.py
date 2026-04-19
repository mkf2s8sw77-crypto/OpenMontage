"""MiniMax Official music generation tool.

Directly calls the MiniMax official music API.
Does NOT go through fal.ai.

The default model version is configurable via MINIMAX_MUSIC_MODEL env var
because official documentation historically shows inconsistent model names.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)

# Default model - exposed so callers / tests can reference / override
DEFAULT_MUSIC_MODEL = os.environ.get("MINIMAX_MUSIC_MODEL", "music-2.0")


def get_music_api_key() -> str | None:
    """Prefer a dedicated music key when provided, otherwise fall back."""
    return os.environ.get("MINIMAX_MUSIC_API_KEY") or os.environ.get("MINIMAX_API_KEY")


class MiniMaxOfficialMusic(BaseTool):
    name = "minimax_official_music"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "music_generation"
    provider = "minimax_official"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = []
    install_instructions = (
        "Set MINIMAX_MUSIC_API_KEY (preferred) or MINIMAX_API_KEY:\n"
        "  export MINIMAX_MUSIC_API_KEY=your_music_key_here\n"
        "  export MINIMAX_API_KEY=your_general_key_here\n"
        "Get a key at https://platform.minimaxi.com/\n"
        "Optionally set MINIMAX_MUSIC_MODEL to override the default music model."
    )
    agent_skills = []

    capabilities = ["generate_music", "generate_sfx"]
    supports = {}
    best_for = [
        "high-quality music generation via MiniMax official API",
        "background music for video",
    ]
    not_good_for = ["offline generation"]

    input_schema = {
        "type": "object",
        "required": ["prompt", "lyrics"],
        "properties": {
            "prompt": {
                "type": "string",
                "description": "Music description (mood, genre, instruments, tempo)",
            },
            "lyrics": {
                "type": "string",
                "description": "Lyrics content used by MiniMax music generation.",
            },
            "model": {
                "type": "string",
                "default": DEFAULT_MUSIC_MODEL,
                "description": "MiniMax music model (configurable; defaults to music-2.0 or MINIMAX_MUSIC_MODEL env var)",
            },
            "duration_seconds": {
                "type": "number",
                "minimum": 3,
                "maximum": 600,
                "description": "Target duration in seconds (3-600s)",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "duration_seconds"]
    side_effects = ["writes audio file to output_path", "calls MiniMax Official API"]
    user_visible_verification = [
        "Listen to generated music for mood and quality",
    ]

    def get_status(self) -> ToolStatus:
        if get_music_api_key():
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # Approximate: ~$0.05 per 30 seconds
        duration = inputs.get("duration_seconds", 30)
        return round(duration / 30 * 0.05, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = get_music_api_key()
        if not api_key:
            return ToolResult(
                success=False,
                error="No MiniMax music API key. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key)
        except Exception as exc:
            return ToolResult(success=False, error=f"MiniMax music generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs)
        return result

    def _generate(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        from lib.providers.minimax_official_client import (
            MiniMaxAPIError,
            MiniMaxOfficialClient,
        )

        client = MiniMaxOfficialClient(api_key=api_key)

        prompt = inputs["prompt"]
        lyrics = inputs["lyrics"]
        model = inputs.get("model", DEFAULT_MUSIC_MODEL)
        duration = inputs.get("duration_seconds")

        output_path = Path(inputs.get("output_path", "minimax_music.mp3"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "lyrics": lyrics,
            "stream": False,
            "output_format": "url",
            "audio_setting": {
                "format": "mp3",
            },
        }
        try:
            resp = client.post(
                "/v1/music_generation",
                json=payload,
            )
            data = resp.json()
        except MiniMaxAPIError:
            raise
        except Exception as exc:
            return ToolResult(success=False, error=f"Failed to parse MiniMax music response: {exc}")

        base_resp = data.get("base_resp", {})
        status_code = base_resp.get("status_code", 0)
        if status_code != 0:
            msg = base_resp.get("status_msg", "Unknown error")
            return ToolResult(
                success=False,
                error=f"MiniMax music API error {status_code}: {msg}",
            )

        audio_payload = data.get("data", {}).get("audio")
        if isinstance(audio_payload, str) and audio_payload.startswith(("http://", "https://")):
            client.download_file(audio_payload, output_path)
        elif isinstance(audio_payload, str):
            from lib.providers.minimax_official_client import write_hex_payload

            write_hex_payload(audio_payload, output_path)
        else:
            return ToolResult(
                success=False,
                error=f"No audio payload in response: {data}",
            )

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "prompt": prompt,
                "lyrics": lyrics,
                "duration_seconds": duration,
                "audio_url": audio_payload if isinstance(audio_payload, str) and audio_payload.startswith(("http://", "https://")) else None,
                "output": str(output_path),
                "format": "mp3",
            },
            artifacts=[str(output_path)],
            model=model,
        )
