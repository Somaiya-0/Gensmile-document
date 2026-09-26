"""add guest trials table

Revision ID: ece61f51e707
Revises: b4f1a2c3e5d7
Create Date: 2026-09-12 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'ece61f51e707'
down_revision: Union[str, None] = 'b4f1a2c3e5d7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "guest_trials",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("trial_key", sa.String(length=255), nullable=False),
        sa.Column("trial_count", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("trial_key", name="uq_guest_trials_trial_key"),
    )
    op.create_index(
        "ix_guest_trials_trial_key",
        "guest_trials",
        ["trial_key"],
    )


def downgrade() -> None:
    op.drop_index("ix_guest_trials_trial_key", table_name="guest_trials")
    op.drop_table("guest_trials")
