"""Add patient fields and free_generation_used to lab_links

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-11 00:00:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('lab_links', sa.Column('patient_user_id', sa.Uuid(), nullable=True))
    op.add_column('lab_links', sa.Column('patient_name', sa.String(255), nullable=True))
    op.add_column('lab_links', sa.Column('patient_phone', sa.String(50), nullable=True))
    op.add_column('lab_links', sa.Column('free_generation_used', sa.Boolean(), nullable=False, server_default='false'))
    op.create_foreign_key('fk_lab_links_patient_user_id', 'lab_links', 'user_accounts', ['patient_user_id'], ['id'], ondelete='SET NULL')


def downgrade() -> None:
    op.drop_constraint('fk_lab_links_patient_user_id', 'lab_links', type_='foreignkey')
    op.drop_column('lab_links', 'patient_user_id')
    op.drop_column('lab_links', 'patient_name')
    op.drop_column('lab_links', 'patient_phone')
    op.drop_column('lab_links', 'free_generation_used')
