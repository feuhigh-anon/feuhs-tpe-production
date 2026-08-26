"""Provision the approved 45-account synthetic pilot from an offline plan.

This administrator-only command uses a Supabase secret key entered at the
terminal prompt. It creates pilot records only; it never activates the final
roster import batch.
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

try:
    from scripts.provision_alpha import one, secure_password, upsert_one
except ModuleNotFoundError:
    from provision_alpha import one, secure_password, upsert_one


PERIOD_CODE = "PILOT-2026-Q1"


def read_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise SystemExit(f"File not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("SUPABASE_URL", ""))
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--bundle", type=Path, default=Path("exports/roster_import_SY2026_Q1_pilot"))
    parser.add_argument("--open-days", type=int, default=7, choices=range(1, 31), metavar="1-30")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.url.startswith("https://") or ".supabase.co" not in args.url:
        raise SystemExit("Provide the hosted Supabase project URL with --url or SUPABASE_URL.")

    plan = read_rows(args.plan)
    teacher_rows = read_rows(args.bundle / "teachers_stage.csv")
    teacher_email = {row["employee_number"]: (row.get("email") or None) for row in teacher_rows}
    accounts: dict[str, dict[str, str]] = {}
    for row in plan:
        accounts.setdefault(row["pilot_student_key"], row)
    if len(accounts) != 45:
        raise SystemExit(f"Expected 45 unique pilot accounts; found {len(accounts)}.")
    counts = {cohort: sum(row["cohort"] == cohort for row in accounts.values()) for cohort in ("JHS", "G11", "G12")}
    if counts != {"JHS": 15, "G11": 15, "G12": 15}:
        raise SystemExit(f"Expected 15 accounts per cohort; found {counts}.")
    if any(not row["email"].endswith("@example.invalid") for row in accounts.values()):
        raise SystemExit("Every pilot account must use the reserved example.invalid domain.")

    secret_key = getpass.getpass("Supabase secret key (input hidden): ").strip()
    if not secret_key.startswith("sb_secret_"):
        raise SystemExit("A current sb_secret_ key is required for pilot provisioning.")
    fingerprint = hashlib.sha256(secret_key.encode("utf-8")).hexdigest()[:8]
    print(f"Secret key received ({len(secret_key)} characters; fingerprint {fingerprint}).")
    client = create_client(args.url, secret_key, options=SyncClientOptions(auto_refresh_token=False, persist_session=False))

    existing_users = client.auth.admin.list_users(page=1, per_page=1000)
    existing_emails = {str(user.email).casefold() for user in existing_users if user.email}
    duplicates = sorted(row["email"] for row in accounts.values() if row["email"].casefold() in existing_emails)
    if duplicates:
        raise SystemExit("Pilot accounts already exist; no changes were made: " + ", ".join(duplicates))

    periods = client.table("evaluation_periods").select("id,code,status").eq("code", PERIOD_CODE).limit(2).execute().data or []
    if len(periods) != 1:
        raise SystemExit(f"Expected exactly one {PERIOD_CODE} period; found {len(periods)}.")
    period = periods[0]
    if period["status"] != "draft":
        raise SystemExit(f"Pilot period must be draft before provisioning; found {period['status']!r}.")

    now = datetime.now(timezone.utc)
    client.table("evaluation_periods").update({
        "opens_at": (now - timedelta(minutes=5)).isoformat(),
        "closes_at": (now + timedelta(days=args.open_days)).isoformat(),
    }).eq("id", period["id"]).execute()

    bank_ids: dict[str, int] = {}
    for level in ("JHS", "SHS"):
        bank = one(client.table("question_banks").select("id").eq("code", f"faculty-evaluation-{level.lower()}").eq("version", 1).eq("status", "published").execute(), f"Published {level} version-1 question bank was not found.")
        bank_ids[level] = int(bank["id"])
        client.table("evaluation_period_instruments").upsert({
            "evaluation_period_id": period["id"], "school_level": level, "question_bank_id": bank["id"]
        }, on_conflict="evaluation_period_id,school_level").execute()

    section_ids: dict[str, int] = {}
    assignment_ids: dict[str, int] = {}
    for row in plan:
        section = upsert_one(client, "sections", {
            "code": row["section_code"], "school_level": row["school_level"],
            "grade_level": int(row["grade_level"]), "strand": None, "is_active": True,
        }, "code")
        section_ids[row["section_code"]] = int(section["id"])
        teacher = upsert_one(client, "teachers", {
            "employee_number": row["teacher_employee_number"], "display_name": row["teacher_name"],
            "email": teacher_email.get(row["teacher_employee_number"]), "is_active": True,
        }, "employee_number")
        subject = upsert_one(client, "subjects", {
            "code": row["subject_code"], "name": row["subject_name"], "is_active": True,
        }, "code")
        assignment = upsert_one(client, "teaching_assignments", {
            "evaluation_period_id": period["id"], "section_id": section_ids[row["section_code"]],
            "subject_id": subject["id"], "teacher_id": teacher["id"], "is_active": True,
        }, "evaluation_period_id,section_id,subject_id,teacher_id")
        assignment_ids[row["assignment_key"]] = int(assignment["id"])

    credentials: list[dict[str, Any]] = []
    student_ids: dict[str, str] = {}
    for key, account in accounts.items():
        password = secure_password()
        created = client.auth.admin.create_user({
            "email": account["email"], "password": password, "email_confirm": True,
            "user_metadata": {"display_name": f"Synthetic {account['cohort']} Pilot Student {key[-2:]}"},
        })
        if created.user is None:
            raise RuntimeError(f"Supabase did not return a user for {account['email']}.")
        user_id = str(created.user.id)
        student_ids[key] = user_id
        client.table("profiles").update({"display_name": f"Synthetic {account['cohort']} Pilot Student {key[-2:]}", "role": "student", "is_active": True}).eq("id", user_id).execute()
        client.table("students").upsert({
            "profile_id": user_id, "student_number": account["student_number"], "section_id": section_ids[account["section_code"]],
        }, on_conflict="profile_id").execute()
        assignment_rows = [{"student_id": user_id, "teaching_assignment_id": assignment_ids[row["assignment_key"]], "is_active": True} for row in plan if row["pilot_student_key"] == key]
        client.table("student_assignments").upsert(assignment_rows, on_conflict="student_id,teaching_assignment_id").execute()
        credentials.append({
            "email": account["email"], "password": password, "pilot_student_key": key,
            "student_number": account["student_number"], "cohort": account["cohort"],
            "school_level": account["school_level"], "grade_level": account["grade_level"],
            "section_code": account["section_code"], "assignment_count": len(assignment_rows),
            "period_code": PERIOD_CODE,
        })

    client.table("evaluation_periods").update({"status": "open"}).eq("id", period["id"]).execute()
    output_dir = Path("exports")
    output_dir.mkdir(exist_ok=True)
    output = output_dir / f"pilot_credentials_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(credentials[0]))
        writer.writeheader()
        writer.writerows(credentials)
    print(f"Provisioned {len(credentials)} synthetic accounts: JHS=15, G11=15, G12=15.")
    print(f"Pilot period {PERIOD_CODE} is open for {args.open_days} days.")
    print(f"Credentials saved locally with owner-only permissions: {output}")
    print("This did not activate the final roster import batch.")


if __name__ == "__main__":
    main()
