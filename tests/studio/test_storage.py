"""Tests for studio_api.storage helpers."""

from __future__ import annotations

from studio_api.storage import build_output_path


def test_build_output_path_generates_unique_names_within_same_second():
    first = build_output_path("storage-test", "images", "image", "png")
    second = build_output_path("storage-test", "images", "image", "png")

    assert first != second
    assert first.name.startswith("image-")
    assert second.name.startswith("image-")
