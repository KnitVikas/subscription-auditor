from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Budget, Subscription, User
from app.schemas.budget import (
    BudgetCreate,
    BudgetListResponse,
    BudgetOut,
    BudgetUpdate,
)
from app.services import budgets as budgets_service
from app.services import insights

router = APIRouter(prefix="/budgets", tags=["budgets"])


def _spend_by_category(db: Session, user_id: UUID) -> dict[str, Decimal]:
    """Current monthly-equivalent spend per category (lowercased key) from the
    user's active subscriptions."""
    subs = db.scalars(
        select(Subscription).where(
            Subscription.user_id == user_id, Subscription.status == "active"
        )
    ).all()
    spend: dict[str, Decimal] = {}
    for s in subs:
        key = (s.category or "").strip().lower()
        spend[key] = spend.get(key, Decimal("0")) + insights.monthly_equivalent(
            s.amount, s.cadence
        )
    return spend


def _to_out(budget: Budget, spend: dict[str, Decimal]) -> BudgetOut:
    spent = spend.get(budget.category.strip().lower(), Decimal("0")).quantize(
        Decimal("0.01")
    )
    return BudgetOut(
        id=budget.id,
        category=budget.category,
        monthly_limit=budget.monthly_limit,
        currency=budget.currency,
        spent=spent,
        status=budgets_service.status_for(spent, budget.monthly_limit),
    )


@router.get("", response_model=BudgetListResponse)
def list_budgets(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> BudgetListResponse:
    budgets = db.scalars(
        select(Budget).where(Budget.user_id == user.id).order_by(Budget.category.asc())
    ).all()
    spend = _spend_by_category(db, user.id)
    return BudgetListResponse(budgets=[_to_out(b, spend) for b in budgets])


@router.post("", response_model=BudgetOut, status_code=status.HTTP_201_CREATED)
def create_budget(
    payload: BudgetCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetOut:
    category = payload.category.strip()
    existing = db.scalar(
        select(Budget).where(
            Budget.user_id == user.id, Budget.category == category
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="A budget for this category exists")
    budget = Budget(
        user_id=user.id,
        category=category,
        monthly_limit=payload.monthly_limit,
        currency=payload.currency,
    )
    db.add(budget)
    db.commit()
    db.refresh(budget)
    return _to_out(budget, _spend_by_category(db, user.id))


@router.patch("/{budget_id}", response_model=BudgetOut)
def update_budget(
    budget_id: UUID,
    payload: BudgetUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BudgetOut:
    budget = db.scalar(
        select(Budget).where(Budget.id == budget_id, Budget.user_id == user.id)
    )
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    budget.monthly_limit = payload.monthly_limit
    db.commit()
    db.refresh(budget)
    return _to_out(budget, _spend_by_category(db, user.id))


@router.delete("/{budget_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_budget(
    budget_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    budget = db.scalar(
        select(Budget).where(Budget.id == budget_id, Budget.user_id == user.id)
    )
    if budget is None:
        raise HTTPException(status_code=404, detail="Budget not found")
    db.delete(budget)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
