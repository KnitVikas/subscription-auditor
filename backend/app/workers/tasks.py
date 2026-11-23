"""Celery tasks: ingest_gmail, detect_subscriptions, scan_renewals.

These are the orchestration layer. They own DB sessions and call the pure
services (gmail, detection, enrichment, alerts) to do the actual work.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import decrypt_token
from app.models import (
    Connection,
    Correction,
    Subscription,
    SubscriptionTransaction,
    Transaction,
)
from app.services import alerts, detection, enrichment, gmail
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def _update_connection_sync(connection_id: str, **fields) -> None:
    """Update a connection's sync_* columns in a short-lived session, so a
    long-running scan can report progress that pollers see immediately."""
    session = SessionLocal()
    try:
        conn = session.get(Connection, UUID(connection_id))
        if conn is not None:
            for key, value in fields.items():
                setattr(conn, key, value)
            session.commit()
    finally:
        session.close()


@celery_app.task(name="app.workers.tasks.ingest_gmail")
def ingest_gmail(connection_id: str, days: int | None = None) -> dict:
    """Pull receipt emails from the last `days` days for a connection into
    transactions, then rebuild that user's subscriptions."""
    db = SessionLocal()
    try:
        connection = db.get(Connection, UUID(connection_id))
        if connection is None or connection.status != "active":
            return {"status": "skipped", "reason": "connection missing/inactive"}

        access_token = decrypt_token(connection.access_token_enc)
        refresh_token = decrypt_token(connection.refresh_token_enc)

        days = gmail.clamp_scan_days(days)
        # Mark the sync running before the slow fetch. Commit releases the
        # write lock so progress updates (separate sessions) don't contend.
        connection.sync_status = "running"
        connection.sync_days = days
        connection.sync_done = 0
        connection.sync_total = 0
        connection.sync_error = None
        db.commit()

        progress = {"total": 0}
        reported = {"done": -1}

        def on_progress(done: int, total: int) -> None:
            progress["total"] = total
            step = max(10, total // 20) if total else 1
            if done != total and done - reported["done"] < step:
                return
            reported["done"] = done
            _update_connection_sync(
                connection_id, sync_status="running", sync_done=done, sync_total=total
            )

        try:
            receipts = list(
                gmail.fetch_receipts(
                    access_token, refresh_token, days=days, on_progress=on_progress
                )
            )
        except Exception as exc:  # noqa: BLE001 - surface any fetch failure to the UI
            logger.exception("Gmail sync failed for connection %s", connection_id)
            _update_connection_sync(
                connection_id, sync_status="failed", sync_error=str(exc)[:500]
            )
            return {"status": "failed", "error": str(exc)[:500]}

        # Each scan replaces this connection's charges, so results reflect the
        # selected range and the current parsing rules. Nothing is committed
        # if the fetch above fails.
        for old in db.scalars(
            select(Transaction).where(Transaction.connection_id == connection.id)
        ).all():
            db.delete(old)
        db.flush()

        inserted = 0
        seen_refs: set[str] = set()
        for receipt in receipts:
            if receipt.raw_ref in seen_refs:
                continue
            seen_refs.add(receipt.raw_ref)
            db.add(
                Transaction(
                    user_id=connection.user_id,
                    connection_id=connection.id,
                    source="gmail",
                    raw_merchant=receipt.raw_merchant,
                    amount=receipt.amount,
                    currency=receipt.currency,
                    occurred_at=receipt.occurred_at,
                    raw_ref=receipt.raw_ref,
                    sender_domain=receipt.sender_domain,
                    recurring_hint=receipt.recurring_hint,
                    cadence_hint=receipt.cadence_hint,
                    renews_at_hint=receipt.renews_at_hint,
                    trial_hint=receipt.trial_hint,
                )
            )
            inserted += 1

        connection.last_synced_at = datetime.now(timezone.utc)
        connection.sync_status = "done"
        connection.sync_total = progress["total"]
        connection.sync_done = progress["total"]
        connection.sync_error = None
        db.commit()

        detect_subscriptions.delay(str(connection.user_id))
        return {"status": "ok", "inserted": inserted, "days": days}
    except Exception as exc:  # noqa: BLE001 - mark sync failed, don't crash caller
        logger.exception("Gmail ingest failed for connection %s", connection_id)
        db.rollback()
        _update_connection_sync(
            connection_id, sync_status="failed", sync_error=str(exc)[:500]
        )
        return {"status": "failed", "error": str(exc)[:500]}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.detect_subscriptions")
def detect_subscriptions(user_id: str) -> dict:
    """Run the recurrence engine over a user's transactions and upsert
    subscriptions."""
    db = SessionLocal()
    try:
        uid = UUID(user_id)
        txns = db.scalars(
            select(Transaction).where(Transaction.user_id == uid)
        ).all()

        inputs = [
            detection.TxnInput(
                id=str(t.id),
                raw_merchant=t.raw_merchant,
                amount=t.amount,
                currency=t.currency,
                occurred_at=t.occurred_at,
                sender_domain=t.sender_domain,
                recurring_hint=t.recurring_hint,
                cadence_hint=t.cadence_hint,
                renews_at_hint=t.renews_at_hint,
                trial_hint=t.trial_hint,
            )
            for t in txns
        ]
        candidates = detection.detect_subscriptions(inputs)

        # User corrections, keyed by merchant so they reapply across rebuilds.
        corrections: dict[str, dict[str, str]] = {}
        for c in db.scalars(select(Correction).where(Correction.user_id == uid)).all():
            corrections.setdefault(c.merchant_key, {})[c.field] = c.value

        # Rebuild subscriptions for this user from scratch (idempotent).
        existing = db.scalars(
            select(Subscription).where(Subscription.user_id == uid)
        ).all()
        preserved_status = {s.merchant_key: s.status for s in existing}
        for s in existing:
            db.delete(s)
        db.flush()

        for cand in candidates:
            overrides = corrections.get(cand.merchant_key, {})
            # A user who marked this "not a subscription" should never see it again.
            if overrides.get("not_subscription") == "true":
                continue

            enriched = enrichment.enrich(cand.merchant_key, cand.raw_merchant)
            # Keep a user-set 'cancelled'/'ignored' status across rebuilds.
            prior = preserved_status.get(cand.merchant_key)
            status = prior if prior in ("cancelled", "ignored") else cand.status

            sub = Subscription(
                user_id=uid,
                merchant_key=cand.merchant_key,
                merchant_name=overrides.get("merchant_name", enriched.merchant_name),
                category=overrides.get("category") or enriched.category,
                logo_url=enriched.logo_url,
                amount=Decimal(overrides["amount"]) if "amount" in overrides else cand.amount,
                currency=cand.currency,
                cadence=overrides.get("cadence", cand.cadence),
                first_seen_at=cand.first_seen_at,
                last_charge_at=cand.last_charge_at,
                next_renewal_at=cand.next_renewal_at,
                status=status,
                confidence_score=cand.confidence_score,
            )
            db.add(sub)
            db.flush()
            for txn_id in cand.transaction_ids:
                db.add(
                    SubscriptionTransaction(
                        subscription_id=sub.id, transaction_id=UUID(txn_id)
                    )
                )
        db.commit()
        return {"status": "ok", "subscriptions": len(candidates)}
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.scan_renewals")
def scan_renewals() -> dict:
    """Nightly: send renewal/trial reminders for upcoming renewals, notices for
    any detected price hikes, and over-budget warnings."""
    db = SessionLocal()
    try:
        reminders = alerts.send_due_reminders(db)
        price_hikes = alerts.send_price_hike_alerts(db)
        budget_overages = alerts.send_budget_alerts(db)
        return {
            "status": "ok",
            "reminders": reminders,
            "price_hikes": price_hikes,
            "budget_overages": budget_overages,
        }
    finally:
        db.close()


@celery_app.task(name="app.workers.tasks.weekly_digest")
def weekly_digest() -> dict:
    """Weekly: email each opted-in user a summary of the coming week's renewals."""
    db = SessionLocal()
    try:
        sent = alerts.send_weekly_digests(db)
        return {"status": "ok", "digests": sent}
    finally:
        db.close()
