"""add multi tenant rls

Revision ID: 20260329_06
Revises: 20260329_05
Create Date: 2026-03-29
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260329_06"
down_revision = "20260329_05"
branch_labels = None
depends_on = None


def _table_names(inspector) -> set[str]:
    return set(inspector.get_table_names())


def _enable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} ENABLE ROW LEVEL SECURITY")


def _disable_rls(table_name: str) -> None:
    op.execute(f"ALTER TABLE {table_name} DISABLE ROW LEVEL SECURITY")


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if "plan_features" not in tables:
        op.create_table(
            "plan_features",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("plan_name", sa.String(length=50), nullable=False),
            sa.Column("features", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("limits", postgresql.JSONB(astext_type=sa.Text()), nullable=False, server_default=sa.text("'{}'::jsonb")),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.UniqueConstraint("plan_name", name="unique_plan_features_plan_name"),
        )

    if "tenant_usage_tracking" not in tables:
        op.create_table(
            "tenant_usage_tracking",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
            sa.Column("client_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("clients.id"), nullable=False),
            sa.Column("resource_type", sa.String(length=50), nullable=False),
            sa.Column("usage_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
            sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("NOW()")),
            sa.UniqueConstraint("client_id", "resource_type", "period_start", name="unique_client_resource_period"),
        )
        op.create_index("idx_usage_tracking_client", "tenant_usage_tracking", ["client_id", "period_start"])

    op.execute(
        """
        INSERT INTO plan_features (plan_name, features, limits)
        VALUES
            (
                'starter',
                '{"ticketing_state_machine": true, "sla_management": false, "customer_360": false, "auto_reply_approval_queue": true, "rbi_compliance": false, "auto_escalation": false}'::jsonb,
                '{"tickets_per_month": 500, "api_calls_per_day": 1000, "users": 3}'::jsonb
            ),
            (
                'pro',
                '{"ticketing_state_machine": true, "sla_management": true, "customer_360": true, "auto_reply_approval_queue": true, "rbi_compliance": true, "auto_escalation": false}'::jsonb,
                '{"tickets_per_month": 2000, "api_calls_per_day": 10000, "users": 10}'::jsonb
            ),
            (
                'max',
                '{"ticketing_state_machine": true, "sla_management": true, "customer_360": true, "auto_reply_approval_queue": true, "rbi_compliance": true, "auto_escalation": false}'::jsonb,
                '{"tickets_per_month": 10000, "api_calls_per_day": 50000, "users": 25}'::jsonb
            ),
            (
                'scale',
                '{"ticketing_state_machine": true, "sla_management": true, "customer_360": true, "auto_reply_approval_queue": true, "rbi_compliance": true, "auto_escalation": false}'::jsonb,
                '{"tickets_per_month": 100000, "api_calls_per_day": 250000, "users": 100}'::jsonb
            ),
            (
                'enterprise',
                '{"ticketing_state_machine": true, "sla_management": true, "customer_360": true, "auto_reply_approval_queue": true, "rbi_compliance": true, "auto_escalation": true}'::jsonb,
                '{"tickets_per_month": -1, "api_calls_per_day": -1, "users": -1}'::jsonb
            )
        ON CONFLICT (plan_name) DO UPDATE
        SET features = EXCLUDED.features,
            limits = EXCLUDED.limits,
            updated_at = NOW()
        """
    )

    if bind.dialect.name.startswith("postgresql"):
        if "complaints" in tables:
            _enable_rls("complaints")
            op.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_policies
                        WHERE schemaname = current_schema()
                          AND tablename = 'complaints'
                          AND policyname = 'complaints_tenant_isolation_policy'
                    ) THEN
                        CREATE POLICY complaints_tenant_isolation_policy ON complaints
                            FOR ALL
                            USING (client_id::text = current_setting('app.current_client_id', true))
                            WITH CHECK (client_id::text = current_setting('app.current_client_id', true));
                    END IF;
                END $$;
                """
            )

        if "customers" in tables:
            _enable_rls("customers")
            op.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_policies
                        WHERE schemaname = current_schema()
                          AND tablename = 'customers'
                          AND policyname = 'customers_tenant_isolation_policy'
                    ) THEN
                        CREATE POLICY customers_tenant_isolation_policy ON customers
                            FOR ALL
                            USING (client_id::text = current_setting('app.current_client_id', true))
                            WITH CHECK (client_id::text = current_setting('app.current_client_id', true));
                    END IF;
                END $$;
                """
            )

        if "ticket_comments" in tables:
            _enable_rls("ticket_comments")
            op.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_policies
                        WHERE schemaname = current_schema()
                          AND tablename = 'ticket_comments'
                          AND policyname = 'ticket_comments_tenant_isolation_policy'
                    ) THEN
                        CREATE POLICY ticket_comments_tenant_isolation_policy ON ticket_comments
                            FOR ALL
                            USING (
                                EXISTS (
                                    SELECT 1
                                    FROM complaints
                                    WHERE complaints.id = ticket_comments.complaint_id
                                      AND complaints.client_id::text = current_setting('app.current_client_id', true)
                                )
                            )
                            WITH CHECK (
                                EXISTS (
                                    SELECT 1
                                    FROM complaints
                                    WHERE complaints.id = ticket_comments.complaint_id
                                      AND complaints.client_id::text = current_setting('app.current_client_id', true)
                                )
                            );
                    END IF;
                END $$;
                """
            )

        if "ai_reply_queue" in tables:
            _enable_rls("ai_reply_queue")
            op.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_policies
                        WHERE schemaname = current_schema()
                          AND tablename = 'ai_reply_queue'
                          AND policyname = 'ai_reply_queue_tenant_isolation_policy'
                    ) THEN
                        CREATE POLICY ai_reply_queue_tenant_isolation_policy ON ai_reply_queue
                            FOR ALL
                            USING (client_id::text = current_setting('app.current_client_id', true))
                            WITH CHECK (client_id::text = current_setting('app.current_client_id', true));
                    END IF;
                END $$;
                """
            )

        if "rbi_complaints" in tables:
            _enable_rls("rbi_complaints")
            op.execute(
                """
                DO $$
                BEGIN
                    IF NOT EXISTS (
                        SELECT 1 FROM pg_policies
                        WHERE schemaname = current_schema()
                          AND tablename = 'rbi_complaints'
                          AND policyname = 'rbi_complaints_tenant_isolation_policy'
                    ) THEN
                        CREATE POLICY rbi_complaints_tenant_isolation_policy ON rbi_complaints
                            FOR ALL
                            USING (client_id::text = current_setting('app.current_client_id', true))
                            WITH CHECK (client_id::text = current_setting('app.current_client_id', true));
                    END IF;
                END $$;
                """
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = _table_names(inspector)

    if bind.dialect.name.startswith("postgresql"):
        if "rbi_complaints" in tables:
            op.execute("DROP POLICY IF EXISTS rbi_complaints_tenant_isolation_policy ON rbi_complaints")
            _disable_rls("rbi_complaints")
        if "ai_reply_queue" in tables:
            op.execute("DROP POLICY IF EXISTS ai_reply_queue_tenant_isolation_policy ON ai_reply_queue")
            _disable_rls("ai_reply_queue")
        if "ticket_comments" in tables:
            op.execute("DROP POLICY IF EXISTS ticket_comments_tenant_isolation_policy ON ticket_comments")
            _disable_rls("ticket_comments")
        if "customers" in tables:
            op.execute("DROP POLICY IF EXISTS customers_tenant_isolation_policy ON customers")
            _disable_rls("customers")
        if "complaints" in tables:
            op.execute("DROP POLICY IF EXISTS complaints_tenant_isolation_policy ON complaints")
            _disable_rls("complaints")

    if "tenant_usage_tracking" in tables:
        op.drop_index("idx_usage_tracking_client", table_name="tenant_usage_tracking")
        op.drop_table("tenant_usage_tracking")
    if "plan_features" in tables:
        op.drop_table("plan_features")
