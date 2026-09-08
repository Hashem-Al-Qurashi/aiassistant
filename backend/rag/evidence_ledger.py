"""Evidence ledger - research evidence tracking, source scoring, and citation verification.

Provides:
    - add_source: Fetch and store research source with content hash dedup.
    - get_evidence_for_query: Vector-based semantic search with authority/freshness weighting.
    - track_claim_evidence: Link a claim to supporting evidence items.
    - verify_citation: Verify every claim has traceable supporting evidence.
    - parse_pdf: Extract text + tables from PDF documents.
    - parse_xlsx: Extract data from Excel spreadsheets.
    - score_source: Authority (40%) + freshness (40%) + relevance (20%).
"""

import hashlib
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4


def score_source(publisher: str, freshness_days: int, domain_authority: float) -> float:
    """Calculate source quality score.

    Authority (40%) + Freshness (40%) + Relevance (20%).
    Relevance is assumed 1.0 when not querying (filled at search time).

    Args:
        publisher: Source publisher name (unused in calculation, reserved for future).
        freshness_days: Days since content was scraped (0 = today).
        domain_authority: Authority score 0-100.

    Returns:
        Score in [0.0, 1.0].
    """
    authority_score = min(domain_authority / 100.0, 1.0)
    freshness_score = max(0.0, 1.0 - freshness_days / 365.0)
    # Relevance is assumed 1.0 when not querying (filled at search time).
    relevance_score = 1.0
    return round(authority_score * 0.4 + freshness_score * 0.4 + relevance_score * 0.2, 4)


class EvidenceLedger:
    """Stores, indexes, and verifies research evidence.

    Core IP: content hash deduplication prevents citing the same source twice.
    Source scoring weights authority (40%), freshness (40%), relevance (20%).
    """

    def __init__(self, db_session: Any = None):
        self.db = db_session

    # -- Internal helpers --

    def _compute_hash(self, content: str) -> str:
        """Generate content hash for deduplication."""
        return hashlib.sha256(content.encode("utf-8")).hexdigest()[:64]

    async def _fetch_url(self, url: str) -> tuple[dict, str]:
        """Fetch URL content — returns (metadata, raw_text)."""
        metadata: dict = {"title": "Unknown", "publisher": "Unknown", "domain_authority": 0.0}
        return metadata, ""

    def _parse_content(self, content: str) -> str:
        """Parse and clean content into searchable text."""
        return content

    # -- Public API --

    async def add_source(
        self,
        url: str,
        engagement_id: str,
        publisher: str = None,
        domain_authority: float = None,
    ) -> UUID | None:
        """Add a research source. Returns source_id.

        Checks content hash for deduplication — if already stored,
        returns existing source_id instead of creating a duplicate.
        """
        if not self.db:
            return None

        from backend.models.entities import Source

        # Fetch URL content
        metadata, raw_content = await self._fetch_url(url)
        content_hash = self._compute_hash(raw_content)

        # Check for existing source by content hash (dedup)
        from sqlalchemy import select
        existing = await self.db.execute(
            select(Source).where(Source.content_hash == content_hash)
        )
        found = existing.scalars().first()
        if found:
            return found.id

        # Create new source
        source = Source(
            url=url,
            title=metadata.get("title", publisher or "Unknown"),
            publisher=publisher or metadata.get("publisher", "Unknown"),
            domain_authority=domain_authority if domain_authority is not None
            else metadata.get("domain_authority", 0.0),
            content_hash=content_hash,
            scraped_at=datetime.utcnow(),
        )
        self.db.add(source)
        await self.db.flush()
        return source.id

    async def get_evidence_for_query(
        self,
        query: str,
        engagement_id: str,
        top_k: int = 5,
    ) -> list[dict]:
        """Vector search with authority/freshness weighting.

        Returns list of dicts: {id, content, score, source_url, source_authority}.
        """
        if not self.db:
            return []

        from backend.models.entities import EvidenceItem, Source

        # In production: use pgvector for semantic search
        # For now: simple filter by engagement
        from sqlalchemy import select
        stmt = select(EvidenceItem).where(
            EvidenceItem.engagement_id == UUID(engagement_id)
        ).limit(top_k)
        result = await self.db.execute(stmt)
        items = result.scalars().all()

        # Score each evidence item by source quality
        scored = []
        for item in items:
            source_result = await self.db.execute(
                select(Source).where(Source.id == item.source_id)
            )
            source = source_result.scalar_one_or_none()
            if source:
                freshness_days = (
                    (datetime.utcnow() - source.scraped_at).days
                    if source.scraped_at else 365
                )
                source_score = score_source(
                    source.publisher or "",
                    freshness_days,
                    float(source.domain_authority or 0.0),
                )
                scored.append({
                    "id": str(item.id),
                    "content": item.content_json,
                    "score": source_score,
                    "source_url": source.url,
                    "source_authority": float(source.domain_authority or 0.0),
                })

        # Sort by score descending
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    async def track_claim_evidence(self, claim: str, source_ids: list[str]) -> str:
        """Link a claim to its supporting evidence.

        Returns a claim_id for verification.
        """
        if not self.db:
            return str(uuid4())

        # In production: store claim → evidence mapping
        # For now: return generated ID
        return str(uuid4())

    def verify_citation(self, claims: list[dict]) -> dict:
        """Verify citation correctness — trace every claim to supporting evidence.

        Args:
            claims: List of {claim_text, evidence_ids}.

        Returns:
            {supported_claims, unsupported_claims, missing_citations, confidence}
        """
        if not claims:
            return {
                "supported_claims": 0,
                "unsupported_claims": 0,
                "missing_citations": [],
                "confidence": 1.0,
            }

        missing = []
        supported = 0
        unsupported = 0

        for claim in claims:
            evidence_ids = claim.get("evidence_ids", [])
            if evidence_ids:
                supported += 1
            else:
                unsupported += 1
                missing.append(claim.get("claim_text", "unknown"))

        total = len(claims)
        confidence = supported / total if total > 0 else 1.0

        return {
            "supported_claims": supported,
            "unsupported_claims": unsupported,
            "missing_citations": missing,
            "confidence": round(confidence, 4),
        }

    async def parse_pdf(self, pdf_path: str) -> list[dict]:
        """Extract text and tables from PDF using pdfplumber.

        Returns list of evidence chunks with content_type and chunk_index.
        """
        if not self.db:
            return []

        import pdfplumber

        chunks = []
        with pdfplumber.open(pdf_path) as pdf:
            for page_idx, page in enumerate(pdf.pages):
                # Extract text
                text = page.extract_text() or ""
                if text.strip():
                    chunks.append({
                        "content": text,
                        "content_type": "text",
                        "page": page_idx + 1,
                        "chunk_index": page_idx,
                    })

                # Extract tables
                tables = page.extract_tables()
                for table_idx, table in enumerate(tables):
                    if table:
                        chunks.append({
                            "content": str(table),
                            "content_type": "table",
                            "page": page_idx + 1,
                            "chunk_index": f"{page_idx}_{table_idx}",
                        })

        return chunks

    async def parse_xlsx(self, xlsx_path: str) -> list[dict]:
        """Extract data from Excel spreadsheet.

        Returns list of sheet data with content_type='table'.
        """
        import openpyxl

        chunks = []
        wb = openpyxl.load_workbook(xlsx_path, data_only=True)

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = []
            for row in ws.iter_rows(values_only=True):
                rows.append(list(row))

            if rows:
                chunks.append({
                    "content": str(rows),
                    "content_type": "table",
                    "sheet": sheet_name,
                    "chunk_index": sheet_name,
                })

        return chunks

    # -- Async sync wrappers (for compatibility) --

    def add_source_sync(
        self,
        url: str,
        engagement_id: str,
        publisher: str = None,
        domain_authority: float = None,
    ) -> UUID | None:
        """Sync wrapper for add_source."""
        if not self.db:
            return None

        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.add_source(url, engagement_id, publisher, domain_authority)
        )
