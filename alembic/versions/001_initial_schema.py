"""Initial schema: core entities for StratOS.

Revision ID: 001_initial_schema
Revises:
Create Date: 2026-09-08 18:30:00.000000

Creates all 10 core tables:
- organizations
- engagements
- assumptions
- sources
- evidence_items
- hypotheses
- hypothesis_evidence (many-to-many)
- recommendations
- dependency_edges (with recursive CTE support)
"""

from alembic import op
import sqlalchemy as sa
import uuid

# revision identifiers
revision = "001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # organizations
    op.create_table(
        "organizations",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(255), unique=True, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # engagements
    op.create_table(
        "engagements",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("org_id", sa.UUID(as_uuid=True), sa.ForeignKey("organizations.id")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="discovery"),
        sa.Column("objective", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # assumptions
    op.create_table(
        "assumptions",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("engagement_id", sa.UUID(as_uuid=True), sa.ForeignKey("engagements.id")),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("value", sa.Text),
        sa.Column("criticality", sa.Text(), nullable=False, server_default="medium"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # sources
    op.create_table(
        "sources",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("url", sa.String(2048), unique=True),
        sa.Column("title", sa.String(512)),
        sa.Column("publisher", sa.String(255)),
        sa.Column("author", sa.String(255)),
        sa.Column("published_at", sa.DateTime(timezone=True)),
        sa.Column("domain_authority", sa.Numeric(3, 2)),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("scraped_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # evidence_items
    op.create_table(
        "evidence_items",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("engagement_id", sa.UUID(as_uuid=True), sa.ForeignKey("engagements.id")),
        sa.Column("source_id", sa.UUID(as_uuid=True), sa.ForeignKey("sources.id")),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("content_type", sa.Text(), nullable=False, server_default="text"),
        sa.Column("content_json", sa.Text),
        sa.Column("chunk_index", sa.Integer),
        sa.Column("embedding", sa.Text),  # VECTOR(1536) in Postgres, TEXT in SQLite
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # hypotheses
    op.create_table(
        "hypotheses",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("engagement_id", sa.UUID(as_uuid=True), sa.ForeignKey("engagements.id")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("confidence", sa.Numeric(4, 2)),
        sa.Column("status", sa.Text(), nullable=False, server_default="proposed"),
        sa.Column("supporting_evidence", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # hypothesis_evidence (many-to-many)
    op.create_table(
        "hypothesis_evidence",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("hypothesis_id", sa.UUID(as_uuid=True), sa.ForeignKey("hypotheses.id")),
        sa.Column("evidence_item_id", sa.UUID(as_uuid=True), sa.ForeignKey("evidence_items.id")),
        sa.Column("weight", sa.Numeric(3, 2), server_default="1.0"),
    )

    # recommendations
    op.create_table(
        "recommendations",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("engagement_id", sa.UUID(as_uuid=True), sa.ForeignKey("engagements.id")),
        sa.Column("hypothesis_id", sa.UUID(as_uuid=True), sa.ForeignKey("hypotheses.id")),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("confidence", sa.Numeric(4, 2)),
        sa.Column("status", sa.Text(), nullable=False, server_default="draft"),
        sa.Column("supporting_evidence", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # dependency_edges
    op.create_table(
        "dependency_edges",
        sa.Column("id", sa.UUID(as_uuid=True), primary_key=True, default=uuid.uuid4),
        sa.Column("engagement_id", sa.UUID(as_uuid=True), sa.ForeignKey("engagements.id")),
        sa.Column("source_type", sa.String(50), nullable=False),
        sa.Column("source_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("target_type", sa.String(50), nullable=False),
        sa.Column("target_id", sa.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint(
            "engagement_id", "source_type", "source_id",
            "target_type", "target_id",
            name="uq_dependency_edge",
        ),
    )

    # Indexes for graph traversal performance
    op.create_index(
        "idx_dependency_source",
        "dependency_edges",
        ["engagement_id", "source_type", "source_id"],
    )
    op.create_index(
        "idx_dependency_target",
        "dependency_edges",
        ["engagement_id", "target_type", "target_id"],
    )


def downgrade():
    op.drop_index("idx_dependency_source", table_name="dependency_edges")
    op.drop_index("idx_dependency_target", table_name="dependency_edges")
    op.drop_table("dependency_edges")
    op.drop_table("recommendations")
    op.drop_table("hypothesis_evidence")
    op.drop_table("hypotheses")
    op.drop_table("evidence_items")
    op.drop_table("sources")
    op.drop_table("assumptions")
    op.drop_table("engagements")
    op.drop_table("organizations")
