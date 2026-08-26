"""Upload a validated roster bundle to the private Supabase staging tables.

The command creates one draft import batch, uploads the six staged CSV files,
and runs the database validator. It never activates a roster. A Supabase
``sb_secret_`` key is requested interactively and is not written to disk.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import json
import os
from datetime import date
from pathlib import Path
from typing import Any

from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions


STAGE_FILES = {
    "roster_stage_sections": "sections_stage.csv",
    "roster_stage_teachers": "teachers_stage.csv",
    "roster_stage_subjects": "subjects_stage.csv",
    "roster_stage_students": "students_stage.csv",
    "roster_stage_teaching_assignments": "teaching_assignments_stage.csv",
    "roster_stage_student_assignments": "student_assignments_stage.csv",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.getenv("SUPABASE_URL", ""),
        help="Hosted Supabase project URL; defaults to SUPABASE_URL.",
    )
    parser.add_argument(
        "--bundle",
        type=Path,
        default=Path("exports/roster_import_SY2026_Q1_final"),
        help="Prepared, git-ignored staging bundle directory.",
    )
    parser.add_argument("--batch-code", help="Expected batch code; defaults to manifest value.")
    parser.add_argument(
        "--evaluation-period-code",
        help="Expected evaluation period code; defaults to manifest value.",
    )
    return parser.parse_args()


def response_rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if not isinstance(data, list):
        raise RuntimeError("Supabase returned an unexpected response.")
    return data


def read_bundle(bundle: Path) -> tuple[dict[str, Any], dict[str, list[dict[str, str]]]]:
    manifest_path = bundle / "manifest.json"
    if not manifest_path.is_file():
        raise SystemExit(f"Bundle manifest not found: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("errors") != 0:
        raise SystemExit("The bundle has validation errors; rebuild it before uploading.")

    tables: dict[str, list[dict[str, str]]] = {}
    for table, filename in STAGE_FILES.items():
        path = bundle / filename
        if not path.is_file():
            raise SystemExit(f"Required staging file not found: {path}")
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise SystemExit(f"Staging file is empty: {path}")
        if any(row.get("batch_code") != manifest.get("batch_code") for row in rows):
            raise SystemExit(f"Batch code mismatch in {path.name}.")
        tables[table] = rows
    return manifest, tables


def insert_chunks(client: Client, table: str, rows: list[dict[str, Any]], chunk_size: int = 500) -> None:
    for start in range(0, len(rows), chunk_size):
        client.table(table).insert(rows[start : start + chunk_size]).execute()


def main() -> None:
    args = parse_args()
    url = args.url.strip()
    if not url.startswith("https://") or ".supabase.co" not in url:
        raise SystemExit("Provide the hosted Supabase project URL with --url or SUPABASE_URL.")

    manifest, tables = read_bundle(args.bundle)
    batch_code = args.batch_code or manifest.get("batch_code")
    period_code = args.evaluation_period_code or manifest.get("evaluation_period_code")
    if batch_code != manifest.get("batch_code"):
        raise SystemExit("--batch-code does not match the bundle manifest.")
    if period_code != manifest.get("evaluation_period_code"):
        raise SystemExit("--evaluation-period-code does not match the bundle manifest.")
    try:
        source_date = date.fromisoformat(str(manifest["source_date"]))
    except (KeyError, ValueError) as exc:
        raise SystemExit("The bundle manifest contains an invalid source_date.") from exc

    secret_key = getpass.getpass("Supabase secret key (input hidden): ").strip()
    if not secret_key.startswith("sb_secret_"):
        raise SystemExit("A current sb_secret_ key is required for roster staging.")
    fingerprint = hashlib.sha256(secret_key.encode("utf-8")).hexdigest()[:8]
    print(f"Secret key received ({len(secret_key)} characters; fingerprint {fingerprint}).")

    client = create_client(
        url,
        secret_key,
        options=SyncClientOptions(auto_refresh_token=False, persist_session=False),
    )
    periods = response_rows(
        client.table("evaluation_periods")
        .select("id,code,status")
        .eq("code", period_code)
        .limit(2)
        .execute()
    )
    if len(periods) != 1:
        raise SystemExit(f"Expected exactly one evaluation period {period_code!r}; found {len(periods)}.")
    period = periods[0]
    if period["status"] != "draft":
        raise SystemExit(
            f"Evaluation period {period_code!r} is {period['status']!r}; staging requires draft status."
        )
    existing = response_rows(
        client.table("roster_import_batches")
        .select("id,status")
        .eq("batch_code", batch_code)
        .limit(2)
        .execute()
    )
    if existing:
        raise SystemExit(
            f"Batch {batch_code!r} already exists (id={existing[0]['id']}, status={existing[0]['status']})."
        )

    batch = response_rows(
        client.table("roster_import_batches")
        .insert(
            {
                "batch_code": batch_code,
                "evaluation_period_id": period["id"],
                "source_filename": manifest["source_filename"],
                "source_sha256": manifest["source_sha256"],
                "source_date": source_date.isoformat(),
                "status": "draft",
                "notes": "Uploaded from locally validated final roster bundle; activation intentionally deferred.",
            }
        )
        .execute()
    )[0]
    batch_id = batch["id"]
    print(f"Created draft roster import batch {batch_code} (id={batch_id}).")

    field_maps = {
        "roster_stage_sections": ("section_code", "canvas_section_name", "school_level", "grade_level", "strand", "source_row"),
        "roster_stage_teachers": ("employee_number", "display_name", "email", "source_row"),
        "roster_stage_subjects": ("subject_code", "subject_name", "source_row"),
        "roster_stage_students": ("student_number", "display_name", "email", "section_code", "source_row"),
        "roster_stage_teaching_assignments": ("assignment_key", "section_code", "subject_code", "teacher_employee_number", "source_row"),
        "roster_stage_student_assignments": ("student_number", "assignment_key", "source_row"),
    }
    for table, rows in tables.items():
        columns = field_maps[table]
        prepared = []
        for row in rows:
            record: dict[str, Any] = {"batch_id": batch_id}
            for column in columns:
                value = row.get(column, "")
                if column == "source_row":
                    record[column] = int(value) if value else None
                elif column == "grade_level":
                    record[column] = int(value)
                elif column == "strand":
                    record[column] = value or None
                elif column == "email":
                    record[column] = value or None
                else:
                    record[column] = value
            prepared.append(record)
        insert_chunks(client, table, prepared)
        print(f"Uploaded {len(prepared):,} rows to {table}.")

    result = client.rpc("validate_roster_import_batch", {"p_batch_id": batch_id}).execute()
    validation = result.data
    print("Database validation result:")
    print(json.dumps(validation, indent=2, sort_keys=True))
    print("Roster remains staged only. No production tables were activated.")


if __name__ == "__main__":
    main()
