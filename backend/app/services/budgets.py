"""Budget evaluation helpers. Pure (no DB/network) so they're easy to test."""
from __future__ import annotations

from decimal import Decimal

# A budget is "near" its limit once spend reaches this fraction of it.
_NEAR_THRESHOLD = Decimal("0.8")

STATUS_OK = "ok"
STATUS_NEAR = "near"
STATUS_OVER = "over"


def status_for(spent: Decimal, monthly_limit: Decimal) -> str:
    if monthly_limit <= 0:
        return STATUS_OK
    if spent > monthly_limit:
        return STATUS_OVER
    if spent >= monthly_limit * _NEAR_THRESHOLD:
        return STATUS_NEAR
    return STATUS_OK
