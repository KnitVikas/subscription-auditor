import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class NotificationSettings(Base):
    """Per-user notification preferences. One row per user (user_id is the PK).

    Lives in its own table so new preference toggles don't require altering the
    users table. When no row exists, the alerts service falls back to sensible
    defaults, so absence of a row means "all alerts on".
    """

    __tablename__ = "notification_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    renewal_lead_days: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    digest_enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    trial_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    price_hike_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    budget_alerts: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
