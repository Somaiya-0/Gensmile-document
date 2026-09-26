"""add_description_and_is_active_to_clinics

Revision ID: a2b3c4d5e6f7
Revises: 3f4c30963427
Create Date: 2026-06-04 11:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a2b3c4d5e6f7'
down_revision: Union[str, None] = '3f4c30963427'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('clinics', sa.Column('description', sa.Text(), nullable=True))
    op.add_column('clinics', sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    op.drop_column('clinics', 'is_active')
    op.drop_column('clinics', 'description')
