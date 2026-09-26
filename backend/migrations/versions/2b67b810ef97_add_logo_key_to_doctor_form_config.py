"""add logo_key to doctor form config

Revision ID: 2b67b810ef97
Revises: b3a7c1e9f2d4
Create Date: 2026-08-23 14:10:17.714077

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '2b67b810ef97'
down_revision: Union[str, None] = 'b3a7c1e9f2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'doctor_form_configs',
        sa.Column('logo_key', sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    op.drop_column('doctor_form_configs', 'logo_key')
