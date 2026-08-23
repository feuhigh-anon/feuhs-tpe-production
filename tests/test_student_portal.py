import unittest
from dataclasses import replace
from pathlib import Path

from feval.student_demo_data import DEMO_ASSIGNMENTS, DEMO_STUDENT, DEMO_SUBMISSIONS
from feval.student_portal import (
    assignments_for_student,
    evaluation_key,
    pending_assignments,
    submitted_assignment_ids,
)


class StudentPortalTest(unittest.TestCase):
    def test_public_demo_records_are_explicitly_synthetic(self):
        self.assertEqual(DEMO_STUDENT.name, "Demo Student")
        self.assertTrue(DEMO_STUDENT.email.endswith(".invalid"))
        self.assertIn("DEMO", DEMO_STUDENT.section)
        self.assertTrue(all(item.teacher_name.startswith("Teacher ") for item in DEMO_ASSIGNMENTS))
        self.assertTrue(all(item.teacher_email.endswith(".invalid") for item in DEMO_ASSIGNMENTS))
        self.assertTrue(all("DEMO" in item.section for item in DEMO_ASSIGNMENTS))

    def test_student_only_receives_assignments_for_rostered_section(self):
        assignments = assignments_for_student(DEMO_STUDENT, DEMO_ASSIGNMENTS)

        self.assertEqual(len(assignments), 6)
        self.assertEqual({item.section for item in assignments}, {"11STEM-DEMO"})
        self.assertNotIn("Statistics and Probability", {item.subject for item in assignments})

    def test_section_is_not_selected_from_assignment_data(self):
        other_section_student = replace(DEMO_STUDENT, section="11ABM-DEMO", strand="ABM")
        assignments = assignments_for_student(other_section_student, DEMO_ASSIGNMENTS)

        self.assertEqual(len(assignments), 1)
        self.assertEqual(assignments[0].subject, "Statistics and Probability")

    def test_submitted_assignments_are_removed_from_pending_list(self):
        assignments = assignments_for_student(DEMO_STUDENT, DEMO_ASSIGNMENTS)
        submitted = submitted_assignment_ids(DEMO_STUDENT, DEMO_SUBMISSIONS)
        pending = pending_assignments(assignments, submitted)

        self.assertEqual(len(submitted), 2)
        self.assertEqual(len(pending), 4)
        self.assertTrue(all(item.id not in submitted for item in pending))

    def test_evaluation_key_is_stable_and_period_scoped(self):
        assignment = assignments_for_student(DEMO_STUDENT, DEMO_ASSIGNMENTS)[0]

        self.assertEqual(
            evaluation_key(DEMO_STUDENT, assignment),
            f"{DEMO_STUDENT.id}:{assignment.id}:{DEMO_STUDENT.evaluation_period}".lower(),
        )

    def test_student_interface_uses_teacher_performance_brand_and_guidance(self):
        source = (
            Path(__file__).resolve().parents[1] / "student_app.py"
        ).read_text(encoding="utf-8")

        self.assertNotIn("Faculty Evaluation", source)
        self.assertIn("Teacher Performance Evaluation", source)
        self.assertIn("Data Privacy Act of 2012", source)
        self.assertIn("Second Semester of School Year 2025-2026", source)
        self.assertIn("Do not share your evaluation answers", source)


if __name__ == "__main__":
    unittest.main()
