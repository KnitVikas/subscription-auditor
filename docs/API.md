# API Reference

REST API for Subscription Auditor, served by FastAPI. All endpoints except auth require a `Authorization: Bearer <jwt>` header.

Base URL (local): `http://localhost:8000`

Related reading: [ARCHITECTURE.md](ARCHITECTURE.md), [DATA_MODEL.md](DATA_MODEL.md).

---

## Conventions

- All request/response bodies are JSON.
- Timestamps are ISO 8601 UTC.
- Money is returned as `{ "amount": "199.00", "currency": "INR" }`.
- Errors use standard HTTP codes with a body `{ "detail": "message" }`.

---

## Auth

### POST /auth/signup
Create an account.

Request:
```json
{ "email": "user@example.com", "password": "secret123" }
```
Response `201`:
```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```

### POST /auth/login
Request:
```json
{ "email": "user@example.com", "password": "secret123" }
```
Response `200`:
```json
{ "access_token": "<jwt>", "token_type": "bearer" }
```

---

## Connections

### GET /connections/gmail/url
Returns the Google OAuth consent URL (read-only Gmail scope). The frontend redirects the user here.

Response `200`:
```json
{ "url": "https://accounts.google.com/o/oauth2/v2/auth?..." }
```

### GET /connections/gmail/callback
OAuth redirect target. Exchanges the `code` for tokens, encrypts and stores them, creates a `connection`, and enqueues the first `ingest_gmail` job. Redirects back to the frontend `connect` screen.

Query params: `code`, `state`.

### POST /connections/{id}/sync
Manually trigger a re-scan of a connection (enqueues `ingest_gmail`).

Response `202`:
```json
{ "status": "queued" }
```

### DELETE /connections/{id}
Disconnect a source. Revokes tokens and cascade-deletes all transactions/subscriptions derived from it.

Response `204`.

---

## Subscriptions

### GET /subscriptions
List the user's detected subscriptions plus spend totals.

Response `200`:
```json
{
  "totals": {
    "monthly": "4380.00",
    "yearly": "52560.00",
    "currency": "INR",
    "count": 11
  },
  "subscriptions": [
    {
      "id": "…",
      "merchant_name": "Netflix",
      "category": "Entertainment",
      "logo_url": "…",
      "amount": "199.00",
      "currency": "INR",
      "cadence": "monthly",
      "next_renewal_at": "2026-12-01T00:00:00Z",
      "status": "active",
      "confidence_score": 0.95
    }
  ]
}
```

### GET /subscriptions/{id}
Detail for one subscription, including its charge history (from `subscription_transactions`).

Response `200`:
```json
{
  "id": "…",
  "merchant_name": "Netflix",
  "amount": "199.00",
  "currency": "INR",
  "cadence": "monthly",
  "status": "active",
  "history": [
    { "occurred_at": "2026-11-01T00:00:00Z", "amount": "199.00" },
    { "occurred_at": "2026-10-01T00:00:00Z", "amount": "149.00" }
  ]
}
```

### PATCH /subscriptions/{id}
Update user-controlled status (e.g. mark cancelled or ignore).

Request:
```json
{ "status": "cancelled" }
```
Response `200`: updated subscription.

---

## Alerts

### GET /alerts
Upcoming and recent alerts for the user.

Response `200`:
```json
{
  "alerts": [
    {
      "id": "…",
      "subscription_id": "…",
      "type": "renewal",
      "scheduled_for": "2026-11-29T09:00:00Z",
      "sent_at": null,
      "channel": "email"
    }
  ]
}
```

### PATCH /alerts/settings
Update reminder preferences (lead time, channel).

Request:
```json
{ "renewal_lead_days": 2, "channel": "email" }
```
Response `200`: updated settings.

---

## Account

### DELETE /account
Hard-delete the account and all associated data (cascades through all tables). Required for trust and Google OAuth verification.

Response `204`.

---

## Endpoint summary

| Method | Path | Purpose |
|---|---|---|
| POST | /auth/signup | Create account |
| POST | /auth/login | Log in |
| GET | /connections/gmail/url | Get OAuth consent URL |
| GET | /connections/gmail/callback | OAuth callback |
| POST | /connections/{id}/sync | Re-scan a source |
| DELETE | /connections/{id} | Disconnect a source |
| GET | /subscriptions | List subscriptions + totals |
| GET | /subscriptions/{id} | Subscription detail + history |
| PATCH | /subscriptions/{id} | Update status |
| GET | /alerts | List alerts |
| PATCH | /alerts/settings | Update reminder prefs |
| DELETE | /account | Delete account + all data |
