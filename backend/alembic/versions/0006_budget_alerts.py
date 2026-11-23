"""budget over-limit alerts: nullable alert subscription, alert category, and a
budget_alerts notification toggle

Revision ID: 0006_budget_alerts
Revises: 0005_budgets
Create Date: 2026-11-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_budget_alerts"
down_revision: Union[str, None] = "0005_budgets"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("alerts") as batch:
        batch.alter_column("subscription_id", existing_type=sa.Uuid(), nullable=True)
        batch.add_column(sa.Column("category", sa.String(), nullable=True))
    op.add_column(
        "notification_settings",
        sa.Column(
            "budget_alerts", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )


def downgrade() -> None:
    op.drop_column("notification_settings", "budget_alerts")
    with op.batch_alter_table("alerts") as batch:
        batch.drop_column("category")
        batch.alter_column("subscription_id", existing_type=sa.Uuid(), nullable=False)
