"""add auto reply approval queue

Revision ID: 20260329_04
Revises: 20260329_03
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260329_04"
down_revision = "20260329_03"
branch_labels = None
depends_on = None


def _index_names(inspector, table_name: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "reply_templates" not in tables:
        op.create_table(
            "reply_templates",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id", ondelete="CASCADE"), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("category", sa.String(length=50), nullable=True),
            sa.Column("template_body", sa.Text(), nullable=False),
            sa.Column("variables", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'[]'::jsonb")),
            sa.Column("usage_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("avg_satisfaction", sa.Float(), nullable=True),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.UniqueConstraint("client_id", "name", name="unique_client_template"),
        )
        op.create_index(
            "idx_templates_client_category",
            "reply_templates",
            ["client_id", "category"],
            postgresql_where=sa.text("enabled = true"),
        )

    if "ai_reply_queue" not in tables:
        op.create_table(
            "ai_reply_queue",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("complaint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("complaints.id", ondelete="CASCADE"), nullable=False),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("generated_reply", sa.Text(), nullable=False),
            sa.Column("confidence_score", sa.Float(), nullable=False),
            sa.Column("generation_strategy", sa.String(length=50), nullable=True),
            sa.Column("generation_metadata", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("status", sa.String(length=50), nullable=False, server_default=sa.text("'pending'")),
            sa.Column("reviewed_by", sa.String(length=255), nullable=True),
            sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("edited_reply", sa.Text(), nullable=True),
            sa.Column("rejection_reason", sa.Text(), nullable=True),
            sa.Column("hallucination_check_passed", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("toxicity_score", sa.Float(), nullable=False, server_default=sa.text("0.0")),
            sa.Column("factual_consistency_score", sa.Float(), nullable=False, server_default=sa.text("0.8")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.UniqueConstraint("complaint_id", name="unique_complaint_queue"),
            sa.CheckConstraint("confidence_score >= 0 AND confidence_score <= 1", name="ck_ai_reply_queue_confidence"),
        )
        op.create_index("idx_reply_queue_status", "ai_reply_queue", ["client_id", "status", "created_at"])
        op.create_index("idx_reply_queue_confidence", "ai_reply_queue", ["client_id", "confidence_score"])
        op.create_index(
            "idx_reply_queue_pending",
            "ai_reply_queue",
            ["client_id", "created_at"],
            postgresql_where=sa.text("status = 'pending'"),
        )

    if "reply_feedback" not in tables:
        op.create_table(
            "reply_feedback",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("complaint_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("complaints.id"), nullable=False),
            sa.Column("reply_queue_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("ai_reply_queue.id"), nullable=True),
            sa.Column("customer_responded", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("customer_response_sentiment", sa.Float(), nullable=True),
            sa.Column("ticket_reopened", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("escalated_after_reply", sa.Boolean(), nullable=False, server_default=sa.text("false")),
            sa.Column("satisfaction_score", sa.Integer(), nullable=True),
            sa.Column("time_to_customer_response_seconds", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.UniqueConstraint("complaint_id", name="unique_complaint_feedback"),
            sa.CheckConstraint("satisfaction_score BETWEEN 1 AND 5", name="ck_reply_feedback_satisfaction"),
        )
        op.create_index("idx_feedback_queue", "reply_feedback", ["reply_queue_id"])

    if "reply_ab_tests" not in tables:
        op.create_table(
            "reply_ab_tests",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("test_name", sa.String(length=100), nullable=False),
            sa.Column("variant_a_strategy", sa.String(length=100), nullable=True),
            sa.Column("variant_b_strategy", sa.String(length=100), nullable=True),
            sa.Column("traffic_split", sa.Float(), nullable=False, server_default=sa.text("0.5")),
            sa.Column("status", sa.String(length=20), nullable=False, server_default=sa.text("'active'")),
            sa.Column("start_date", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("end_date", sa.DateTime(timezone=True), nullable=True),
            sa.Column("winner", sa.String(length=10), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.CheckConstraint("traffic_split >= 0 AND traffic_split <= 1", name="ck_reply_ab_tests_traffic_split"),
        )

    if "reply_quality_metrics" not in tables:
        op.create_table(
            "reply_quality_metrics",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("total_replies_generated", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("auto_approved_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("human_approved_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("rejected_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("avg_confidence_score", sa.Float(), nullable=True),
            sa.Column("avg_satisfaction_score", sa.Float(), nullable=True),
            sa.Column("hallucination_rate", sa.Float(), nullable=True),
            sa.Column("reopened_rate", sa.Float(), nullable=True),
            sa.Column("escalation_rate", sa.Float(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.UniqueConstraint("client_id", "period_start", "period_end", name="unique_client_period"),
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "reply_quality_metrics" in tables:
        op.drop_table("reply_quality_metrics")
    if "reply_ab_tests" in tables:
        op.drop_table("reply_ab_tests")
    if "reply_feedback" in tables:
        indexes = _index_names(inspector, "reply_feedback")
        if "idx_feedback_queue" in indexes:
            op.drop_index("idx_feedback_queue", table_name="reply_feedback")
        op.drop_table("reply_feedback")
    if "ai_reply_queue" in tables:
        indexes = _index_names(inspector, "ai_reply_queue")
        for index_name in ["idx_reply_queue_pending", "idx_reply_queue_confidence", "idx_reply_queue_status"]:
            if index_name in indexes:
                op.drop_index(index_name, table_name="ai_reply_queue")
        op.drop_table("ai_reply_queue")
    if "reply_templates" in tables:
        indexes = _index_names(inspector, "reply_templates")
        if "idx_templates_client_category" in indexes:
            op.drop_index("idx_templates_client_category", table_name="reply_templates")
        op.drop_table("reply_templates")
