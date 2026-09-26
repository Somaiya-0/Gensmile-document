"""add patient document change logs

Revision ID: a1c2e3f4b5d6
Revises: ece61f51e707
Create Date: 2026-09-26 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1c2e3f4b5d6'
down_revision: Union[str, None] = 'ece61f51e707'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'patient_document_change_logs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('document_id', sa.Uuid(), nullable=False),
        sa.Column('changed_by_user_id', sa.Uuid(), nullable=True),
        sa.Column('changed_by_name', sa.String(length=255), nullable=False),
        sa.Column('change_type', sa.String(length=20), nullable=False),
        sa.Column('field_key', sa.String(length=150), nullable=True),
        sa.Column('field_label', sa.String(length=255), nullable=False),
        sa.Column('old_value', sa.Text(), nullable=True),
        sa.Column('new_value', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['patient_documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['changed_by_user_id'], ['user_accounts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_patient_document_change_logs_document_id'),
        'patient_document_change_logs', ['document_id'], unique=False,
    )
    op.create_index(
        op.f('ix_patient_document_change_logs_created_at'),
        'patient_document_change_logs', ['created_at'], unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_patient_document_change_logs_created_at'), table_name='patient_document_change_logs')
    op.drop_index(op.f('ix_patient_document_change_logs_document_id'), table_name='patient_document_change_logs')
    op.drop_table('patient_document_change_logs')
