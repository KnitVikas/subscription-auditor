from decimal import Decimal

from app.services.gmail import html_to_text, parse_receipt_email, sender_domain


def test_sender_domain_extraction():
    assert sender_domain("Apple <no_reply@email.apple.com>") == "apple.com"
    assert sender_domain("Acme <billing@service.co.in>") == "service.co.in"
    assert sender_domain("Friend <me@gmail.com>") == ""
    assert sender_domain("plain text no email") == ""


def test_recurring_and_cadence_hints():
    parsed = parse_receipt_email(
        message_id="r1",
        from_header="Netflix <info@netflix.com>",
        subject="Your Netflix receipt",
        date_header="Mon, 01 Nov 2026 10:00:00 +0530",
        body="We charged Rs 199. Your plan renews on 01 December 2026 at Rs 199 per month.",
    )
    assert parsed is not None
    assert parsed.amount == Decimal("199")
    assert parsed.recurring_hint is True
    assert parsed.cadence_hint == "monthly"
    assert parsed.sender_domain == "netflix.com"
    assert parsed.renews_at_hint is not None
    assert (parsed.renews_at_hint.year, parsed.renews_at_hint.month, parsed.renews_at_hint.day) == (
        2026,
        12,
        1,
    )


def test_trial_hint_detected():
    parsed = parse_receipt_email(
        message_id="r2",
        from_header="Spotify <receipts@spotify.com>",
        subject="Your Spotify subscription",
        date_header="Wed, 03 Mar 2026 08:00:00 +0000",
        body="Your free trial ends on 10 Mar 2026. Then you pay $4.99 per month.",
    )
    assert parsed is not None
    assert parsed.trial_hint is True
    assert parsed.cadence_hint == "monthly"


def test_parse_inr_receipt():
    parsed = parse_receipt_email(
        message_id="abc123",
        from_header="Netflix <info@netflix.com>",
        subject="Your Netflix receipt",
        date_header="Mon, 01 Nov 2026 10:00:00 +0530",
        body="Thanks! We charged Rs 199 to your card.",
    )
    assert parsed is not None
    assert parsed.raw_merchant == "Netflix"
    assert parsed.amount == Decimal("199")
    assert parsed.currency == "INR"
    assert parsed.raw_ref == "abc123"


def test_parse_rupee_symbol_with_commas():
    parsed = parse_receipt_email(
        message_id="x1",
        from_header="Amazon Prime <no-reply@amazon.in>",
        subject="Prime membership renewed",
        date_header="Tue, 02 Jan 2026 08:00:00 +0000",
        body="Your membership of ₹1,499 has been renewed.",
    )
    assert parsed is not None
    assert parsed.amount == Decimal("1499")
    assert parsed.currency == "INR"


def test_parse_usd_receipt():
    parsed = parse_receipt_email(
        message_id="x2",
        from_header="Spotify <receipts@spotify.com>",
        subject="Receipt",
        date_header="Wed, 03 Mar 2026 08:00:00 +0000",
        body="We charged $9.99 to your account.",
    )
    assert parsed is not None
    assert parsed.amount == Decimal("9.99")
    assert parsed.currency == "USD"


def test_merchant_from_domain_when_no_name():
    parsed = parse_receipt_email(
        message_id="x3",
        from_header="billing@hotstar.com",
        subject="Payment",
        date_header="Wed, 03 Mar 2026 08:00:00 +0000",
        body="Amount: Rs 299",
    )
    assert parsed is not None
    assert parsed.raw_merchant == "hotstar"


def test_newsletter_subject_returns_none():
    parsed = parse_receipt_email(
        message_id="x5",
        from_header="The Neuron <hi@theneurondaily.com>",
        subject="OpenAI just raised $40 billion",
        date_header="Wed, 03 Mar 2026 08:00:00 +0000",
        body="Plus: a $895 gadget and our weekly subscription picks.",
    )
    assert parsed is None


def test_digest_subject_returns_none():
    parsed = parse_receipt_email(
        message_id="x6",
        from_header="Groww Digest <digest@groww.in>",
        subject="Your weekly market digest: payment stocks rally",
        date_header="Wed, 03 Mar 2026 08:00:00 +0000",
        body="Nifty closed at Rs 22,000.",
    )
    assert parsed is None


def test_prefers_amount_near_total_keyword():
    parsed = parse_receipt_email(
        message_id="x7",
        from_header="Swiggy <noreply@swiggy.in>",
        subject="Your order receipt",
        date_header="Wed, 03 Mar 2026 08:00:00 +0000",
        body="Item price: Rs 150 x 2. Delivery Rs 30. Subtotal Rs 300. Order Total: Rs 330",
    )
    assert parsed is not None
    assert parsed.amount == Decimal("330")


def test_skips_unlabelled_amount_for_charged_one():
    parsed = parse_receipt_email(
        message_id="x8",
        from_header="YouTube <no-reply@youtube.com>",
        subject="Your YouTube Premium receipt",
        date_header="Wed, 03 Mar 2026 08:00:00 +0000",
        body="Save Rs 50 with annual billing! You were charged Rs 129 today.",
    )
    assert parsed is not None
    assert parsed.amount == Decimal("129")


def test_zero_amounts_are_ignored():
    parsed = parse_receipt_email(
        message_id="x9",
        from_header="bigbasket <alerts@bigbasket.com>",
        subject="Your order is confirmed",
        date_header="Wed, 03 Mar 2026 08:00:00 +0000",
        body="Delivery fee: Rs 0.00. Order Total: Rs 0",
    )
    assert parsed is None


def test_html_to_text_strips_markup():
    markup = "<html><head><style>p{}</style></head><body><p>Total:&nbsp;<b>&#8377;499</b></p></body></html>"
    assert html_to_text(markup) == "Total: ₹499"


def test_no_amount_returns_none():
    parsed = parse_receipt_email(
        message_id="x4",
        from_header="Netflix <info@netflix.com>",
        subject="Welcome to Netflix",
        date_header="Wed, 03 Mar 2026 08:00:00 +0000",
        body="Thanks for signing up!",
    )
    assert parsed is None
