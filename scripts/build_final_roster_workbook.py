"""Build a private final-roster reconciliation workbook for QC review.

This is an offline transformation. It replaces the student and
student-assignment sheets with the Aug 25 enrollment roster, using the
existing Canvas/SIS reconciliation for section and assignment context. It
does not upload data or activate a Supabase batch.
"""

from __future__ import annotations

import argparse
import re
from collections import Counter, defaultdict
from pathlib import Path

from openpyxl import load_workbook


DEFAULT_SOURCE = Path(
    "outputs/ucsp_roster_reconciliation_20260824/"
    "FEU_HS_Teacher_Performance_Evaluation_Roster_UCSP_Reconciled_SectionsRefreshed.xlsx"
)
DEFAULT_ENROLLMENT = Path(
    "/Users/ronmarccharlesms/Downloads/"
    "FEU HS Enrolled as of Aug 25_SY26-27(3).xlsx"
)
DEFAULT_OUTPUT = Path("outputs/FEU_TPE_Final_Q1_2026-2027.xlsx")


def clean(value: object) -> str:
    return "" if value is None else str(value).strip()


def grade_number(value: object) -> int:
    match = re.search(r"\d+", clean(value))
    if not match:
        raise SystemExit(f"Could not determine grade level from {value!r}")
    return int(match.group())


def records(sheet) -> tuple[list[str], list[dict[str, object]]]:
    rows = list(sheet.iter_rows(values_only=True))
    headers = [clean(value) for value in rows[0]]
    return headers, [dict(zip(headers, row)) for row in rows[1:] if any(row)]


def replace_sheet(workbook, name: str, headers: list[str], rows: list[dict[str, object]]) -> None:
    if name in workbook.sheetnames:
        del workbook[name]
    sheet = workbook.create_sheet(name)
    sheet.append(headers)
    for row in rows:
        sheet.append([row.get(header, "") for header in headers])
    sheet.freeze_panes = "A2"
    sheet.auto_filter.ref = sheet.dimensions


def build(source: Path, enrollment: Path, output: Path) -> dict[str, int]:
    if not source.is_file():
        raise SystemExit(f"Source reconciliation workbook does not exist: {source}")
    if not enrollment.is_file():
        raise SystemExit(f"Final enrollment workbook does not exist: {enrollment}")

    workbook = load_workbook(source)
    enrollment_book = load_workbook(enrollment, read_only=True, data_only=True)
    try:
        section_headers, section_rows = records(workbook["Sections"])
        old_student_headers, old_student_rows = records(workbook["Students"])
        assignment_headers, assignment_rows = records(workbook["Teaching Assignments"])
        roster_headers, roster_rows = records(enrollment_book["As of August 25"])
    finally:
        enrollment_book.close()

    section_by_source: dict[str, dict[str, object]] = {}
    for row in old_student_rows:
        source_name = clean(row.get("source_k12_section"))
        if source_name:
            candidate = {
                "canvas_section_name": clean(row.get("canvas_section_name")),
                "section_code": clean(row.get("section_code")),
            }
            previous = section_by_source.setdefault(source_name, candidate)
            if previous != candidate:
                raise SystemExit(f"Ambiguous existing section mapping: {source_name}")

    # The final workbook uses the same official labels as the SIS exports, but
    # the JHS/GAS rows are explicitly guarded so they cannot be lost again.
    explicit = {
        "GRADE 7 Sec-1 (S.Y.26-27)": ("Grade 7-1", "G07-1"),
        "GRADE 7 Sec-2 (S.Y.26-27)": ("Grade 7-2", "G07-2"),
        "GRADE 8 Sec-1 (S.Y.26-27)": ("Grade 8-1", "G08-1"),
        "GRADE 8 Sec-2 (S.Y.26-27)": ("Grade 8-2", "G08-2"),
        "GRADE 9 Sec-1 (S.Y.26-27)": ("Grade 9-1", "G09-1"),
        "GRADE 9 Sec-2 (S.Y.26-27)": ("Grade 9-2", "G09-2"),
        "GRADE 10 Sec-1 (S.Y.26-27)": ("Grade 10-1", "G10-1"),
        "GRADE 10 Sec-2 (S.Y.26-27)": ("Grade 10-2", "G10-2"),
        "12GAS-1A (S.Y. 26-27)": ("12GAS-1A", "12G01a"),
        "12GAS-1B (S.Y. 26-27)": ("12GAS-1B", "12G01b"),
    }
    section_by_source.update(
        {source_name: {"canvas_section_name": canvas, "section_code": code} for source_name, (canvas, code) in explicit.items()}
    )

    missing = sorted({clean(row.get("K12 - Section")) for row in roster_rows} - set(section_by_source))
    if missing:
        raise SystemExit("Final roster sections have no reconciliation mapping: " + "; ".join(missing))

    students: list[dict[str, object]] = []
    for row in roster_rows:
        student_number = clean(row.get("Student Number"))
        source_name = clean(row.get("K12 - Section"))
        mapping = section_by_source[source_name]
        grade = grade_number(row.get("Year Level"))
        first = clean(row.get("First Name"))
        middle = clean(row.get("Middle Name"))
        last = clean(row.get("Last Name"))
        students.append({
            "student_number": student_number,
            "canvas_user_id": f"H{student_number}",
            "full_name": " ".join(part for part in (first, middle, last) if part),
            "first_name": first,
            "middle_name": middle,
            "last_name": last,
            "email": f"{student_number}@feuhighschool.edu.ph",
            "school_level": "JHS" if grade <= 10 else "SHS",
            "grade_level": grade,
            "canvas_section_name": mapping["canvas_section_name"],
            "section_code": mapping["section_code"],
            "source_k12_section": source_name,
            "review_status": "Matched",
            "review_notes": "Final Aug 25 enrollment roster",
        })

    by_section: dict[str, list[dict[str, object]]] = defaultdict(list)
    for assignment in assignment_rows:
        by_section[clean(assignment.get("section_code"))].append(assignment)
    assignments_by_key = {clean(row.get("assignment_key")): row for row in assignment_rows}
    subject_counts = Counter(
        (clean(row.get("section_code")), clean(row.get("subject_code"))) for row in assignment_rows
    )
    eligible = {
        clean(row.get("assignment_key"))
        for row in assignment_rows
        if subject_counts[(clean(row.get("section_code")), clean(row.get("subject_code")))] == 1
    }
    student_assignments: list[dict[str, object]] = []
    for student in students:
        for assignment in by_section[clean(student["section_code"])]:
            key = clean(assignment.get("assignment_key"))
            if key in eligible:
                student_assignments.append({
                    "student_number": student["student_number"],
                    "assignment_key": key,
                    "school_level": student["school_level"],
                    "canvas_section_name": student["canvas_section_name"],
                    "section_code": student["section_code"],
                    "subject_code": assignment.get("subject_code"),
                    "subject_long_name": assignment.get("subject_long_name"),
                    "teacher_user_id": assignment.get("teacher_user_id"),
                    "teacher_name": assignment.get("teacher_name"),
                    "review_status": "Ready",
                })

    student_headers = old_student_headers
    student_assignment_headers, _ = records(workbook["Student Assignments"])
    replace_sheet(workbook, "Students", student_headers, students)
    replace_sheet(workbook, "Student Assignments", student_assignment_headers, student_assignments)

    if "Review Guide" in workbook.sheetnames:
        guide = workbook["Review Guide"]
        guide.append(["Roster refresh", "Aug 25 final enrollment roster with Canvas/SIS reconciliation"])
        guide.append(["Import status", "QC review required; no Supabase import performed"])
        guide.append(["Shared-class policy", "Student assignments exclude section-subject pairs with multiple teachers"])

    output.parent.mkdir(parents=True, exist_ok=True)
    workbook.save(output)
    workbook.close()
    return {
        "students": len(students),
        "student_assignments": len(student_assignments),
        "eligible_assignments": len(eligible),
        "excluded_shared_assignments": len(assignment_rows) - len(eligible),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--enrollment", type=Path, default=DEFAULT_ENROLLMENT)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    counts = build(args.source, args.enrollment, args.output)
    print(f"Created {args.output}")
    print("; ".join(f"{key}={value}" for key, value in counts.items()))


if __name__ == "__main__":
    main()
