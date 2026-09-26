"""add video_generating_since to smile_simulations

Revision ID: f4a8b3c2d1e0
Revises: 2b67b810ef97
Create Date: 2026-08-25 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f4a8b3c2d1e0'
down_revision: Union[str, None] = '2b67b810ef97'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('smile_simulations', sa.Column('video_generating_since', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column('smile_simulations', 'video_generating_since')
