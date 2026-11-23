#!/usr/bin/env python
"""Standalone Gmail fetch + parse script.

Runs the *exact same* pipeline the app uses during a sync:
  Gmail search -> message download -> LLM batch parsing (with per-email
  confidence threshold) -> rule-based fallback -> ParsedReceipt.

It reuses `app.services.gmail.fetch_receipts` directly, so the logic is
identical to production; this is just a thin CLI around it for inspecting what
the parser extracts from a real inbox, outside the web app / worker.

Credentials are read from a Gmail connection you've already linked in the app
(the OAuth tokens are decrypted the same way the worker does). Nothing is
written back to the database.

Usage (from the backend/ directory, inside the venv):
    python scripts/fetch_and_parse.py                  # 90 days, table output
    python scripts/fetch_and_parse.py --days 30 --limit 20
    python scripts/fetch_and_parse.py --email you@example.com
    python scripts/fetch_and_parse.py --max-messages 50 --json
    python scripts/fetch_and_parse.py --no-llm          # force the regex parser
    python scripts/fetch_and_parse.py --list            # list linked accounts
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from decimal import Decimal

# The Windows console (cp1252) can't encode emoji/unicode that show up in email
# subjects and bodies; force UTF-8 so logging the fetched messages never crashes.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# Make `import app...` work when run as `python scripts/fetch_and_parse.py`, and
# run from the backend root so the relative sqlite DATABASE_URL (./subauditor.db)
# and the .env lookup resolve the same way regardless of the caller's cwd.
_BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _BACKEND_ROOT)
os.chdir(_BACKEND_ROOT)

from sqlalchemy import select  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import SessionLocal  # noqa: E402
from app.core.security import decrypt_token  # noqa: E402
from app.models import Connection, User  # noqa: E402
from app.services import gmail  # noqa: E402


def _list_connections() -> None:
    db = SessionLocal()
    try:
        rows = db.execute(
            select(Connection, User.email)
            .join(User, User.id == Connection.user_id)
            .where(Connection.type == "gmail")
        ).all()
        if not rows:
            print("No Gmail connections found. Link an account in the app first.")
            return
        print("Linked Gmail accounts:")
        for conn, email in rows:
            print(
                f"  - {email}  (status={conn.status}, "
                f"last_synced={conn.last_synced_at or 'never'})"
            )
    finally:
        db.close()


def _load_tokens(email: str | None) -> tuple[str, str | None, str]:
    """Return (access_token, refresh_token, account_email) for a linked Gmail
    connection, decrypting the stored OAuth tokens."""
    db = SessionLocal()
    try:
        stmt = (
            select(Connection, User.email)
            .join(User, User.id == Connection.user_id)
            .where(Connection.type == "gmail")
        )
        if email:
            stmt = stmt.where(User.email == email)
        row = db.execute(stmt).first()
        if row is None:
            raise SystemExit(
                "No matching Gmail connection. Use --list to see linked accounts, "
                "or link one in the app first."
            )
        conn, account_email = row
        access = decrypt_token(conn.access_token_enc)
        refresh = decrypt_token(conn.refresh_token_enc)
        if not access and not refresh:
            raise SystemExit(f"Connection for {account_email} has no usable tokens.")
        return access, refresh, account_email
    finally:
        db.close()


def _receipt_to_dict(r) -> dict:
    return {
        "merchant": r.raw_merchant,
        "amount": str(r.amount),
        "currency": r.currency,
        "occurred_at": r.occurred_at.isoformat(),
        "sender_domain": r.sender_domain,
        "recurring_hint": r.recurring_hint,
        "cadence_hint": r.cadence_hint,
        "renews_at_hint": r.renews_at_hint.isoformat() if r.renews_at_hint else None,
        "trial_hint": r.trial_hint,
        "raw_ref": r.raw_ref,
    }


def _print_table(receipts: list) -> None:
    if not receipts:
        print("\nNo receipts parsed from the fetched emails.")
        return
    print(f"\n{'MERCHANT':<24} {'AMOUNT':>12} {'CAD':<8} {'FLAGS':<16} DATE")
    print("-" * 78)
    for r in receipts:
        flags = ",".join(
            f for f, on in (("rec", r.recurring_hint), ("trial", r.trial_hint)) if on
        )
        amount = f"{r.currency} {r.amount}"
        print(
            f"{r.raw_merchant[:24]:<24} {amount:>12} "
            f"{(r.cadence_hint or '-'):<8} {flags:<16} "
            f"{r.occurred_at.date().isoformat()}"
        )

    totals: dict[str, Decimal] = {}
    for r in receipts:
        totals[r.currency] = totals.get(r.currency, Decimal("0")) + r.amount
    print("-" * 78)
    print(f"{len(receipts)} receipt(s).")
    for cur, total in sorted(totals.items()):
        print(f"  total seen in {cur}: {total}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", help="Which linked account to use (default: first)")
    parser.add_argument("--days", type=int, default=settings.gmail_scan_days)
    parser.add_argument("--max-messages", type=int, default=settings.gmail_scan_max_messages)
    parser.add_argument("--limit", type=int, default=0, help="Only print first N receipts")
    parser.add_argument("--json", action="store_true", help="Output JSON instead of a table")
    parser.add_argument("--no-llm", action="store_true", help="Force the rule-based parser")
    parser.add_argument("--list", action="store_true", help="List linked Gmail accounts and exit")
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Log each fetched email (id/from/subject/date/size) to stderr",
    )
    args = parser.parse_args()

    if args.verbose:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
        # Only turn on our Gmail service logger, not noisy third-party libs.
        gmail_logger = logging.getLogger("app.services.gmail")
        gmail_logger.setLevel(logging.DEBUG)
        gmail_logger.addHandler(handler)

    if args.list:
        _list_connections()
        return

    # Toggle the LLM exactly as the app would via config (fetch_receipts reads this).
    if args.no_llm:
        settings.llm_receipt_parsing = False

    access, refresh, account_email = _load_tokens(args.email)
    days = gmail.clamp_scan_days(args.days)
    mode = "rule-based" if args.no_llm else f"LLM ({settings.openai_model}) + rules"
    print(
        f"Account: {account_email} | window: {days}d | "
        f"max messages: {args.max_messages} | parser: {mode}",
        file=sys.stderr,
    )

    def on_progress(done: int, total: int) -> None:
        print(f"\rFetched {done}/{total} messages...", end="", file=sys.stderr)

    receipts = list(
        gmail.fetch_receipts(
            access,
            refresh,
            days=days,
            max_messages=args.max_messages,
            on_progress=on_progress,
        )
    )
    print("", file=sys.stderr)  # newline after the progress line

    if args.limit > 0:
        receipts = receipts[: args.limit]

    if args.json:
        print(json.dumps([_receipt_to_dict(r) for r in receipts], indent=2))
    else:
        _print_table(receipts)


if __name__ == "__main__":
    main()
