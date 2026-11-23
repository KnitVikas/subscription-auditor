from datetime import datetime, timezone
from decimal import Decimal

from app.services import receipt_llm

FROM = "Netflix <info@mailer.netflix.com>"
DATE = "Mon, 10 Nov 2026 10:00:00 +0000"


def _build(data):
    return receipt_llm.receipt_from_llm_data(
        data, message_id="m1", from_header=FROM, date_header=DATE
    )


def test_not_a_receipt_returns_none():
    assert _build({"is_receipt": False, "amount": 0}) is None
    assert _build({"is_receipt": True, "amount": 0}) is None
    assert _build({"is_receipt": True}) is None  # no amount


def test_full_receipt_mapping():
    r = _build(
        {
            "is_receipt": True,
            "merchant": "Netflix",
            "amount": 649,
            "currency": "INR",
            "recurring": True,
            "cadence": "monthly",
            "trial": False,
            "renews_on": "2026-12-10",
        }
    )
    assert r is not None
    assert r.raw_merchant == "Netflix"
    assert r.amount == Decimal("649")
    assert r.currency == "INR"
    assert r.cadence_hint == "monthly"
    assert r.recurring_hint is True
    assert r.renews_at_hint == datetime(2026, 12, 10, tzinfo=timezone.utc)
    # Derived from the email, not the model:
    assert r.raw_ref == "m1"
    assert r.sender_domain == "netflix.com"
    assert r.occurred_at == datetime(2026, 11, 10, 10, 0, tzinfo=timezone.utc)


def test_currency_defaults_and_cadence_validation():
    r = _build(
        {"is_receipt": True, "amount": "9.99", "currency": "xxx", "cadence": "daily"}
    )
    assert r.currency == "INR"  # unknown currency -> default
    assert r.cadence_hint is None  # invalid cadence dropped
    assert r.amount == Decimal("9.99")


def test_merchant_falls_back_to_sender():
    r = _build({"is_receipt": True, "amount": 100, "merchant": "  "})
    assert r.raw_merchant == "Netflix"  # from the From header display name


def test_trial_sets_recurring_hint():
    r = _build({"is_receipt": True, "amount": 199, "trial": True, "recurring": False})
    assert r.trial_hint is True
    assert r.recurring_hint is True  # trial implies an upcoming recurring charge


def test_bad_date_is_ignored():
    r = _build({"is_receipt": True, "amount": 100, "renews_on": "not-a-date"})
    assert r.renews_at_hint is None


# --- batch parsing -------------------------------------------------------- #
def _inputs(n):
    return [
        receipt_llm.EmailInput(
            message_id=f"m{i}",
            from_header=FROM,
            subject="Receipt",
            date_header=DATE,
            body="body",
        )
        for i in range(n)
    ]


def test_results_from_batch_maps_by_index_with_confidence():
    inputs = _inputs(3)
    data = {
        "items": [
            {"index": 0, "is_receipt": True, "amount": 649, "currency": "INR", "confidence": 0.95},
            {"index": 1, "is_receipt": False, "amount": 0, "confidence": 0.9},
            # index 2 omitted on purpose
        ]
    }
    results = receipt_llm.results_from_batch_json(data, inputs)
    assert len(results) == 3
    assert results[0].is_receipt and results[0].confidence == 0.95
    assert results[0].receipt is not None and results[0].receipt.raw_ref == "m0"
    assert results[1].is_receipt is False and results[1].receipt is None
    assert results[2] is None  # omitted -> caller falls back to rules


def test_results_from_batch_accepts_bare_list_and_clamps_confidence():
    inputs = _inputs(1)
    data = [{"index": 0, "is_receipt": True, "amount": 100, "confidence": 5}]
    results = receipt_llm.results_from_batch_json(data, inputs)
    assert results[0].confidence == 1.0  # clamped to [0, 1]


def test_results_from_batch_handles_garbage():
    inputs = _inputs(2)
    assert receipt_llm.results_from_batch_json({}, inputs) == [None, None]
    assert receipt_llm.results_from_batch_json({"items": "nope"}, inputs) == [None, None]
