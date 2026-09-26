"""Add credits_expires_at and stripe_checkout_session_id to subscriptions

Revision ID: e4f2a1b8c9d0
Revises: bac0c495212c
Create Date: 2026-05-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'e4f2a1b8c9d0'
down_revision: Union[str, None] = 'bac0c495212c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'subscriptions',
        sa.Column('credits_expires_at', sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        'subscriptions',
        sa.Column('stripe_checkout_session_id', sa.String(200), nullable=True),
    )
    op.create_index(
        'ix_subscriptions_stripe_checkout_session_id',
        'subscriptions',
        ['stripe_checkout_session_id'],
    )


def downgrade() -> None:
    op.drop_index('ix_subscriptions_stripe_checkout_session_id', table_name='subscriptions')
    op.drop_column('subscriptions', 'stripe_checkout_session_id')
    op.drop_column('subscriptions', 'credits_expires_at')
