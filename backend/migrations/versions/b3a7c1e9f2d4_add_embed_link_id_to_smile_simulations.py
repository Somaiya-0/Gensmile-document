"""Add embed_link_id to smile_simulations

Revision ID: b3a7c1e9f2d4
Revises: 9f1c2d3e4a5b
Create Date: 2026-08-21 08:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3a7c1e9f2d4'
down_revision: Union[str, None] = '9f1c2d3e4a5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('smile_simulations', sa.Column('embed_link_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_smile_simulations_embed_link_id'), 'smile_simulations', ['embed_link_id'], unique=False)
    op.create_foreign_key(
        'smile_simulations_embed_link_id_fkey',
        'smile_simulations', 'embed_links',
        ['embed_link_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('smile_simulations_embed_link_id_fkey', 'smile_simulations', type_='foreignkey')
    op.drop_index(op.f('ix_smile_simulations_embed_link_id'), table_name='smile_simulations')
    op.drop_column('smile_simulations', 'embed_link_id')
