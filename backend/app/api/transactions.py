from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.models import Transaction, User
from app.schemas.transaction import TransactionListResponse, TransactionOut

router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    days: int = Query(settings.gmail_scan_max_days, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    txns = db.scalars(
        select(Transaction)
        .where(Transaction.user_id == user.id, Transaction.occurred_at >= cutoff)
        .order_by(Transaction.occurred_at.desc())
    ).all()
    return TransactionListResponse(
        transactions=[TransactionOut.model_validate(t) for t in txns]
    )
