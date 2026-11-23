# Project Structure

The complete folder and file layout for Subscription Auditor, with an explanation of what lives where and why. The structure is a monorepo: a Next.js `frontend` and a Python FastAPI `backend`, plus local `infra`.

Related reading: [ARCHITECTURE.md](ARCHITECTURE.md), [DATA_MODEL.md](DATA_MODEL.md).

---

## Top-level layout

```
subscription-auditor/
  README.md                  Project overview and doc map
  docs/                      All documentation (this folder)
  frontend/                  Next.js (React) web app
  backend/                   Python FastAPI app + workers
  infra/                     docker-compose and local infra config
  .env.example               Sample environment variables
  .gitignore
```

---

## Frontend (`frontend/`)

```
frontend/
  app/                       Next.js App Router routes
    layout.tsx
    page.tsx                 Landing / redirect
    login/page.tsx
    signup/page.tsx
    connect/page.tsx         "Connect Gmail" flow
    dashboard/page.tsx       Spend summary + subscription list
    subscriptions/[id]/page.tsx   Subscription detail
    settings/page.tsx        Alert + account settings
  components/
    SpendSummary.tsx         Total monthly/yearly spend card
    SubscriptionCard.tsx     One subscription row/card
    SubscriptionList.tsx
    ConnectGmailButton.tsx
    AlertBadge.tsx
  lib/
    api.ts                   Typed REST client (attaches JWT)
    auth.ts                  Token storage + auth helpers
    format.ts                Currency/date formatting
  styles/
    globals.css              Tailwind entry
  package.json
  next.config.js
  tailwind.config.js
  tsconfig.json
```

Why: the App Router keeps routes and UI colocated. `lib/api.ts` is the single place that knows how to talk to the backend, so auth and base-URL logic are not scattered.

---

## Backend (`backend/`)

```
backend/
  app/
    main.py                  FastAPI entrypoint, router registration, CORS
    core/
      config.py              Settings (env-driven, pydantic-settings)
      db.py                  SQLAlchemy engine + session dependency
      security.py            Password hashing, JWT, AES-GCM token encryption
    models/                  SQLAlchemy ORM models (one concern per file)
      user.py
      connection.py
      transaction.py
      subscription.py
      alert.py
    schemas/                 Pydantic request/response DTOs
      auth.py
      connection.py
      subscription.py
      alert.py
    api/                     FastAPI routers (HTTP layer)
      deps.py                Shared dependencies (current user, db session)
      auth.py                /auth/*
      connections.py         /connections/*
      subscriptions.py       /subscriptions/*
      alerts.py              /alerts/*
    services/                Business logic (importable by API + workers)
      gmail.py               OAuth + receipt search/parse
      detection.py           Pure recurrence-detection engine
      enrichment.py          Merchant cleanup + category + logo
      alerts.py              Reminder scheduling + sending
    workers/
      celery_app.py          Celery + Beat configuration
      tasks.py               ingest_gmail, detect_subscriptions, scan_renewals
  alembic/
    env.py
    versions/                Migration files
  tests/
    test_detection.py        Unit tests for the recurrence engine
    test_gmail_parse.py
  pyproject.toml             Dependencies + tooling config
  alembic.ini
```

Why this split:
- **`api/` is thin** - routers validate input and call services. No business logic lives in HTTP handlers.
- **`services/` is reusable** - both the API (e.g. trigger a sync) and the workers (e.g. run the sync) import the same functions.
- **`detection.py` is pure** - no DB or network calls inside the core algorithm, so it is trivially unit-testable (`tests/test_detection.py`).
- **`models/` vs `schemas/`** - ORM models (database shape) are kept separate from Pydantic DTOs (API shape) so the two can evolve independently.

---

## Infra (`infra/`)

```
infra/
  docker-compose.yml         Local Postgres + Redis
  postgres/
    init.sql                 Optional seed / extensions
```

`docker-compose up` gives you Postgres and Redis locally so the backend and workers can run against real services.

---

## Environment variables (`.env.example`)

```
# Database
DATABASE_URL=postgresql+psycopg://user:pass@localhost:5432/subscription_auditor

# Redis / Celery
REDIS_URL=redis://localhost:6379/0

# Auth
JWT_SECRET=change-me
JWT_EXPIRE_MINUTES=10080

# Token encryption (AES-GCM key, base64, 32 bytes)
TOKEN_ENCRYPTION_KEY=change-me

# Google OAuth (Gmail read-only)
GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=
GOOGLE_REDIRECT_URI=http://localhost:8000/connections/gmail/callback

# LLM (optional; rule-based fallback used if absent)
OPENAI_API_KEY=

# Email provider
RESEND_API_KEY=
FROM_EMAIL=alerts@subscription-auditor.app

# Frontend
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
```

---

## Where each phase adds code

| Phase | New code mostly lands in |
|---|---|
| Phase 1 (MVP) | everything above |
| Phase 2 (retention) | `services/classification.py`, `services/cancel_guides.py`, `services/notifications/` (email, WhatsApp, push), `services/billing.py` |
| Phase 3 (scale) | `services/account_aggregator.py` feeding the same `transactions` table, `services/merge.py`, `services/insights.py`, `services/budgets.py`, and a new `mobile/` app |

See [ROADMAP.md](ROADMAP.md) for the phase breakdown.
