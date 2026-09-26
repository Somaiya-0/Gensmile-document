"""add 90-day drip campaign opt-out toggle and send log

Revision ID: f1a2b3c4d5e6
Revises: c9d0e1f2a3b4
Create Date: 2026-07-28 00:00:00.000000

Adds `notify_email_drip_campaign` to user_settings (defaults to True — the
campaign is opt-out) and a `drip_campaign_email_log` table that records which
of the scheduled emails have already gone out per user, so the daily
scheduler tick never sends the same email twice.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'f1a2b3c4d5e6'
down_revision: Union[str, None] = 'c9d0e1f2a3b4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "user_settings",
        sa.Column(
            "notify_email_drip_campaign",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )
    op.alter_column("user_settings", "notify_email_drip_campaign", server_default=None)

    op.create_table(
        "drip_campaign_email_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Uuid(),
            sa.ForeignKey("user_accounts.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email_key", sa.String(length=50), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("user_id", "email_key", name="uq_drip_campaign_user_email_key"),
    )
    op.create_index(
        "ix_drip_campaign_email_log_user_id",
        "drip_campaign_email_log",
        ["user_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_drip_campaign_email_log_user_id", table_name="drip_campaign_email_log")
    op.drop_table("drip_campaign_email_log")
    op.drop_column("user_settings", "notify_email_drip_campaign")
