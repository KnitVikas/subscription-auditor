# Security, Privacy, and Compliance

Subscription Auditor reads users' email receipts and, later, their bank transactions. Trust is the product: if users do not believe their data is safe, they will not connect anything. This document lists the non-negotiable rules and how each is implemented.

Related reading: [DATA_MODEL.md](DATA_MODEL.md), [ARCHITECTURE.md](ARCHITECTURE.md).

---

## 1. Principles

1. **Least privilege** - request the narrowest scope that works.
2. **Minimize data** - extract what we need, discard the rest.
3. **Encrypt secrets at rest** - tokens are never stored in plaintext.
4. **User control** - users can disconnect and delete everything, at any time.
5. **Transparency** - tell users exactly what we read and why.

---

## 2. Gmail access

- Scope: `https://www.googleapis.com/auth/gmail.readonly` only. Never request send/modify scopes.
- Only search for receipt/renewal emails; do not crawl the entire mailbox.
- Store **only extracted fields** (merchant, amount, currency, date, message id). Full email bodies are processed in memory and discarded.
- Use the OAuth `state` parameter to prevent CSRF on the callback.

### Google OAuth verification
Gmail read-only is a **restricted scope**. Before a public launch, the app must pass Google's OAuth verification, which may include a third-party security assessment. Plan for this as a pre-launch task:
- Publish a privacy policy and terms of service.
- Document exactly how Gmail data is used, stored, and deleted.
- Provide a working data-deletion flow.

During development, the app can run in "testing" mode with up to 100 manually added test users.

---

## 3. Token encryption

- OAuth access and refresh tokens are encrypted with **AES-GCM** before being written to `connections.access_token_enc` / `refresh_token_enc`.
- The encryption key (`TOKEN_ENCRYPTION_KEY`) lives in environment variables / a secrets manager, never in the database or repository.
- Each encryption uses a fresh random nonce, stored alongside the ciphertext.
- Key rotation: support a key id prefix on ciphertext so old tokens can be re-encrypted with a new key.

Implemented in `backend/app/core/security.py`.

---

## 4. Authentication

- Passwords hashed with **argon2** (or bcrypt).
- JWTs signed with `JWT_SECRET`, with a sensible expiry.
- Every non-auth endpoint requires a valid JWT, and every query is scoped by `user_id` from the token - a user can never read another user's rows.
- Rate-limit `/auth/login` and `/auth/signup` (Redis) to slow brute-force attempts.

---

## 5. Transport and infrastructure

- HTTPS everywhere in production.
- CORS restricted to the frontend origin.
- Database and Redis are not publicly reachable; use managed services with encryption at rest.
- Secrets are injected by the hosting platform, never committed. `.env` is in `.gitignore`; only `.env.example` is committed.

---

## 6. Data deletion

- `DELETE /connections/{id}` revokes the Google token and cascade-deletes all transactions, subscriptions, and alerts derived from that connection.
- `DELETE /account` deletes the user and everything they own (foreign keys use `ON DELETE CASCADE`).
- Deletion is immediate and hard, not a soft-delete flag.

---

## 7. LLM usage

- Send the LLM only the **merchant string** (e.g. `"NETFLIX COM 94"`), never email bodies, names, or amounts tied to a user.
- Cache results by merchant string so the same value is not resent.
- If no LLM key is configured, the rule-based fallback is used and nothing leaves the system.

---

## 8. Logging

- Never log tokens, passwords, or email contents.
- Log job ids, user ids, and counts (e.g. "ingested 14 transactions") for debugging.

---

## 9. Account Aggregator (Phase 3)

- Integrate only through a licensed AA provider (Setu, Finvu, Perfios).
- The app never sees bank credentials; it receives consented, time-bound financial data.
- Respect consent artifacts: purpose, data range, and expiry. Stop fetching when consent expires or is revoked.
- Review RBI and AA ecosystem rules for the "Financial Information User" role before going live.

---

## Pre-launch checklist

- [ ] Gmail scope is read-only
- [ ] Tokens encrypted with AES-GCM, key outside the DB
- [ ] Email bodies not persisted
- [ ] All queries scoped by user id
- [ ] Auth endpoints rate-limited
- [ ] Disconnect and account deletion work end to end
- [ ] Privacy policy and terms published
- [ ] Google OAuth verification submitted
