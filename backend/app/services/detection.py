"""Recurrence-detection engine.

This module is PURE: it performs no database or network I/O. It takes a list of
transaction records and returns subscription candidates. This makes it trivially
unit-testable (see tests/test_detection.py), which matters because it is the most
important logic in the product.
"""
from __future__ import annotations

import re
import statistics
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from decimal import Decimal

# Cadence definitions: (label, typical interval days, tolerance days)
_CADENCES = [
    ("weekly", 7, 2),
    ("monthly", 30, 5),
    ("yearly", 365, 20),
]
_CADENCE_DAYS = {"weekly": 7, "monthly": 30, "yearly": 365}

_MIN_CHARGES = 2
_AMOUNT_TOLERANCE = Decimal("0.15")  # +/- 15%, used to flag price hikes
_MAX_AMOUNT_RATIO = Decimal("1.5")  # max/min charge ratio to still be "one subscription"
# Two emails for the same charge (receipt + confirmation) land close together.
_DUPLICATE_WINDOW_DAYS = 5

_NORMALIZE_STRIP = re.compile(r"[^a-z]+")

# Brands that are subscriptions by nature, so a single charge is enough to
# treat them as recurring. Deliberately excludes merchants that also sell
# one-off items under the same sender domain (e.g. amazon, google), which would
# otherwise flag ordinary purchases. Those still get detected via recurring_hint.
SUBSCRIPTION_MERCHANTS = {
    "netflix", "spotify", "youtube", "icloud", "apple", "itunes",
    "hotstar", "jiohotstar", "disney", "disneyplus", "adobe", "notion",
    "chatgpt", "openai", "linkedin", "github",
}


@dataclass
class TxnInput:
    id: str
    raw_merchant: str
    amount: Decimal
    currency: str
    occurred_at: datetime
    sender_domain: str = ""
    recurring_hint: bool = False
    cadence_hint: str | None = None
    renews_at_hint: datetime | None = None
    trial_hint: bool = False


@dataclass
class SubscriptionCandidate:
    merchant_key: str
    raw_merchant: str
    amount: Decimal
    currency: str
    cadence: str
    first_seen_at: datetime
    last_charge_at: datetime
    next_renewal_at: datetime | None
    confidence_score: float
    status: str
    transaction_ids: list[str] = field(default_factory=list)


def normalize_merchant(raw: str) -> str:
    """Collapse messy merchant strings to a grouping key.

    'NETFLIX COM 94 LOS GAT' and 'NETFLIX.COM' both map to 'netflix'.
    """
    lowered = raw.lower()
    # Drop trailing numbers / city codes by keeping alpha tokens only.
    tokens = [t for t in _NORMALIZE_STRIP.split(lowered) if t]
    # Common noise tokens to drop.
    noise = {"com", "inc", "ltd", "pvt", "in", "india", "payment", "www"}
    meaningful = [t for t in tokens if t not in noise]
    if not meaningful:
        meaningful = tokens
    # Use the first meaningful token as the grouping key. This keeps noisy
    # trailing tokens (location/city codes) from splitting one merchant apart,
    # e.g. 'netflix com 94 los gat' and 'netflix.com' both map to 'netflix'.
    return meaningful[0] if meaningful else lowered


def _amounts_consistent(amounts: list[Decimal]) -> bool:
    """Charges belong to one subscription if they are in the same ballpark.

    Uses a max/min ratio rather than a tight band so that genuine price hikes
    (e.g. 149 -> 199) still count as the same subscription, while wildly
    different amounts (e.g. 199 vs 999) are rejected.
    """
    lo, hi = min(amounts), max(amounts)
    if lo <= 0:
        return False
    return (hi / lo) <= _MAX_AMOUNT_RATIO


def _classify_cadence(intervals: list[float]) -> tuple[str, int] | None:
    """Return (cadence_label, interval_days) if intervals match a known cadence."""
    if not intervals:
        return None
    avg = statistics.mean(intervals)
    for label, days, tol in _CADENCES:
        if abs(avg - days) <= tol:
            return label, days
    return None


def _interval_regularity(intervals: list[float], expected_days: int) -> float:
    """0..1 score: how close intervals are to the expected cadence."""
    if not intervals:
        return 0.0
    deviations = [abs(i - expected_days) / expected_days for i in intervals]
    mean_dev = statistics.mean(deviations)
    return max(0.0, 1.0 - mean_dev)


def _detect_price_hike(amounts: list[Decimal]) -> bool:
    if len(amounts) < 2:
        return False
    return amounts[-1] > amounts[0] * (Decimal("1") + _AMOUNT_TOLERANCE)


def _group_key(txn: TxnInput) -> str:
    """Group charges by sender domain's main label (so 'apple.com' and an
    'iTunes Store' display name collapse together), falling back to the
    normalized merchant name when there is no usable domain."""
    if txn.sender_domain:
        return txn.sender_domain.split(".")[0]
    return normalize_merchant(txn.raw_merchant)


def _collapse_duplicates(txns_sorted: list[TxnInput]) -> list[TxnInput]:
    """Drop repeat emails for the same charge: same amount within a few days.
    Keeps the earliest occurrence."""
    collapsed: list[TxnInput] = []
    for txn in txns_sorted:
        is_dup = any(
            c.amount == txn.amount
            and abs((txn.occurred_at - c.occurred_at).days) < _DUPLICATE_WINDOW_DAYS
            for c in collapsed
        )
        if not is_dup:
            collapsed.append(txn)
    return collapsed


def _single_charge_candidate(key: str, txn: TxnInput) -> SubscriptionCandidate | None:
    """A lone charge is a subscription only if the email signals recurrence or
    the merchant is a known subscription brand."""
    if not (txn.recurring_hint or key in SUBSCRIPTION_MERCHANTS):
        return None
    cadence = txn.cadence_hint or "monthly"
    interval_days = _CADENCE_DAYS.get(cadence, 30)
    next_renewal = txn.renews_at_hint or (txn.occurred_at + timedelta(days=interval_days))
    status = "trial" if txn.trial_hint else "active"
    # Lower confidence than multi-charge detection: it rests on one data point.
    confidence = 0.5 if txn.recurring_hint else 0.4
    return SubscriptionCandidate(
        merchant_key=key,
        raw_merchant=txn.raw_merchant,
        amount=txn.amount,
        currency=txn.currency,
        cadence=cadence,
        first_seen_at=txn.occurred_at,
        last_charge_at=txn.occurred_at,
        next_renewal_at=next_renewal,
        confidence_score=confidence,
        status=status,
        transaction_ids=[txn.id],
    )


def _multi_charge_candidate(
    key: str, txns_sorted: list[TxnInput]
) -> SubscriptionCandidate | None:
    amounts = [t.amount for t in txns_sorted]
    if not _amounts_consistent(amounts):
        return None

    dates = [t.occurred_at for t in txns_sorted]
    intervals = [
        (dates[i + 1] - dates[i]).total_seconds() / 86400.0
        for i in range(len(dates) - 1)
    ]
    cadence_match = _classify_cadence(intervals)
    if cadence_match is None:
        return None
    cadence, interval_days = cadence_match

    last_charge = dates[-1]
    next_renewal = last_charge + timedelta(days=interval_days)
    regularity = _interval_regularity(intervals, interval_days)
    # Confidence blends interval regularity with having more data points.
    count_factor = min(1.0, len(txns_sorted) / 4.0)
    confidence = round(0.6 * regularity + 0.4 * count_factor, 2)

    if any(t.trial_hint for t in txns_sorted):
        status = "trial"
    elif _detect_price_hike(amounts):
        status = "price_hike"
    else:
        status = "active"
    typical_amount = Decimal(str(statistics.median(amounts)))

    return SubscriptionCandidate(
        merchant_key=key,
        raw_merchant=txns_sorted[-1].raw_merchant,
        amount=typical_amount,
        currency=txns_sorted[-1].currency,
        cadence=cadence,
        first_seen_at=dates[0],
        last_charge_at=last_charge,
        next_renewal_at=next_renewal,
        confidence_score=confidence,
        status=status,
        transaction_ids=[t.id for t in txns_sorted],
    )


def detect_subscriptions(transactions: list[TxnInput]) -> list[SubscriptionCandidate]:
    """Group charges by merchant and emit subscription candidates. Groups with
    two or more charges use cadence rules; a single charge can still qualify via
    recurrence hints or a known subscription brand."""
    groups: dict[str, list[TxnInput]] = {}
    for txn in transactions:
        groups.setdefault(_group_key(txn), []).append(txn)

    candidates: list[SubscriptionCandidate] = []
    for key, txns in groups.items():
        txns_sorted = _collapse_duplicates(sorted(txns, key=lambda t: t.occurred_at))

        if len(txns_sorted) >= _MIN_CHARGES:
            candidate = _multi_charge_candidate(key, txns_sorted)
        else:
            candidate = _single_charge_candidate(key, txns_sorted[0])

        if candidate is not None:
            candidates.append(candidate)
    return candidates
