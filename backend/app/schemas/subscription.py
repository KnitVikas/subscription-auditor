from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class SubscriptionOut(BaseModel):
    id: UUID
    merchant_name: str
    category: str | None
    logo_url: str | None
    amount: Decimal
    currency: str
    cadence: str
    next_renewal_at: datetime | None
    status: str
    confidence_score: Decimal
    flags: list[str] = []

    class Config:
        from_attributes = True


class Totals(BaseModel):
    monthly: Decimal
    yearly: Decimal
    currency: str
    count: int


class SubscriptionListResponse(BaseModel):
    totals: Totals
    subscriptions: list[SubscriptionOut]


class ChargeOut(BaseModel):
    occurred_at: datetime
    amount: Decimal


class SubscriptionDetailResponse(SubscriptionOut):
    first_seen_at: datetime | None
    last_charge_at: datetime | None
    history: list[ChargeOut]


class SubscriptionUpdate(BaseModel):
    status: str  # 'active' | 'cancelled' | 'ignored'


class CorrectionCreate(BaseModel):
    # One of: merchant_name | category | amount | cadence | not_subscription
    field: str
    value: str
