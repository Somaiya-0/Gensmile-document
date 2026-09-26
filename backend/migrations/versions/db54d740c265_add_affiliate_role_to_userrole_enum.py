"""add affiliate role to userrole enum

Revision ID: db54d740c265
Revises: 02b8ba0cbb9f
Create Date: 2026-07-23 19:51:28.592482

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'db54d740c265'
down_revision: Union[str, None] = '02b8ba0cbb9f'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'affiliate'")


def downgrade() -> None:
    pass  # Postgres can't remove enum values directly
