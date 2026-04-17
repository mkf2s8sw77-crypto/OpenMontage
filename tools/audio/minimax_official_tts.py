"""MiniMax Official text-to-speech tool.

Directly calls the MiniMax official TTS API (speech-2.8-hd by default).
Does NOT go through fal.ai.
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
DEFAULT_TTS_MODEL = "speech-2.8-hd"


class MiniMaxOfficialTTS(BaseTool):
    name = "minimax_official_tts"
    version = "0.1.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "minimax_official"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:MINIMAX_API_KEY"]
    install_instructions = (
        "Set the MINIMAX_API_KEY environment variable:\n"
        "  export MINIMAX_API_KEY=your_key_here\n"
        "Get a key at https://platform.minimaxi.com/"
    )
    fallback = "piper_tts"
    fallback_tools = ["piper_tts"]
    agent_skills = []

    capabilities = ["text_to_speech", "voice_selection"]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": False,
        "native_audio": True,
    }
    best_for = [
        "high-quality narration via MiniMax official API",
        "Chinese/English bilingual TTS",
    ]
    not_good_for = ["voice clone matching", "fully offline production"]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string"},
            "model": {
                "type": "string",
                "default": DEFAULT_TTS_MODEL,
                "description": "MiniMax TTS model (e.g. speech-2.8-hd)",
            },
            "voice": {
                "type": "string",
                "default": "male-qn-qingse",
                "description": "MiniMax voice ID",
            },
            "speed": {
                "type": "number",
                "default": 1.0,
                "description": "Speech speed multiplier (0.5–2.0)",
            },
            "vol": {
                "type": "number",
                "default": 1.0,
                "description": "Volume (0–2)",
            },
            "pitch": {
                "type": "number",
                "default": 0,
                "description": "Pitch adjustment in semitones",
            },
            "output_format": {
                "type": "string",
                "enum": ["mp3", "wav", "flac"],
                "default": "mp3",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=256, vram_mb=0, disk_mb=50, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["text", "model", "voice", "speed", "vol", "pitch", "output_format"]
    side_effects = ["writes audio file to output_path", "calls MiniMax Official API"]
    user_visible_verification = [
        "Listen to generated audio for intelligibility and tone",
    ]

    def get_status(self) -> ToolStatus:
        if os.environ.get("MINIMAX_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # MiniMax TTS pricing is roughly $0.8 per 1M characters (CNY, approximate)
        return round(len(inputs.get("text", "")) / 1_000_000 * 0.8, 4)

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        api_key = os.environ.get("MINIMAX_API_KEY")
        if not api_key:
            return ToolResult(
                success=False,
                error="No MiniMax API key. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._generate(inputs, api_key)
        except Exception as exc:
            return ToolResult(success=False, error=f"MiniMax TTS failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs)
        return result

    def _generate(self, inputs: dict[str, Any], api_key: str) -> ToolResult:
        from lib.providers.minimax_official_client import (
            MiniMaxAPIError,
            MiniMaxOfficialClient,
        )

        client = MiniMaxOfficialClient(api_key=api_key)

        text = inputs["text"]
        model = inputs.get("model", DEFAULT_TTS_MODEL)
        voice = inputs.get("voice", "male-qn-qingse")
        speed = inputs.get("speed", 1.0)
        vol = inputs.get("vol", 1.0)
        pitch = inputs.get("pitch", 0)
        output_format = inputs.get("output_format", "mp3")

        ext = output_format
        output_path = Path(inputs.get("output_path", f"minimax_tts.{ext}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Build request payload
        payload: dict[str, Any] = {
            "model": model,
            "text": text,
            "stream": False,
        }

        # Only include audio setting if not default
        audio_settings: dict[str, Any] = {}
        if speed != 1.0:
            audio_settings["speed"] = speed
        if vol != 1.0:
            audio_settings["vol"] = vol
        if pitch != 0:
            audio_settings["pitch"] = pitch
        if audio_settings:
            payload["audio_setting"] = audio_settings

        # Voice can be passed as string or dict
        if isinstance(voice, str):
            payload["voice_id"] = voice
        else:
            payload["voice_id"] = voice

        try:
            resp = client.post(
                "/v1/t2a_v2",
                json=payload,
            )
            data = resp.json()
        except MiniMaxAPIError:
            raise
        except Exception as exc:
            return ToolResult(success=False, error=f"Failed to parse MiniMax TTS response: {exc}")

        # The TTS API returns audio data in the response directly
        # or with a file_url to download
        file_url = (
            data.get("data", {})
            .get("audio", {})
            .get("file_url")
            or data.get("data", {})
            .get("file_url")
        )
        if not file_url:
            # Some API shapes put the URL at the top level
            file_url = data.get("file_url") or data.get("data", {}).get("url")

        if not file_url:
            # Try to detect API error
            base_resp = data.get("base_resp", {})
            status_code = base_resp.get("status_code", 0)
            if status_code != 0:
                msg = base_resp.get("status_msg", "Unknown error")
                return ToolResult(
                    success=False,
                    error=f"MiniMax TTS API error {status_code}: {msg}",
                )
            return ToolResult(
                success=False,
                error=f"No audio URL in response: {data}",
            )

        # Download the audio file
        client.download_file(file_url, output_path)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "voice": voice,
                "format": ext,
                "text_length": len(text),
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            model=model,
        )
