from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class ConnectionOut(BaseModel):
    id: UUID
    type: str
    status: str
    last_synced_at: datetime | None
    sync_status: str
    sync_total: int
    sync_done: int
    sync_error: str | None
    sync_days: int | None

    class Config:
        from_attributes = True


class ConnectionListResponse(BaseModel):
    connections: list[ConnectionOut]


class OAuthUrlResponse(BaseModel):
    url: str


class SyncResponse(BaseModel):
    status: str
