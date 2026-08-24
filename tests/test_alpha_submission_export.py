import unittest

from scripts.export_alpha_submissions import response_fields, summary_fields


class AlphaSubmissionExportTest(unittest.TestCase):
    def test_summary_identifies_student_roster_and_teacher_assignment(self):
        fields = set(summary_fields())

        self.assertTrue(
            {
                "submission_id",
                "student_number",
                "school_level",
                "grade_level",
                "section",
                "subject_name",
                "teacher_name",
                "submitted_at",
            }.issubset(fields)
        )

    def test_response_export_contains_rating_and_qualitative_values(self):
        fields = set(response_fields())

        self.assertTrue(
            {
                "question",
                "response_type",
                "rating_value",
                "text_value",
                "is_not_applicable",
            }.issubset(fields)
        )


if __name__ == "__main__":
    unittest.main()
