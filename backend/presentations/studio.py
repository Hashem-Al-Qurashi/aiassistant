"""Presentation studio — deck generation and semantic slide editing.

Core IP: structured slide objects with objective/message/evidence/layout/brand
fields, semantic editing instructions, and editable PPTX export.
"""

import io
from typing import Any


class PresentationStudio:
    """Generates structured presentation decks from reports.

    Each slide has: objective, message, evidence, layout, brand fields.
    Supports semantic editing ("turn slide 8 into a 2x2 matrix") and
    PPTX export with editability preserved.
    """

    # -- Internal helpers --

    def _infer_layout(self, section: dict) -> str:
        """Infer slide layout from section type."""
        section_type = section.get("type", "")
        if "summary" in section_type:
            return "title_content"
        if "recommendation" in section_type:
            return "title_bullets_evidence"
        return "title_content"

    def _build_slide(self, section: dict, brand_profile: dict) -> dict:
        """Build a structured slide object from a report section."""
        return {
            "id": section["id"],
            "type": section.get("type", "content"),
            "title": section.get("heading", ""),
            "objective": section.get("heading", ""),
            "message": section.get("content", ""),
            "evidence": section.get("evidence_refs", []),
            "assumptions": section.get("assumptions", []),
            "confidence": section.get("confidence", 1.0),
            "layout": self._infer_layout(section),
            "brand": brand_profile,
        }

    def infer_brand_profile(self, metadata: dict) -> dict:
        """Infer brand profile from uploaded deck metadata."""
        return {
            "colors": metadata.get("colors", ["#1a73e8", "#34a853"]),
            "font_family": metadata.get("font_family", "Arial"),
            "layout_pattern": metadata.get("layout_pattern", "title_left_content_right"),
        }

    # -- Public API --

    def generate_deck(self, report_json: dict, brand_profile: dict) -> dict:
        """Create structured slides from report JSON.

        Each slide: objective + message + evidence + layout + brand.
        """
        slides = []
        sections = report_json.get("sections", [])

        for section in sections:
            slide = self._build_slide(section, brand_profile)
            slides.append(slide)

        return {
            "title": report_json.get("title", "Untitled Deck"),
            "slides": slides,
            "brand_profile": brand_profile,
        }

    def edit_slide(self, slide_id: str, instruction: str, deck: dict) -> dict:
        """Conversationally edit a specific slide.

        Example: "Turn slide 8 into a 2x2 matrix"
        """
        slides = deck.get("slides", [])

        for slide in slides:
            if slide["id"] == slide_id:
                instruction_lower = instruction.lower()
                if "2x2 matrix" in instruction_lower or "matrix" in instruction_lower:
                    slide["layout"] = "matrix_2x2"
                elif "chart" in instruction_lower:
                    slide["layout"] = "chart"
                elif "comparison" in instruction_lower:
                    slide["layout"] = "comparison_table"
                elif "timeline" in instruction_lower:
                    slide["layout"] = "timeline"
                else:
                    slide["message"] = instruction

                return slide

        return {}

    def export_pptx(self, presentation: dict) -> bytes:
        """Generate editable PPTX from structured slide objects.

        Uses python-pptx to preserve editability.
        """
        from pptx import Presentation

        prs = Presentation()
        title_slide_layout = prs.slide_layouts[0]
        bullet_slide_layout = prs.slide_layouts[1]

        # Title slide
        title_slide = prs.slides.add_slide(title_slide_layout)
        title_slide.shapes.title.text = presentation.get("title", "Untitled")

        # Content slides
        for slide_data in presentation.get("slides", []):
            slide = prs.slides.add_slide(bullet_slide_layout)
            slide.shapes.title.text = slide_data.get("title", "")

            body = slide.shapes.placeholders[1]
            tf = body.text_frame
            tf.text = slide_data.get("message", "")

            if slide_data.get("evidence"):
                for ev in slide_data["evidence"]:
                    p = tf.add_paragraph()
                    p.text = f"Source: {ev}"
                    p.level = 1

        buffer = io.BytesIO()
        prs.save(buffer)
        buffer.seek(0)
        return buffer.getvalue()
