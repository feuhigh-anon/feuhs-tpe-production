"""Delete synthetic roster-pilot accounts and their temporary evaluation data."""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import os
from pathlib import Path

from supabase import create_client
from supabase.lib.client_options import SyncClientOptions


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("SUPABASE_URL", ""))
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--period-code", default="PILOT-2026-Q1")
    parser.add_argument("--delete-credentials", action="store_true")
    args = parser.parse_args()
    credentials = rows(args.credentials)
    if not credentials or any(not r["email"].endswith("@example.invalid") or not r["student_number"].startswith("PILOT-") for r in credentials):
        raise SystemExit("Refusing cleanup: credentials do not contain only reserved synthetic pilot identities.")
    secret = getpass.getpass("Supabase secret key (input hidden): ").strip()
    if not secret.startswith("sb_secret_"):
        raise SystemExit("A current sb_secret_ key is required for cleanup.")
    print(f"Secret key received ({len(secret)} characters; fingerprint {hashlib.sha256(secret.encode()).hexdigest()[:8]}).")
    client = create_client(args.url, secret, options=SyncClientOptions(auto_refresh_token=False, persist_session=False))
    users = client.auth.admin.list_users(page=1, per_page=1000)
    user_by_email = {str(u.email).casefold(): str(u.id) for u in users if u.email}
    user_ids = [user_by_email[r["email"].casefold()] for r in credentials if r["email"].casefold() in user_by_email]
    student_numbers = [r["student_number"] for r in credentials]
    students = client.table("students").select("profile_id,student_number").in_("student_number", student_numbers).execute().data or []
    student_ids = [str(r["profile_id"]) for r in students]
    submissions = client.table("evaluation_submissions").select("id").in_("student_id", student_ids).eq("evaluation_period_id", client.table("evaluation_periods").select("id").eq("code", args.period_code).single().execute().data["id"]).execute().data or []
    submission_ids = [int(r["id"]) for r in submissions]
    if submission_ids:
        client.table("evaluation_responses").delete().in_("submission_id", submission_ids).execute()
        client.table("submission_audit_events").delete().in_("submission_id", submission_ids).execute()
        client.table("evaluation_submissions").delete().in_("id", submission_ids).execute()
    if student_ids:
        client.table("student_assignments").delete().in_("student_id", student_ids).execute()
        client.table("students").delete().in_("profile_id", student_ids).execute()
        client.table("profiles").delete().in_("id", student_ids).execute()
    for user_id in user_ids:
        client.auth.admin.delete_user(user_id)
    client.table("evaluation_periods").update({"status": "draft"}).eq("code", args.period_code).execute()
    if args.delete_credentials:
        args.credentials.unlink()
    print(f"Removed {len(user_ids)} Auth users, {len(student_ids)} student rows, and {len(submission_ids)} submissions.")
    print(f"Pilot period {args.period_code} returned to draft.")


if __name__ == "__main__":
    main()
