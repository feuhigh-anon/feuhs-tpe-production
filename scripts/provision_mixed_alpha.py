"""Provision a 10-student mixed JHS, Grade 11, and Grade 12 alpha cohort.

This administrator-only script uses a Supabase secret key entered at the
terminal prompt. All generated identities are explicitly synthetic, and the
owner-only credentials file is written under the Git-ignored exports/ folder.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from supabase import create_client
from supabase.lib.client_options import SyncClientOptions
from supabase_auth.errors import AuthApiError

try:
    from scripts.provision_alpha import one, secure_password, upsert_one
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from provision_alpha import one, secure_password, upsert_one


COHORTS: tuple[dict[str, Any], ...] = (
    {
        "key": "JHS",
        "student_count": 4,
        "section": {
            "code": "07JHS-MIXED-ALPHA",
            "school_level": "JHS",
            "grade_level": 7,
            "strand": "",
            "is_active": True,
        },
        "assignments": (
            ("ALPHA-J7-T001", "Teacher JHS Mathematics", "ALPHA-J7-MATH", "Mathematics 7"),
            ("ALPHA-J7-T002", "Teacher JHS Science", "ALPHA-J7-SCI", "Science 7"),
            ("ALPHA-J7-T003", "Teacher JHS English", "ALPHA-J7-ENG", "English 7"),
        ),
    },
    {
        "key": "G11",
        "student_count": 3,
        "section": {
            "code": "11STEM-MIXED-ALPHA",
            "school_level": "SHS",
            "grade_level": 11,
            "strand": "STEM",
            "is_active": True,
        },
        "assignments": (
            ("ALPHA-G11-T001", "Teacher Grade 11 Mathematics", "ALPHA-G11-GM", "General Mathematics"),
            ("ALPHA-G11-T002", "Teacher Grade 11 Science", "ALPHA-G11-ELS", "Earth and Life Science"),
            ("ALPHA-G11-T003", "Teacher Grade 11 Communication", "ALPHA-G11-OC", "Oral Communication in Context"),
        ),
    },
    {
        "key": "G12",
        "student_count": 3,
        "section": {
            "code": "12STEM-MIXED-ALPHA",
            "school_level": "SHS",
            "grade_level": 12,
            "strand": "STEM",
            "is_active": True,
        },
        "assignments": (
            ("ALPHA-G12-T001", "Teacher Grade 12 Physics", "ALPHA-G12-GP1", "General Physics 1"),
            ("ALPHA-G12-T002", "Teacher Grade 12 UCSP", "ALPHA-G12-UCSP", "Understanding Culture, Society, and Politics"),
            ("ALPHA-G12-T003", "Teacher Grade 12 Arts", "ALPHA-G12-CPAR", "Contemporary Philippine Arts from the Regions"),
        ),
    },
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.getenv("SUPABASE_URL", ""),
        help="Hosted project URL; defaults to SUPABASE_URL.",
    )
    parser.add_argument(
        "--open-days",
        type=int,
        default=7,
        choices=range(1, 31),
        metavar="1-30",
        help="Number of days the synthetic evaluation period remains open.",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help=(
            "Delete and recreate only the ten alpha.mixed.*@example.invalid "
            "accounts. Use this to recover from an interrupted mixed-alpha run."
        ),
    )
    return parser.parse_args()


def planned_accounts() -> list[dict[str, Any]]:
    accounts: list[dict[str, Any]] = []
    for cohort in COHORTS:
        section = cohort["section"]
        for index in range(1, cohort["student_count"] + 1):
            accounts.append(
                {
                    "cohort": cohort,
                    "index": index,
                    "email": f"alpha.mixed.{cohort['key'].lower()}{index:02d}@example.invalid",
                    "display_name": f"{cohort['key']} Mixed Alpha Student {index:02d}",
                    "student_number": f"ALPHA-MIXED-{cohort['key']}-{index:04d}",
                    "section": section,
                }
            )
    return accounts


def main() -> None:
    args = parse_args()
    url = args.url.strip()
    if not url.startswith("https://") or ".supabase.co" not in url:
        raise SystemExit("Provide the hosted Supabase project URL with --url or SUPABASE_URL.")

    secret_key = getpass.getpass("Supabase secret key (input hidden): ").strip()
    if not secret_key.startswith("sb_secret_"):
        raise SystemExit("A current sb_secret_ key is required for administrator provisioning.")
    fingerprint = hashlib.sha256(secret_key.encode("utf-8")).hexdigest()[:8]
    print(f"Secret key received ({len(secret_key)} characters; fingerprint {fingerprint}).")

    client = create_client(
        url,
        secret_key,
        options=SyncClientOptions(auto_refresh_token=False, persist_session=False),
    )
    accounts = planned_accounts()
    try:
        users = client.auth.admin.list_users(page=1, per_page=1000)
    except AuthApiError as exc:
        raise SystemExit(f"Supabase administrator authentication failed: {exc}") from None
    existing_users = {
        str(user.email).casefold(): user
        for user in users
        if user.email
    }
    target_emails = {row["email"].casefold() for row in accounts}
    duplicates = sorted(email for email in target_emails if email in existing_users)
    if duplicates and args.replace_existing:
        for email in duplicates:
            user = existing_users[email]
            client.auth.admin.delete_user(str(user.id))
        print(f"Removed {len(duplicates)} existing mixed-alpha account(s) before recreation.")
        duplicates = []
    if duplicates:
        raise SystemExit(
            "Mixed alpha accounts already exist; no changes were made. "
            "If the prior run was interrupted, rerun with --replace-existing. Accounts: "
            + ", ".join(duplicates)
        )

    now = datetime.now(timezone.utc)
    period = upsert_one(
        client,
        "evaluation_periods",
        {
            "code": "ALPHA-2026-01",
            "academic_year": "2026-2027",
            "term": "Synthetic Mixed Alpha Test",
            "opens_at": (now - timedelta(minutes=5)).isoformat(),
            "closes_at": (now + timedelta(days=args.open_days)).isoformat(),
            "status": "open",
        },
        "code",
    )
    for school_level in ("JHS", "SHS"):
        question_bank = one(
            client.table("question_banks")
            .select("id")
            .eq("code", f"faculty-evaluation-{school_level.lower()}")
            .eq("version", 1)
            .eq("status", "published")
            .execute(),
            f"Published {school_level} question bank version 1 was not found.",
        )
        client.table("evaluation_period_instruments").upsert(
            {
                "evaluation_period_id": period["id"],
                "school_level": school_level,
                "question_bank_id": question_bank["id"],
            },
            on_conflict="evaluation_period_id,school_level",
        ).execute()

    cohort_context: dict[str, tuple[dict[str, Any], list[int]]] = {}
    for cohort in COHORTS:
        section = upsert_one(client, "sections", cohort["section"], "code")
        assignment_ids: list[int] = []
        for employee_number, teacher_name, subject_code, subject_name in cohort["assignments"]:
            teacher = upsert_one(
                client,
                "teachers",
                {
                    "employee_number": employee_number,
                    "display_name": teacher_name,
                    "email": f"{employee_number.lower()}@example.invalid",
                    "is_active": True,
                },
                "employee_number",
            )
            subject = upsert_one(
                client,
                "subjects",
                {"code": subject_code, "name": subject_name, "is_active": True},
                "code",
            )
            assignment = upsert_one(
                client,
                "teaching_assignments",
                {
                    "evaluation_period_id": period["id"],
                    "section_id": section["id"],
                    "subject_id": subject["id"],
                    "teacher_id": teacher["id"],
                    "is_active": True,
                },
                "evaluation_period_id,section_id,subject_id,teacher_id",
            )
            assignment_ids.append(int(assignment["id"]))
        cohort_context[cohort["key"]] = (section, assignment_ids)

    credentials: list[dict[str, Any]] = []
    for account in accounts:
        cohort = account["cohort"]
        section, assignment_ids = cohort_context[cohort["key"]]
        password = secure_password()
        created = client.auth.admin.create_user(
            {
                "email": account["email"],
                "password": password,
                "email_confirm": True,
                "user_metadata": {"display_name": account["display_name"]},
            }
        )
        if created.user is None:
            raise RuntimeError(f"Supabase did not return the created user for {account['email']}.")
        user_id = str(created.user.id)
        client.table("profiles").update(
            {"display_name": account["display_name"], "role": "student", "is_active": True}
        ).eq("id", user_id).execute()
        client.table("students").upsert(
            {
                "profile_id": user_id,
                "student_number": account["student_number"],
                "section_id": section["id"],
            },
            on_conflict="profile_id",
        ).execute()
        client.table("student_assignments").upsert(
            [
                {"student_id": user_id, "teaching_assignment_id": assignment_id, "is_active": True}
                for assignment_id in assignment_ids
            ],
            on_conflict="student_id,teaching_assignment_id",
        ).execute()
        credentials.append(
            {
                "email": account["email"],
                "password": password,
                "display_name": account["display_name"],
                "student_number": account["student_number"],
                "section": account["section"]["code"],
                "school_level": account["section"]["school_level"],
                "grade_level": account["section"]["grade_level"],
                "assignment_count": len(assignment_ids),
            }
        )

    output = write_credentials(credentials)
    print("Created 10 synthetic accounts: 4 JHS, 3 Grade 11, and 3 Grade 12.")
    print("Created 9 synthetic teaching assignments; each account has 3 evaluations.")
    print(f"Credentials saved locally with owner-only permissions: {output}")
    print("Delete the synthetic users and local credential file after alpha testing.")


def write_credentials(rows: list[dict[str, Any]]) -> Path:
    output_dir = Path("exports")
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = output_dir / f"alpha_mixed_credentials_{timestamp}.csv"
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return output


if __name__ == "__main__":
    main()
