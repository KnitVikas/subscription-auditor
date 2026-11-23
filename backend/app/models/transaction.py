import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base


class Transaction(Base):
    """Source-agnostic normalized charge. Gmail receipts and (later) bank
    transactions both land here in the same shape."""

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("connection_id", "raw_ref", name="uq_txn_connection_ref"),
        Index("idx_txn_group", "user_id", "raw_merchant", "occurred_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    connection_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("connections.id", ondelete="CASCADE"), nullable=False
    )
    source: Mapped[str] = mapped_column(String, nullable=False)  # 'gmail' | 'aa'
    raw_merchant: Mapped[str] = mapped_column(String, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String, default="INR", nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    raw_ref: Mapped[str] = mapped_column(String, nullable=False)
    # Detection signals parsed from the email (see services/gmail.py).
    sender_domain: Mapped[str] = mapped_column(String, default="", nullable=False)
    recurring_hint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    cadence_hint: Mapped[str | None] = mapped_column(String, nullable=True)
    renews_at_hint: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    trial_hint: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
