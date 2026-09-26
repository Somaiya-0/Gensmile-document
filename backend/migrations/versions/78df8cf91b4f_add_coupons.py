"""Add coupons and coupon_redemptions tables

Revision ID: 78df8cf91b4f
Revises: fea1608e2b58
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '78df8cf91b4f'
down_revision: Union[str, None] = 'fea1608e2b58'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'coupons',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('code', sa.String(length=40), nullable=False),
        sa.Column('bonus_credits', sa.Integer(), nullable=False),
        sa.Column('bonus_days', sa.Integer(), nullable=False),
        sa.Column('max_redemptions', sa.Integer(), nullable=True),
        sa.Column('redemptions_count', sa.Integer(), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('active', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_coupons_code'), 'coupons', ['code'], unique=True)

    op.create_table(
        'coupon_redemptions',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('coupon_id', sa.Uuid(), nullable=False),
        sa.Column('user_id', sa.Uuid(), nullable=False),
        sa.Column('external_transaction_id', sa.String(length=200), nullable=True),
        sa.Column('redeemed_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['coupon_id'], ['coupons.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user_accounts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('coupon_id', 'user_id', name='uq_coupon_user'),
    )
    op.create_index(
        op.f('ix_coupon_redemptions_coupon_id'), 'coupon_redemptions', ['coupon_id'], unique=False
    )
    op.create_index(
        op.f('ix_coupon_redemptions_user_id'), 'coupon_redemptions', ['user_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_coupon_redemptions_user_id'), table_name='coupon_redemptions')
    op.drop_index(op.f('ix_coupon_redemptions_coupon_id'), table_name='coupon_redemptions')
    op.drop_table('coupon_redemptions')
    op.drop_index(op.f('ix_coupons_code'), table_name='coupons')
    op.drop_table('coupons')
