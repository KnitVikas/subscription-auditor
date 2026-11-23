"""detection signals on transactions + sync state on connections

Revision ID: 0002_detection_signals
Revises: 0001_initial
Create Date: 2026-11-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0002_detection_signals"
down_revision: Union[str, None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("sender_domain", sa.String(), nullable=False, server_default=""),
    )
    op.add_column(
        "transactions",
        sa.Column("recurring_hint", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.add_column("transactions", sa.Column("cadence_hint", sa.String(), nullable=True))
    op.add_column(
        "transactions",
        sa.Column("renews_at_hint", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "transactions",
        sa.Column("trial_hint", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    op.add_column(
        "connections",
        sa.Column("sync_status", sa.String(), nullable=False, server_default="idle"),
    )
    op.add_column(
        "connections",
        sa.Column("sync_total", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "connections",
        sa.Column("sync_done", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("connections", sa.Column("sync_error", sa.String(), nullable=True))
    op.add_column("connections", sa.Column("sync_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("connections", "sync_days")
    op.drop_column("connections", "sync_error")
    op.drop_column("connections", "sync_done")
    op.drop_column("connections", "sync_total")
    op.drop_column("connections", "sync_status")

    op.drop_column("transactions", "trial_hint")
    op.drop_column("transactions", "renews_at_hint")
    op.drop_column("transactions", "cadence_hint")
    op.drop_column("transactions", "recurring_hint")
    op.drop_column("transactions", "sender_domain")
