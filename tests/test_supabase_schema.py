import json
from pathlib import Path
import re
import unittest

from feval.questions import DEFAULT_QUESTION_BLOCKS


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "202608230001_initial_schema.sql"
)
QUESTION_BANK_PATH = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "202608230002_question_banks_v1.sql"
)


class SupabaseSchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sql = MIGRATION_PATH.read_text(encoding="utf-8").lower()

    def test_versioned_question_bank_contract_is_present(self):
        self.assertIn("create table public.question_banks", self.sql)
        self.assertIn("unique (code, version)", self.sql)
        self.assertIn("create table public.question_items", self.sql)
        self.assertIn("question_items_guard_changes", self.sql)

    def test_duplicate_submissions_are_blocked_by_database_constraint(self):
        self.assertIn(
            "unique (student_id, teaching_assignment_id, evaluation_period_id)",
            self.sql,
        )

    def test_sensitive_tables_have_rls_and_no_direct_student_writes(self):
        for table in (
            "evaluation_submissions",
            "evaluation_responses",
            "submission_audit_events",
        ):
            self.assertIn(
                f"alter table public.{table} enable row level security",
                self.sql,
            )
            self.assertIn(
                f"revoke all on public.{table} from anon, authenticated",
                self.sql,
            )

    def test_atomic_submission_function_is_restricted_to_authenticated_users(self):
        signature = "public.submit_evaluation(bigint, jsonb, text)"
        self.assertIn("create or replace function public.submit_evaluation", self.sql)
        self.assertIn("security definer", self.sql)
        self.assertIn(f"revoke execute on function {signature} from public", self.sql)
        self.assertIn(f"grant execute on function {signature} to authenticated", self.sql)

    def test_seeded_question_text_matches_python_instruments(self):
        seed_sql = QUESTION_BANK_PATH.read_text(encoding="utf-8")
        payloads = re.findall(r"\$items\$\s*(\[.*?\])\s*\$items\$", seed_sql, re.DOTALL)
        self.assertEqual(len(payloads), 2)

        seeded = {
            item["stable_key"]: item["prompt"]
            for payload in payloads
            for item in json.loads(payload)
        }
        expected = {
            item.id: item.text
            for block in DEFAULT_QUESTION_BLOCKS.values()
            for item in (
                block.faculty_items
                + block.self_eval_items
                + block.open_ended_items
            )
        }
        self.assertEqual(seeded, expected)


if __name__ == "__main__":
    unittest.main()
