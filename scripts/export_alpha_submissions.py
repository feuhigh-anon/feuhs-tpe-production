"""Export administrator-readable alpha submissions to owner-only CSV files."""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.getenv("SUPABASE_URL", ""),
        help="Hosted project URL; defaults to SUPABASE_URL.",
    )
    parser.add_argument(
        "--period-code",
        default="ALPHA-2026-01",
        help="Evaluation period to export; defaults to ALPHA-2026-01.",
    )
    return parser.parse_args()


def rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if not isinstance(data, list):
        raise RuntimeError("Supabase returned an unexpected response.")
    return data


def indexed(client: Client, table: str, columns: str = "*") -> dict[Any, dict[str, Any]]:
    return {row["id"]: row for row in rows(client.table(table).select(columns).execute())}


def main() -> None:
    args = parse_args()
    url = args.url.strip()
    if not url.startswith("https://") or ".supabase.co" not in url:
        raise SystemExit("Provide the hosted Supabase project URL with --url or SUPABASE_URL.")
    if not args.period_code.startswith("ALPHA-"):
        raise SystemExit("This safety-limited exporter accepts only ALPHA-* periods.")

    secret_key = getpass.getpass("Supabase secret key (input hidden): ").strip()
    if not secret_key.startswith("sb_secret_"):
        raise SystemExit("A current sb_secret_ key is required for administrator export.")
    fingerprint = hashlib.sha256(secret_key.encode("utf-8")).hexdigest()[:8]
    print(f"Secret key received ({len(secret_key)} characters; fingerprint {fingerprint}).")
    client = create_client(
        url,
        secret_key,
        options=SyncClientOptions(auto_refresh_token=False, persist_session=False),
    )

    periods = rows(
        client.table("evaluation_periods")
        .select("id,code")
        .eq("code", args.period_code)
        .limit(1)
        .execute()
    )
    if len(periods) != 1:
        raise SystemExit(f"Evaluation period {args.period_code!r} was not found.")
    period_id = periods[0]["id"]
    submissions = rows(
        client.table("evaluation_submissions")
        .select("id,student_id,teaching_assignment_id,question_bank_id,submitted_at,client_version")
        .eq("evaluation_period_id", period_id)
        .order("submitted_at")
        .execute()
    )

    students = {
        row["profile_id"]: row
        for row in rows(client.table("students").select("profile_id,student_number,section_id").execute())
    }
    profiles = indexed(client, "profiles", "id,display_name")
    sections = indexed(client, "sections", "id,code,school_level,grade_level,strand")
    assignments = indexed(
        client,
        "teaching_assignments",
        "id,section_id,subject_id,teacher_id",
    )
    teachers = indexed(client, "teachers", "id,employee_number,display_name")
    subjects = indexed(client, "subjects", "id,code,name")
    questions = indexed(
        client,
        "question_items",
        "id,section_key,prompt,response_type,position",
    )
    responses = rows(
        client.table("evaluation_responses")
        .select("submission_id,question_item_id,rating_value,text_value,is_not_applicable")
        .in_("submission_id", [row["id"] for row in submissions] or [-1])
        .execute()
    )

    summary_rows: list[dict[str, Any]] = []
    context_by_submission: dict[int, dict[str, Any]] = {}
    for submission in submissions:
        student = students[submission["student_id"]]
        profile = profiles[submission["student_id"]]
        section = sections[student["section_id"]]
        assignment = assignments[submission["teaching_assignment_id"]]
        teacher = teachers[assignment["teacher_id"]]
        subject = subjects[assignment["subject_id"]]
        context = {
            "submission_id": submission["id"],
            "submitted_at": submission["submitted_at"],
            "student_number": student["student_number"],
            "student_name": profile["display_name"],
            "school_level": section["school_level"],
            "grade_level": section["grade_level"],
            "section": section["code"],
            "subject_code": subject["code"],
            "subject_name": subject["name"],
            "teacher_employee_number": teacher["employee_number"],
            "teacher_name": teacher["display_name"],
            "client_version": submission["client_version"],
        }
        summary_rows.append(context)
        context_by_submission[int(submission["id"])] = context

    response_rows: list[dict[str, Any]] = []
    for response in responses:
        question = questions[response["question_item_id"]]
        response_rows.append(
            {
                **context_by_submission[int(response["submission_id"])],
                "question_section": question["section_key"],
                "question_position": question["position"],
                "question": question["prompt"],
                "response_type": question["response_type"],
                "rating_value": response["rating_value"],
                "text_value": response["text_value"],
                "is_not_applicable": response["is_not_applicable"],
            }
        )
    response_rows.sort(
        key=lambda row: (row["submitted_at"], row["submission_id"], row["question_position"])
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = Path("exports") / f"alpha_submission_review_{timestamp}"
    output_dir.mkdir(parents=True, mode=0o700)
    write_csv(output_dir / "submission_summary.csv", summary_rows, summary_fields())
    write_csv(output_dir / "submission_responses.csv", response_rows, response_fields())
    print(f"Exported {len(summary_rows)} submissions and {len(response_rows)} responses.")
    print(f"Private review files: {output_dir}")


def summary_fields() -> list[str]:
    return [
        "submission_id", "submitted_at", "student_number", "student_name",
        "school_level", "grade_level", "section", "subject_code", "subject_name",
        "teacher_employee_number", "teacher_name", "client_version",
    ]


def response_fields() -> list[str]:
    return summary_fields() + [
        "question_section", "question_position", "question", "response_type",
        "rating_value", "text_value", "is_not_applicable",
    ]


def write_csv(path: Path, data: list[dict[str, Any]], fieldnames: list[str]) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)


if __name__ == "__main__":
    main()
