"""MiniMax Official video generation tool.

Directly calls the MiniMax official async video generation API.
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


DEFAULT_VIDEO_MODEL = "MiniMax-Hailuo-2.3"


class MiniMaxOfficialVideo(BaseTool):
    name = "minimax_official_video"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "video_generation"
    provider = "minimax_official"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.ASYNC
    determinism = Determinism.STOCHASTIC
    runtime = ToolRuntime.API

    dependencies = ["env:MINIMAX_API_KEY"]
    install_instructions = (
        "Set the MINIMAX_API_KEY environment variable:\n"
        "  export MINIMAX_API_KEY=your_key_here\n"
        "Get a key at https://platform.minimaxi.com/"
    )
    agent_skills = []

    capabilities = ["text_to_video", "image_to_video", "first_last_frame_to_video"]
    supports = {
        "text_to_video": True,
        "image_to_video": True,
        "first_last_frame_to_video": True,
        "native_audio": False,
    }
    best_for = [
        "official MiniMax direct video generation",
        "async video generation without fal.ai",
        "text-to-video and image-conditioned video on MiniMax CN node",
    ]
    not_good_for = ["offline generation", "instant turnaround"]
    fallback_tools = ["minimax_video", "kling_video", "veo_video", "wan_video"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "operation": {
                "type": "string",
                "enum": ["text_to_video", "image_to_video", "first_last_frame_to_video"],
                "default": "text_to_video",
            },
            "model": {
                "type": "string",
                "default": DEFAULT_VIDEO_MODEL,
                "description": "MiniMax official video model",
            },
            "duration": {
                "type": "integer",
                "enum": [6, 10],
                "default": 6,
            },
            "resolution": {
                "type": "string",
                "enum": ["768P", "1080P"],
                "default": "1080P",
            },
            "first_frame_image": {
                "type": "string",
                "description": "Image URL used as the first frame for image_to_video or first_last_frame_to_video",
            },
            "last_frame_image": {
                "type": "string",
                "description": "Image URL used as the final frame for first_last_frame_to_video",
            },
            "callback_url": {"type": "string"},
            "aigc_watermark": {"type": "boolean", "default": False},
            "prompt_optimizer": {"type": "boolean", "default": True},
            "output_path": {"type": "string"},
            "poll_interval_seconds": {"type": "number", "default": 10},
            "timeout_seconds": {"type": "number", "default": 900},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=500, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "operation", "duration", "resolution"]
    side_effects = ["writes video file to output_path", "calls MiniMax Official API"]
    user_visible_verification = ["Watch generated clip for motion coherence and prompt adherence"]

    def get_status(self) -> ToolStatus:
        if os.environ.get("MINIMAX_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        duration = int(inputs.get("duration", 6))
        resolution = inputs.get("resolution", "1080P")
        per_second = 0.06 if resolution == "1080P" else 0.04
        return round(duration * per_second, 4)

    def estimate_runtime(self, inputs: dict[str, Any]) -> float:
        duration = int(inputs.get("duration", 6))
        return 60.0 if duration <= 6 else 120.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if not os.environ.get("MINIMAX_API_KEY"):
            return ToolResult(
                success=False,
                error="No MiniMax API key. " + self.install_instructions,
            )

        start = time.time()
        try:
            result = self._generate(inputs)
        except Exception as exc:
            return ToolResult(success=False, error=f"MiniMax official video generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        result.cost_usd = self.estimate_cost(inputs)
        return result

    def _build_payload(self, inputs: dict[str, Any]) -> dict[str, Any]:
        operation = inputs.get("operation", "text_to_video")
        payload: dict[str, Any] = {
            "model": inputs.get("model", DEFAULT_VIDEO_MODEL),
            "prompt": inputs["prompt"],
            "duration": int(inputs.get("duration", 6)),
            "resolution": inputs.get("resolution", "1080P"),
            "aigc_watermark": bool(inputs.get("aigc_watermark", False)),
            "prompt_optimizer": bool(inputs.get("prompt_optimizer", True)),
        }
        if inputs.get("callback_url"):
            payload["callback_url"] = inputs["callback_url"]

        if operation == "image_to_video":
            first_frame = inputs.get("first_frame_image")
            if not first_frame:
                raise ValueError("image_to_video requires first_frame_image")
            payload["first_frame_image"] = first_frame
        elif operation == "first_last_frame_to_video":
            first_frame = inputs.get("first_frame_image")
            last_frame = inputs.get("last_frame_image")
            if not first_frame or not last_frame:
                raise ValueError("first_last_frame_to_video requires first_frame_image and last_frame_image")
            payload["first_frame_image"] = first_frame
            payload["last_frame_image"] = last_frame

        return payload

    def _generate(self, inputs: dict[str, Any]) -> ToolResult:
        from lib.providers.minimax_official_client import MiniMaxOfficialClient
        from tools.video._shared import probe_output

        client = MiniMaxOfficialClient()
        payload = self._build_payload(inputs)

        task_id = client.create_video_generation_task(payload)
        task_result = client.poll_video_generation(
            task_id,
            poll_interval_seconds=float(inputs.get("poll_interval_seconds", 10)),
            timeout_seconds=float(inputs.get("timeout_seconds", 900)),
        )

        file_id = task_result.get("file_id")
        if not file_id:
            raise ValueError(f"MiniMax video task succeeded without file_id: {task_result}")

        file_info = client.retrieve_file(file_id)
        download_url = file_info.get("download_url")
        if not download_url:
            raise ValueError(f"MiniMax file metadata missing download_url: {file_info}")

        output_path = Path(inputs.get("output_path", "minimax_official_video.mp4"))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        client.download_file(str(download_url), output_path)

        probed = probe_output(output_path)
        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": payload["model"],
                "prompt": inputs["prompt"],
                "operation": inputs.get("operation", "text_to_video"),
                "task_id": str(task_id),
                "task_status": task_result.get("status", "Success"),
                "file_id": str(file_id),
                "download_url": str(download_url),
                "output": str(output_path),
                "output_path": str(output_path),
                "format": "mp4",
                "resolution": payload["resolution"],
                "duration_requested_seconds": payload["duration"],
                **probed,
            },
            artifacts=[str(output_path)],
            model=str(payload["model"]),
        )
