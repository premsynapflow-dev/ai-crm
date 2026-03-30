"""seed initial data

Revision ID: 20260330_01
Revises: 20260329_06
Create Date: 2026-03-30 00:00:00

"""

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "20260330_01"
down_revision = "20260329_06"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        text(
            """
            INSERT INTO rbi_complaint_categories (category_code, category_name, subcategory_code, subcategory_name, tat_days) VALUES
            ('ATM', 'ATM / Debit Card', 'ATM_FAIL', 'Failed Transaction', 30),
            ('ATM', 'ATM / Debit Card', 'ATM_CASH', 'Cash Not Dispensed', 30),
            ('CC', 'Credit Card', 'CC_UNAUTHORIZED', 'Unauthorized Transaction', 30),
            ('CC', 'Credit Card', 'CC_BILLING', 'Billing Dispute', 30),
            ('LOAN', 'Loans', 'LOAN_DISBURSEMENT', 'Delayed Disbursement', 30),
            ('LOAN', 'Loans', 'LOAN_INTEREST', 'Interest Rate Issue', 30),
            ('DEP', 'Deposits', 'DEP_INTEREST', 'Interest Not Credited', 30),
            ('NB', 'Net Banking', 'NB_ACCESS', 'Login Issue', 30),
            ('NB', 'Net Banking', 'NB_TXN', 'Transaction Failure', 30),
            ('MOBILE', 'Mobile Banking', 'MOBILE_APP', 'App Not Working', 30),
            ('BRANCH', 'Branch Banking', 'BRANCH_SERVICE', 'Poor Service', 30),
            ('OTHER', 'Others', 'OTHER', 'Other Complaints', 30)
            ON CONFLICT DO NOTHING
            """
        )
    )

    op.execute(
        text(
            """
            INSERT INTO plan_features (plan_name, features, limits) VALUES
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
    )


def downgrade() -> None:
    op.execute(
        text(
            """
            DELETE FROM plan_features
            WHERE plan_name IN ('starter', 'pro', 'max', 'scale', 'enterprise')
            """
        )
    )
    op.execute(
        text(
            """
            DELETE FROM rbi_complaint_categories
            WHERE (category_code, subcategory_code) IN (
                ('ATM', 'ATM_FAIL'),
                ('ATM', 'ATM_CASH'),
                ('CC', 'CC_UNAUTHORIZED'),
                ('CC', 'CC_BILLING'),
                ('LOAN', 'LOAN_DISBURSEMENT'),
                ('LOAN', 'LOAN_INTEREST'),
                ('DEP', 'DEP_INTEREST'),
                ('NB', 'NB_ACCESS'),
                ('NB', 'NB_TXN'),
                ('MOBILE', 'MOBILE_APP'),
                ('BRANCH', 'BRANCH_SERVICE'),
                ('OTHER', 'OTHER')
            )
            """
        )
    )
