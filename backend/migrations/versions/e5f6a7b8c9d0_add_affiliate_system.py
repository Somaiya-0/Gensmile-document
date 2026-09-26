"""Add affiliate system: affiliates and affiliate_commissions tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-14 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── affiliates table ──────────────────────────────────────────────────────
    # Enum types are created implicitly (checkfirst) by create_table below —
    # a separate explicit CREATE TYPE here would double-create them and fail.
    op.create_table(
        "affiliates",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "active", "suspended", name="affiliatestatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("commission_rate", sa.Numeric(5, 4), nullable=False, server_default="0.2000"),
        sa.Column("payout_method", sa.String(50), nullable=True),
        sa.Column("payout_email", sa.String(255), nullable=True),
        sa.Column("payout_account", sa.String(255), nullable=True),
        sa.Column("payout_notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index("ix_affiliates_code", "affiliates", ["code"])
    op.create_index("ix_affiliates_status", "affiliates", ["status"])
    op.create_index("ix_affiliates_user_id", "affiliates", ["user_id"])

    # ── affiliate_commissions table ───────────────────────────────────────────
    op.create_table(
        "affiliate_commissions",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("affiliate_id", sa.UUID(), nullable=False),
        sa.Column("billing_transaction_id", sa.UUID(), nullable=True),
        sa.Column("referred_user_id", sa.UUID(), nullable=False),
        sa.Column("amount_cents", sa.Integer(), nullable=False),
        sa.Column("commission_cents", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("pending", "paid", "cancelled", name="commissionstatus"),
            nullable=False,
            server_default="pending",
        ),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["affiliate_id"], ["affiliates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["billing_transaction_id"], ["billing_transactions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["referred_user_id"], ["user_accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_affiliate_commissions_affiliate_id", "affiliate_commissions", ["affiliate_id"])
    op.create_index("ix_affiliate_commissions_billing_transaction_id", "affiliate_commissions", ["billing_transaction_id"])
    op.create_index("ix_affiliate_commissions_referred_user_id", "affiliate_commissions", ["referred_user_id"])
    op.create_index("ix_affiliate_commissions_status", "affiliate_commissions", ["status"])

    # ── Add referred_by_affiliate_id to user_accounts ─────────────────────────
    op.add_column(
        "user_accounts",
        sa.Column("referred_by_affiliate_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_user_accounts_referred_by_affiliate_id",
        "user_accounts",
        "affiliates",
        ["referred_by_affiliate_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_user_accounts_referred_by_affiliate_id",
        "user_accounts",
        ["referred_by_affiliate_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_accounts_referred_by_affiliate_id", table_name="user_accounts")
    op.drop_constraint("fk_user_accounts_referred_by_affiliate_id", "user_accounts", type_="foreignkey")
    op.drop_column("user_accounts", "referred_by_affiliate_id")

    op.drop_index("ix_affiliate_commissions_status", table_name="affiliate_commissions")
    op.drop_index("ix_affiliate_commissions_referred_user_id", table_name="affiliate_commissions")
    op.drop_index("ix_affiliate_commissions_billing_transaction_id", table_name="affiliate_commissions")
    op.drop_index("ix_affiliate_commissions_affiliate_id", table_name="affiliate_commissions")
    op.drop_table("affiliate_commissions")

    op.drop_index("ix_affiliates_user_id", table_name="affiliates")
    op.drop_index("ix_affiliates_status", table_name="affiliates")
    op.drop_index("ix_affiliates_code", table_name="affiliates")
    op.drop_table("affiliates")

    op.execute("DROP TYPE IF EXISTS commissionstatus")
    op.execute("DROP TYPE IF EXISTS affiliatestatus")
