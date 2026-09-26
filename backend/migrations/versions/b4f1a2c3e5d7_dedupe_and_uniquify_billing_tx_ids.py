"""dedupe and uniquify billing_transactions payment/external ids

The webhook (Stripe/Apple server push) and the client-confirm path
(activate_from_session / verify_and_grant_transaction) both check
"does a row with this id already exist" then insert if not. Without a
DB-level unique constraint, a race between the two let both sides pass
the check before either committed, inserting the same purchase twice
and inflating total_revenue.

This migration removes existing duplicates (keeping the earliest row per
id) and adds the missing unique constraints so a repeat of that race
fails atomically instead of double-inserting.

Revision ID: b4f1a2c3e5d7
Revises: f4a8b3c2d1e0
Create Date: 2026-09-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b4f1a2c3e5d7'
down_revision: Union[str, None] = 'f4a8b3c2d1e0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("""
        DELETE FROM billing_transactions
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY stripe_payment_intent_id
                    ORDER BY created_at ASC, id ASC
                ) AS rn
                FROM billing_transactions
                WHERE stripe_payment_intent_id IS NOT NULL
            ) ranked
            WHERE rn > 1
        )
    """)
    op.execute("""
        DELETE FROM billing_transactions
        WHERE id IN (
            SELECT id FROM (
                SELECT id, ROW_NUMBER() OVER (
                    PARTITION BY external_transaction_id
                    ORDER BY created_at ASC, id ASC
                ) AS rn
                FROM billing_transactions
                WHERE external_transaction_id IS NOT NULL
            ) ranked
            WHERE rn > 1
        )
    """)

    op.drop_index('ix_billing_transactions_stripe_payment_intent_id', table_name='billing_transactions')
    op.create_index(
        op.f('ix_billing_transactions_stripe_payment_intent_id'),
        'billing_transactions', ['stripe_payment_intent_id'], unique=True,
    )
    op.drop_index('ix_billing_transactions_external_transaction_id', table_name='billing_transactions')
    op.create_index(
        op.f('ix_billing_transactions_external_transaction_id'),
        'billing_transactions', ['external_transaction_id'], unique=True,
    )


def downgrade() -> None:
    # Deleted duplicate rows are not restored.
    op.drop_index(op.f('ix_billing_transactions_stripe_payment_intent_id'), table_name='billing_transactions')
    op.create_index(
        op.f('ix_billing_transactions_stripe_payment_intent_id'),
        'billing_transactions', ['stripe_payment_intent_id'], unique=False,
    )
    op.drop_index(op.f('ix_billing_transactions_external_transaction_id'), table_name='billing_transactions')
    op.create_index(
        op.f('ix_billing_transactions_external_transaction_id'),
        'billing_transactions', ['external_transaction_id'], unique=False,
    )
