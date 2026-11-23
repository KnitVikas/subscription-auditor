"""Gmail OAuth + receipt search/parse.

The network-facing helpers (OAuth flow, message fetch) are thin wrappers around
the Google client libraries. The parsing logic (`parse_receipt_email`) is pure
and unit-tested in tests/test_gmail_parse.py.
"""
from __future__ import annotations

import base64
import html
import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from email.utils import parsedate_to_datetime

from app.core.config import settings

logger = logging.getLogger(__name__)

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# Gmail search query for likely receipt / renewal emails.
RECEIPT_QUERY = (
    'subscription OR receipt OR invoice OR "your payment" OR "payment received" '
    'OR renews OR "subscription confirmed" OR "order confirmation"'
)
# Newsletters and marketing land in these Gmail tabs; receipts rarely do.
EXCLUDED_CATEGORIES = "-category:promotions -category:social -category:forums"

# A receipt's subject names the transaction; a newsletter's subject is a headline.
_TRANSACTIONAL_SUBJECT_RE = re.compile(
    r"receipt|invoice|payment|paid|order|renew|subscription|membership|billing|"
    r"\bbill\b|charged|debited|transaction|purchase|\bplan\b|trial",
    re.IGNORECASE,
)
_NEWSLETTER_SUBJECT_RE = re.compile(r"newsletter|digest|webinar", re.IGNORECASE)

# Words that sit just before the charged amount. Strong words name the final
# charge; weak words may label an item or a promo.
_STRONG_AMOUNT_CONTEXT_RE = re.compile(
    r"total|charged|debited|billed|payable|paid", re.IGNORECASE
)
_WEAK_AMOUNT_CONTEXT_RE = re.compile(r"amount|price", re.IGNORECASE)
_AMOUNT_CONTEXT_WINDOW = 40

# Currency symbol / code -> ISO code.
_CURRENCY_MAP = {
    "₹": "INR",
    "rs": "INR",
    "inr": "INR",
    "$": "USD",
    "usd": "USD",
    "€": "EUR",
    "eur": "EUR",
    "£": "GBP",
    "gbp": "GBP",
}

_AMOUNT_RE = re.compile(
    r"(₹|rs\.?|inr|\$|usd|€|eur|£|gbp)\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
    re.IGNORECASE,
)

# Generic mail providers whose domain is not a merchant.
_GENERIC_EMAIL_DOMAINS = {
    "gmail.com", "googlemail.com", "outlook.com", "hotmail.com", "live.com",
    "yahoo.com", "yahoo.co.in", "ymail.com", "aol.com", "proton.me",
    "protonmail.com", "zoho.com", "rediffmail.com", "me.com",
}
# Multi-label public suffixes we must keep intact (e.g. example.co.in).
_TWO_LABEL_TLDS = {
    "co.in", "co.uk", "com.au", "co.nz", "com.br", "co.jp", "com.sg",
    "co.za", "com.mx", "co.id", "org.in", "net.in",
}

# Signals that a charge is part of a recurring plan, even from a single email.
_RECURRING_HINT_RE = re.compile(
    r"renews?\s+on|next\s+billing\s+date|renewal\s+date|auto[-\s]?renew|recurring|"
    r"\bsubscription\b|\bmembership\b|per\s+month|/\s*month|per\s+year|/\s*year|"
    r"\bmonthly\b|\bannual(?:ly)?\b|\byearly\b",
    re.IGNORECASE,
)
_MONTHLY_HINT_RE = re.compile(r"per\s+month|/\s*month|\bmonthly\b", re.IGNORECASE)
_YEARLY_HINT_RE = re.compile(
    r"per\s+year|/\s*year|\bannual(?:ly)?\b|\byearly\b", re.IGNORECASE
)
_TRIAL_HINT_RE = re.compile(
    r"trial\s+ends|free\s+trial|trial\s+period|your\s+trial", re.IGNORECASE
)
_RENEWS_DATE_RE = re.compile(
    r"(?:renews?\s+on|next\s+billing\s+date|renewal\s+date)[:\s]+([A-Za-z0-9 ,/-]{6,30})",
    re.IGNORECASE,
)
# Date formats accepted in renewal hints (commas are stripped before matching).
_HINT_DATE_FORMATS = (
    ("%d %B %Y", 3),
    ("%d %b %Y", 3),
    ("%B %d %Y", 3),
    ("%b %d %Y", 3),
    ("%Y-%m-%d", 1),
    ("%d-%m-%Y", 1),
    ("%d/%m/%Y", 1),
)


@dataclass
class ParsedReceipt:
    raw_merchant: str
    amount: Decimal
    currency: str
    occurred_at: datetime
    raw_ref: str
    sender_domain: str = ""
    recurring_hint: bool = False
    cadence_hint: str | None = None
    renews_at_hint: datetime | None = None
    trial_hint: bool = False


def _parse_amount(text: str) -> tuple[Decimal, str] | None:
    """Pick the charged amount: the last one labelled 'total'/'charged'/'paid'
    (receipts list subtotals first), else the first labelled 'amount'/'price',
    else the first amount in the text."""
    matches = [
        m for m in _AMOUNT_RE.finditer(text) if m.group(2).replace(",", "").strip("0.")
    ]
    if not matches:
        return None

    def _labelled(m: re.Match, pattern: re.Pattern) -> bool:
        return bool(pattern.search(text[max(0, m.start() - _AMOUNT_CONTEXT_WINDOW) : m.start()]))

    strong = [m for m in matches if _labelled(m, _STRONG_AMOUNT_CONTEXT_RE)]
    weak = [m for m in matches if _labelled(m, _WEAK_AMOUNT_CONTEXT_RE)]
    match = strong[-1] if strong else weak[0] if weak else matches[0]
    symbol = match.group(1).lower().rstrip(".")
    raw_number = match.group(2).replace(",", "")
    try:
        amount = Decimal(raw_number)
    except InvalidOperation:
        return None
    currency = _CURRENCY_MAP.get(symbol, "INR")
    return amount, currency


def _merchant_from_sender(from_header: str) -> str:
    """Extract a merchant label from a From header like
    'Netflix <info@netflix.com>'."""
    from_header = from_header.strip()
    name_match = re.match(r'"?([^"<]+?)"?\s*<', from_header)
    if name_match:
        return name_match.group(1).strip()
    domain_match = re.search(r"@([\w.-]+)", from_header)
    if domain_match:
        domain = domain_match.group(1)
        return domain.split(".")[0]
    return from_header


def sender_domain(from_header: str) -> str:
    """Registrable domain of the sender, e.g. 'no_reply@email.apple.com' ->
    'apple.com'. Returns '' for generic mail providers (gmail, outlook, ...)."""
    match = re.search(r"@([\w.-]+)", from_header)
    if not match:
        return ""
    labels = [label for label in match.group(1).lower().strip(".").split(".") if label]
    if len(labels) < 2:
        return ""
    domain = ".".join(labels[-2:])
    if len(labels) >= 3 and domain in _TWO_LABEL_TLDS:
        domain = ".".join(labels[-3:])
    return "" if domain in _GENERIC_EMAIL_DOMAINS else domain


def email_datetime(date_header: str) -> datetime:
    """Parse an email Date header to an aware datetime, defaulting to now."""
    try:
        dt = parsedate_to_datetime(date_header)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (TypeError, ValueError):
        return datetime.now(timezone.utc)


def _parse_hint_date(text: str) -> datetime | None:
    """Best-effort date parse from a renewal-hint snippet. Returns None if no
    supported format matches."""
    cleaned = re.sub(r"\s+", " ", text.replace(",", " ")).strip()
    tokens = cleaned.split()
    for fmt, span in _HINT_DATE_FORMATS:
        if len(tokens) < span:
            continue
        candidate = " ".join(tokens[:span])
        try:
            return datetime.strptime(candidate, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def parse_receipt_email(
    *, message_id: str, from_header: str, subject: str, date_header: str, body: str
) -> ParsedReceipt | None:
    """Pure parser. Returns a ParsedReceipt, or None if the email does not look
    like a receipt or has no amount."""
    if not _TRANSACTIONAL_SUBJECT_RE.search(subject) or _NEWSLETTER_SUBJECT_RE.search(subject):
        return None
    searchable = f"{subject}\n{body}"
    parsed_amount = _parse_amount(searchable)
    if parsed_amount is None:
        return None
    amount, currency = parsed_amount

    occurred_at = email_datetime(date_header)

    cadence_hint = None
    if _MONTHLY_HINT_RE.search(searchable):
        cadence_hint = "monthly"
    elif _YEARLY_HINT_RE.search(searchable):
        cadence_hint = "yearly"

    renews_at_hint = None
    renews_match = _RENEWS_DATE_RE.search(searchable)
    if renews_match:
        renews_at_hint = _parse_hint_date(renews_match.group(1))

    return ParsedReceipt(
        raw_merchant=_merchant_from_sender(from_header),
        amount=amount,
        currency=currency,
        occurred_at=occurred_at,
        raw_ref=message_id,
        sender_domain=sender_domain(from_header),
        recurring_hint=bool(_RECURRING_HINT_RE.search(searchable)),
        cadence_hint=cadence_hint,
        renews_at_hint=renews_at_hint,
        trial_hint=bool(_TRIAL_HINT_RE.search(searchable)),
    )


# ---------------------------------------------------------------------------
# Network-facing helpers (not exercised by unit tests)
# ---------------------------------------------------------------------------
def _client_config() -> dict:
    return {
        "web": {
            "client_id": settings.google_client_id,
            "client_secret": settings.google_client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [settings.google_redirect_uri],
        }
    }


def get_authorization_url(state: str) -> str:
    from google_auth_oauthlib.flow import Flow

    # PKCE off: the verifier would have to survive until the callback, which
    # builds a fresh Flow. The client secret authenticates the code exchange.
    flow = Flow.from_client_config(
        _client_config(), scopes=GMAIL_SCOPES, autogenerate_code_verifier=False
    )
    flow.redirect_uri = settings.google_redirect_uri
    url, _ = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent", state=state
    )
    return url


def exchange_code(code: str) -> dict:
    """Exchange an authorization code for tokens. Returns a dict with
    access_token, refresh_token, expiry."""
    from google_auth_oauthlib.flow import Flow

    flow = Flow.from_client_config(_client_config(), scopes=GMAIL_SCOPES)
    flow.redirect_uri = settings.google_redirect_uri
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": creds.expiry,
    }


def _build_credentials(access_token: str, refresh_token: str | None):
    from google.oauth2.credentials import Credentials

    return Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        scopes=GMAIL_SCOPES,
    )


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


_HTML_DROP_RE = re.compile(r"<(style|script|head)\b.*?</\1>", re.IGNORECASE | re.DOTALL)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def html_to_text(markup: str) -> str:
    text = _HTML_TAG_RE.sub(" ", _HTML_DROP_RE.sub(" ", markup))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def _collect_text_parts(payload: dict, found: dict[str, str]) -> None:
    mime = payload.get("mimeType", "")
    data = payload.get("body", {}).get("data")
    if mime in ("text/plain", "text/html") and data and mime not in found:
        found[mime] = base64.urlsafe_b64decode(data).decode("utf-8", errors="ignore")
    for part in payload.get("parts", []) or []:
        _collect_text_parts(part, found)


def _extract_body(payload: dict) -> str:
    """Plain-text body of a Gmail message, preferring the text/plain part and
    falling back to tag-stripped HTML."""
    found: dict[str, str] = {}
    _collect_text_parts(payload, found)
    if found.get("text/plain", "").strip():
        return found["text/plain"]
    return html_to_text(found.get("text/html", ""))


# Gmail runs batch items concurrently and rejects bursts with "Too many
# concurrent requests for user" well before its documented 50-per-batch limit.
_BATCH_SIZE = 5
_RETRYABLE_STATUSES = (403, 429, 500, 503)


def _list_message_ids(service, query: str, max_messages: int) -> list[str]:
    ids: list[str] = []
    page_token = None
    while len(ids) < max_messages:
        listing = (
            service.users()
            .messages()
            .list(
                userId="me",
                q=query,
                maxResults=min(500, max_messages - len(ids)),
                pageToken=page_token,
            )
            .execute()
        )
        ids.extend(m["id"] for m in listing.get("messages", []))
        page_token = listing.get("nextPageToken")
        if not page_token:
            break
    return ids[:max_messages]


def _status_of(exception) -> int | None:
    return getattr(getattr(exception, "resp", None), "status", None)


def _get_message(service, message_id: str):
    return service.users().messages().get(userId="me", id=message_id, format="full")


def _fetch_messages(
    service, ids: list[str], batch_rounds: int = 3, on_progress=None
) -> list[dict]:
    messages: list[dict] = []
    pending = list(ids)
    total = len(ids)

    def _report() -> None:
        if on_progress is not None:
            on_progress(min(len(messages), total), total)

    for attempt in range(batch_rounds):
        failed: list[str] = []

        def _collect(request_id, response, exception):
            if exception is None:
                messages.append(response)
            elif _status_of(exception) in _RETRYABLE_STATUSES:
                failed.append(request_id)
            else:
                logger.warning("Skipping Gmail message %s: %s", request_id, exception)

        for start in range(0, len(pending), _BATCH_SIZE):
            batch = service.new_batch_http_request(callback=_collect)
            for message_id in pending[start : start + _BATCH_SIZE]:
                batch.add(_get_message(service, message_id), request_id=message_id)
            batch.execute()
            _report()

        pending = failed
        if not pending:
            _report()
            return messages
        time.sleep(2**attempt)

    # Sequential requests are slower but not subject to the concurrency limit.
    from googleapiclient.errors import HttpError

    for message_id in pending:
        for retry in range(3):
            try:
                messages.append(_get_message(service, message_id).execute())
                break
            except HttpError as exc:
                if _status_of(exc) not in _RETRYABLE_STATUSES or retry == 2:
                    logger.warning("Skipping Gmail message %s: %s", message_id, exc)
                    break
                time.sleep(2**retry)
        _report()
    return messages


def clamp_scan_days(days: int | None) -> int:
    return max(1, min(days or settings.gmail_scan_days, settings.gmail_scan_max_days))


def fetch_receipts(
    access_token: str,
    refresh_token: str | None,
    days: int | None = None,
    max_messages: int | None = None,
    on_progress=None,
):
    """Fetch and parse receipt emails from the last `days` days.
    Yields ParsedReceipt objects. `on_progress(done, total)` is called as
    messages are downloaded."""
    from googleapiclient.discovery import build

    days = clamp_scan_days(days)
    max_messages = max_messages or settings.gmail_scan_max_messages

    creds = _build_credentials(access_token, refresh_token)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    query = f"({RECEIPT_QUERY}) {EXCLUDED_CATEGORIES} newer_than:{days}d"
    ids = _list_message_ids(service, query, max_messages)
    if on_progress is not None:
        on_progress(0, len(ids))

    messages = _fetch_messages(service, ids, on_progress=on_progress)

    # Lazy import avoids an import cycle (receipt_llm imports from this module).
    from app.services import receipt_llm

    inputs = []
    for msg in messages:
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        email_input = receipt_llm.EmailInput(
            message_id=msg["id"],
            from_header=_header(headers, "From"),
            subject=_header(headers, "Subject"),
            date_header=_header(headers, "Date"),
            body=_extract_body(payload),
        )
        inputs.append(email_input)
        logger.debug(
            "fetched email id=%s from=%r subject=%r date=%r body_chars=%d\nbody=%s",
            email_input.message_id,
            email_input.from_header,
            email_input.subject,
            email_input.date_header,
            len(email_input.body),
            email_input.body,
        )

    def _rules(inp) -> "ParsedReceipt | None":
        return parse_receipt_email(
            message_id=inp.message_id,
            from_header=inp.from_header,
            subject=inp.subject,
            date_header=inp.date_header,
            body=inp.body,
        )

    if not receipt_llm.enabled():
        for inp in inputs:
            parsed = _rules(inp)
            if parsed is not None:
                yield parsed
        return

    threshold = settings.llm_parse_min_confidence
    batch_size = max(1, settings.llm_parse_batch_size)
    llm_budget = settings.llm_parse_max_messages
    llm_used = 0

    for start in range(0, len(inputs), batch_size):
        batch = inputs[start : start + batch_size]
        if llm_used < llm_budget:
            llm_used += len(batch)
            try:
                results = receipt_llm.parse_batch(batch)
            except Exception as exc:  # noqa: BLE001 - fall back to rules on any error
                logger.warning(
                    "LLM batch parse failed (%d emails), using rules: %s",
                    len(batch),
                    exc,
                )
                results = [None] * len(batch)
        else:
            results = [None] * len(batch)

        for inp, res in zip(batch, results):
            if res is None:
                parsed = _rules(inp)  # LLM didn't run / errored / omitted
            elif not res.is_receipt:
                parsed = None  # trust the agent's rejection
            elif res.receipt is not None and res.confidence >= threshold:
                parsed = res.receipt  # high-confidence extraction
            else:
                parsed = _rules(inp)  # low confidence or unbuildable -> rules
            if parsed is not None:
                yield parsed
