"""MiniMax Official image generation tool.

Directly calls the MiniMax official image API (image-01 by default).
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
DEFAULT_IMAGE_MODEL = "image-01"


class MiniMaxOfficialImage(BaseTool):
    name = "minimax_official_image"
    version = "0.1.0"
    tier = ToolTier.GENERATE
    capability = "image_generation"
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
    agent_skills = []

    capabilities = ["generate_image", "text_to_image", "image_edit"]
    supports = {
        "text_in_image": True,
        "multiple_outputs": False,
    }
    best_for = [
        "high-quality image generation via MiniMax official API",
        "Chinese prompt support",
    ]
    not_good_for = ["offline generation", "budget-constrained projects"]

    input_schema = {
        "type": "object",
        "required": ["prompt"],
        "properties": {
            "prompt": {"type": "string"},
            "model": {
                "type": "string",
                "default": DEFAULT_IMAGE_MODEL,
                "description": "MiniMax image model (e.g. image-01)",
            },
            "aspect_ratio": {
                "type": "string",
                "enum": ["1:1", "16:9", "9:16", "4:3", "3:4", "21:9"],
                "default": "1:1",
            },
            "resolution": {
                "type": "string",
                "description": "Output resolution (e.g. 1024x1024). If omitted, uses model default.",
            },
            "image_url": {
                "type": "string",
                "description": "Reference image URL for image-to-image generation",
            },
            "output_format": {
                "type": "string",
                "enum": ["png", "jpeg", "webp"],
                "default": "png",
            },
            "output_path": {"type": "string"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=1, ram_mb=512, vram_mb=0, disk_mb=100, network_required=True
    )
    retry_policy = RetryPolicy(max_retries=2, retryable_errors=["rate_limit", "timeout"])
    idempotency_key_fields = ["prompt", "model", "aspect_ratio", "resolution", "image_url", "output_format"]
    side_effects = ["writes image file to output_path", "calls MiniMax Official API"]
    user_visible_verification = [
        "Inspect generated image for relevance and quality",
    ]

    def get_status(self) -> ToolStatus:
        if os.environ.get("MINIMAX_API_KEY"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        # MiniMax image generation is approximately $0.01-0.02 per image
        return 0.02

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
            return ToolResult(success=False, error=f"MiniMax image generation failed: {exc}")

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
        model = inputs.get("model", DEFAULT_IMAGE_MODEL)
        aspect_ratio = inputs.get("aspect_ratio", "1:1")
        resolution = inputs.get("resolution")
        image_url = inputs.get("image_url")
        output_format = inputs.get("output_format", "png")

        ext = output_format
        output_path = Path(inputs.get("output_path", f"minimax_image.{ext}"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        payload: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
        }

        if aspect_ratio:
            payload["aspect_ratio"] = aspect_ratio
        if resolution:
            payload["resolution"] = resolution
        if image_url:
            payload["image_url"] = image_url

        try:
            resp = client.post(
                "/v1/image_generation",
                json=payload,
            )
            data = resp.json()
        except MiniMaxAPIError:
            raise
        except Exception as exc:
            return ToolResult(success=False, error=f"Failed to parse MiniMax image response: {exc}")

        # Extract image URL from response
        # Response shape: { data: { images: [{ url: "..." }] } }
        image_url_result = (
            data.get("data", {})
            .get("images", [{}])[0]
            .get("url")
            or data.get("data", {})
            .get("image_url")
            or data.get("data", {})
            .get("url")
            or data.get("url")
        )

        if not image_url_result:
            base_resp = data.get("base_resp", {})
            status_code = base_resp.get("status_code", 0)
            if status_code != 0:
                msg = base_resp.get("status_msg", "Unknown error")
                return ToolResult(
                    success=False,
                    error=f"MiniMax image API error {status_code}: {msg}",
                )
            return ToolResult(
                success=False,
                error=f"No image URL in response: {data}",
            )

        # Download the image
        client.download_file(image_url_result, output_path)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "prompt": prompt,
                "aspect_ratio": aspect_ratio,
                "resolution": resolution,
                "output": str(output_path),
            },
            artifacts=[str(output_path)],
            model=model,
        )
