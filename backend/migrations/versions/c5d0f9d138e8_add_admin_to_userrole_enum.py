"""add ADMIN to userrole enum

Revision ID: c5d0f9d138e8
Revises: 44afe21bf535
Create Date: 2026-08-07 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c5d0f9d138e8'
down_revision: Union[str, None] = '44afe21bf535'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'ADMIN'")


def downgrade() -> None:
    pass  # Postgres can't remove enum values directly
