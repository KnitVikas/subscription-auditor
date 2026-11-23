from datetime import datetime, timezone
from decimal import Decimal

from app.services import alerts


def _item(name, amount, day):
    return alerts.DigestItem(
        name=name,
        when=datetime(2026, 11, day, tzinfo=timezone.utc),
        amount=Decimal(amount),
        currency="INR",
    )


def test_build_digest_empty_is_none():
    assert alerts.build_digest([]) is None


def test_build_digest_totals_and_lists_items():
    subject, body = alerts.build_digest(
        [_item("Netflix", "649", 14), _item("Spotify", "119", 18)]
    )
    assert "768" in subject  # 649 + 119
    assert "2 renewals totalling" in body
    assert "Netflix" in body and "Spotify" in body
    assert "14 Nov" in body


def test_build_digest_singular_wording():
    _, body = alerts.build_digest([_item("Netflix", "649", 14)])
    assert "1 renewal totalling" in body


def test_price_change_detects_hike():
    assert alerts.price_change([Decimal("499"), Decimal("499"), Decimal("649")]) == (
        Decimal("499"),
        Decimal("649"),
    )


def test_price_change_none_when_stable():
    assert alerts.price_change([Decimal("499"), Decimal("499")]) is None
    assert alerts.price_change([Decimal("499")]) is None


def test_email_builders_have_subject_and_body():
    for builder in (alerts.renewal_email, alerts.trial_email):
        subject, body = builder("Netflix", "14 Nov 2026", "Rs 649")
        assert "Netflix" in subject
        assert "Netflix" in body and "649" in body

    subject, body = alerts.price_hike_email("Netflix", "Rs 499", "Rs 649")
    assert "Netflix" in subject
    assert "499" in body and "649" in body


def test_budget_email():
    subject, body = alerts.budget_email("Streaming", "Rs 948", "Rs 500")
    assert "Streaming" in subject
    assert "948" in body and "500" in body
