"""Tests for video studio — scene decomposition and rendering skeleton.

Phase 5: Video generation pipeline TDD (RED → GREEN → REFACTOR).
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from backend.video.scene_generator import VideoStudio


class TestVideoStudio:
    """Test video scene decomposition and rendering."""

    def test_decompose_to_scenes(self):
        """G2: Report decomposed into structured video scenes."""
        studio = VideoStudio()
        report = {
            "title": "Market Entry Strategy",
            "sections": [
                {
                    "id": "exec",
                    "type": "executive_summary",
                    "heading": "Executive Summary",
                    "content": "Key findings",
                },
                {
                    "id": "rec1",
                    "type": "recommendation",
                    "heading": "Enter Riyadh",
                    "content": "High ROI opportunity",
                },
            ],
        }

        scenes = studio.decompose_to_scenes(report)

        assert len(scenes) >= 1
        assert all("id" in s for s in scenes)
        assert all("title" in s for s in scenes)
        assert all("narration" in s for s in scenes)

    def test_scene_types(self):
        """G2: Scenes include hook, evidence montage, recommendation reveal."""
        studio = VideoStudio()
        report = {
            "title": "Strategy",
            "sections": [
                {
                    "id": "exec",
                    "type": "executive_summary",
                    "heading": "Summary",
                    "content": "text",
                },
                {
                    "id": "rec1",
                    "type": "recommendation",
                    "heading": "Recommend",
                    "content": "text",
                },
            ],
        }

        scenes = studio.decompose_to_scenes(report)

        scene_types = [s.get("scene_type") for s in scenes]
        assert "hook" in scene_types

    def test_render_scene_returns_path(self):
        """G2: render_scene returns output path string."""
        studio = VideoStudio()
        scene = {
            "id": "scene_1",
            "title": "Hook",
            "scene_type": "hook",
            "narration": "Welcome to the strategy video",
            "content_items": [],
        }

        path = studio.render_scene(scene, brand_profile={})

        assert path is not None
        assert isinstance(path, str)

    @pytest.mark.asyncio
    async def test_export_video_returns_path(self):
        """G2: export_video assembles scenes and returns output path."""
        studio = VideoStudio()
        scenes = [
            {
                "id": "scene_1",
                "title": "Hook",
                "scene_type": "hook",
                "narration": "Intro",
                "content_items": [],
            },
        ]

        output_path = await studio.export_video(scenes, "/tmp/test_video.mp4")

        assert output_path is not None
        assert isinstance(output_path, str)

    def test_scene_has_visual_description(self):
        """G2: Each scene has visual description for rendering."""
        studio = VideoStudio()
        report = {
            "title": "Strategy",
            "sections": [
                {
                    "id": "exec",
                    "type": "executive_summary",
                    "heading": "Summary",
                    "content": "text",
                },
            ],
        }

        scenes = studio.decompose_to_scenes(report)
        assert "visual_description" in scenes[0]

    def test_no_scenes_for_empty_report(self):
        """G2: Empty report returns minimal hook scene."""
        studio = VideoStudio()
        report = {"title": "Empty", "sections": []}

        scenes = studio.decompose_to_scenes(report)

        assert len(scenes) >= 1
        assert scenes[0]["scene_type"] == "hook"
