from pathlib import Path
import unittest

from scripts.prepare_roster_import import employee_number, prepare_rows


def valid_sheets():
    return {
        "Sections": [
            {
                "school_level": "SHS",
                "grade_level": "12",
                "canvas_section_name": "12STEM-1A",
                "section_code": "12STEM-1A",
                "review_status": "Ready",
                "_source_row": 2,
            }
        ],
        "Subjects": [
            {
                "subject_code": "UCSP",
                "subject_long_name": "Understanding Culture, Society, and Politics",
                "review_status": "Ready",
                "_source_row": 2,
            }
        ],
        "Teachers": [
            {
                "teacher_user_id": "H202290001",
                "teacher_name": "Alpha, Teacher",
                "teacher_email": "alpha@example.invalid",
                "review_status": "Ready",
                "_source_row": 2,
            },
            {
                "teacher_user_id": "H202290002",
                "teacher_name": "Beta, Teacher",
                "teacher_email": "beta@example.invalid",
                "review_status": "Ready",
                "_source_row": 3,
            },
        ],
        "Teaching Assignments": [
            {
                "assignment_key": "UCSP-A",
                "section_code": "12STEM-1A",
                "subject_code": "UCSP",
                "teacher_user_id": "H202290001",
                "review_status": "Ready",
                "_source_row": 2,
            },
            {
                "assignment_key": "UCSP-B",
                "section_code": "12STEM-1A",
                "subject_code": "UCSP",
                "teacher_user_id": "H202290002",
                "review_status": "Ready",
                "_source_row": 3,
            },
        ],
        "Students": [
            {
                "student_number": "202600001",
                "full_name": "Synthetic Student",
                "email": "student@example.invalid",
                "section_code": "12STEM-1A",
                "review_status": "Matched",
                "_source_row": 2,
            }
        ],
        "Student Assignments": [
            {
                "student_number": "202600001",
                "assignment_key": "UCSP-A",
                "review_status": "Ready",
                "_source_row": 2,
            }
        ],
        "QC Issues": [],
    }


class RosterImportPreparationTest(unittest.TestCase):
    def test_canvas_teacher_id_becomes_employee_number(self):
        self.assertEqual(employee_number("H202290001"), "202290001")
        self.assertEqual(employee_number("ALPHA-T001"), "ALPHA-T001")

    def test_shared_class_is_preserved_as_information(self):
        prepared = prepare_rows(valid_sheets())

        self.assertEqual(prepared.error_count, 0)
        shared = [issue for issue in prepared.issues if issue.code == "SHARED_CLASS"]
        self.assertEqual(len(shared), 1)
        self.assertEqual(len(prepared.teaching_assignments), 2)

    def test_student_mapped_to_both_shared_teachers_requires_review(self):
        sheets = valid_sheets()
        sheets["Student Assignments"].append(
            {
                "student_number": "202600001",
                "assignment_key": "UCSP-B",
                "review_status": "Ready",
                "_source_row": 3,
            }
        )

        prepared = prepare_rows(sheets)

        self.assertEqual(prepared.error_count, 0)
        self.assertTrue(
            any(
                issue.code == "STUDENT_ASSIGNED_TO_SHARED_TEACHERS"
                and issue.severity == "warning"
                for issue in prepared.issues
            )
        )

    def test_open_workbook_qc_blocks_bundle(self):
        sheets = valid_sheets()
        sheets["QC Issues"] = [
            {
                "severity": "High",
                "record_id": "12STEM-1A",
                "issue": "No active teacher enrollment",
                "resolution": "Open",
                "_source_row": 2,
            }
        ]

        prepared = prepare_rows(sheets)

        self.assertEqual(prepared.error_count, 1)
        self.assertEqual(prepared.issues[-1].code, "OPEN_WORKBOOK_QC")

    def test_high_severity_qc_cannot_be_accepted(self):
        sheets = valid_sheets()
        sheets["QC Issues"] = [
            {
                "severity": "High",
                "record_id": "12STEM-1A",
                "issue": "No active teacher enrollment",
                "resolution": "Accepted",
                "_source_row": 2,
            }
        ]

        prepared = prepare_rows(sheets)

        self.assertTrue(
            any(issue.code == "ACCEPTED_HIGH_WORKBOOK_QC" for issue in prepared.issues)
        )

    def test_cross_section_student_assignment_is_rejected(self):
        sheets = valid_sheets()
        sheets["Students"][0]["section_code"] = "12STEM-OTHER"

        prepared = prepare_rows(sheets)

        codes = {issue.code for issue in prepared.issues}
        self.assertIn("UNKNOWN_SECTION", codes)
        self.assertIn("CROSS_SECTION_ASSIGNMENT", codes)


class RosterImportMigrationContractTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = (
            Path(__file__).resolve().parents[1]
            / "supabase"
            / "migrations"
            / "202608240001_roster_import_staging.sql"
        ).read_text(encoding="utf-8").lower()

    def test_staging_tables_are_private(self):
        for table in (
            "roster_import_batches",
            "roster_stage_sections",
            "roster_stage_teachers",
            "roster_stage_subjects",
            "roster_stage_students",
            "roster_stage_teaching_assignments",
            "roster_stage_student_assignments",
            "roster_import_issues",
        ):
            self.assertIn(f"alter table public.{table} enable row level security", self.sql)
            self.assertIn(f"revoke all on public.{table} from anon, authenticated", self.sql)

    def test_activation_is_service_role_only(self):
        signature = "public.activate_roster_import_batch(bigint)"
        self.assertIn(f"revoke execute on function {signature} from public, anon, authenticated", self.sql)
        self.assertIn(f"grant execute on function {signature} to service_role", self.sql)

    def test_shared_classes_are_not_collapsed(self):
        self.assertIn("'shared_class'", self.sql)
        self.assertIn(
            "unique (evaluation_period_id, section_id, subject_id, teacher_id)",
            (
                Path(__file__).resolve().parents[1]
                / "supabase"
                / "migrations"
                / "202608230001_initial_schema.sql"
            ).read_text(encoding="utf-8").lower(),
        )


if __name__ == "__main__":
    unittest.main()
