from decimal import Decimal

from pydantic import BaseModel


class CategorySpendOut(BaseModel):
    category: str
    monthly: Decimal
    share: float


class MonthSpendOut(BaseModel):
    month: str
    total: Decimal


class InsightsResponse(BaseModel):
    currency: str
    monthly_total: Decimal
    by_category: list[CategorySpendOut]
    by_month: list[MonthSpendOut]
    trend_pct: float | None
