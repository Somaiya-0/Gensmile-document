"""Allow multiple embed_links per doctor (drop unique constraint)

Revision ID: 44afe21bf535
Revises: 05a16574bb32
Create Date: 2026-08-05 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op


revision: str = '44afe21bf535'
down_revision: Union[str, None] = '05a16574bb32'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint('embed_links_doctor_profile_id_key', 'embed_links', type_='unique')
    op.drop_index('ix_embed_links_doctor_profile_id', table_name='embed_links')
    op.create_index(
        op.f('ix_embed_links_doctor_profile_id'), 'embed_links', ['doctor_profile_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_embed_links_doctor_profile_id'), table_name='embed_links')
    op.create_index(
        'ix_embed_links_doctor_profile_id', 'embed_links', ['doctor_profile_id'], unique=True
    )
    op.create_unique_constraint('embed_links_doctor_profile_id_key', 'embed_links', ['doctor_profile_id'])
