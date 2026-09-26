"""Add affiliation and license_number to doctor_profiles

Revision ID: f3a9c2d1e8b7
Revises: e4f2a1b8c9d0
Create Date: 2026-05-09 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f3a9c2d1e8b7'
down_revision: Union[str, None] = 'e4f2a1b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'doctor_profiles',
        sa.Column('affiliation', sa.String(500), nullable=True),
    )
    op.add_column(
        'doctor_profiles',
        sa.Column('license_number', sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('doctor_profiles', 'license_number')
    op.drop_column('doctor_profiles', 'affiliation')
