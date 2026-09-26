"""merge_duplicate_heads

Revision ID: aa0751bd86f6
Revises: 0fd640e38242, 874b3054014e
Create Date: 2026-06-03 16:38:12.736678

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'aa0751bd86f6'
down_revision: Union[str, None] = ('0fd640e38242', '874b3054014e')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
