"""add custom_simulations to subscription

Revision ID: f9f0f3d10ab8
Revises: a2b3c4d5e6f7
Create Date: 2026-06-10 20:11:54.993381
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = 'f9f0f3d10ab8'
down_revision: Union[str, None] = 'a2b3c4d5e6f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "subscriptions",
        sa.Column("custom_simulations", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("subscriptions", "custom_simulations")
