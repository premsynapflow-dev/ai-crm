"""Phase 2: complaint clustering, embeddings, revenue risk snapshots, copilot queries, user skills.

Revision ID: 20260603_03
Revises: 20260603_02
Create Date: 2026-06-03
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "20260603_03"
down_revision = "20260603_02"
branch_labels = None
depends_on = None


def _is_pg() -> bool:
    return op.get_bind().dialect.name == "postgresql"


def _uuid():
    return postgresql.UUID(as_uuid=True) if _is_pg() else sa.Uuid(as_uuid=True)


def _jsonb():
    return postgresql.JSONB(astext_type=sa.Text()) if _is_pg() else sa.JSON()


def _tables() -> set[str]:
    return set(sa.inspect(op.get_bind()).get_table_names())


def _columns(table: str) -> set[str]:
    return {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}


def upgrade() -> None:
    existing = _tables()

    # -- complaint_clusters: DBSCAN cluster metadata + Gemini summaries --
    if "complaint_clusters" not in existing:
        op.create_table(
            "complaint_clusters",
            sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "client_id", _uuid(),
                sa.ForeignKey("clients.id", ondelete="CASCADE"),
                nullable=False, index=True,
            ),
            sa.Column("cluster_label", sa.Integer, nullable=False),
            sa.Column("cluster_size", sa.Integer, nullable=False, server_default="0"),
            sa.Column("summary", sa.Text, nullable=True),
            sa.Column("top_category", sa.String(100), nullable=True),
            sa.Column("top_entities", _jsonb(), nullable=False, server_default="{}"),
            sa.Column("period_start", sa.Date, nullable=False),
            sa.Column("period_end", sa.Date, nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.create_index(
            "idx_complaint_clusters_client_period",
            "complaint_clusters",
            ["client_id", "period_start"],
        )

    # -- complaint_embeddings: vector embeddings for semantic clustering --
    if "complaint_embeddings" not in existing:
        if _is_pg():
            try:
                op.execute("CREATE EXTENSION IF NOT EXISTS vector")
                op.execute("""
                    CREATE TABLE complaint_embeddings (
                        complaint_id UUID PRIMARY KEY
                            REFERENCES complaints(id) ON DELETE CASCADE,
                        embedding vector(768),
                        model_version VARCHAR(50) DEFAULT 'text-embedding-004',
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    )
                """)
                # ivfflat index needs at least one row; create it non-fatally
                try:
                    op.execute("""
                        CREATE INDEX idx_complaint_embeddings_ivf
                        ON complaint_embeddings
                        USING ivfflat (embedding vector_cosine_ops)
                        WITH (lists = 100)
                    """)
                except Exception:
                    pass
            except Exception:
                # pgvector unavailable; fall back to TEXT storage
                op.create_table(
                    "complaint_embeddings",
                    sa.Column(
                        "complaint_id", _uuid(),
                        sa.ForeignKey("complaints.id", ondelete="CASCADE"),
                        primary_key=True,
                    ),
                    sa.Column("embedding", sa.Text, nullable=True),
                    sa.Column("model_version", sa.String(50), nullable=True,
                              server_default="text-embedding-004"),
                    sa.Column(
                        "created_at",
                        sa.DateTime(timezone=True),
                        server_default=sa.text("now()"),
                        nullable=False,
                    ),
                )
        else:
            # SQLite: store embeddings as JSON text
            op.create_table(
                "complaint_embeddings",
                sa.Column(
                    "complaint_id", _uuid(),
                    sa.ForeignKey("complaints.id", ondelete="CASCADE"),
                    primary_key=True,
                ),
                sa.Column("embedding", sa.Text, nullable=True),
                sa.Column("model_version", sa.String(50), nullable=True),
                sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            )

    # -- cluster_id FK on complaints --
    comp_cols = _columns("complaints")
    if "cluster_id" not in comp_cols:
        op.add_column(
            "complaints",
            sa.Column("cluster_id", _uuid(), nullable=True),
        )
        if _is_pg():
            try:
                op.create_foreign_key(
                    "fk_complaints_cluster_id",
                    "complaints", "complaint_clusters",
                    ["cluster_id"], ["id"],
                    ondelete="SET NULL",
                )
            except Exception:
                pass
        op.create_index("idx_complaints_cluster_id", "complaints", ["cluster_id"])

    # -- revenue_risk_snapshots: daily revenue-at-risk calculation --
    if "revenue_risk_snapshots" not in existing:
        op.create_table(
            "revenue_risk_snapshots",
            sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "client_id", _uuid(),
                sa.ForeignKey("clients.id", ondelete="CASCADE"),
                nullable=False, index=True,
            ),
            sa.Column("snapshot_date", sa.Date, nullable=False),
            sa.Column("revenue_at_risk", sa.Numeric(12, 2), nullable=True),
            sa.Column("high_risk_customer_count", sa.Integer, nullable=True),
            sa.Column("avg_churn_probability", sa.Float, nullable=True),
            sa.Column(
                "computed_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
            sa.UniqueConstraint("client_id", "snapshot_date", name="uq_revenue_risk_client_date"),
        )
        op.create_index(
            "idx_revenue_risk_client_date",
            "revenue_risk_snapshots",
            ["client_id", "snapshot_date"],
        )

    # -- copilot_queries: AI executive Q&A history --
    if "copilot_queries" not in existing:
        op.create_table(
            "copilot_queries",
            sa.Column("id", _uuid(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column(
                "client_id", _uuid(),
                sa.ForeignKey("clients.id", ondelete="CASCADE"),
                nullable=False, index=True,
            ),
            sa.Column(
                "user_id", _uuid(),
                sa.ForeignKey("client_users.id", ondelete="SET NULL"),
                nullable=True, index=True,
            ),
            sa.Column("query", sa.Text, nullable=False),
            sa.Column("response", sa.Text, nullable=True),
            sa.Column("context_used", _jsonb(), nullable=True),
            sa.Column("latency_ms", sa.Integer, nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("now()"),
                nullable=False,
            ),
        )
        op.create_index(
            "idx_copilot_queries_client_time",
            "copilot_queries",
            ["client_id", "created_at"],
        )

    # -- skills + display_name + is_active on client_users --
    user_cols = _columns("client_users")
    if "skills" not in user_cols:
        op.add_column(
            "client_users",
            sa.Column("skills", _jsonb(), nullable=False, server_default="[]"),
        )
    if "display_name" not in user_cols:
        op.add_column(
            "client_users",
            sa.Column("display_name", sa.String(255), nullable=True),
        )
    if "is_active" not in user_cols:
        op.add_column(
            "client_users",
            sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        )


def downgrade() -> None:
    existing = _tables()

    if "copilot_queries" in existing:
        op.drop_table("copilot_queries")

    if "revenue_risk_snapshots" in existing:
        op.drop_table("revenue_risk_snapshots")

    if "complaints" in existing:
        comp_cols = _columns("complaints")
        if "cluster_id" in comp_cols:
            try:
                op.drop_index("idx_complaints_cluster_id", "complaints")
            except Exception:
                pass
            if _is_pg():
                try:
                    op.drop_constraint("fk_complaints_cluster_id", "complaints", type_="foreignkey")
                except Exception:
                    pass
            op.drop_column("complaints", "cluster_id")

    if "complaint_embeddings" in existing:
        op.drop_table("complaint_embeddings")

    if "complaint_clusters" in existing:
        op.drop_table("complaint_clusters")

    if "client_users" in existing:
        user_cols = _columns("client_users")
        for col in ("skills", "display_name", "is_active"):
            if col in user_cols:
                op.drop_column("client_users", col)
