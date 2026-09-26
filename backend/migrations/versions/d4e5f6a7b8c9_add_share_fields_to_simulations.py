"""Add share_token, share_expires_at, lab_link_label to smile_simulations

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-11 01:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('smile_simulations', sa.Column('share_token', sa.String(255), nullable=True))
    op.add_column('smile_simulations', sa.Column('share_expires_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('smile_simulations', sa.Column('lab_link_label', sa.String(255), nullable=True))
    op.create_index('ix_smile_simulations_share_token', 'smile_simulations', ['share_token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_smile_simulations_share_token', table_name='smile_simulations')
    op.drop_column('smile_simulations', 'lab_link_label')
    op.drop_column('smile_simulations', 'share_expires_at')
    op.drop_column('smile_simulations', 'share_token')
