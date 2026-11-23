# Subscription Auditor

Find the money leaking out of your bank account. Subscription Auditor connects to a user's email (and later their bank via India's Account Aggregator framework), discovers every recurring charge, surfaces the forgotten ones, and reminds them before each renewal so they can cancel what they no longer use.

> "Wait, I'm paying for THAT?" - that reaction is the product.

---

## Why this project

- **Pays now:** The value is literally money saved. Users happily pay a small monthly fee (or a cut of savings) for a tool that finds forgotten subscriptions.
- **Can be big:** It is fintech. It starts as a simple subscription dashboard and expands into a full personal-finance product (budgeting, bill negotiation, spending insights). Companies like Rocket Money / Truebill proved this in the US; there is no strong Indian equivalent yet, and the Account Aggregator framework makes the timing right.

---

## What it does (end state)

1. **Discovers** all recurring charges from email receipts and/or bank transactions.
2. **Shows** a dashboard: "You are paying Rs 4,380/month across 11 subscriptions."
3. **Flags** the suspicious ones: unused, trial-about-to-convert, price hikes.
4. **Reminds** before renewals and helps the user cancel.

---

## Tech stack

| Layer | Choice |
|---|---|
| Frontend | Next.js (React) + Tailwind |
| Backend | Python FastAPI (REST) |
| ORM / migrations | SQLAlchemy + Alembic |
| Database | PostgreSQL |
| Async / jobs | Celery + Redis (+ Celery Beat for scheduled scans) |
| LLM | OpenAI / Claude (merchant cleanup, cached, with rule-based fallback) |
| Email | Resend or AWS SES |
| Auth | JWT (email + password) |
| Local infra | docker-compose (Postgres + Redis) |

---

## Documentation map

Start here, then follow the links based on what you need.

| Document | What it covers |
|---|---|
| [docs/ROADMAP.md](docs/ROADMAP.md) | All three phases at a glance and how they build on each other |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | System architecture, components, and diagrams |
| [docs/PROJECT_STRUCTURE.md](docs/PROJECT_STRUCTURE.md) | Full folder and file layout, explained |
| [docs/DATA_MODEL.md](docs/DATA_MODEL.md) | Database schema and table-by-table reference |
| [docs/PIPELINE.md](docs/PIPELINE.md) | The ingest -> detect -> enrich -> alert pipeline in detail |
| [docs/API.md](docs/API.md) | REST API endpoint reference |
| [docs/SECURITY.md](docs/SECURITY.md) | Security, privacy, and compliance (this is financial data) |
| [docs/phases/PHASE_1_MVP.md](docs/phases/PHASE_1_MVP.md) | Phase 1: Gmail-based MVP (build this first) |
| [docs/phases/PHASE_2_RETENTION.md](docs/phases/PHASE_2_RETENTION.md) | Phase 2: retention and trust features |
| [docs/phases/PHASE_3_SCALE.md](docs/phases/PHASE_3_SCALE.md) | Phase 3: Account Aggregator and scale |

---

## Core design principle

**Data sources are pluggable.** Gmail receipts (Phase 1) and bank transactions via Account Aggregator (Phase 3) both normalize into the same `transactions` table. The detection engine never cares where the data came from, so growing from the MVP to the full product requires no rewrite of the core.

---

## Running locally

### Prerequisites
- Docker (for Postgres + Redis)
- Python 3.11+
- Node 18+

### 1. Environment
```bash
cp .env.example .env
# Generate a token encryption key and paste it into TOKEN_ENCRYPTION_KEY:
python -c "import os,base64;print(base64.b64encode(os.urandom(32)).decode())"
```
Gmail connect and email sending are optional for local dev: without Google
credentials you can still sign up, log in, and explore the UI; without a Resend
key, reminder emails are logged to the worker console instead of being sent.

### 2. Infrastructure
```bash
cd infra
docker compose up -d        # starts Postgres on 5432 and Redis on 6379
```

### 3. Backend
```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
alembic upgrade head        # create the schema
uvicorn app.main:app --reload --port 8000
```

In two more terminals (same venv), start the worker and scheduler:
```bash
celery -A app.workers.celery_app worker --loglevel=info      # background jobs
celery -A app.workers.celery_app beat --loglevel=info        # nightly renewal scan
```

### 4. Frontend
```bash
cd frontend
npm install
npm run dev                 # http://localhost:3000
```

### 5. Tests
```bash
cd backend
pytest                      # exercises the detection engine and the receipt parser
```

### Gmail setup (optional, for real ingestion)
1. In Google Cloud Console, create an OAuth client (type: Web application).
2. Add the redirect URI `http://localhost:8000/connections/gmail/callback`.
3. Enable the Gmail API and add yourself as a test user.
4. Put the client id/secret in `.env` (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`).

Note: the Gmail `readonly` scope is a restricted scope. Running in "testing"
mode (up to 100 manually added users) needs no verification; a public launch
requires Google OAuth verification. See [docs/SECURITY.md](docs/SECURITY.md).

---

## Current status

Phase 1 MVP implemented: auth, Gmail OAuth ingestion, the recurrence-detection
engine, merchant enrichment, the dashboard, and nightly renewal reminders. See
[docs/phases/PHASE_1_MVP.md](docs/phases/PHASE_1_MVP.md) for scope and the
definition of done, and [docs/ROADMAP.md](docs/ROADMAP.md) for what comes next.
