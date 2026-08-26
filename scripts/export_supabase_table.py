"""Export one Supabase table to a local CSV using the service key.

This is an administrator utility. Sensitive tables require the explicit
``--include-sensitive`` flag. Files are written under ignored exports/ by
default and are never suitable for committing to Git.
"""

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


ALLOWED_TABLES = {
    "evaluation_period_instruments",
    "evaluation_periods",
    "evaluation_responses",
    "evaluation_submissions",
    "profiles",
    "question_banks",
    "question_items",
    "roster_import_batches",
    "roster_import_issues",
    "roster_stage_sections",
    "roster_stage_student_assignments",
    "roster_stage_students",
    "roster_stage_subjects",
    "roster_stage_teachers",
    "roster_stage_teaching_assignments",
    "sections",
    "student_assignments",
    "students",
    "submission_audit_events",
    "subjects",
    "teachers",
    "teaching_assignments",
}

SENSITIVE_TABLES = {
    "profiles",
    "students",
    "evaluation_submissions",
    "evaluation_responses",
    "submission_audit_events",
    "roster_stage_students",
    "roster_stage_student_assignments",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("table", choices=sorted(ALLOWED_TABLES))
    parser.add_argument("--url", default=os.getenv("SUPABASE_URL", ""))
    parser.add_argument("--batch-id", type=int, help="Filter staging/import tables to one batch.")
    parser.add_argument("--include-sensitive", action="store_true")
    parser.add_argument("--output-dir", type=Path, default=Path("exports"))
    return parser.parse_args()


def rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if not isinstance(data, list):
        raise RuntimeError("Supabase returned an unexpected response.")
    return data


def paged(client: Client, table: str, batch_id: int | None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    start = 0
    while True:
        query = client.table(table).select("*").range(start, start + 999)
        if batch_id is not None and table.startswith(("roster_stage_", "roster_import_")):
            query = query.eq("batch_id", batch_id)
        chunk = rows(query.execute())
        result.extend(chunk)
        if len(chunk) < 1000:
            return result
        start += 1000


def main() -> None:
    args = parse_args()
    url = args.url.strip()
    if not url.startswith("https://") or ".supabase.co" not in url:
        raise SystemExit("Provide the hosted Supabase project URL with --url or SUPABASE_URL.")
    if args.table in SENSITIVE_TABLES and not args.include_sensitive:
        raise SystemExit(
            f"{args.table} may contain personal or response data; rerun with --include-sensitive only if required."
        )
    if args.batch_id is not None and not args.table.startswith(("roster_stage_", "roster_import_")):
        raise SystemExit("--batch-id is only valid for roster staging/import tables.")

    secret_key = getpass.getpass("Supabase secret key (input hidden): ").strip()
    if not secret_key.startswith("sb_secret_"):
        raise SystemExit("A current sb_secret_ key is required for table export.")
    fingerprint = hashlib.sha256(secret_key.encode("utf-8")).hexdigest()[:8]
    print(f"Secret key received ({len(secret_key)} characters; fingerprint {fingerprint}).")
    client = create_client(
        url,
        secret_key,
        options=SyncClientOptions(auto_refresh_token=False, persist_session=False),
    )
    data = paged(client, args.table, args.batch_id)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    suffix = f"_batch{args.batch_id}" if args.batch_id is not None else ""
    path = args.output_dir / f"supabase_{args.table}{suffix}_{datetime.now():%Y%m%d_%H%M%S}.csv"
    fields = sorted({key for row in data for key in row})
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(data)
    print(f"Exported {len(data):,} rows to {path}")
    print("Review the file locally and do not commit it to GitHub.")


if __name__ == "__main__":
    main()
