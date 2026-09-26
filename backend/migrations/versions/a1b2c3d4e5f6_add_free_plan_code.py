"""Add free plan code to plancode enum and update default subscription plan

Revision ID: a1b2c3d4e5f6
Revises: e4f2a1b8c9d0
Create Date: 2026-05-10 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = 'e4f2a1b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'free' value to the plancode enum (PostgreSQL supports IF NOT EXISTS)
    op.execute("ALTER TYPE plancode ADD VALUE IF NOT EXISTS 'free'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values — downgrade is a no-op
    pass
