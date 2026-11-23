from datetime import datetime, timedelta, timezone
from decimal import Decimal

from app.services.detection import (  # noqa: F401
    TxnInput,
    detect_subscriptions,
    normalize_merchant,
)


def _txn(id_: str, merchant: str, amount: str, dt: datetime) -> TxnInput:
    return TxnInput(
        id=id_,
        raw_merchant=merchant,
        amount=Decimal(amount),
        currency="INR",
        occurred_at=dt,
    )


def _monthly_dates(n: int, start: datetime) -> list[datetime]:
    return [start + timedelta(days=30 * i) for i in range(n)]


BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def test_normalize_merchant_groups_noisy_strings():
    assert normalize_merchant("NETFLIX COM 94 LOS GAT") == normalize_merchant("NETFLIX.COM")
    assert normalize_merchant("Netflix") == "netflix"


def test_monthly_subscription_detected():
    dates = _monthly_dates(3, BASE)
    txns = [_txn(str(i), "NETFLIX.COM", "199", d) for i, d in enumerate(dates)]
    subs = detect_subscriptions(txns)
    assert len(subs) == 1
    sub = subs[0]
    assert sub.cadence == "monthly"
    assert sub.amount == Decimal("199")
    # next renewal is ~30 days after last charge
    assert sub.next_renewal_at == dates[-1] + timedelta(days=30)
    assert sub.confidence_score > 0.7
    assert len(sub.transaction_ids) == 3


def test_yearly_subscription_detected():
    dates = [BASE, BASE + timedelta(days=365)]
    txns = [_txn(str(i), "Amazon Prime", "1499", d) for i, d in enumerate(dates)]
    subs = detect_subscriptions(txns)
    assert len(subs) == 1
    assert subs[0].cadence == "yearly"


def test_price_hike_flagged():
    dates = _monthly_dates(3, BASE)
    amounts = ["149", "149", "199"]
    txns = [_txn(str(i), "Spotify", a, d) for i, (a, d) in enumerate(zip(amounts, dates))]
    subs = detect_subscriptions(txns)
    assert len(subs) == 1
    assert subs[0].status == "price_hike"


def test_single_charge_not_a_subscription():
    txns = [_txn("1", "Amazon", "2500", BASE)]
    assert detect_subscriptions(txns) == []


def test_irregular_charges_not_detected():
    dates = [BASE, BASE + timedelta(days=3), BASE + timedelta(days=50)]
    amounts = ["100", "900", "25"]
    txns = [_txn(str(i), "Random Shop", a, d) for i, (a, d) in enumerate(zip(amounts, dates))]
    subs = detect_subscriptions(txns)
    assert subs == []


def test_inconsistent_amounts_rejected():
    dates = _monthly_dates(3, BASE)
    amounts = ["199", "999", "199"]
    txns = [_txn(str(i), "Netflix", a, d) for i, (a, d) in enumerate(zip(amounts, dates))]
    subs = detect_subscriptions(txns)
    assert subs == []


def test_apple_and_itunes_group_and_collapse():
    # Same charge, two sender names and two emails three days apart.
    t1 = TxnInput(
        id="1", raw_merchant="iTunes Store", amount=Decimal("219"), currency="INR",
        occurred_at=datetime(2026, 8, 27, tzinfo=timezone.utc), sender_domain="apple.com",
    )
    t2 = TxnInput(
        id="2", raw_merchant="Apple", amount=Decimal("219"), currency="INR",
        occurred_at=datetime(2026, 8, 30, tzinfo=timezone.utc), sender_domain="apple.com",
    )
    subs = detect_subscriptions([t1, t2])
    assert len(subs) == 1
    assert subs[0].merchant_key == "apple"
    assert subs[0].amount == Decimal("219")
    # Duplicate email collapsed: only the earliest charge is linked.
    assert subs[0].transaction_ids == ["1"]


def test_single_charge_with_recurring_hint_detected():
    t = TxnInput(
        id="1", raw_merchant="SomeApp", amount=Decimal("499"), currency="INR",
        occurred_at=BASE, recurring_hint=True, cadence_hint="monthly",
    )
    subs = detect_subscriptions([t])
    assert len(subs) == 1
    assert subs[0].cadence == "monthly"
    assert subs[0].status == "active"
    assert subs[0].confidence_score == 0.5


def test_single_food_order_not_detected():
    t = TxnInput(
        id="1", raw_merchant="Swiggy", amount=Decimal("250"), currency="INR",
        occurred_at=BASE, sender_domain="swiggy.in",
    )
    assert detect_subscriptions([t]) == []


def test_single_charge_trial_flagged():
    t = TxnInput(
        id="1", raw_merchant="Netflix", amount=Decimal("0"), currency="INR",
        occurred_at=BASE, sender_domain="netflix.com", trial_hint=True,
    )
    subs = detect_subscriptions([t])
    assert len(subs) == 1
    assert subs[0].status == "trial"
