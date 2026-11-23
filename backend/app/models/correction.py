import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Correction(Base):
    """A user's manual correction to a detected subscription.

    Keyed by merchant_key so it re-applies every time the detection engine
    rebuilds subscriptions from scratch. `field` is one of
    merchant_name / category / amount / cadence / not_subscription.
    """

    __tablename__ = "corrections"
    __table_args__ = (
        UniqueConstraint("user_id", "merchant_key", "field", name="uq_correction_field"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # Informational link to the subscription at correction time; subscriptions
    # are rebuilt on each sync, so merchant_key is what actually reapplies.
    subscription_id: Mapped[uuid.UUID | None] = mapped_column(Uuid, nullable=True)
    merchant_key: Mapped[str] = mapped_column(String, nullable=False)
    field: Mapped[str] = mapped_column(String, nullable=False)
    value: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
