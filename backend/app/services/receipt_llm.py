"""LLM receipt-parsing agent.

A separate, self-contained agent that reads one email (sender, subject, body)
and extracts the subscription/receipt fields the rest of the pipeline expects.
It mirrors the enrichment agent's shape: it only runs when an OpenAI key is
configured, and the rule-based parser in `gmail.py` is used as a fallback on any
failure.

`receipt_from_llm_data` is PURE (no network) so the field validation and mapping
are unit tested; `parse_receipt_llm` is the thin network wrapper that calls the
model and raises on failure so the caller can fall back to rules.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

from app.core.config import settings
from app.services import llm
from app.services.gmail import (
    ParsedReceipt,
    _merchant_from_sender,
    email_datetime,
    sender_domain,
)

_BODY_CHARS = 6000  # truncate long emails to keep a single-email prompt small
_BATCH_BODY_CHARS = 3000  # tighter per-email budget when batching many emails
_ALLOWED_CURRENCIES = {"INR", "USD", "EUR", "GBP"}
_CADENCES = {"monthly", "yearly"}

_SYSTEM_PROMPT = (
    "You extract structured billing data from a single email. The email may be a "
    "subscription receipt, an invoice, a renewal/trial notice, OR something that "
    "is NOT a payment (newsletter, marketing, shipping update, OTP, social). "
    "Return ONLY JSON with these keys:\n"
    '  is_receipt (boolean): true only if the email shows an actual charge, '
    "invoice, or an upcoming subscription renewal/trial conversion with an amount.\n"
    "  merchant (string): clean brand name, e.g. 'Netflix'.\n"
    "  amount (number): the amount charged or to be charged. 0 if unknown.\n"
    "  currency (string): ISO code, one of INR, USD, EUR, GBP.\n"
    "  recurring (boolean): true if it's a subscription/membership/recurring plan.\n"
    "  cadence (string|null): 'monthly' or 'yearly' if stated, else null.\n"
    "  trial (boolean): true if it mentions a free trial ending/converting.\n"
    "  renews_on (string|null): next renewal/charge date as 'YYYY-MM-DD', else null.\n"
    "Do not invent amounts. If there is no clear amount, set is_receipt=false."
)

_BATCH_SYSTEM_PROMPT = (
    "You extract structured billing data from several emails at once. The input "
    "contains multiple emails, each marked '--- EMAIL <index> ---'. For EACH "
    'email return one object in a JSON array under the key "items". Each object '
    "must have:\n"
    "  index (integer): the email's index from the marker.\n"
    "  is_receipt (boolean): true only if it shows an actual charge, invoice, or "
    "an upcoming subscription renewal/trial conversion with an amount.\n"
    "  merchant (string), amount (number, 0 if unknown), currency (INR|USD|EUR|GBP),\n"
    "  recurring (boolean), cadence ('monthly'|'yearly'|null), trial (boolean),\n"
    "  renews_on ('YYYY-MM-DD'|null),\n"
    "  confidence (number 0..1): how confident you are this extraction is correct.\n"
    "Return exactly one object per input email. Do not invent amounts; if there "
    "is no clear amount set is_receipt=false and a low confidence."
)


@dataclass
class EmailInput:
    message_id: str
    from_header: str
    subject: str
    date_header: str
    body: str


@dataclass
class LLMResult:
    receipt: ParsedReceipt | None  # built when is_receipt and the amount is valid
    confidence: float  # 0..1
    is_receipt: bool


def enabled() -> bool:
    return bool(settings.openai_api_key) and settings.llm_receipt_parsing


def _as_float(value) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _as_decimal(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _parse_iso_date(value) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.strptime(value.strip()[:10], "%Y-%m-%d").replace(
            tzinfo=timezone.utc
        )
    except ValueError:
        return None


def receipt_from_llm_data(
    data: dict,
    *,
    message_id: str,
    from_header: str,
    date_header: str,
) -> ParsedReceipt | None:
    """Build a ParsedReceipt from the model's JSON, or None if the email isn't a
    receipt / has no usable amount. Pure and unit-tested."""
    if not isinstance(data, dict) or not data.get("is_receipt"):
        return None

    amount = _as_decimal(data.get("amount"))
    if amount is None or amount <= 0:
        return None

    currency = str(data.get("currency") or "INR").upper()
    if currency not in _ALLOWED_CURRENCIES:
        currency = "INR"

    merchant = (str(data.get("merchant") or "")).strip() or _merchant_from_sender(
        from_header
    )

    cadence = data.get("cadence")
    cadence_hint = cadence if cadence in _CADENCES else None
    renews_at_hint = _parse_iso_date(data.get("renews_on"))

    return ParsedReceipt(
        raw_merchant=merchant,
        amount=amount,
        currency=currency,
        occurred_at=email_datetime(date_header),
        raw_ref=message_id,
        sender_domain=sender_domain(from_header),
        recurring_hint=bool(
            data.get("recurring") or cadence_hint or renews_at_hint or data.get("trial")
        ),
        cadence_hint=cadence_hint,
        renews_at_hint=renews_at_hint,
        trial_hint=bool(data.get("trial")),
    )


def parse_receipt_llm(
    *,
    message_id: str,
    from_header: str,
    subject: str,
    date_header: str,
    body: str,
) -> ParsedReceipt | None:
    """Call the model to parse one email. Returns a ParsedReceipt, or None when
    the model says it isn't a receipt. Raises on network/parse errors so the
    caller can fall back to the rule-based parser."""
    user_content = (
        f"From: {from_header}\n"
        f"Subject: {subject}\n\n"
        f"Body:\n{(body or '')[:_BODY_CHARS]}"
    )
    data = llm.chat_json(_SYSTEM_PROMPT, user_content)
    return receipt_from_llm_data(
        data,
        message_id=message_id,
        from_header=from_header,
        date_header=date_header,
    )


def results_from_batch_json(
    data, inputs: list[EmailInput]
) -> list[LLMResult | None]:
    """Map a batch response to one result per input (aligned by index). An entry
    is None when the model omitted that index, so the caller can fall back to the
    rule-based parser for it. Pure and unit-tested."""
    raw = data.get("items") if isinstance(data, dict) else data
    by_index: dict[int, dict] = {}
    if isinstance(raw, list):
        for item in raw:
            if isinstance(item, dict) and isinstance(item.get("index"), int):
                by_index[item["index"]] = item

    results: list[LLMResult | None] = []
    for i, inp in enumerate(inputs):
        item = by_index.get(i)
        if item is None:
            results.append(None)
            continue
        receipt = receipt_from_llm_data(
            item,
            message_id=inp.message_id,
            from_header=inp.from_header,
            date_header=inp.date_header,
        )
        results.append(
            LLMResult(
                receipt=receipt,
                confidence=_as_float(item.get("confidence")),
                is_receipt=bool(item.get("is_receipt")),
            )
        )
    return results


def parse_batch(inputs: list[EmailInput]) -> list[LLMResult | None]:
    """Parse several emails in one model call. Returns one result per input
    (None where the model gave nothing). Raises on network/parse errors so the
    caller can fall back to rules for the whole batch."""
    parts = [
        f"--- EMAIL {i} ---\n"
        f"From: {inp.from_header}\n"
        f"Subject: {inp.subject}\n"
        f"Body:\n{(inp.body or '')[:_BATCH_BODY_CHARS]}"
        for i, inp in enumerate(inputs)
    ]
    data = llm.chat_json(_BATCH_SYSTEM_PROMPT, "\n\n".join(parts))
    return results_from_batch_json(data, inputs)
