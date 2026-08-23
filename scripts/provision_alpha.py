"""Provision a small synthetic Supabase alpha cohort.

This administrator-only script uses a Supabase secret key entered at the
terminal prompt. Generated credentials are written to the ignored exports/
directory with owner-only permissions.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions
from supabase_auth.errors import AuthApiError


FIXTURES = {
    "SHS": {
        "section": {
            "code": "11STEM-ALPHA",
            "school_level": "SHS",
            "grade_level": 11,
            "strand": "STEM",
            "is_active": True,
        },
        "assignments": (
            {
                "teacher": {
                    "employee_number": "ALPHA-T001",
                    "display_name": "Teacher Alpha",
                    "email": "teacher.alpha@example.invalid",
                    "is_active": True,
                },
                "subject": {
                    "code": "ALPHA-CALC",
                    "name": "Basic Calculus",
                    "is_active": True,
                },
            },
            {
                "teacher": {
                    "employee_number": "ALPHA-T002",
                    "display_name": "Teacher Beta",
                    "email": "teacher.beta@example.invalid",
                    "is_active": True,
                },
                "subject": {
                    "code": "ALPHA-EARTH",
                    "name": "Earth Science",
                    "is_active": True,
                },
            },
        ),
    },
    "JHS": {
        "section": {
            "code": "07JHS-ALPHA",
            "school_level": "JHS",
            "grade_level": 7,
            "strand": "",
            "is_active": True,
        },
        "assignments": (
            {
                "teacher": {
                    "employee_number": "ALPHA-JHS-T001",
                    "display_name": "Teacher Gamma",
                    "email": "teacher.gamma.jhs@example.invalid",
                    "is_active": True,
                },
                "subject": {
                    "code": "ALPHA-JHS-MATH",
                    "name": "JHS Mathematics",
                    "is_active": True,
                },
            },
            {
                "teacher": {
                    "employee_number": "ALPHA-JHS-T002",
                    "display_name": "Teacher Delta",
                    "email": "teacher.delta.jhs@example.invalid",
                    "is_active": True,
                },
                "subject": {
                    "code": "ALPHA-JHS-SCI",
                    "name": "JHS Science",
                    "is_active": True,
                },
            },
        ),
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--school-level",
        choices=("SHS", "JHS"),
        default="SHS",
        help="Synthetic school-level fixture to provision; defaults to SHS.",
    )
    parser.add_argument(
        "--url",
        default=os.getenv("SUPABASE_URL", ""),
        help="Hosted project URL; defaults to SUPABASE_URL.",
    )
    parser.add_argument(
        "--students",
        type=int,
        default=2,
        choices=range(2, 11),
        metavar="2-10",
        help="Number of fictional student accounts to create.",
    )
    parser.add_argument(
        "--open-days",
        type=int,
        default=7,
        choices=range(1, 31),
        metavar="1-30",
        help="Number of days the synthetic evaluation period remains open.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    school_level = args.school_level
    fixture = FIXTURES[school_level]
    section_definition = fixture["section"]
    url = args.url.strip()
    if not url.startswith("https://") or ".supabase.co" not in url:
        raise SystemExit("Provide the hosted Supabase project URL with --url or SUPABASE_URL.")

    secret_key = getpass.getpass("Supabase secret key (input hidden): ").strip()
    if not secret_key.startswith("sb_secret_"):
        raise SystemExit("A current sb_secret_ key is required for administrator provisioning.")
    fingerprint = hashlib.sha256(secret_key.encode("utf-8")).hexdigest()[:8]
    print(
        f"Secret key received ({len(secret_key)} characters; fingerprint {fingerprint})."
    )

    client = create_client(
        url,
        secret_key,
        options=SyncClientOptions(
            auto_refresh_token=False,
            persist_session=False,
        ),
    )
    email_prefix = "alpha.student" if school_level == "SHS" else "alpha.jhs.student"
    emails = [
        f"{email_prefix}{index:02d}@example.invalid"
        for index in range(1, args.students + 1)
    ]
    try:
        users = client.auth.admin.list_users(page=1, per_page=1000)
    except AuthApiError as exc:
        if "invalid api key" in str(exc).casefold():
            raise SystemExit(
                "Supabase rejected the secret key. Copy the complete active sb_secret_ key "
                "from this project's Settings > API Keys page and try again."
            ) from None
        raise SystemExit(f"Supabase administrator authentication failed: {exc}") from None
    existing = {
        str(user.email).casefold()
        for user in users
        if user.email
    }
    duplicates = sorted(email for email in emails if email.casefold() in existing)
    if duplicates:
        raise SystemExit(
            "Alpha accounts already exist; no changes were made: " + ", ".join(duplicates)
        )

    section = upsert_one(client, "sections", section_definition, "code")
    question_bank = one(
        client.table("question_banks")
        .select("id")
        .eq("code", f"faculty-evaluation-{school_level.lower()}")
        .eq("version", 1)
        .eq("status", "published")
        .execute(),
        f"Published {school_level} question bank version 1 was not found.",
    )

    now = datetime.now(timezone.utc)
    period = upsert_one(
        client,
        "evaluation_periods",
        {
            "code": "ALPHA-2026-01",
            "academic_year": "2026-2027",
            "term": "Synthetic Alpha Test",
            "opens_at": (now - timedelta(minutes=5)).isoformat(),
            "closes_at": (now + timedelta(days=args.open_days)).isoformat(),
            "status": "open",
        },
        "code",
    )
    client.table("evaluation_period_instruments").upsert(
        {
            "evaluation_period_id": period["id"],
            "school_level": school_level,
            "question_bank_id": question_bank["id"],
        },
        on_conflict="evaluation_period_id,school_level",
    ).execute()

    teaching_assignment_ids = []
    for definition in fixture["assignments"]:
        teacher = upsert_one(
            client, "teachers", definition["teacher"], "employee_number"
        )
        subject = upsert_one(client, "subjects", definition["subject"], "code")
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
        teaching_assignment_ids.append(assignment["id"])

    credentials = []
    for index, email in enumerate(emails, start=1):
        password = secure_password()
        display_name = f"{school_level} Alpha Student {index:02d}"
        student_number = f"ALPHA-{school_level}-{index:04d}"
        created = client.auth.admin.create_user(
            {
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"display_name": display_name},
            }
        )
        user = created.user
        if user is None:
            raise RuntimeError(f"Supabase did not return the created user for {email}.")

        client.table("profiles").update(
            {"display_name": display_name, "role": "student", "is_active": True}
        ).eq("id", str(user.id)).execute()
        client.table("students").upsert(
            {
                "profile_id": str(user.id),
                "student_number": student_number,
                "section_id": section["id"],
            },
            on_conflict="profile_id",
        ).execute()
        client.table("student_assignments").upsert(
            [
                {
                    "student_id": str(user.id),
                    "teaching_assignment_id": assignment_id,
                    "is_active": True,
                }
                for assignment_id in teaching_assignment_ids
            ],
            on_conflict="student_id,teaching_assignment_id",
        ).execute()
        credentials.append(
            {
                "email": email,
                "password": password,
                "display_name": display_name,
                "student_number": student_number,
                "section": section_definition["code"],
            }
        )

    output = write_credentials(credentials, school_level)
    print(
        f"Created {len(credentials)} synthetic {school_level} students and "
        f"{len(teaching_assignment_ids)} assignments."
    )
    print(f"Credentials saved locally with owner-only permissions: {output}")
    print("Delete the synthetic users and local credential file after alpha testing.")


def upsert_one(
    client: Client,
    table: str,
    values: dict[str, Any],
    conflict_columns: str,
) -> dict[str, Any]:
    return one(
        client.table(table)
        .upsert(values, on_conflict=conflict_columns)
        .execute(),
        f"Unable to upsert {table}.",
    )


def one(response: Any, message: str) -> dict[str, Any]:
    data = getattr(response, "data", None)
    if not isinstance(data, list) or len(data) != 1:
        raise RuntimeError(message)
    return data[0]


def secure_password() -> str:
    return f"Fe!{secrets.token_urlsafe(12)}9a"


def write_credentials(rows: list[dict[str, str]], school_level: str = "SHS") -> Path:
    output_dir = Path("exports")
    output_dir.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output = output_dir / f"alpha_{school_level.lower()}_credentials_{timestamp}.csv"
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return output


if __name__ == "__main__":
    main()
