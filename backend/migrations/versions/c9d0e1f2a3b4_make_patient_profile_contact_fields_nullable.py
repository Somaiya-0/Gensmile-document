"""make patient_profile phone/address fields nullable

Revision ID: c9d0e1f2a3b4
Revises: b8d9e0f1a2b3
Create Date: 2026-07-25 00:00:00.000000

Doctor-created patients (POST /doctors/patients) no longer require phone,
full_address, street_address, city, state_name, country_name, country_code,
or zip_code up front -- only full_name and email are required. These columns
were NOT NULL, which forced the frontend to submit placeholder junk data
("N/A", "+10000000000", "00000") for fields the doctor left blank.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9d0e1f2a3b4'
down_revision: Union[str, None] = 'b8d9e0f1a2b3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_COLUMNS = [
    ("phone", sa.String(length=50)),
    ("full_address", sa.Text()),
    ("street_address", sa.String(length=255)),
    ("city", sa.String(length=120)),
    ("state_name", sa.String(length=120)),
    ("country_name", sa.String(length=120)),
    ("country_code", sa.String(length=10)),
    ("zip_code", sa.String(length=30)),
]


def upgrade() -> None:
    for column_name, column_type in _COLUMNS:
        op.alter_column(
            "patient_profiles",
            column_name,
            existing_type=column_type,
            nullable=True,
        )


def downgrade() -> None:
    for column_name, column_type in _COLUMNS:
        op.alter_column(
            "patient_profiles",
            column_name,
            existing_type=column_type,
            nullable=False,
        )
