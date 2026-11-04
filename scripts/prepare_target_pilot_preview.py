"""Build a private, offline target-aware preview for the existing synthetic pilot."""
from __future__ import annotations

import argparse
import csv
import json
import os
from collections import Counter, defaultdict
from pathlib import Path


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def write_csv(path: Path, rows: list[dict], fields: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    path.chmod(0o600)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True, help="Validated target-aware Q2 bundle directory")
    parser.add_argument("--old-pilot-preview", type=Path, required=True,
                        help="Prior target preview; used only for the 45 synthetic account and section plan")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    manifest = json.loads((args.bundle / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("contract") != "roster-v2-validated" or manifest.get("counts", {}).get("students") != 2661:
        raise SystemExit("Expected the validated 2,661-student Q2 bundle")
    students = read_csv(args.bundle / "students.csv")
    allocations = read_csv(args.bundle / "evaluation_allocations.csv")
    teachers = read_csv(args.bundle / "teachers.csv")
    subject_loads = read_csv(args.bundle / "subject_loads.csv")
    homeroom = {row["section_code"]: row for row in read_csv(args.bundle / "homeroom.csv")}
    groups = {row["section_code"]: row["teaching_section_code"]
              for row in read_csv(args.bundle / "section_groups.csv")}
    teacher_names = {row["employee_number"]: row.get("display_name", "") for row in teachers}
    load_keys = {row["assignment_key"] for row in subject_loads}
    program_codes = {row["program_code"] for row in read_csv(args.bundle / "programs.csv")}

    real_by_section: dict[tuple[str, str], list[str]] = defaultdict(list)
    for row in students:
        key = (row["section_code"], row["teaching_section_code"])
        real_by_section[key].append(row["student_number"])
    for ids in real_by_section.values():
        ids.sort()

    targets_by_student: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in allocations:
        targets_by_student[row["student_number"]].append(row)

    old_rows = read_csv(args.old_pilot_preview)
    accounts_by_key: dict[str, dict[str, str]] = {}
    for row in old_rows:
        accounts_by_key.setdefault(row["pilot_student_key"], row)
    accounts = [accounts_by_key[key] for key in sorted(accounts_by_key)]
    cohorts = Counter(row["cohort"] for row in accounts)
    if len(accounts) != 45 or cohorts != Counter({"JHS": 15, "G11": 15, "G12": 15}):
        raise SystemExit(f"Expected the existing 45-account pilot roster (15 per cohort), got {dict(cohorts)}")

    output = args.output_dir
    payload_rows: list[dict[str, str]] = []
    review_rows: list[dict[str, str]] = []
    proxy_cursor: Counter[tuple[str, str]] = Counter()
    mapped_accounts = []
    old_section_remap = Counter()

    for account in accounts:
        original_section = account["source_plan_section_code"]
        official_section = account["student_section_code"]
        if original_section == "11GS02":
            official_section = "11GS01"
            old_section_remap[original_section] += 1
        teaching_section = groups.get(official_section, official_section)
        section_key = (official_section, teaching_section)
        proxy_ids = real_by_section.get(section_key, [])
        if not proxy_ids:
            raise SystemExit(f"No current master-list students in pilot section {official_section}/{teaching_section}")
        proxy_id = proxy_ids[proxy_cursor[section_key] % len(proxy_ids)]
        proxy_cursor[section_key] += 1
        proxy_targets = targets_by_student.get(proxy_id, [])
        types = Counter(row["target_type"] for row in proxy_targets)
        subject_teacher_ids = {row["teacher_employee_number"] for row in proxy_targets
                               if row["target_type"] == "subject_teacher"}
        expected = Counter({"subject_teacher": 2, "homeroom_adviser": 1, "homeroom_program": 1})
        if types != expected or len(subject_teacher_ids) != 2:
            raise SystemExit(f"Proxy target validation failed for section {official_section}")

        for target in proxy_targets:
            teacher_id = target.get("teacher_employee_number", "")
            target_key = target["target_key"]
            if target["target_type"] == "subject_teacher" and target_key.removeprefix("SUBJECT|") not in load_keys:
                raise SystemExit(f"Pilot target does not resolve to current SubjectLoads: {target_key}")
            if target["target_type"] == "homeroom_program" and target.get("program_code") not in program_codes:
                raise SystemExit("Pilot homeroom program is absent from the current catalog bundle")
            if target["target_type"] == "homeroom_adviser" and teacher_id != homeroom[teaching_section]["adviser_employee_number"]:
                raise SystemExit(f"Pilot adviser mismatch in {teaching_section}")
            base = {
                "pilot_student_key": account["pilot_student_key"],
                "email": account["email"],
                "cohort": account["cohort"],
                "grade_level": account["grade_level"],
                "student_section_code": official_section,
                "teaching_section_code": teaching_section,
                "target_type": target["target_type"],
                "target_key": target_key,
                "teacher_employee_number": teacher_id,
                "subject_code": target.get("subject_code", ""),
                "subject_name": target.get("subject_name", ""),
                "program_code": target.get("program_code", ""),
                "allocation_basis": target.get("allocation_basis", ""),
            }
            payload_rows.append(base)
            review_rows.append({**base, "teacher_name": teacher_names.get(teacher_id, "")})
        mapped_accounts.append({
            "pilot_student_key": account["pilot_student_key"],
            "cohort": account["cohort"],
            "official_section": official_section,
            "teaching_section": teaching_section,
            "proxy_student_targets_from_section": True,
        })

    target_types = Counter(row["target_type"] for row in payload_rows)
    expected_target_types = Counter({"subject_teacher": 90, "homeroom_adviser": 45, "homeroom_program": 45})
    if len(payload_rows) != 180 or target_types != expected_target_types:
        raise SystemExit(f"Expected 180 pilot targets, got {len(payload_rows)} / {dict(target_types)}")

    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    fields = ["pilot_student_key", "email", "cohort", "grade_level", "student_section_code",
              "teaching_section_code", "target_type", "target_key", "teacher_employee_number",
              "subject_code", "subject_name", "program_code", "allocation_basis"]
    write_csv(output / "pilot_target_import_preview.csv", payload_rows, fields)
    write_csv(output / "pilot_target_review.csv", review_rows, fields + ["teacher_name"])
    write_csv(output / "pilot_accounts_section_summary.csv", mapped_accounts,
              ["pilot_student_key", "cohort", "official_section", "teaching_section", "proxy_student_targets_from_section"])

    summary = {
        "contract": "synthetic-pilot-target-preview",
        "source_q2_bundle": str(args.bundle),
        "source_q2_manifest_sha256": __import__("hashlib").sha256((args.bundle / "manifest.json").read_bytes()).hexdigest(),
        "pilot_accounts": len(accounts),
        "accounts_by_cohort": dict(cohorts),
        "pilot_target_rows": len(payload_rows),
        "targets_by_type": dict(target_types),
        "unique_subject_teachers_in_pilot": len({r["teacher_employee_number"] for r in payload_rows if r["target_type"] == "subject_teacher"}),
        "unique_subject_codes_in_pilot": len({r["subject_code"] for r in payload_rows if r["target_type"] == "subject_teacher"}),
        "remapped_old_sections": dict(old_section_remap),
        "period_code": "PILOT-SY2026-2027-Q2-FINALS-01",
        "period_status": "draft; do not open until target-aware app is deployed",
        "live_import_performed": False,
    }
    (output / "summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    (output / "summary.json").chmod(0o600)
    note = (
        "# Q2 target-aware pre-upload and pilot review\n\n"
        f"The master list contains {manifest['counts']['students']:,} unique students. The local roster candidate has "
        f"{manifest['counts']['subject_allocations']:,} subject targets, {manifest['counts']['adviser_allocations']:,} adviser targets, "
        f"{manifest['counts']['program_allocations']:,} program targets, and {manifest['counts']['evaluation_allocations']:,} total targets.\n\n"
        f"It contains {manifest['counts']['subject_loads']} eligible SubjectLoads, {manifest['counts']['teachers']} teachers, "
        f"and {manifest['counts']['advisory_sections']} adviser/teaching sections. All {manifest['canvas_sm_courses_excluded']} Canvas `_SM` courses are excluded. "
        f"The subject invitation basis is {manifest['counts']['subject_allocation_basis']['regular_load']:,} regular and "
        f"{manifest['counts']['subject_allocation_basis']['advisory_secondary']:,} advisory-secondary. "
        f"Teachers with zero subject invitations: {manifest['counts']['zero_subject_invitation_teachers']}.\n\n"
        "## Pre-upload checks already completed locally\n\n"
        "- Every student has exactly two distinct subject teachers, one homeroom adviser, and one Be Brave homeroom program.\n"
        "- All subject targets resolve to current section-subject-teacher loads; adviser and program targets resolve to the section mappings.\n"
        "- SubjectLoads remains authoritative. Regular-load assignments are preferred; adviser overlaps are secondary. The specified Grade 7-2, 8-2, and 10-2 Science loads are omitted.\n"
        "- The 11GS01 official section keeps its 11ME02 teaching/adviser mapping.\n"
        "- The full roster has not been uploaded. The manifest marks this bundle `database_compatible=false`; the legacy uploader must not be used.\n\n"
        "## Existing-account synthetic pilot preview\n\n"
        f"The old pilot account list maps to {summary['pilot_accounts']} synthetic accounts (15 each for JHS, Grade 11, and Grade 12) and "
        f"{summary['pilot_target_rows']} target links (90 subject, 45 adviser, 45 program). The old 11GS02 pilot slot maps to official 11GS01 and teaching section 11ME02. "
        "For each synthetic account, the two subject targets are copied from a real-student allocation in that same current official/teaching section; this preserves a valid current student target pattern without copying the real student identity. "
        "This preview creates no Auth users and writes no database rows. Keep the pilot period draft until the matching app is deployed and acceptance checks pass.\n\n"
        "## Before any upload\n\n"
        "Confirm the consolidated summary, check the two suspended Canvas accounts before enabling their logins, and use a target-aware staged import with a draft period. "
        "The questionnaire schema migrations are already applied; do not reapply them. No current target-aware uploader is approved for this bundle.\n"
    )
    (output / "PREUPLOAD_AND_PILOT_REVIEW.md").write_text(note, encoding="utf-8")
    (output / "PREUPLOAD_AND_PILOT_REVIEW.md").chmod(0o600)
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
