from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class BudgetCreate(BaseModel):
    category: str = Field(min_length=1)
    monthly_limit: Decimal = Field(gt=0)
    currency: str = "INR"


class BudgetUpdate(BaseModel):
    monthly_limit: Decimal = Field(gt=0)


class BudgetOut(BaseModel):
    id: UUID
    category: str
    monthly_limit: Decimal
    currency: str
    spent: Decimal  # current monthly-equivalent spend in this category
    status: str  # ok | near | over


class BudgetListResponse(BaseModel):
    budgets: list[BudgetOut]
