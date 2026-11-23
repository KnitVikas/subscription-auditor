from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.models import Alert, NotificationSettings, User
from app.schemas.alert import (
    AlertListResponse,
    AlertRunResponse,
    AlertSettingsResponse,
    AlertSettingsUpdate,
    EmailStatusResponse,
)
from app.services import alerts as alerts_service

router = APIRouter(prefix="/alerts", tags=["alerts"])


def _get_or_create_settings(db: Session, user: User) -> NotificationSettings:
    ns = db.get(NotificationSettings, user.id)
    if ns is None:
        ns = NotificationSettings(
            user_id=user.id,
            renewal_lead_days=user.renewal_lead_days or settings.renewal_lead_days,
        )
        db.add(ns)
        db.commit()
        db.refresh(ns)
    return ns


def _settings_response(ns: NotificationSettings) -> AlertSettingsResponse:
    return AlertSettingsResponse(
        renewal_lead_days=ns.renewal_lead_days,
        digest_enabled=ns.digest_enabled,
        trial_alerts=ns.trial_alerts,
        price_hike_alerts=ns.price_hike_alerts,
        budget_alerts=ns.budget_alerts,
    )


@router.get("", response_model=AlertListResponse)
def list_alerts(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AlertListResponse:
    alerts = db.scalars(
        select(Alert).where(Alert.user_id == user.id).order_by(Alert.scheduled_for.desc())
    ).all()
    return AlertListResponse(alerts=alerts)


@router.get("/settings", response_model=AlertSettingsResponse)
def get_settings(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AlertSettingsResponse:
    return _settings_response(_get_or_create_settings(db, user))


@router.patch("/settings", response_model=AlertSettingsResponse)
def update_settings(
    payload: AlertSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AlertSettingsResponse:
    ns = _get_or_create_settings(db, user)
    if payload.renewal_lead_days is not None:
        ns.renewal_lead_days = payload.renewal_lead_days
        user.renewal_lead_days = payload.renewal_lead_days  # keep fallback in sync
    if payload.digest_enabled is not None:
        ns.digest_enabled = payload.digest_enabled
    if payload.trial_alerts is not None:
        ns.trial_alerts = payload.trial_alerts
    if payload.price_hike_alerts is not None:
        ns.price_hike_alerts = payload.price_hike_alerts
    if payload.budget_alerts is not None:
        ns.budget_alerts = payload.budget_alerts
    db.commit()
    db.refresh(ns)
    return _settings_response(ns)


@router.get("/email-status", response_model=EmailStatusResponse)
def email_status(user: User = Depends(get_current_user)) -> EmailStatusResponse:
    """Report whether alert emails will actually be delivered, based on the
    configured provider key and whether FROM_EMAIL's domain is verified."""
    status = alerts_service.email_status()
    return EmailStatusResponse(
        provider_configured=status.provider_configured,
        from_email=status.from_email,
        from_domain=status.from_domain,
        deliverable=status.deliverable,
        detail=status.detail,
    )


@router.post("/run-now", response_model=AlertRunResponse)
def run_now(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> AlertRunResponse:
    """Run all alert checks for the current user immediately and report what was
    sent. Useful in local dev (where the nightly/weekly beat doesn't run) and as
    a manual 'send me what's due now'. Without a deliverable email setup,
    messages are logged instead of emailed."""
    reminders = alerts_service.send_due_reminders(db, only_user=user)
    price_hikes = alerts_service.send_price_hike_alerts(db, only_user=user)
    digests = alerts_service.send_weekly_digests(db, only_user=user)
    budget_overages = alerts_service.send_budget_alerts(db, only_user=user)
    status = alerts_service.email_status()
    return AlertRunResponse(
        reminders=reminders,
        price_hikes=price_hikes,
        digests=digests,
        budget_overages=budget_overages,
        email_configured=status.deliverable,
        email_detail=status.detail,
    )
