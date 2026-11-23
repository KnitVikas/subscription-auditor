"""Subscription classification: derive user-facing flags from a subscription and
its charge history.

This module is PURE (no DB/network), so it is easy to unit-test. The flags are
additive and can co-exist (e.g. a subscription may be both `price_hike` and
`duplicate`). They are computed at read time, not stored, so they always reflect
the current data and rules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal

# Charges more than this many cadence-intervals old suggest the subscription is
# dormant (no recent charge), which we surface as "possibly unused". We cannot
# see product usage from receipts, so this is an inactivity heuristic.
_UNUSED_INTERVAL_FACTOR = 2.0
_PRICE_HIKE_TOLERANCE = Decimal("0.15")  # latest > earliest * 1.15
_CADENCE_DAYS = {"weekly": 7, "monthly": 30, "yearly": 365}

FLAG_PRICE_HIKE = "price_hike"
FLAG_TRIAL = "trial"
FLAG_UNUSED = "unused"
FLAG_DUPLICATE = "duplicate"


@dataclass
class SubscriptionView:
    """Minimal, DB-free view of a subscription used for classification."""

    id: str
    category: str | None
    cadence: str
    status: str
    amounts_in_order: list[Decimal] = field(default_factory=list)
    last_charge_at: datetime | None = None
    has_trial_hint: bool = False


def is_price_hike(amounts_in_order: list[Decimal]) -> bool:
    if len(amounts_in_order) < 2:
        return False
    return amounts_in_order[-1] > amounts_in_order[0] * (Decimal("1") + _PRICE_HIKE_TOLERANCE)


def is_trial(view: SubscriptionView) -> bool:
    return view.has_trial_hint or view.status == "trial"


def is_unused(
    last_charge_at: datetime | None, cadence: str, now: datetime | None = None
) -> bool:
    """True when the most recent charge is older than a couple of billing
    cycles, i.e. the service has gone quiet."""
    if last_charge_at is None:
        return False
    interval = _CADENCE_DAYS.get(cadence)
    if interval is None:
        return False
    now = now or datetime.now(timezone.utc)
    if last_charge_at.tzinfo is None:
        last_charge_at = last_charge_at.replace(tzinfo=timezone.utc)
    age_days = (now - last_charge_at).total_seconds() / 86400.0
    return age_days > _UNUSED_INTERVAL_FACTOR * interval


def classify(view: SubscriptionView, now: datetime | None = None) -> list[str]:
    """Per-subscription flags (everything except `duplicate`, which needs the
    full set to compare categories). Cancelled/ignored subscriptions get no
    flags; the user has already dealt with them."""
    if view.status in ("cancelled", "ignored"):
        return []
    flags: list[str] = []
    if is_trial(view):
        flags.append(FLAG_TRIAL)
    if is_price_hike(view.amounts_in_order):
        flags.append(FLAG_PRICE_HIKE)
    if is_unused(view.last_charge_at, view.cadence, now):
        flags.append(FLAG_UNUSED)
    return flags


def find_duplicate_ids(views: list[SubscriptionView]) -> set[str]:
    """IDs of active subscriptions that share a category with another active
    one (e.g. two music services), so the user can spot overlap."""
    by_category: dict[str, list[str]] = {}
    for view in views:
        if view.status in ("cancelled", "ignored") or not view.category:
            continue
        by_category.setdefault(view.category.lower(), []).append(view.id)
    duplicates: set[str] = set()
    for ids in by_category.values():
        if len(ids) > 1:
            duplicates.update(ids)
    return duplicates
