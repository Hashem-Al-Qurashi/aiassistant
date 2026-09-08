"""Tests for EvidenceLedger — research evidence tracking and verification.

G2: TDD tests for web scraping, PDF/XLSX parsing, citation tracking,
source scoring, and pgvector semantic search.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from uuid import uuid4

from backend.rag.evidence_ledger import EvidenceLedger, score_source


class TestScoreSource:
    """Unit tests for source scoring algorithm."""

    def test_perfect_authority_and_freshness(self):
        """Authority 100, fresh today → score = 1.0."""
        score = score_source("example.com", 0, 100.0)
        authority_score = min(100.0 / 100, 1.0)  # 1.0
        freshness_score = max(0, 1 - (0 / 365))  # 1.0
        expected = authority_score * 0.4 + freshness_score * 0.4 + 0.2
        assert score == pytest.approx(expected, abs=0.001)

    def test_zero_authority(self):
        """Authority 0, fresh today → score = 0.2 (relevance only)."""
        score = score_source("unknown.com", 0, 0.0)
        authority_score = 0.0
        freshness_score = 1.0
        expected = authority_score * 0.4 + freshness_score * 0.4 + 0.2
        assert score == pytest.approx(expected, abs=0.001)

    def test_one_year_old(self):
        """Freshness 365 days → freshness_score = 0."""
        score = score_source("example.com", 365, 80.0)
        authority_score = min(80.0 / 100, 1.0)  # 0.8
        freshness_score = 0.0  # 1 - 365/365 = 0
        expected = authority_score * 0.4 + freshness_score * 0.4 + 0.2
        assert score == pytest.approx(expected, abs=0.001)

    def test_over_one_year_old_clamps_freshness_to_zero(self):
        """Freshness > 365 days → freshness_score clamped to 0."""
        score = score_source("example.com", 400, 80.0)
        authority_score = 0.8
        freshness_score = max(0, 1 - (400 / 365))  # clamped to 0
        expected = authority_score * 0.4 + freshness_score * 0.4 + 0.2
        assert score == pytest.approx(expected, abs=0.001)


class TestEvidenceLedger:
    """Tests for EvidenceLedger core operations."""

    @pytest.mark.asyncio
    async def test_no_db_returns_empty_search(self):
        """search without DB returns empty list."""
        ledger = EvidenceLedger(db_session=None)
        results = await ledger.get_evidence_for_query("market size", "eng-1")
        assert results == []

    def test_verify_citation_no_claims(self):
        """verify_citation with empty claims returns fully supported."""
        ledger = EvidenceLedger(db_session=None)
        result = ledger.verify_citation([])
        assert result["supported_claims"] == 0
        assert result["unsupported_claims"] == 0
        assert result["missing_citations"] == []

    @pytest.mark.asyncio
    async def test_add_source_validates_url(self, db_session):
        """G2: add_source creates a Source entity with content hash."""
        from backend.models.entities import Source

        with patch.object(EvidenceLedger, '_fetch_url', new_callable=AsyncMock) as mock_fetch, \
             patch.object(EvidenceLedger, '_parse_content', return_value="Full content of the page."), \
             patch.object(EvidenceLedger, '_compute_hash', return_value="abc123"):
            mock_fetch.return_value = ({
                "title": "Market Report",
                "publisher": "Statista",
                "domain_authority": 95.0,
            }, "Full content of the page.")

            ledger = EvidenceLedger(db_session=db_session)
            source_id = await ledger.add_source("https://statista.com/report", "market")

            assert source_id is not None

    @pytest.mark.asyncio
    async def test_add_source_dedup_by_content_hash(self):
        """G2: add_source with same content hash returns existing source_id."""
        from backend.models.entities import Source

        existing_source = MagicMock()
        existing_source.id = uuid4()
        existing_source.url = "https://statista.com/report"

        mock_db = MagicMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = existing_source
        mock_db.execute = AsyncMock(return_value=mock_result)

        ledger = EvidenceLedger(db_session=mock_db)
        with patch.object(EvidenceLedger, '_compute_hash', return_value="abc123"):
            result_id = await ledger.add_source("https://statista.com/report", "market")

        assert str(result_id) == str(existing_source.id)

    @pytest.mark.asyncio
    async def test_get_evidence_for_query_returns_scored_results(self):
        """G2: semantic search returns evidence items with source scores."""
        from backend.models.entities import EvidenceItem, Source
        from uuid import uuid4 as uuid4_gen

        eng_id = str(uuid4())
        source = Source(
            url="https://example.com",
            title="Test Source",
            publisher="Example",
            domain_authority=80.0,
            content_hash="hash123",
        )
        await db_session.flush() if False else None

        evidence = EvidenceItem(
            engagement_id=uuid4(),
            source_id=source.id,
            content_hash="hash123",
        )

        mock_db = MagicMock()
        # First call: select EvidenceItem → returns evidence
        mock_db.execute = AsyncMock(side_effect=[
            MagicMock(),  # evidence query
            MagicMock(),  # source query
        ])
        # Configure side effects for the two execute calls
        ev_result = MagicMock()
        ev_result.scalars.return_value.all.return_value = [evidence]
        src_result = MagicMock()
        src_result.scalar_one_or_none.return_value = source
        mock_db.execute = AsyncMock(side_effect=[ev_result, src_result])

        ledger = EvidenceLedger(db_session=mock_db)
        results = await ledger.get_evidence_for_query("market size", eng_id)

        assert len(results) == 1
        assert results[0]["source_url"] == "https://example.com"
