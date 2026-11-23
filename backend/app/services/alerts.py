"""Alert scheduling and sending: renewal reminders, trial-ending warnings,
price-hike notices, and the weekly digest.

The Celery tasks (scan_renewals, weekly_digest) call the send_* functions here,
which own the "who is due" queries and email delivery. The message-building and
decision helpers at the top are PURE (no DB/network) so they are easy to unit
test. Email delivery goes through Resend if configured; otherwise it logs, so
the whole flow works end to end in local development without an email provider.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import (
    Alert,
    Budget,
    NotificationSettings,
    Subscription,
    SubscriptionTransaction,
    Transaction,
    User,
)
from app.services import classification, insights

logger = logging.getLogger("subscription_auditor.alerts")

_SIGNATURE = "\n\n- Subscription Auditor"


# --------------------------------------------------------------------------- #
# Pure helpers (no DB / network) - unit tested
# --------------------------------------------------------------------------- #
def _format_money(amount, currency: str) -> str:
    symbol = {"INR": "Rs ", "USD": "$", "EUR": "EUR ", "GBP": "GBP "}.get(currency, "")
    return f"{symbol}{amount}"


def renewal_email(name: str, when: str, amount: str) -> tuple[str, str]:
    return (
        f"{name} renews soon",
        f"Heads up: {name} renews on {when} for {amount}.\n\n"
        f"If you no longer use it, now is a good time to cancel." + _SIGNATURE,
    )


def trial_email(name: str, when: str, amount: str) -> tuple[str, str]:
    return (
        f"{name} free trial ends soon",
        f"Your {name} free trial ends on {when}, after which you'll be charged "
        f"{amount}.\n\nCancel before then if you don't want to continue." + _SIGNATURE,
    )


def price_hike_email(name: str, old: str, new: str) -> tuple[str, str]:
    return (
        f"{name} raised its price",
        f"{name} increased from {old} to {new}.\n\n"
        f"It might be worth checking whether you still need it at the new price."
        + _SIGNATURE,
    )


def budget_email(category: str, spent: str, limit: str) -> tuple[str, str]:
    return (
        f"You're over budget on {category}",
        f"Your {category} subscriptions now cost {spent} a month, above your "
        f"{limit} budget.\n\nReview them and cancel anything you no longer need."
        + _SIGNATURE,
    )


def price_change(amounts_in_order: list[Decimal]) -> tuple[Decimal, Decimal] | None:
    """If the charge history shows a price hike, return (old, new); else None."""
    if not classification.is_price_hike(amounts_in_order):
        return None
    return amounts_in_order[0], amounts_in_order[-1]


@dataclass
class DigestItem:
    name: str
    when: datetime
    amount: Decimal
    currency: str


def build_digest(items: list[DigestItem]) -> tuple[str, str] | None:
    """Build the weekly digest subject/body, or None if there's nothing to say."""
    if not items:
        return None
    currency = items[0].currency
    total = sum((i.amount for i in items), Decimal("0"))
    count = len(items)
    header = (
        f"This week you have {count} renewal{'s' if count != 1 else ''} "
        f"totalling {_format_money(total, currency)}."
    )
    lines = [
        f"- {i.name}: {_format_money(i.amount, i.currency)} on {i.when.strftime('%d %b')}"
        for i in items
    ]
    subject = f"Your subscriptions this week ({_format_money(total, currency)})"
    body = header + "\n\n" + "\n".join(lines) + _SIGNATURE
    return subject, body


# --------------------------------------------------------------------------- #
# Email delivery and configuration checks
# --------------------------------------------------------------------------- #
def _from_domain() -> str:
    from_email = settings.from_email or ""
    return from_email.split("@")[-1].lower() if "@" in from_email else ""


@dataclass
class EmailStatus:
    """Best-effort view of whether outgoing email will actually be delivered,
    based on the configured provider key and sender domain."""

    provider_configured: bool
    from_email: str
    from_domain: str
    deliverable: bool
    detail: str


def _verified_domains() -> tuple[set[str] | None, str]:
    """Verified sending domains on the Resend account, or (None, reason) if the
    list can't be fetched (bad key, network, etc.)."""
    try:
        resp = httpx.get(
            "https://api.resend.com/domains",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            timeout=10,
        )
        if resp.status_code in (401, 403):
            return None, "the API key was rejected"
        resp.raise_for_status()
        data = resp.json().get("data", []) or []
        return {d["name"].lower() for d in data if d.get("status") == "verified"}, "ok"
    except Exception as exc:  # pragma: no cover - network
        return None, str(exc)[:200]


def email_status() -> EmailStatus:
    """Check whether FROM_EMAIL is on a verified sending domain so we can tell
    the user up front whether alert emails will reach them."""
    from_email = settings.from_email
    domain = _from_domain()

    if not settings.resend_api_key:
        return EmailStatus(
            provider_configured=False,
            from_email=from_email,
            from_domain=domain,
            deliverable=False,
            detail="No email provider configured. Alerts are logged on the server instead of emailed.",
        )
    # Resend's shared test sender works, but only to the account owner's address.
    if domain == "resend.dev":
        return EmailStatus(
            True,
            from_email,
            domain,
            True,
            "Using Resend's test sender; delivery works only to your own Resend account email.",
        )
    verified, reason = _verified_domains()
    if verified is None:
        return EmailStatus(
            True,
            from_email,
            domain,
            False,
            f"Couldn't verify the sender domain with Resend ({reason}). Emails may be rejected.",
        )
    if domain in verified:
        return EmailStatus(
            True, from_email, domain, True, f"Sending from a verified domain ({domain})."
        )
    return EmailStatus(
        True,
        from_email,
        domain,
        False,
        f"The sender domain '{domain}' isn't verified on Resend, so emails will be "
        f"rejected. Verify it in Resend and point FROM_EMAIL at an address on that "
        f"domain, or use onboarding@resend.dev for testing.",
    )


def _send_email(to_email: str, subject: str, body: str) -> bool:
    if not settings.resend_api_key:
        logger.info("[dev email] to=%s subject=%s\n%s", to_email, subject, body)
        return True
    try:
        resp = httpx.post(
            "https://api.resend.com/emails",
            headers={"Authorization": f"Bearer {settings.resend_api_key}"},
            json={
                "from": settings.from_email,
                "to": [to_email],
                "subject": subject,
                "text": body,
            },
            timeout=15,
        )
        resp.raise_for_status()
        return True
    except httpx.HTTPStatusError as exc:  # pragma: no cover - network
        logger.warning(
            "Resend rejected email to %s (%s): %s",
            to_email,
            exc.response.status_code,
            exc.response.text[:300],
        )
        return False
    except Exception as exc:  # pragma: no cover - network
        logger.warning("Failed to send email to %s: %s", to_email, exc)
        return False


# --------------------------------------------------------------------------- #
# DB-backed senders
# --------------------------------------------------------------------------- #
@dataclass
class _Prefs:
    renewal_lead_days: int
    digest_enabled: bool
    trial_alerts: bool
    price_hike_alerts: bool
    budget_alerts: bool


def _prefs_for(db: Session, user: User) -> _Prefs:
    ns = db.get(NotificationSettings, user.id)
    if ns is not None:
        return _Prefs(
            renewal_lead_days=ns.renewal_lead_days,
            digest_enabled=ns.digest_enabled,
            trial_alerts=ns.trial_alerts,
            price_hike_alerts=ns.price_hike_alerts,
            budget_alerts=ns.budget_alerts,
        )
    # No row yet -> sensible defaults (all alerts on), lead days from the user.
    return _Prefs(
        renewal_lead_days=user.renewal_lead_days or settings.renewal_lead_days,
        digest_enabled=True,
        trial_alerts=True,
        price_hike_alerts=True,
        budget_alerts=True,
    )


def _sub_context(db: Session, sub_ids: list) -> dict:
    """Per-subscription charge context: ordered amounts and whether any charge
    carried a trial hint. Keyed by subscription id."""
    if not sub_ids:
        return {}
    rows = db.execute(
        select(
            SubscriptionTransaction.subscription_id,
            Transaction.amount,
            Transaction.trial_hint,
        )
        .join(Transaction, Transaction.id == SubscriptionTransaction.transaction_id)
        .where(SubscriptionTransaction.subscription_id.in_(sub_ids))
        .order_by(Transaction.occurred_at.asc())
    ).all()
    ctx: dict = {}
    for sub_id, amount, trial in rows:
        entry = ctx.setdefault(sub_id, {"amounts": [], "trial": False})
        entry["amounts"].append(amount)
        entry["trial"] = entry["trial"] or bool(trial)
    return ctx


def _pending_alert(
    db: Session, user_id, subscription_id, type_: str, scheduled_for
) -> Alert | None:
    """Return an Alert that still needs sending for this (subscription, type,
    cycle), or None if one was already sent. An existing but unsent row is
    reused so a previous send failure is retried on the next run."""
    existing = db.scalar(
        select(Alert).where(
            Alert.subscription_id == subscription_id,
            Alert.type == type_,
            Alert.scheduled_for == scheduled_for,
        )
    )
    if existing is not None:
        return None if existing.sent_at is not None else existing
    alert = Alert(
        user_id=user_id,
        subscription_id=subscription_id,
        type=type_,
        scheduled_for=scheduled_for,
        channel="email",
    )
    db.add(alert)
    db.flush()
    return alert


def _users(db: Session, only_user: User | None) -> list[User]:
    return [only_user] if only_user is not None else list(db.scalars(select(User)).all())


def send_due_reminders(db: Session, only_user: User | None = None) -> int:
    """Create and send reminders for subscriptions renewing within each user's
    lead window. A subscription whose charges carried a trial hint gets a
    trial-ending warning instead of a plain renewal reminder. Returns the number
    of emails sent."""
    now = datetime.now(timezone.utc)
    sent = 0

    for user in _users(db, only_user):
        prefs = _prefs_for(db, user)
        window_end = now + timedelta(days=prefs.renewal_lead_days)

        subs = db.scalars(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.status == "active",
                Subscription.next_renewal_at.is_not(None),
                Subscription.next_renewal_at <= window_end,
                Subscription.next_renewal_at >= now,
            )
        ).all()
        if not subs:
            continue

        ctx = _sub_context(db, [s.id for s in subs])
        for sub in subs:
            is_trial = ctx.get(sub.id, {}).get("trial", False)
            if is_trial and not prefs.trial_alerts:
                continue
            alert_type = "trial_ending" if is_trial else "renewal"
            alert = _pending_alert(
                db, user.id, sub.id, alert_type, sub.next_renewal_at
            )
            if alert is None:
                continue

            amount = _format_money(sub.amount, sub.currency)
            when = sub.next_renewal_at.strftime("%d %b %Y")
            builder = trial_email if is_trial else renewal_email
            subject, body = builder(sub.merchant_name, when, amount)
            if _send_email(user.email, subject, body):
                alert.sent_at = datetime.now(timezone.utc)
                sent += 1

        db.commit()

    return sent


def send_price_hike_alerts(db: Session, only_user: User | None = None) -> int:
    """Notify users whose active subscriptions show a price increase. Deduped on
    the latest charge date so each hike is only sent once. Returns emails sent."""
    sent = 0

    for user in _users(db, only_user):
        prefs = _prefs_for(db, user)
        if not prefs.price_hike_alerts:
            continue

        subs = db.scalars(
            select(Subscription).where(
                Subscription.user_id == user.id,
                Subscription.status == "active",
            )
        ).all()
        if not subs:
            continue

        ctx = _sub_context(db, [s.id for s in subs])
        for sub in subs:
            amounts = ctx.get(sub.id, {}).get("amounts") or []
            change = price_change(amounts)
            if change is None:
                continue
            old, new = change
            key_dt = sub.last_charge_at or datetime.now(timezone.utc)
            alert = _pending_alert(db, user.id, sub.id, "price_hike", key_dt)
            if alert is None:
                continue

            subject, body = price_hike_email(
                sub.merchant_name,
                _format_money(old, sub.currency),
                _format_money(new, sub.currency),
            )
            if _send_email(user.email, subject, body):
                alert.sent_at = datetime.now(timezone.utc)
                sent += 1

        db.commit()

    return sent


def send_weekly_digests(db: Session, only_user: User | None = None) -> int:
    """Send each opted-in user a summary of renewals in the next 7 days. Digests
    aren't deduped via Alert rows (they have no single subscription); the weekly
    beat cadence is the dedupe. Returns the number of digests sent."""
    now = datetime.now(timezone.utc)
    week_end = now + timedelta(days=7)
    sent = 0

    for user in _users(db, only_user):
        prefs = _prefs_for(db, user)
        if not prefs.digest_enabled:
            continue

        subs = db.scalars(
            select(Subscription)
            .where(
                Subscription.user_id == user.id,
                Subscription.status == "active",
                Subscription.next_renewal_at.is_not(None),
                Subscription.next_renewal_at >= now,
                Subscription.next_renewal_at <= week_end,
            )
            .order_by(Subscription.next_renewal_at.asc())
        ).all()

        items = [
            DigestItem(
                name=s.merchant_name,
                when=s.next_renewal_at,
                amount=s.amount,
                currency=s.currency,
            )
            for s in subs
        ]
        built = build_digest(items)
        if built is None:
            continue
        subject, body = built
        if _send_email(user.email, subject, body):
            sent += 1

    return sent


def _category_spend(db: Session, user_id) -> dict[str, Decimal]:
    """Current monthly-equivalent spend per category (lowercased key) from the
    user's active subscriptions."""
    subs = db.scalars(
        select(Subscription).where(
            Subscription.user_id == user_id, Subscription.status == "active"
        )
    ).all()
    spend: dict[str, Decimal] = {}
    for s in subs:
        key = (s.category or "").strip().lower()
        spend[key] = spend.get(key, Decimal("0")) + insights.monthly_equivalent(
            s.amount, s.cadence
        )
    return spend


def _pending_category_alert(
    db: Session, user_id, type_: str, category: str, scheduled_for
) -> Alert | None:
    """Like _pending_alert, but keyed on a category instead of a subscription,
    for alerts (budget_over) that aren't tied to one subscription."""
    existing = db.scalar(
        select(Alert).where(
            Alert.user_id == user_id,
            Alert.type == type_,
            Alert.category == category,
            Alert.scheduled_for == scheduled_for,
        )
    )
    if existing is not None:
        return None if existing.sent_at is not None else existing
    alert = Alert(
        user_id=user_id,
        subscription_id=None,
        category=category,
        type=type_,
        scheduled_for=scheduled_for,
        channel="email",
    )
    db.add(alert)
    db.flush()
    return alert


def send_budget_alerts(db: Session, only_user: User | None = None) -> int:
    """Email users whose current recurring spend in a category exceeds its
    budget. Deduped to once per category per month. Returns emails sent."""
    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    sent = 0

    for user in _users(db, only_user):
        prefs = _prefs_for(db, user)
        if not prefs.budget_alerts:
            continue

        budgets = db.scalars(select(Budget).where(Budget.user_id == user.id)).all()
        if not budgets:
            continue

        spend = _category_spend(db, user.id)
        for budget in budgets:
            spent = spend.get(budget.category.strip().lower(), Decimal("0"))
            if spent <= budget.monthly_limit:
                continue
            alert = _pending_category_alert(
                db, user.id, "budget_over", budget.category, month_start
            )
            if alert is None:
                continue

            subject, body = budget_email(
                budget.category,
                _format_money(spent.quantize(Decimal("0.01")), budget.currency),
                _format_money(budget.monthly_limit, budget.currency),
            )
            if _send_email(user.email, subject, body):
                alert.sent_at = datetime.now(timezone.utc)
                sent += 1

        db.commit()

    return sent
