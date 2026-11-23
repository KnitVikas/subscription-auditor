from decimal import Decimal, InvalidOperation
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import Correction, Subscription, SubscriptionTransaction, Transaction, User
from app.schemas.subscription import (
    ChargeOut,
    CorrectionCreate,
    SubscriptionDetailResponse,
    SubscriptionListResponse,
    SubscriptionOut,
    SubscriptionUpdate,
    Totals,
)
from app.services import classification

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

_VALID_STATUSES = {"active", "cancelled", "ignored"}
_CORRECTABLE_FIELDS = {"merchant_name", "category", "amount", "cadence", "not_subscription"}
_VALID_CADENCES = {"weekly", "monthly", "yearly"}


def _flags_by_id(db: Session, user_id: UUID) -> dict[str, list[str]]:
    """Compute classification flags for every subscription of a user, keyed by
    subscription id (as str)."""
    subs = db.scalars(
        select(Subscription).where(Subscription.user_id == user_id)
    ).all()
    if not subs:
        return {}

    rows = db.execute(
        select(
            SubscriptionTransaction.subscription_id,
            Transaction.amount,
            Transaction.occurred_at,
            Transaction.trial_hint,
        )
        .join(Transaction, Transaction.id == SubscriptionTransaction.transaction_id)
        .where(SubscriptionTransaction.subscription_id.in_([s.id for s in subs]))
        .order_by(Transaction.occurred_at.asc())
    ).all()

    ctx: dict = {}
    for sub_id, amount, occurred_at, trial in rows:
        entry = ctx.setdefault(sub_id, {"amounts": [], "last": None, "trial": False})
        entry["amounts"].append(amount)
        entry["last"] = occurred_at  # ascending order -> keeps the latest
        entry["trial"] = entry["trial"] or bool(trial)

    views = [
        classification.SubscriptionView(
            id=str(s.id),
            category=s.category,
            cadence=s.cadence,
            status=s.status,
            amounts_in_order=ctx.get(s.id, {}).get("amounts") or [s.amount],
            last_charge_at=ctx.get(s.id, {}).get("last") or s.last_charge_at,
            has_trial_hint=ctx.get(s.id, {}).get("trial", False),
        )
        for s in subs
    ]
    duplicates = classification.find_duplicate_ids(views)
    result: dict[str, list[str]] = {}
    for view in views:
        flags = classification.classify(view)
        if view.id in duplicates:
            flags.append(classification.FLAG_DUPLICATE)
        result[view.id] = flags
    return result


def _with_flags(sub: Subscription, flags: list[str]) -> SubscriptionOut:
    return SubscriptionOut.model_validate(sub).model_copy(update={"flags": flags})

# Factor to convert a cadence's charge into a monthly-equivalent amount.
_MONTHLY_FACTOR = {
    "weekly": Decimal("52") / Decimal("12"),
    "monthly": Decimal("1"),
    "yearly": Decimal("1") / Decimal("12"),
    "unknown": Decimal("1"),
}


def _monthly_equivalent(amount: Decimal, cadence: str) -> Decimal:
    return amount * _MONTHLY_FACTOR.get(cadence, Decimal("1"))


@router.get("", response_model=SubscriptionListResponse)
def list_subscriptions(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> SubscriptionListResponse:
    subs = db.scalars(
        select(Subscription)
        .where(Subscription.user_id == user.id)
        .order_by(Subscription.next_renewal_at.asc().nullslast())
    ).all()

    active = [s for s in subs if s.status in ("active", "price_hike", "trial")]
    monthly = sum((_monthly_equivalent(s.amount, s.cadence) for s in active), Decimal("0"))
    monthly = monthly.quantize(Decimal("0.01"))
    currency = active[0].currency if active else "INR"

    totals = Totals(
        monthly=monthly,
        yearly=(monthly * 12).quantize(Decimal("0.01")),
        currency=currency,
        count=len(active),
    )
    flags_map = _flags_by_id(db, user.id)
    return SubscriptionListResponse(
        totals=totals,
        subscriptions=[_with_flags(s, flags_map.get(str(s.id), [])) for s in subs],
    )


@router.get("/{subscription_id}", response_model=SubscriptionDetailResponse)
def get_subscription(
    subscription_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionDetailResponse:
    sub = db.scalar(
        select(Subscription).where(
            Subscription.id == subscription_id, Subscription.user_id == user.id
        )
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    charges = db.scalars(
        select(Transaction)
        .join(
            SubscriptionTransaction,
            SubscriptionTransaction.transaction_id == Transaction.id,
        )
        .where(SubscriptionTransaction.subscription_id == sub.id)
        .order_by(Transaction.occurred_at.desc())
    ).all()

    flags = _flags_by_id(db, user.id).get(str(sub.id), [])
    return SubscriptionDetailResponse(
        **_with_flags(sub, flags).model_dump(),
        first_seen_at=sub.first_seen_at,
        last_charge_at=sub.last_charge_at,
        history=[ChargeOut(occurred_at=c.occurred_at, amount=c.amount) for c in charges],
    )


@router.patch("/{subscription_id}", response_model=SubscriptionOut)
def update_subscription(
    subscription_id: UUID,
    payload: SubscriptionUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SubscriptionOut:
    if payload.status not in _VALID_STATUSES:
        raise HTTPException(status_code=422, detail="Invalid status")
    sub = db.scalar(
        select(Subscription).where(
            Subscription.id == subscription_id, Subscription.user_id == user.id
        )
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")
    sub.status = payload.status
    db.commit()
    db.refresh(sub)
    flags = _flags_by_id(db, user.id).get(str(sub.id), [])
    return _with_flags(sub, flags)


def _normalize_correction(field: str, value: str) -> str:
    """Validate a correction and return the stored value, or raise 422."""
    if field not in _CORRECTABLE_FIELDS:
        raise HTTPException(status_code=422, detail="Unknown field")
    if field == "amount":
        try:
            amount = Decimal(value)
        except InvalidOperation:
            raise HTTPException(status_code=422, detail="Invalid amount")
        if amount <= 0:
            raise HTTPException(status_code=422, detail="Amount must be positive")
        return str(amount)
    if field == "cadence" and value not in _VALID_CADENCES:
        raise HTTPException(status_code=422, detail="Invalid cadence")
    if field == "not_subscription" and value not in ("true", "false"):
        raise HTTPException(status_code=422, detail="Invalid value")
    if field == "merchant_name":
        value = value.strip()
        if not value:
            raise HTTPException(status_code=422, detail="Name is required")
    return value


@router.post("/{subscription_id}/corrections")
def create_correction(
    subscription_id: UUID,
    payload: CorrectionCreate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Record and apply a user correction. Corrections are keyed by merchant so
    they survive the subscription rebuild on each sync."""
    value = _normalize_correction(payload.field, payload.value)
    sub = db.scalar(
        select(Subscription).where(
            Subscription.id == subscription_id, Subscription.user_id == user.id
        )
    )
    if sub is None:
        raise HTTPException(status_code=404, detail="Subscription not found")

    existing = db.scalar(
        select(Correction).where(
            Correction.user_id == user.id,
            Correction.merchant_key == sub.merchant_key,
            Correction.field == payload.field,
        )
    )
    if existing is None:
        db.add(
            Correction(
                user_id=user.id,
                subscription_id=sub.id,
                merchant_key=sub.merchant_key,
                field=payload.field,
                value=value,
            )
        )
    else:
        existing.value = value
        existing.subscription_id = sub.id

    # Apply to the current subscription so the change is visible immediately.
    if payload.field == "not_subscription" and value == "true":
        db.delete(sub)
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    if payload.field == "merchant_name":
        sub.merchant_name = value
    elif payload.field == "category":
        sub.category = value or None
    elif payload.field == "amount":
        sub.amount = Decimal(value)
    elif payload.field == "cadence":
        sub.cadence = value

    db.commit()
    db.refresh(sub)
    flags = _flags_by_id(db, user.id).get(str(sub.id), [])
    return _with_flags(sub, flags)
