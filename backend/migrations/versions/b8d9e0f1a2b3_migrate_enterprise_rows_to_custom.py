"""migrate existing ENTERPRISE plan rows to CUSTOM

Revision ID: b8d9e0f1a2b3
Revises: b7c8d9e0f1a2
Create Date: 2026-07-24 00:00:01.000000

The product no longer sells a separate "Enterprise" tier — the onboarding
catalog only offers "Custom" now (app/core/onboarding_catalog.py). Any
existing subscriptions/onboarding sessions still stored as ENTERPRISE
predate that rename and should read as CUSTOM. Split into its own migration
(after b7c8d9e0f1a2) since a newly added enum value can't reliably be used
in the same transaction that added it.
"""
from typing import Sequence, Union

from alembic import op


revision: str = 'b8d9e0f1a2b3'
down_revision: Union[str, None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE subscriptions SET plan_code = 'CUSTOM' WHERE plan_code = 'ENTERPRISE'")
    op.execute("UPDATE onboarding_sessions SET selected_plan = 'CUSTOM' WHERE selected_plan = 'ENTERPRISE'")


def downgrade() -> None:
    op.execute("UPDATE subscriptions SET plan_code = 'ENTERPRISE' WHERE plan_code = 'CUSTOM'")
    op.execute("UPDATE onboarding_sessions SET selected_plan = 'ENTERPRISE' WHERE selected_plan = 'CUSTOM'")
