"""Core entity models for StratOS."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    Column,
    String,
    Text,
    DateTime,
    ForeignKey,
    Enum,
    Integer,
    Numeric,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from enum import Enum as PyEnum

from backend.core.base import Base
from backend.database import TESTING

if not TESTING:
    from pgvector.sqlalchemy import Vector

if not TESTING:
    from pgvector.sqlalchemy import Vector
else:
    Vector = None


class Organization(Base):
    """Organization entity - top-level tenant."""
    __tablename__ = "organizations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    name = Column(String(255), nullable=False)
    slug = Column(String(255), unique=True, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    engagements = relationship("Engagement", back_populates="organization")


class EngagementStatus(str, PyEnum):
    DISCOVERY = "discovery"
    RESEARCH = "research"
    ANALYSIS = "analysis"
    RECOMMENDATIONS = "recommendations"
    DELIVERABLES = "deliverables"
    ARCHIVED = "archived"


class Engagement(Base):
    """Engagement entity - the core stateful object in StratOS."""
    __tablename__ = "engagements"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    org_id = Column(UUID(as_uuid=True), ForeignKey("organizations.id"))
    name = Column(String(255), nullable=False)
    status = Column(
        Enum(EngagementStatus),
        nullable=False,
        default=EngagementStatus.DISCOVERY,
    )
    objective = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    organization = relationship("Organization", back_populates="engagements")
    assumptions = relationship("Assumption", back_populates="engagement")
    evidence_items = relationship("EvidenceItem", back_populates="engagement")
    hypotheses = relationship("Hypothesis", back_populates="engagement")
    recommendations = relationship("Recommendation", back_populates="engagement")
    dependency_edges = relationship("DependencyEdge", back_populates="engagement")


class AssumptionCriticality(str, PyEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class Assumption(Base):
    """Assumption entity - declared beliefs that shape recommendations."""
    __tablename__ = "assumptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    engagement_id = Column(UUID(as_uuid=True), ForeignKey("engagements.id"))
    name = Column(String(255), nullable=False)
    description = Column(Text)
    value = Column(Text)
    criticality = Column(
        Enum(AssumptionCriticality),
        nullable=False,
        default=AssumptionCriticality.MEDIUM,
    )
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    engagement = relationship("Engagement", back_populates="assumptions")


class EvidenceContentType(str, PyEnum):
    TEXT = "text"
    TABLE = "table"
    CHART = "chart"
    IMAGE = "image"


class EvidenceItem(Base):
    """Evidence item - research findings with content hash and embedding."""
    __tablename__ = "evidence_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    engagement_id = Column(UUID(as_uuid=True), ForeignKey("engagements.id"))
    source_id = Column(UUID(as_uuid=True), ForeignKey("sources.id"))
    content_hash = Column(String(64), nullable=False)
    content_type = Column(
        Enum(EvidenceContentType),
        nullable=False,
        default=EvidenceContentType.TEXT,
    )
    content_json = Column(Text)
    chunk_index = Column(Integer)
    embedding = Column(Vector(1536) if not TESTING else String(100))
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    engagement = relationship("Engagement", back_populates="evidence_items")
    source = relationship("Source", back_populates="evidence_items")
    hypothesis_evidence = relationship("HypothesisEvidence", back_populates="evidence_item")


class HypothesisStatus(str, PyEnum):
    PROPOSED = "proposed"
    SUPPORTED = "supported"
    REFUTED = "refuted"
    TESTING = "testing"


class Hypothesis(Base):
    """Hypothesis entity - testable claims backed by evidence."""
    __tablename__ = "hypotheses"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    engagement_id = Column(UUID(as_uuid=True), ForeignKey("engagements.id"))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    confidence = Column(Numeric(4, 2))
    status = Column(
        Enum(HypothesisStatus),
        nullable=False,
        default=HypothesisStatus.PROPOSED,
    )
    supporting_evidence = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    engagement = relationship("Engagement", back_populates="hypotheses")
    evidence = relationship("HypothesisEvidence", back_populates="hypothesis")


class HypothesisEvidence(Base):
    """Many-to-many link between hypotheses and evidence with weight."""
    __tablename__ = "hypothesis_evidence"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    hypothesis_id = Column(UUID(as_uuid=True), ForeignKey("hypotheses.id"))
    evidence_item_id = Column(UUID(as_uuid=True), ForeignKey("evidence_items.id"))
    weight = Column(Numeric(3, 2), default=1.0)

    hypothesis = relationship("Hypothesis", back_populates="evidence")
    evidence_item = relationship("EvidenceItem", back_populates="hypothesis_evidence")


class Source(Base):
    """Source entity - research source with metadata."""
    __tablename__ = "sources"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    url = Column(String(2048), unique=True)
    title = Column(String(512))
    publisher = Column(String(255))
    author = Column(String(255))
    published_at = Column(DateTime(timezone=True))
    domain_authority = Column(Numeric(3, 2))
    content_hash = Column(String(64), nullable=False)
    scraped_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    evidence_items = relationship("EvidenceItem", back_populates="source")


class RecommendationStatus(str, PyEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    IMPLEMENTED = "implemented"
    REJECTED = "rejected"


class Recommendation(Base):
    """Recommendation entity - actionable outputs linked to evidence."""
    __tablename__ = "recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    engagement_id = Column(UUID(as_uuid=True), ForeignKey("engagements.id"))
    hypothesis_id = Column(UUID(as_uuid=True), ForeignKey("hypotheses.id"))
    title = Column(String(255), nullable=False)
    description = Column(Text)
    confidence = Column(Numeric(4, 2))
    status = Column(
        Enum(RecommendationStatus),
        nullable=False,
        default=RecommendationStatus.DRAFT,
    )
    supporting_evidence = Column(Text)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    updated_at = Column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    engagement = relationship("Engagement", back_populates="recommendations")


class DependencyEdge(Base):
    """Dependency edge - tracks relationships between entities."""
    __tablename__ = "dependency_edges"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    engagement_id = Column(UUID(as_uuid=True), ForeignKey("engagements.id"))
    source_type = Column(
        String(50),
        nullable=False,
        comment="assumption, hypothesis, recommendation, slide, video_scene",
    )
    source_id = Column(UUID(as_uuid=True), nullable=False)
    target_type = Column(String(50), nullable=False)
    target_id = Column(UUID(as_uuid=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint(
            "engagement_id",
            "source_type",
            "source_id",
            "target_type",
            "target_id",
            name="uq_dependency_edge",
        ),
        Index(
            "idx_dependency_source",
            "engagement_id",
            "source_type",
            "source_id",
        ),
    )

    engagement = relationship("Engagement", back_populates="dependency_edges")


# pgvector import with graceful fallback for non-PostgreSQL environments
try:
    from pgvector.sqlalchemy import Vector
except ImportError:
    # Fallback if pgvector is not installed
    class Vector:
        def __init__(self, *args, **kwargs):
            pass
