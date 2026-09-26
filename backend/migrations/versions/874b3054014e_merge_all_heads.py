"""merge_all_heads

Revision ID: 874b3054014e
Revises: 2f4bd20eb42a, e5f6a7b8c9d0, f3a9c2d1e8b7
Create Date: 2026-06-03 22:19:47.872403

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '874b3054014e'
down_revision: Union[str, None] = ('2f4bd20eb42a', 'e5f6a7b8c9d0', 'f3a9c2d1e8b7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
