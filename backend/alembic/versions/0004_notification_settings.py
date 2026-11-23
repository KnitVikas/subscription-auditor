"""per-user notification settings

Revision ID: 0004_notification_settings
Revises: 0003_corrections
Create Date: 2026-11-13

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_notification_settings"
down_revision: Union[str, None] = "0003_corrections"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notification_settings",
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("renewal_lead_days", sa.Integer(), nullable=False, server_default="2"),
        sa.Column("digest_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("trial_alerts", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "price_hike_alerts", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("notification_settings")
