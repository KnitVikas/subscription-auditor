"""Spending insights: category breakdown, month-over-month trend, and the
monthly-equivalent cost of recurring subscriptions.

This module is PURE (no DB/network) so it is easy to unit test. The API layer
feeds it plain values pulled from the database.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

# Convert a charge at a given cadence into its monthly-equivalent cost, so
# weekly/yearly plans can be compared on the same footing.
_MONTHLY_FACTOR = {
    "weekly": Decimal("52") / Decimal("12"),
    "monthly": Decimal("1"),
    "yearly": Decimal("1") / Decimal("12"),
    "unknown": Decimal("1"),
}

_UNCATEGORIZED = "Uncategorized"


def monthly_equivalent(amount: Decimal, cadence: str) -> Decimal:
    return amount * _MONTHLY_FACTOR.get(cadence, Decimal("1"))


@dataclass
class SubSpend:
    """Minimal view of a subscription for spend math."""

    category: str | None
    amount: Decimal
    cadence: str


@dataclass
class CategorySpend:
    category: str
    monthly: Decimal
    share: float  # 0..1 of the monthly total


def spend_by_category(subs: list[SubSpend]) -> tuple[Decimal, list[CategorySpend]]:
    """Return (monthly_total, rows) where rows are per-category monthly-equivalent
    spend sorted high to low."""
    totals: dict[str, Decimal] = {}
    for s in subs:
        cat = (s.category or "").strip() or _UNCATEGORIZED
        totals[cat] = totals.get(cat, Decimal("0")) + monthly_equivalent(
            s.amount, s.cadence
        )

    grand = sum(totals.values(), Decimal("0"))
    rows: list[CategorySpend] = []
    for cat, amt in totals.items():
        amt = amt.quantize(Decimal("0.01"))
        share = round(float(amt / grand), 4) if grand > 0 else 0.0
        rows.append(CategorySpend(category=cat, monthly=amt, share=share))
    rows.sort(key=lambda r: r.monthly, reverse=True)
    return grand.quantize(Decimal("0.01")), rows


@dataclass
class MonthSpend:
    month: str  # "YYYY-MM"
    total: Decimal


def spend_by_month(
    charges: list[tuple[datetime, Decimal]], months: int = 6
) -> list[MonthSpend]:
    """Total actual charges per calendar month, oldest to newest, limited to the
    most recent `months` buckets."""
    buckets: dict[str, Decimal] = {}
    for occurred_at, amount in charges:
        key = occurred_at.strftime("%Y-%m")
        buckets[key] = buckets.get(key, Decimal("0")) + amount
    ordered = sorted(buckets.items())
    rows = [MonthSpend(month=k, total=v.quantize(Decimal("0.01"))) for k, v in ordered]
    return rows[-months:] if months > 0 else rows


def trend_pct(by_month: list[MonthSpend]) -> float | None:
    """Percent change from the previous month to the latest. None if there isn't
    enough history or the previous month was zero."""
    if len(by_month) < 2:
        return None
    prev = by_month[-2].total
    latest = by_month[-1].total
    if prev == 0:
        return None
    return round(float((latest - prev) / prev) * 100, 1)
