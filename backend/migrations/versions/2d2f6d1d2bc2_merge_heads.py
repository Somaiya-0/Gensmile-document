"""merge heads

Revision ID: 2d2f6d1d2bc2
Revises: f1a2b3c4d5e6, 78df8cf91b4f
Create Date: 2026-08-05 12:18:33.278823

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2d2f6d1d2bc2'
down_revision: Union[str, None] = ('f1a2b3c4d5e6', '78df8cf91b4f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
