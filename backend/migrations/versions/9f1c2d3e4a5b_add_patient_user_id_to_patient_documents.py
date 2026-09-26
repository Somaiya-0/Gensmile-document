"""Add patient_user_id to patient_documents

Revision ID: 9f1c2d3e4a5b
Revises: 78724b43b5de
Create Date: 2026-08-20 22:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '9f1c2d3e4a5b'
down_revision: Union[str, None] = '78724b43b5de'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('patient_documents', sa.Column('patient_user_id', sa.Uuid(), nullable=True))
    op.create_index(op.f('ix_patient_documents_patient_user_id'), 'patient_documents', ['patient_user_id'], unique=False)
    op.create_foreign_key(
        'patient_documents_patient_user_id_fkey',
        'patient_documents', 'user_accounts',
        ['patient_user_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('patient_documents_patient_user_id_fkey', 'patient_documents', type_='foreignkey')
    op.drop_index(op.f('ix_patient_documents_patient_user_id'), table_name='patient_documents')
    op.drop_column('patient_documents', 'patient_user_id')
