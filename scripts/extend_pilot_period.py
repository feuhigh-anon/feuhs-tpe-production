"""Extend the synthetic roster pilot evaluation window without reprovisioning."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import os
from datetime import datetime, timezone
from urllib.parse import urlparse

from supabase import create_client
from supabase.lib.client_options import SyncClientOptions


PERIOD_CODE = "PILOT-2026-Q1"


def parse_datetime(value: str) -> str:
    normalized = value.strip().replace("Z", "+00:00")
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).isoformat()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("SUPABASE_URL", ""))
    parser.add_argument(
        "--closes-at",
        required=True,
        help="New UTC close time, for example 2026-09-15T23:59:00Z.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    parsed_url = urlparse(args.url)
    if (
        parsed_url.scheme != "https"
        or not parsed_url.hostname
        or not parsed_url.hostname.endswith(".supabase.co")
        or parsed_url.hostname.casefold().startswith("your_project.")
    ):
        raise SystemExit(
            "Provide the actual hosted Supabase project URL, for example "
            "https://abc123xyz.supabase.co. Do not use YOUR_PROJECT as the hostname."
        )

    closes_at = parse_datetime(args.closes_at)
    secret = getpass.getpass("Supabase secret key (input hidden): ").strip()
    if not secret.startswith("sb_secret_"):
        raise SystemExit("A current sb_secret_ key is required.")
    print(f"Secret key received ({len(secret)} characters; fingerprint {hashlib.sha256(secret.encode()).hexdigest()[:8]}).")

    client = create_client(
        args.url,
        secret,
        options=SyncClientOptions(auto_refresh_token=False, persist_session=False),
    )
    periods = (
        client.table("evaluation_periods")
        .select("id,code,status,opens_at,closes_at")
        .eq("code", PERIOD_CODE)
        .limit(2)
        .execute()
        .data
        or []
    )
    if len(periods) != 1:
        raise SystemExit(f"Expected exactly one {PERIOD_CODE} period; found {len(periods)}.")
    period = periods[0]
    if period["code"] != PERIOD_CODE:
        raise SystemExit("Refusing to update an unexpected evaluation period.")

    print(
        f"Current {PERIOD_CODE}: status={period['status']!r}, "
        f"opens_at={period['opens_at']}, closes_at={period['closes_at']}"
    )
    updated = (
        client.table("evaluation_periods")
        .update({"status": "open", "closes_at": closes_at})
        .eq("id", period["id"])
        .eq("code", PERIOD_CODE)
        .execute()
        .data
        or []
    )
    if len(updated) != 1:
        raise SystemExit("The period update did not return exactly one updated row.")
    print(f"Updated {PERIOD_CODE}: status='open', closes_at={closes_at}")
    print("Existing student accounts, assignments, instruments, and submissions were not changed.")


if __name__ == "__main__":
    main()
