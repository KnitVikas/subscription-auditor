from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import (
    account,
    alerts,
    auth,
    budgets,
    cancel_guides,
    connections,
    insights,
    subscriptions,
    transactions,
)
from app.core.config import settings

app = FastAPI(title="Subscription Auditor API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def _startup() -> None:
    # For local SQLite dev, create tables on boot (Alembic targets Postgres).
    if settings.database_url.startswith("sqlite"):
        from app.core.db import init_db

        init_db()


app.include_router(auth.router)
app.include_router(connections.router)
app.include_router(subscriptions.router)
app.include_router(transactions.router)
app.include_router(cancel_guides.router)
app.include_router(alerts.router)
app.include_router(insights.router)
app.include_router(budgets.router)
app.include_router(account.router)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
