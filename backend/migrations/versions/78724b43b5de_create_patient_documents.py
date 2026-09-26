"""create patient documents, patient document files, and doctor form configs

Revision ID: 78724b43b5de
Revises: c5d0f9d138e8
Create Date: 2026-08-20 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = '78724b43b5de'
down_revision: Union[str, None] = 'c5d0f9d138e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'patient_documents',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('doctor_profile_id', sa.Uuid(), nullable=False),
        sa.Column('patient_name', sa.String(length=255), nullable=False),
        sa.Column('patient_email', sa.String(length=255), nullable=True),
        sa.Column('patient_phone', sa.String(length=50), nullable=True),
        sa.Column('visit_date', sa.DateTime(timezone=True), nullable=True),
        sa.Column('chief_concern', sa.Text(), nullable=True),
        sa.Column('last_dds_visit', sa.String(length=255), nullable=True),
        sa.Column('cbct_taken', sa.Boolean(), nullable=True),
        sa.Column('req_radiologist', sa.String(length=255), nullable=True),
        sa.Column('exam_salivary_ph', sa.String(length=50), nullable=True),
        sa.Column('recommend_salivary_test', sa.Boolean(), nullable=True),
        sa.Column('cbct_notes', sa.Text(), nullable=True),
        sa.Column('third_molar_ll', sa.Text(), nullable=True),
        sa.Column('third_molar_lr', sa.Text(), nullable=True),
        sa.Column('third_molar_ul', sa.Text(), nullable=True),
        sa.Column('third_molar_ur', sa.Text(), nullable=True),
        sa.Column('cavitations', sa.Text(), nullable=True),
        sa.Column('third_molar_recommendations', sa.Text(), nullable=True),
        sa.Column('sinus_ul', sa.Text(), nullable=True),
        sa.Column('sinus_ur', sa.Text(), nullable=True),
        sa.Column('existing_rcts', sa.Text(), nullable=True),
        sa.Column('any_into_sinus', sa.Boolean(), nullable=True),
        sa.Column('sinus_recommendations', sa.Text(), nullable=True),
        sa.Column('periodontal_condition', sa.Text(), nullable=True),
        sa.Column('tx_recommendations', sa.Text(), nullable=True),
        sa.Column('md_referral', sa.Boolean(), nullable=True),
        sa.Column('blood_test', sa.Boolean(), nullable=True),
        sa.Column('occlusion', sa.Text(), nullable=True),
        sa.Column('guidance', sa.Text(), nullable=True),
        sa.Column('occlusion_recommendations', sa.Text(), nullable=True),
        sa.Column('custom_fields', sa.JSON(), nullable=False),
        sa.Column('form_config', sa.JSON(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('logo_key', sa.String(length=500), nullable=True),
        sa.Column('share_token', sa.String(length=128), nullable=False),
        sa.Column('is_shared', sa.Boolean(), nullable=False),
        sa.Column('fill_token', sa.String(length=128), nullable=False),
        sa.Column('fill_enabled', sa.Boolean(), nullable=False),
        sa.Column('patient_submitted_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['doctor_profile_id'], ['doctor_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('share_token'),
        sa.UniqueConstraint('fill_token'),
    )
    op.create_index(op.f('ix_patient_documents_doctor_profile_id'), 'patient_documents', ['doctor_profile_id'], unique=False)
    op.create_index(op.f('ix_patient_documents_patient_name'), 'patient_documents', ['patient_name'], unique=False)
    op.create_index(op.f('ix_patient_documents_share_token'), 'patient_documents', ['share_token'], unique=True)
    op.create_index(op.f('ix_patient_documents_fill_token'), 'patient_documents', ['fill_token'], unique=True)

    op.create_table(
        'patient_document_files',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('document_id', sa.Uuid(), nullable=False),
        sa.Column('file_name', sa.String(length=500), nullable=False),
        sa.Column('file_key', sa.String(length=500), nullable=False),
        sa.Column('file_type', sa.String(length=50), nullable=False),
        sa.Column('file_size', sa.Integer(), nullable=False),
        sa.Column('uploaded_by', sa.Uuid(), nullable=True),
        sa.Column('uploaded_by_patient', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['document_id'], ['patient_documents.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['uploaded_by'], ['user_accounts.id'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_patient_document_files_document_id'), 'patient_document_files', ['document_id'], unique=False)

    op.create_table(
        'doctor_form_configs',
        sa.Column('id', sa.Uuid(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('doctor_profile_id', sa.Uuid(), nullable=False),
        sa.Column('fields', sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(['doctor_profile_id'], ['doctor_profiles.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('doctor_profile_id'),
    )
    op.create_index(op.f('ix_doctor_form_configs_doctor_profile_id'), 'doctor_form_configs', ['doctor_profile_id'], unique=True)


def downgrade() -> None:
    op.drop_index(op.f('ix_doctor_form_configs_doctor_profile_id'), table_name='doctor_form_configs')
    op.drop_table('doctor_form_configs')

    op.drop_index(op.f('ix_patient_document_files_document_id'), table_name='patient_document_files')
    op.drop_table('patient_document_files')

    op.drop_index(op.f('ix_patient_documents_fill_token'), table_name='patient_documents')
    op.drop_index(op.f('ix_patient_documents_share_token'), table_name='patient_documents')
    op.drop_index(op.f('ix_patient_documents_patient_name'), table_name='patient_documents')
    op.drop_index(op.f('ix_patient_documents_doctor_profile_id'), table_name='patient_documents')
    op.drop_table('patient_documents')
