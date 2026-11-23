from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AlertOut(BaseModel):
    id: UUID
    subscription_id: UUID | None
    category: str | None
    type: str
    scheduled_for: datetime
    sent_at: datetime | None
    channel: str

    class Config:
        from_attributes = True


class AlertListResponse(BaseModel):
    alerts: list[AlertOut]


class AlertSettingsUpdate(BaseModel):
    """Partial update: only provided fields are changed."""

    renewal_lead_days: int | None = Field(default=None, ge=0, le=30)
    digest_enabled: bool | None = None
    trial_alerts: bool | None = None
    price_hike_alerts: bool | None = None
    budget_alerts: bool | None = None


class AlertSettingsResponse(BaseModel):
    renewal_lead_days: int
    digest_enabled: bool
    trial_alerts: bool
    price_hike_alerts: bool
    budget_alerts: bool


class AlertRunResponse(BaseModel):
    reminders: int
    price_hikes: int
    digests: int
    budget_overages: int
    email_configured: bool
    email_detail: str


class EmailStatusResponse(BaseModel):
    provider_configured: bool
    from_email: str
    from_domain: str
    deliverable: bool
    detail: str
