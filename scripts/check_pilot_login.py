"""Safely test one synthetic pilot login against Supabase Auth.

This command uses only the publishable key and performs no database writes.
It accepts only the reserved example.invalid pilot domain.
"""

from __future__ import annotations

import argparse
import getpass
import os

from supabase import create_client
from supabase.lib.client_options import SyncClientOptions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("SUPABASE_URL", ""))
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    email = args.email.strip().casefold()
    if not email.endswith("@example.invalid") or not email.startswith("pilot."):
        raise SystemExit("This diagnostic accepts only pilot.*@example.invalid accounts.")
    if not args.url.startswith("https://") or ".supabase.co" not in args.url:
        raise SystemExit("Provide the hosted Supabase project URL with --url.")
    key = getpass.getpass("Supabase publishable key (input hidden): ").strip()
    if not key.startswith("sb_publishable_"):
        raise SystemExit("Expected a current sb_publishable_ key.")
    password = getpass.getpass("Pilot password (input hidden): ")
    client = create_client(
        args.url,
        key,
        options=SyncClientOptions(auto_refresh_token=False, persist_session=False),
    )
    try:
        response = client.auth.sign_in_with_password({"email": email, "password": password})
    except Exception as exc:
        print(f"Authentication rejected for {email}: {type(exc).__name__}.")
        print("The account/password pair was not accepted by this Supabase project.")
        raise SystemExit(1) from None
    if response.user is None:
        raise SystemExit("Supabase returned no authenticated user.")
    print(f"Authentication succeeded for {email}.")
    print("The pilot account and password are valid; inspect the deployed app secrets or roster data next.")


if __name__ == "__main__":
    main()
