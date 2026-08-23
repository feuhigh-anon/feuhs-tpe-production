import unittest

from feval.supabase_portal import (
    PortalConfigurationError,
    PortalSubmissionError,
    SupabaseSettings,
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


class SupabasePortalTest(unittest.TestCase):
    def test_student_app_rejects_secret_key(self):
        settings = SupabaseSettings(
            url="https://example.supabase.co",
            publishable_key="sb_secret_do_not_use",
        )

        with self.assertRaises(PortalConfigurationError):
            settings.validate()

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
