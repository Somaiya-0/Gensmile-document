"""add CUSTOM value to plancode enum

Revision ID: b7c8d9e0f1a2
Revises: f9f0f3d10ab8
Create Date: 2026-07-24 00:00:00.000000

The PlanCode.CUSTOM member was added to app/models/enums.py without ever
adding a matching 'CUSTOM' label to the Postgres plancode enum type, so
persisting a Custom-plan subscription/onboarding session was never actually
possible at the DB level. This adds the missing label; a following migration
(b8d9e0f1a2b3) migrates any existing rows.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c8d9e0f1a2'
down_revision: Union[str, None] = 'f9f0f3d10ab8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add 'CUSTOM' value to the plancode enum (PostgreSQL supports IF NOT EXISTS).
    # Matches the uppercase-name convention already used for STARTER/PROFESSIONAL/ENTERPRISE.
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE plancode ADD VALUE IF NOT EXISTS 'CUSTOM'")


def downgrade() -> None:
    # PostgreSQL does not support removing enum values — downgrade is a no-op
    pass
