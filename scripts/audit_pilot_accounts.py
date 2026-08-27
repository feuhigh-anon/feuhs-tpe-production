"""Audit synthetic pilot accounts and related rows without changing data."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import os

from supabase import create_client
from supabase.lib.client_options import SyncClientOptions


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("SUPABASE_URL", ""))
    args = parser.parse_args()
    if not args.url.startswith("https://") or ".supabase.co" not in args.url:
        raise SystemExit("Provide the hosted Supabase project URL with --url.")
    secret = getpass.getpass("Supabase secret key (input hidden): ").strip()
    if not secret.startswith("sb_secret_"):
        raise SystemExit("A current sb_secret_ key is required.")
    print(f"Secret key received ({len(secret)} characters; fingerprint {hashlib.sha256(secret.encode()).hexdigest()[:8]}).")
    client = create_client(args.url, secret, options=SyncClientOptions(auto_refresh_token=False, persist_session=False))

    users = []
    page = 1
    while True:
        page_users = client.auth.admin.list_users(page=page, per_page=1000)
        users.extend(page_users)
        if len(page_users) < 1000:
            break
        page += 1
    pilot_users = [user for user in users if str(getattr(user, "email", "") or "").casefold().startswith("pilot.") and str(getattr(user, "email", "") or "").casefold().endswith("@example.invalid")]
    print(f"Auth users in project: {len(users)}")
    print(f"Synthetic pilot Auth users: {len(pilot_users)}")

    students = client.table("students").select("profile_id,student_number").like("student_number", "PILOT-%").execute().data or []
    profiles = client.table("profiles").select("id,role,is_active").in_("id", [row["profile_id"] for row in students]).execute().data if students else []
    assignments = client.table("student_assignments").select("student_id,teaching_assignment_id").in_("student_id", [row["profile_id"] for row in students]).execute().data if students else []
    print(f"Pilot students rows: {len(students)}")
    print(f"Pilot profiles found for those students: {len(profiles or [])}")
    print(f"Pilot student-assignment rows: {len(assignments or [])}")
    print("This audit is read-only. Staged roster rows do not create Auth users.")


if __name__ == "__main__":
    main()
