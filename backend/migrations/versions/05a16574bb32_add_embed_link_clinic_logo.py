"""Add clinic_logo_name to embed_links

Revision ID: 05a16574bb32
Revises: 6b7fa53e3b0e
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '05a16574bb32'
down_revision: Union[str, None] = '6b7fa53e3b0e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('embed_links', sa.Column('clinic_logo_name', sa.String(length=500), nullable=True))


def downgrade() -> None:
    op.drop_column('embed_links', 'clinic_logo_name')
