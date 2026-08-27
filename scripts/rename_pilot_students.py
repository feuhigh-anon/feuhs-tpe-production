"""Rename the reserved synthetic pilot students for UI inspection.

This changes only synthetic pilot display names and student numbers. Login
emails, passwords, sections, assignments, submissions, and evaluation periods
are preserved.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import os
import re
import tempfile
from pathlib import Path

from supabase import create_client
from supabase.lib.client_options import SyncClientOptions


SURNAME_FIRST_NAMES = {
    "jhs": [
        ("Santos", "Avery"), ("Reyes", "Jordan"), ("Cruz", "Taylor"),
        ("Garcia", "Morgan"), ("Mendoza", "Casey"), ("Navarro", "Riley"),
        ("Castillo", "Quinn"), ("Bautista", "Cameron"), ("Rivera", "Alex"),
        ("Flores", "Jamie"), ("Torres", "Drew"), ("Aquino", "Skyler"),
        ("Villanueva", "Parker"), ("Dizon", "Sam"), ("Domingo", "Robin"),
    ],
    "g11": [
        ("Salazar", "Avery"), ("Mercado", "Jordan"), ("Lim", "Taylor"),
        ("Ramos", "Morgan"), ("Serrano", "Casey"), ("Velasco", "Riley"),
        ("Manalo", "Quinn"), ("Ocampo", "Cameron"), ("Valdez", "Alex"),
        ("Pascual", "Jamie"), ("Estrada", "Drew"), ("Alvarez", "Skyler"),
        ("Rosales", "Parker"), ("Soriano", "Sam"), ("Ortega", "Robin"),
    ],
    "g12": [
        ("De Leon", "Avery"), ("Santiago", "Jordan"), ("Magsino", "Taylor"),
        ("Fernandez", "Morgan"), ("Gonzales", "Casey"), ("Marquez", "Riley"),
        ("Pineda", "Quinn"), ("Tolentino", "Cameron"), ("Aguilar", "Alex"),
        ("Lazaro", "Jamie"), ("Romero", "Drew"), ("Sison", "Skyler"),
        ("Miranda", "Parker"), ("Natividad", "Sam"), ("Manansala", "Robin"),
    ],
}


def parse_email(email: str) -> tuple[str, int] | None:
    match = re.fullmatch(r"pilot\.(jhs|g11|g12)\.(\d{2})@example\.invalid", email.casefold())
    return (match.group(1), int(match.group(2))) if match else None


def read_credentials(path: Path) -> tuple[list[dict[str, str]], list[str]]:
    if not path.is_file():
        raise SystemExit(f"File not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fields = list(reader.fieldnames or [])
    if len(rows) != 45 or not fields:
        raise SystemExit(f"Expected exactly 45 pilot credential rows; found {len(rows)}.")
    if any(parse_email(row.get("email", "")) is None for row in rows):
        raise SystemExit("Refusing to modify credentials: every email must be a reserved pilot account.")
    return rows, fields


def replacement(email: str) -> tuple[str, str]:
    parsed = parse_email(email)
    if parsed is None:
        raise SystemExit(f"Invalid reserved pilot email: {email}")
    cohort, index = parsed
    if not 1 <= index <= 15:
        raise SystemExit(f"Pilot index must be 01-15: {email}")
    surname, first_name = SURNAME_FIRST_NAMES[cohort][index - 1]
    cohort_offset = {"jhs": 0, "g11": 15, "g12": 30}[cohort]
    synthetic_number = 20600000000 + cohort_offset + index
    return f"{surname}, {first_name}", str(synthetic_number)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--credentials", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    if not args.url.startswith("https://") or ".supabase.co" not in args.url:
        raise SystemExit("Provide the hosted Supabase project URL.")

    rows, fields = read_credentials(args.credentials)
    replacements = {row["email"].casefold(): replacement(row["email"]) for row in rows}
    for field in ("display_name", "student_number"):
        if field not in fields:
            fields.append(field)
    for row in rows:
        row["display_name"], row["student_number"] = replacements[row["email"].casefold()
    ]

    if args.dry_run:
        for row in rows:
            print(f"{row['email']} -> {row['display_name']} / {row['student_number']}")
        print("Dry run only; no database or credentials file was changed.")
        return

    secret = getpass.getpass("Supabase secret key (input hidden): ").strip()
    if not secret.startswith("sb_secret_"):
        raise SystemExit("A current sb_secret_ key is required.")
    print(f"Secret key received ({len(secret)} characters; fingerprint {hashlib.sha256(secret.encode()).hexdigest()[:8]}).")
    client = create_client(args.url, secret, options=SyncClientOptions(auto_refresh_token=False, persist_session=False))
    users = client.auth.admin.list_users(page=1, per_page=1000)
    user_by_email = {str(user.email).casefold(): str(user.id) for user in users if user.email}
    missing = sorted(email for email in replacements if email not in user_by_email)
    if missing:
        raise SystemExit("Refusing partial update; Auth users not found: " + ", ".join(missing))

    for row in rows:
        email = row["email"].casefold()
        user_id = user_by_email[email]
        display_name, student_number = replacements[email]
        client.auth.admin.update_user_by_id(user_id, {"user_metadata": {"display_name": display_name}})
        client.table("profiles").update({"display_name": display_name}).eq("id", user_id).eq("role", "student").execute()
        client.table("students").update({"student_number": student_number}).eq("profile_id", user_id).execute()

    directory = args.credentials.parent
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=directory, delete=False) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    os.chmod(temporary, 0o600)
    os.replace(temporary, args.credentials)
    print("Renamed 45 synthetic pilot students and updated their student numbers.")
    print(f"Credentials updated: {args.credentials}")


if __name__ == "__main__":
    main()
