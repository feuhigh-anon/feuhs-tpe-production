"""Audit roster staging and production table coverage without exporting PII.

The report contains counts, statuses, duplicate counts, and table-level
comparisons only. It uses a Supabase service key entered interactively and
writes a JSON report plus a compact CSV summary under the ignored exports/
directory.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions


TABLES = (
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
)

STAGE_KEYS = {
    "roster_stage_sections": ("section_code",),
    "roster_stage_teachers": ("employee_number",),
    "roster_stage_subjects": ("subject_code",),
    "roster_stage_students": ("student_number",),
    "roster_stage_teaching_assignments": ("assignment_key",),
    "roster_stage_student_assignments": ("student_number", "assignment_key"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default=os.getenv("SUPABASE_URL", ""))
    parser.add_argument("--batch-id", type=int, default=1)
    parser.add_argument("--output-dir", type=Path, default=Path("exports"))
    return parser.parse_args()


def rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    if not isinstance(data, list):
        raise RuntimeError("Supabase returned an unexpected response.")
    return data


def paged(client: Client, table: str, columns: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    start = 0
    while True:
        query = client.table(table).select(columns).range(start, start + 999)
        for column, value in (filters or {}).items():
            query = query.eq(column, value)
        chunk = rows(query.execute())
        result.extend(chunk)
        if len(chunk) < 1000:
            return result
        start += 1000


def duplicate_count(data: list[dict[str, Any]], keys: tuple[str, ...]) -> int:
    values = [tuple(str(row.get(key) or "") for key in keys) for row in data]
    return sum(count - 1 for count in Counter(values).values() if count > 1)


def main() -> None:
    args = parse_args()
    url = args.url.strip()
    if not url.startswith("https://") or ".supabase.co" not in url:
        raise SystemExit("Provide the hosted Supabase project URL with --url or SUPABASE_URL.")
    secret_key = getpass.getpass("Supabase secret key (input hidden): ").strip()
    if not secret_key.startswith("sb_secret_"):
        raise SystemExit("A current sb_secret_ key is required for this read-only audit.")
    fingerprint = hashlib.sha256(secret_key.encode("utf-8")).hexdigest()[:8]
    print(f"Secret key received ({len(secret_key)} characters; fingerprint {fingerprint}).")
    client = create_client(
        url,
        secret_key,
        options=SyncClientOptions(auto_refresh_token=False, persist_session=False),
    )

    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "batch_id": args.batch_id,
        "tables": {},
        "batch": None,
        "staging": {},
        "findings": [],
    }
    for table in TABLES:
        response = client.table(table).select("*", count="exact", head=True).execute()
        report["tables"][table] = {"estimated_or_exact_rows": getattr(response, "count", None)}

    batch_rows = rows(
        client.table("roster_import_batches")
        .select("id,batch_code,evaluation_period_id,status,source_filename,validation_summary,created_at,validated_at,activated_at")
        .eq("id", args.batch_id)
        .limit(1)
        .execute()
    )
    if not batch_rows:
        raise SystemExit(f"Roster import batch {args.batch_id} was not found.")
    report["batch"] = batch_rows[0]

    for table, keys in STAGE_KEYS.items():
        data = paged(client, table, ",".join(("id", "batch_id", *keys)), {"batch_id": args.batch_id})
        report["staging"][table] = {
            "rows": len(data),
            "duplicate_key_rows": duplicate_count(data, keys),
        }
        if report["staging"][table]["duplicate_key_rows"]:
            report["findings"].append({
                "severity": "error",
                "table": table,
                "finding": "duplicate staged key rows",
            })

    production_pairs = {
        "sections": ("roster_stage_sections", "sections"),
        "teachers": ("roster_stage_teachers", "teachers"),
        "subjects": ("roster_stage_subjects", "subjects"),
        "students": ("roster_stage_students", "students"),
        "teaching_assignments": ("roster_stage_teaching_assignments", "teaching_assignments"),
        "student_assignments": ("roster_stage_student_assignments", "student_assignments"),
    }
    for label, (stage_table, production_table) in production_pairs.items():
        staged = report["staging"][stage_table]["rows"]
        production = report["tables"][production_table]["estimated_or_exact_rows"]
        report["findings"].append({
            "severity": "info" if production == 0 or production < staged else "ok",
            "table": label,
            "finding": "production count compared with staged count",
            "staged_rows": staged,
            "production_rows": production,
        })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = args.output_dir / f"supabase_roster_audit_{stamp}.json"
    csv_path = args.output_dir / f"supabase_roster_audit_{stamp}.csv"
    json_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=("table_name", "rows", "duplicate_key_rows"))
        writer.writeheader()
        for table, details in report["tables"].items():
            writer.writerow({"table_name": table, "rows": details["estimated_or_exact_rows"], "duplicate_key_rows": ""})
        for table, details in report["staging"].items():
            writer.writerow({"table_name": f"{table} [batch {args.batch_id}]", **details})
    print(f"Wrote redacted audit JSON: {json_path}")
    print(f"Wrote redacted audit CSV: {csv_path}")
    print(f"Findings: {len(report['findings'])}; no names, emails, or student numbers were written.")


if __name__ == "__main__":
    main()
