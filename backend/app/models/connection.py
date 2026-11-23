import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, LargeBinary, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base


class Connection(Base):
    __tablename__ = "connections"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String, nullable=False)  # 'gmail' | 'aa'
    access_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    refresh_token_enc: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String, default="active", nullable=False)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Background sync progress, polled by the dashboard.
    sync_status: Mapped[str] = mapped_column(String, default="idle", nullable=False)
    sync_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sync_done: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    sync_error: Mapped[str | None] = mapped_column(String, nullable=True)
    sync_days: Mapped[int | None] = mapped_column(Integer, nullable=True)

    user = relationship("User", back_populates="connections")
