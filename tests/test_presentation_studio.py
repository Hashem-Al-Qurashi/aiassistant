"""Tests for presentation studio — slide generation and semantic editing.

Phase 4: Presentation Studio TDD (RED → GREEN → REFACTOR).
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from backend.presentations.studio import PresentationStudio


class TestPresentationStudio:
    """Test presentation deck generation and editing."""

    def test_generate_deck_from_report(self):
        """G2: Deck created from report JSON with slides per recommendation."""
        report = {
            "title": "Market Entry Strategy",
            "sections": [
                {
                    "id": "executive_summary",
                    "type": "executive_summary",
                    "heading": "Executive Summary",
                    "content": "Summary text",
                    "evidence_refs": [],
                },
                {
                    "id": "rec_1",
                    "type": "recommendation",
                    "heading": "Enter Riyadh market",
                    "content": "High ROI opportunity",
                    "confidence": 0.75,
                    "assumptions": ["A001"],
                    "evidence_refs": ["E17"],
                },
            ],
        }

        studio = PresentationStudio()
        deck = studio.generate_deck(report, brand_profile={})

        assert "title" in deck
        assert "slides" in deck
        assert len(deck["slides"]) >= 2

    def test_deck_slides_have_layout_fields(self):
        """G2: Each slide has objective, message, evidence, layout, brand."""
        studio = PresentationStudio()
        report = {
            "title": "Test",
            "sections": [
                {
                    "id": "s1",
                    "type": "recommendation",
                    "heading": "Slide Title",
                    "content": "Content",
                    "confidence": 0.8,
                    "assumptions": ["A1"],
                    "evidence_refs": ["E1"],
                },
            ],
        }
        deck = studio.generate_deck(report, {})

        slide = deck["slides"][0]
        assert "objective" in slide
        assert "message" in slide
        assert "evidence" in slide
        assert "layout" in slide
        assert "brand" in slide

    def test_edit_slide_semantic_instruction(self):
        """G2: 'Turn slide X into a 2x2 matrix' updates layout."""
        studio = PresentationStudio()
        report = {
            "title": "Test",
            "sections": [
                {
                    "id": "s1",
                    "type": "recommendation",
                    "heading": "Options",
                    "content": "Various options",
                    "confidence": 0.8,
                    "assumptions": [],
                    "evidence_refs": [],
                },
            ],
        }
        deck = studio.generate_deck(report, {})
        slide_id = deck["slides"][0]["id"]

        updated = studio.edit_slide(slide_id, "Turn into a 2x2 matrix", deck)

        assert updated["layout"] == "matrix_2x2"

    def test_export_pptx(self):
        """G2: PPTX export produces binary data with expected structure."""
        studio = PresentationStudio()
        report = {
            "title": "Test",
            "sections": [
                {
                    "id": "s1",
                    "type": "recommendation",
                    "heading": "Test Slide",
                    "content": "Content",
                    "confidence": 0.8,
                    "assumptions": [],
                    "evidence_refs": [],
                },
            ],
        }
        deck = studio.generate_deck(report, {})

        pptx_bytes = studio.export_pptx(deck)

        assert pptx_bytes is not None
        assert isinstance(pptx_bytes, bytes)
        # PPTX is a zip file
        assert pptx_bytes[:2] == b"PK"

    def test_brand_profile_inference(self):
        """G2: Brand profile can be inferred from uploaded deck metadata."""
        studio = PresentationStudio()
        brand = studio.infer_brand_profile({
            "colors": ["#1a73e8", "#34a853"],
            "font_family": "Arial",
            "layout_pattern": "title_left_content_right",
        })

        assert "colors" in brand
        assert "font_family" in brand
        assert "layout_pattern" in brand

    def test_slide_edit_preserves_other_slides(self):
        """G2: Editing one slide doesn't affect other slides in deck."""
        studio = PresentationStudio()
        report = {
            "title": "Test",
            "sections": [
                {
                    "id": "s1",
                    "type": "recommendation",
                    "heading": "Slide 1",
                    "content": "C1",
                    "confidence": 0.8,
                    "assumptions": [],
                    "evidence_refs": [],
                },
                {
                    "id": "s2",
                    "type": "recommendation",
                    "heading": "Slide 2",
                    "content": "C2",
                    "confidence": 0.7,
                    "assumptions": [],
                    "evidence_refs": [],
                },
            ],
        }
        deck = studio.generate_deck(report, {})
        slide1_id = deck["slides"][0]["id"]
        slide2_original = deck["slides"][1]["objective"]

        studio.edit_slide(slide1_id, "Turn into a 2x2 matrix", deck)

        assert deck["slides"][1]["objective"] == slide2_original
