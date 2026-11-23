from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Subscription, SubscriptionTransaction, Transaction, User
from app.schemas.insights import CategorySpendOut, InsightsResponse, MonthSpendOut
from app.services import insights

router = APIRouter(prefix="/insights", tags=["insights"])

# Subscriptions in these statuses count as live recurring spend.
_ACTIVE = "active"


@router.get("/spend", response_model=InsightsResponse)
def spend(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> InsightsResponse:
    """Category breakdown of current recurring spend plus a month-by-month trend
    of actual subscription charges."""
    subs = db.scalars(
        select(Subscription).where(
            Subscription.user_id == user.id, Subscription.status == _ACTIVE
        )
    ).all()
    currency = subs[0].currency if subs else "INR"

    monthly_total, categories = insights.spend_by_category(
        [insights.SubSpend(s.category, s.amount, s.cadence) for s in subs]
    )

    # Actual charges that formed this user's subscriptions, bucketed by month.
    charge_rows = db.execute(
        select(Transaction.occurred_at, Transaction.amount)
        .join(
            SubscriptionTransaction,
            SubscriptionTransaction.transaction_id == Transaction.id,
        )
        .join(Subscription, Subscription.id == SubscriptionTransaction.subscription_id)
        .where(Subscription.user_id == user.id)
    ).all()
    by_month = insights.spend_by_month([(o, a) for o, a in charge_rows])

    return InsightsResponse(
        currency=currency,
        monthly_total=monthly_total,
        by_category=[
            CategorySpendOut(category=c.category, monthly=c.monthly, share=c.share)
            for c in categories
        ],
        by_month=[MonthSpendOut(month=m.month, total=m.total) for m in by_month],
        trend_pct=insights.trend_pct(by_month),
    )
