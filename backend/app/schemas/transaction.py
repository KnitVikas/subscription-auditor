from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class TransactionOut(BaseModel):
    id: UUID
    source: str
    raw_merchant: str
    amount: Decimal
    currency: str
    occurred_at: datetime

    class Config:
        from_attributes = True


class TransactionListResponse(BaseModel):
    transactions: list[TransactionOut]
