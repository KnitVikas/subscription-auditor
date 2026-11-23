import logging
import secrets
from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import settings
from app.core.db import get_db
from app.core.security import decode_access_token, encrypt_token
from app.models import Connection, User
from app.schemas.connection import (
    ConnectionListResponse,
    ConnectionOut,
    OAuthUrlResponse,
    SyncResponse,
)
from app.services import gmail

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/connections", tags=["connections"])


def _trigger_sync(background_tasks: BackgroundTasks, connection_id: str, days: int) -> None:
    """Run the sync out of band. In eager (local) mode Celery would run inline
    and block the request, so use FastAPI background tasks instead; otherwise
    dispatch to the Celery worker."""
    from app.workers.tasks import ingest_gmail

    if settings.celery_eager:
        background_tasks.add_task(ingest_gmail, connection_id, days)
    else:
        ingest_gmail.delay(connection_id, days)


@router.get("", response_model=ConnectionListResponse)
def list_connections(
    user: User = Depends(get_current_user), db: Session = Depends(get_db)
) -> ConnectionListResponse:
    connections = db.scalars(
        select(Connection).where(Connection.user_id == user.id)
    ).all()
    return ConnectionListResponse(
        connections=[ConnectionOut.model_validate(c) for c in connections]
    )


@router.get("/gmail/url", response_model=OAuthUrlResponse)
def gmail_url(
    days: int = Query(settings.gmail_scan_days, ge=1, le=settings.gmail_scan_max_days),
    user: User = Depends(get_current_user),
) -> OAuthUrlResponse:
    if not settings.google_client_id:
        raise HTTPException(status_code=503, detail="Google OAuth is not configured")
    # Encode the user id into a signed state token (reuses the JWT signer) plus
    # a random nonce for CSRF protection and the requested scan range.
    from app.core.security import create_access_token

    state = f"{create_access_token(str(user.id))}:{secrets.token_urlsafe(16)}:{days}"
    return OAuthUrlResponse(url=gmail.get_authorization_url(state))


@router.get("/gmail/callback")
def gmail_callback(
    background_tasks: BackgroundTasks,
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> RedirectResponse:
    token_part, *rest = state.split(":")
    subject = decode_access_token(token_part)
    days = gmail.clamp_scan_days(int(rest[1]) if len(rest) > 1 and rest[1].isdigit() else None)
    if subject is None:
        raise HTTPException(status_code=400, detail="Invalid OAuth state")
    user = db.get(User, UUID(subject))
    if user is None:
        raise HTTPException(status_code=400, detail="Unknown user in state")

    tokens = gmail.exchange_code(code)
    expiry = tokens.get("expiry")
    if expiry is not None and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)

    connection = db.scalar(
        select(Connection).where(Connection.user_id == user.id, Connection.type == "gmail")
    )
    if connection is None:
        connection = Connection(user_id=user.id, type="gmail")
        db.add(connection)
    connection.access_token_enc = encrypt_token(tokens["access_token"])
    if tokens.get("refresh_token") or connection.refresh_token_enc is None:
        connection.refresh_token_enc = encrypt_token(tokens.get("refresh_token"))
    connection.expires_at = expiry
    connection.status = "active"
    # Mark running immediately so the dashboard shows progress without a gap.
    connection.sync_status = "running"
    connection.sync_days = days
    connection.sync_done = 0
    connection.sync_total = 0
    connection.sync_error = None
    db.commit()
    db.refresh(connection)

    # Start the first sync out of band and return right away.
    _trigger_sync(background_tasks, str(connection.id), days)

    return RedirectResponse(url=f"{settings.frontend_url}/dashboard?syncing=1")


@router.post("/{connection_id}/sync", response_model=SyncResponse, status_code=status.HTTP_202_ACCEPTED)
def sync_connection(
    connection_id: UUID,
    background_tasks: BackgroundTasks,
    days: int = Query(settings.gmail_scan_days, ge=1, le=settings.gmail_scan_max_days),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SyncResponse:
    connection = db.scalar(
        select(Connection).where(
            Connection.id == connection_id, Connection.user_id == user.id
        )
    )
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")

    connection.sync_status = "running"
    connection.sync_days = days
    connection.sync_done = 0
    connection.sync_total = 0
    connection.sync_error = None
    db.commit()

    _trigger_sync(background_tasks, str(connection.id), days)
    return SyncResponse(status="queued")


@router.delete("/{connection_id}", status_code=status.HTTP_204_NO_CONTENT)
def disconnect(
    connection_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    connection = db.scalar(
        select(Connection).where(
            Connection.id == connection_id, Connection.user_id == user.id
        )
    )
    if connection is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    # Deleting the connection cascades to its transactions. Derived
    # subscriptions for this user are removed too (rebuilt on next sync).
    from app.models import Subscription

    for sub in db.scalars(select(Subscription).where(Subscription.user_id == user.id)).all():
        db.delete(sub)
    db.delete(connection)
    db.commit()
