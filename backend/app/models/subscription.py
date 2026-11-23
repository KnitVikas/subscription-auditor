import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Subscription(Base):
    """Derived by the detection engine from grouped transactions."""

    __tablename__ = "subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    merchant_key: Mapped[str] = mapped_column(String, nullable=False)  # normalized grouping key
    merchant_name: Mapped[str] = mapped_column(String, nullable=False)
    category: Mapped[str | None] = mapped_column(String, nullable=True)
    logo_url: Mapped[str | None] = mapped_column(String, nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String, default="INR", nullable=False)
    cadence: Mapped[str] = mapped_column(String, default="unknown", nullable=False)
    first_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_charge_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_renewal_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(3, 2), default=0, nullable=False)

    transactions = relationship(
        "SubscriptionTransaction",
        back_populates="subscription",
        cascade="all, delete-orphan",
    )


class SubscriptionTransaction(Base):
    """Link table: which transactions formed a subscription."""

    __tablename__ = "subscription_transactions"

    subscription_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("subscriptions.id", ondelete="CASCADE"),
        primary_key=True,
    )
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        Uuid,
        ForeignKey("transactions.id", ondelete="CASCADE"),
        primary_key=True,
    )

    subscription = relationship("Subscription", back_populates="transactions")
