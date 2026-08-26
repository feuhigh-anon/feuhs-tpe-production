"""Prepare a 45-account synthetic pilot plan from the staged final roster.

This command is offline. It reads the private staging CSV bundle, selects
15 synthetic students for JHS, Grade 11, and Grade 12, and writes a plan with
real school-year section, subject, and teacher assignments. It does not create
Supabase users or modify the database.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--bundle",
        type=Path,
        default=Path("exports/roster_import_SY2026_Q1_pilot"),
        help="Prepared staging bundle containing the final roster.",
    )
    parser.add_argument("--students-per-cohort", type=int, default=15, choices=range(1, 51))
    parser.add_argument("--output-dir", type=Path, default=Path("exports"))
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise SystemExit(f"Required staging file not found: {path}")
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def round_robin(values: list[str], count: int) -> list[str]:
    if not values:
        raise SystemExit("No eligible sections were found for one of the pilot cohorts.")
    return [values[index % len(values)] for index in range(count)]


def main() -> None:
    args = parse_args()
    bundle = args.bundle
    sections = read_csv(bundle / "sections_stage.csv")
    teachers = read_csv(bundle / "teachers_stage.csv")
    subjects = read_csv(bundle / "subjects_stage.csv")
    assignments = read_csv(bundle / "teaching_assignments_stage.csv")

    section_by_code = {row["section_code"]: row for row in sections}
    teacher_by_number = {row["employee_number"]: row for row in teachers}
    subject_by_code = {row["subject_code"]: row for row in subjects}
    assignment_groups: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for assignment in assignments:
        assignment_groups[(assignment["section_code"], assignment["subject_code"])].append(assignment)

    # Exclude shared section-subjects because the approved policy does not
    # expose ambiguous teacher assignments to students.
    eligible_assignments: dict[str, list[dict[str, str]]] = defaultdict(list)
    for (section_code, _subject_code), group in assignment_groups.items():
        if len({row["teacher_employee_number"] for row in group}) != 1:
            continue
        eligible_assignments[section_code].extend(group)

    cohort_sections = {
        "JHS": sorted(
            code for code, row in section_by_code.items()
            if row["school_level"] == "JHS" and 7 <= int(row["grade_level"]) <= 10
        ),
        "G11": sorted(
            code for code, row in section_by_code.items()
            if row["school_level"] == "SHS" and int(row["grade_level"]) == 11
        ),
        "G12": sorted(
            code for code, row in section_by_code.items()
            if row["school_level"] == "SHS" and int(row["grade_level"]) == 12
        ),
    }

    plan: list[dict[str, Any]] = []
    account_summary: list[dict[str, Any]] = []
    for cohort, eligible_sections in cohort_sections.items():
        selected_sections = round_robin(eligible_sections, args.students_per_cohort)
        for index, section_code in enumerate(selected_sections, start=1):
            section = section_by_code[section_code]
            account_key = f"PILOT-{cohort}-{index:02d}"
            account = {
                "pilot_student_key": account_key,
                "email": f"pilot.{cohort.lower()}.{index:02d}@example.invalid",
                "student_number": account_key,
                "cohort": cohort,
                "school_level": section["school_level"],
                "grade_level": section["grade_level"],
                "section_code": section_code,
                "canvas_section_name": section["canvas_section_name"],
            }
            selected_assignments = sorted(
                eligible_assignments.get(section_code, []),
                key=lambda row: (row["subject_code"], row["teacher_employee_number"]),
            )
            if not selected_assignments:
                raise SystemExit(f"Section {section_code} has no eligible non-shared assignments.")
            account_summary.append({**account, "assignment_count": len(selected_assignments)})
            for assignment in selected_assignments:
                teacher = teacher_by_number.get(assignment["teacher_employee_number"], {})
                subject = subject_by_code.get(assignment["subject_code"], {})
                plan.append({
                    **account,
                    "assignment_key": assignment["assignment_key"],
                    "subject_code": assignment["subject_code"],
                    "subject_name": subject.get("subject_name", ""),
                    "teacher_employee_number": assignment["teacher_employee_number"],
                    "teacher_name": teacher.get("display_name", ""),
                })

    args.output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    csv_path = args.output_dir / f"pilot_cohort_plan_{timestamp}.csv"
    json_path = args.output_dir / f"pilot_cohort_plan_{timestamp}.json"
    fields = list(plan[0])
    descriptor = os.open(csv_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(plan)
    json_path.write_text(
        json.dumps(
            {
                "created_at": datetime.now().isoformat(),
                "students_per_cohort": args.students_per_cohort,
                "total_accounts": len(account_summary),
                "cohorts": {
                    cohort: sum(1 for account in account_summary if account["cohort"] == cohort)
                    for cohort in ("JHS", "G11", "G12")
                },
                "account_summary": account_summary,
                "assignment_rows": len(plan),
                "shared_section_subjects_excluded": sorted(
                    f"{section}|{subject}"
                    for (section, subject), group in assignment_groups.items()
                    if len({row["teacher_employee_number"] for row in group}) != 1
                ),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    os.chmod(json_path, 0o600)
    print(f"Prepared {len(account_summary)} synthetic pilot accounts:")
    print("  JHS: 15")
    print("  G11: 15")
    print("  G12: 15")
    print(f"Assignment rows: {len(plan):,}")
    print(f"Plan CSV: {csv_path}")
    print(f"Plan JSON: {json_path}")
    print("No Supabase users or database rows were created.")


if __name__ == "__main__":
    main()
