"""add uppercase AFFILIATE to userrole enum

Revision ID: fea1608e2b58
Revises: db54d740c265
Create Date: 2026-07-23 19:59:00.308590

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'fea1608e2b58'
down_revision: Union[str, None] = 'db54d740c265'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TYPE userrole ADD VALUE IF NOT EXISTS 'AFFILIATE'")


def downgrade() -> None:
    pass  # Postgres can't remove enum values directly
