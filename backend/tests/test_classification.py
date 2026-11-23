from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.services.classification import (
    FLAG_DUPLICATE,
    FLAG_PRICE_HIKE,
    FLAG_TRIAL,
    FLAG_UNUSED,
    SubscriptionView,
    classify,
    find_duplicate_ids,
    is_price_hike,
    is_unused,
)

NOW = datetime(2026, 11, 13, tzinfo=timezone.utc)


def _view(**kwargs) -> SubscriptionView:
    base = dict(id="1", category="Music", cadence="monthly", status="active")
    base.update(kwargs)
    return SubscriptionView(**base)


def test_price_hike_detection():
    assert is_price_hike([Decimal("149"), Decimal("199")]) is True
    assert is_price_hike([Decimal("199"), Decimal("199")]) is False
    assert is_price_hike([Decimal("199")]) is False


def test_unused_when_charge_is_old():
    recent = NOW - timedelta(days=20)
    stale = NOW - timedelta(days=75)  # > 2 monthly cycles
    assert is_unused(recent, "monthly", NOW) is False
    assert is_unused(stale, "monthly", NOW) is True
    assert is_unused(None, "monthly", NOW) is False


def test_classify_combines_flags():
    view = _view(
        amounts_in_order=[Decimal("149"), Decimal("199")],
        last_charge_at=NOW - timedelta(days=75),
        has_trial_hint=True,
    )
    flags = classify(view, now=NOW)
    assert set(flags) == {FLAG_TRIAL, FLAG_PRICE_HIKE, FLAG_UNUSED}


def test_cancelled_subscription_has_no_flags():
    view = _view(
        status="cancelled",
        amounts_in_order=[Decimal("149"), Decimal("199")],
        last_charge_at=NOW - timedelta(days=400),
        has_trial_hint=True,
    )
    assert classify(view, now=NOW) == []


def test_duplicates_in_same_category():
    views = [
        _view(id="a", category="Music"),
        _view(id="b", category="Music"),
        _view(id="c", category="Entertainment"),
        _view(id="d", category=None),
        _view(id="e", category="Music", status="cancelled"),
    ]
    dupes = find_duplicate_ids(views)
    assert dupes == {"a", "b"}
    assert FLAG_DUPLICATE  # constant exists for the API layer
