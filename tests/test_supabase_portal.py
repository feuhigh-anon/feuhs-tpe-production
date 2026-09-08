import unittest

from feval.supabase_portal import (
    PortalConfigurationError,
    PortalDataError,
    PortalSubmissionError,
    SupabaseSettings,
    AuthSession,
    load_admin_evaluation_summary,
    question_block_from_rows,
    response_payload,
)


def question_rows():
    rows = []
    next_id = 100
    sections = (
        ("teacher_performance", 10, False),
        ("student_experience", 10, False),
        ("student_self_evaluation", 5, True),
        ("qualitative_feedback", 3, False),
    )
    for section_key, count, use_for_rci in sections:
        for position in range(1, count + 1):
            rows.append(
                {
                    "id": next_id,
                    "stable_key": f"{section_key}_{position:02d}",
                    "section_key": section_key,
                    "prompt": f"{section_key} question {position}",
                    "response_type": (
                        "text" if section_key == "qualitative_feedback" else "likert_5"
                    ),
                    "position": position,
                    "is_required": True,
                    "use_for_rci": use_for_rci,
                }
            )
            next_id += 1
    return rows


class FakeResponse:
    def __init__(self, data):
        self.data = data


class FakeQuery:
    def __init__(self, rows):
        self.rows = rows
        self.filters = []

    def select(self, _columns):
        return self

    def eq(self, column, value):
        self.filters.append((column, value))
        return self

    def in_(self, column, values):
        self.filters.append((column, set(values)))
        return self

    def limit(self, _count):
        return self

    def execute(self):
        rows = self.rows
        for column, expected in self.filters:
            if isinstance(expected, set):
                rows = [row for row in rows if row.get(column) in expected]
            else:
                rows = [row for row in rows if row.get(column) == expected]
        return FakeResponse(rows)


class FakeClient:
    def __init__(self, tables):
        self.tables = tables

    def table(self, name):
        return FakeQuery(self.tables.get(name, []))


class SupabasePortalTest(unittest.TestCase):
    def test_student_app_rejects_secret_key(self):
        settings = SupabaseSettings(
            url="https://example.supabase.co",
            publishable_key="sb_secret_do_not_use",
        )

        with self.assertRaises(PortalConfigurationError):
            settings.validate()

    def test_admin_summary_is_assignment_scoped_and_excludes_student_data(self):
        client = FakeClient(
            {
                "profiles": [{"id": "admin-1", "role": "admin", "is_active": True}],
                "evaluation_periods": [{"id": 7, "code": "PILOT-2026-Q1"}],
                "evaluation_submissions": [
                    {"id": 1, "teaching_assignment_id": 10, "evaluation_period_id": 7},
                    {"id": 2, "teaching_assignment_id": 11, "evaluation_period_id": 7},
                ],
                "teaching_assignments": [
                    {"id": 10, "section_id": 20, "subject_id": 30, "teacher_id": 40, "is_active": True},
                    {"id": 11, "section_id": 21, "subject_id": 30, "teacher_id": 40, "is_active": True},
                ],
                "sections": [
                    {"id": 20, "code": "11-A", "school_level": "SHS"},
                    {"id": 21, "code": "11-B", "school_level": "SHS"},
                ],
                "subjects": [{"id": 30, "name": "Science"}],
                "teachers": [{"id": 40, "display_name": "Teacher One"}],
                "question_items": [
                    {"id": 100, "section_key": "teacher_performance"},
                    {"id": 101, "section_key": "student_experience"},
                    {"id": 102, "section_key": "student_self_evaluation"},
                    {"id": 103, "section_key": "qualitative_feedback"},
                ],
                "evaluation_responses": [
                    {"submission_id": 1, "question_item_id": 100, "rating_value": 4},
                    {"submission_id": 1, "question_item_id": 101, "rating_value": 3},
                    {"submission_id": 1, "question_item_id": 102, "rating_value": 5},
                    {"submission_id": 1, "question_item_id": 103, "rating_value": None},
                    {"submission_id": 2, "question_item_id": 100, "rating_value": 2},
                    {"submission_id": 2, "question_item_id": 101, "rating_value": 4},
                    {"submission_id": 2, "question_item_id": 102, "rating_value": 3},
                ],
            }
        )
        session = AuthSession("access", "refresh", "admin-1", "admin@example.test")

        summaries = load_admin_evaluation_summary(client, session, 7)

        self.assertEqual([item.section_code for item in summaries], ["11-A", "11-B"])
        self.assertEqual(summaries[0].response_count, 1)
        self.assertEqual(summaries[0].faculty_mean, 4.0)
        self.assertEqual(summaries[0].experience_mean, 3.0)
        self.assertEqual(summaries[0].self_evaluation_mean, 5.0)
        self.assertNotIn("student_name", summaries[0].__dict__)
        self.assertNotIn("text_value", summaries[0].__dict__)

    def test_admin_summary_rejects_non_admin_profile(self):
        client = FakeClient(
            {"profiles": [{"id": "student-1", "role": "student", "is_active": True}]}
        )
        session = AuthSession("access", "refresh", "student-1", "student@example.test")

        with self.assertRaises(PortalDataError):
            load_admin_evaluation_summary(client, session, 7)

    def test_questionnaire_rows_preserve_four_section_contract(self):
        block = question_block_from_rows("SHS", 7, question_rows())

        self.assertEqual(len(block.faculty_items), 10)
        self.assertEqual(len(block.overall_experience_items), 10)
        self.assertEqual(len(block.rci_items), 5)
        self.assertEqual(len(block.open_ended_items), 3)
        self.assertTrue(all(item.id.isdigit() for item in block.all_items))

    def test_future_question_bank_may_change_item_counts(self):
        rows = question_rows()
        rows = [row for row in rows if row["stable_key"] != "teacher_performance_10"]

        block = question_block_from_rows("SHS", 8, rows)

        self.assertEqual(len(block.faculty_items), 9)
        self.assertEqual(len(block.open_ended_items), 3)

    def test_response_payload_contains_all_database_question_ids(self):
        block = question_block_from_rows("SHS", 7, question_rows())
        assignment_id = "42"
        answers = {
            f"rating_{assignment_id}_{item.id}": 4
            for item in block.quantitative_items
        }
        comments = {
            f"comment_{assignment_id}_{item.id}": "N/A"
            for item in block.open_ended_items
        }

        payload = response_payload(block, assignment_id, answers, comments)

        self.assertEqual(len(payload), 28)
        self.assertEqual(len({item["question_item_id"] for item in payload}), 28)
        self.assertEqual(sum(item["rating_value"] is not None for item in payload), 25)
        self.assertEqual(sum(item["text_value"] is not None for item in payload), 3)

    def test_response_payload_rejects_blank_required_comment(self):
        block = question_block_from_rows("SHS", 7, question_rows())
        assignment_id = "42"
        answers = {
            f"rating_{assignment_id}_{item.id}": 4
            for item in block.quantitative_items
        }
        comments = {
            f"comment_{assignment_id}_{item.id}": "N/A"
            for item in block.open_ended_items
        }
        comments[f"comment_{assignment_id}_{block.open_ended_items[0].id}"] = ""

        with self.assertRaises(PortalSubmissionError):
            response_payload(block, assignment_id, answers, comments)

    def test_response_payload_omits_unanswered_optional_item(self):
        rows = question_rows()
        optional_row = next(
            row for row in rows if row["stable_key"] == "teacher_performance_10"
        )
        optional_row["is_required"] = False
        block = question_block_from_rows("SHS", 7, rows)
        assignment_id = "42"
        answers = {
            f"rating_{assignment_id}_{item.id}": 4
            for item in block.quantitative_items
            if item.id != str(optional_row["id"])
        }
        comments = {
            f"comment_{assignment_id}_{item.id}": "N/A"
            for item in block.open_ended_items
        }

        payload = response_payload(block, assignment_id, answers, comments)

        self.assertEqual(len(payload), 27)
        self.assertNotIn(
            optional_row["id"],
            {item["question_item_id"] for item in payload},
        )


if __name__ == "__main__":
    unittest.main()
