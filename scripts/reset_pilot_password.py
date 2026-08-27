"""Rotate one or all synthetic pilot passwords safely.

This uses the Supabase secret key only for Auth administration. It does not
change roster, assignment, period, submission, or response data.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import os
import secrets
import tempfile
from pathlib import Path

from supabase import create_client
from supabase.lib.client_options import SyncClientOptions


def secure_password() -> str:
    return "Fe!" + secrets.token_urlsafe(12) + "9a"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--email", help="Rotate only this pilot email; otherwise rotate all rows.")
    args = parser.parse_args()
    if not args.url.startswith("https://") or ".supabase.co" not in args.url:
        raise SystemExit("Provide the hosted Supabase project URL.")
    with args.credentials.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0]) if rows else []
    if not rows or not fields or any(not row["email"].startswith("pilot.") or not row["email"].endswith("@example.invalid") for row in rows):
        raise SystemExit("Refusing to rotate: this is not a synthetic pilot credentials file.")
    targets = [row for row in rows if not args.email or row["email"].casefold() == args.email.strip().casefold()]
    if not targets:
        raise SystemExit("No matching pilot email was found in the credentials file.")

    secret = getpass.getpass("Supabase secret key (input hidden): ").strip()
    if not secret.startswith("sb_secret_"):
        raise SystemExit("A current sb_secret_ key is required.")
    print(f"Secret key received ({len(secret)} characters; fingerprint {hashlib.sha256(secret.encode()).hexdigest()[:8]}).")
    client = create_client(args.url, secret, options=SyncClientOptions(auto_refresh_token=False, persist_session=False))
    users = client.auth.admin.list_users(page=1, per_page=1000)
    user_by_email = {str(user.email).casefold(): str(user.id) for user in users if user.email}
    for row in targets:
        user_id = user_by_email.get(row["email"].casefold())
        if not user_id:
            raise SystemExit(f"Auth user not found: {row['email']}")
        password = secure_password()
        client.auth.admin.update_user_by_id(user_id, {"password": password, "email_confirm": True})
        row["password"] = password

    directory = args.credentials.parent
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=directory, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    os.chmod(temporary, 0o600)
    os.replace(temporary, args.credentials)
    print(f"Rotated {len(targets)} pilot password(s) and updated {args.credentials}.")
    print("Test the updated account before distributing credentials again.")


if __name__ == "__main__":
    main()
