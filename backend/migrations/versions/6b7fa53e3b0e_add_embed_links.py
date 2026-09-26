"""Add embed_links table

Revision ID: 6b7fa53e3b0e
Revises: 21d3a9979721
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '6b7fa53e3b0e'
down_revision: Union[str, None] = '21d3a9979721'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'embed_links',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('doctor_profile_id', sa.Uuid(), nullable=False),
        sa.Column('token', sa.String(length=128), nullable=False),
        sa.Column('clinic_id', sa.Uuid(), nullable=True),
        sa.Column('clinic_name', sa.String(length=255), nullable=False),
        sa.Column('clinic_description', sa.Text(), nullable=True),
        sa.Column('clinic_address', sa.Text(), nullable=True),
        sa.Column('clinic_phone', sa.String(length=50), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('daily_generation_limit', sa.Integer(), nullable=False),
        sa.Column('generations_today', sa.Integer(), nullable=False),
        sa.Column('generations_reset_date', sa.Date(), nullable=False),
        sa.Column('total_generations', sa.Integer(), nullable=False),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['doctor_profile_id'], ['doctor_profiles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['clinic_id'], ['clinics.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('doctor_profile_id'),
        sa.UniqueConstraint('token'),
    )
    op.create_index(op.f('ix_embed_links_doctor_profile_id'), 'embed_links', ['doctor_profile_id'], unique=True)
    op.create_index(op.f('ix_embed_links_token'), 'embed_links', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_embed_links_token'), table_name='embed_links')
    op.drop_index(op.f('ix_embed_links_doctor_profile_id'), table_name='embed_links')
    op.drop_table('embed_links')
