import json
from pathlib import Path
import re
import unittest


MIGRATIONS = Path(__file__).resolve().parents[1] / "supabase" / "migrations"
CATALOG = MIGRATIONS / "202610230001_questionnaire_catalog.sql"
TARGET_WORKFLOW = MIGRATIONS / "202610230002_multi_target_instruments.sql"


class TargetMigrationTest(unittest.TestCase):
    def test_catalog_seeds_six_banks_without_activating_student_access(self):
        sql = CATALOG.read_text(encoding="utf-8")
        match = re.search(r"\$instrument_seed\$(.*?)\$instrument_seed\$::jsonb", sql, re.DOTALL)
        self.assertIsNotNone(match)
        instruments = json.loads(match.group(1))
        self.assertEqual(
            {item["target_type"] for item in instruments},
            {"subject_teacher", "homeroom_adviser", "homeroom_program"},
        )
        self.assertEqual(len(instruments), 3)
        self.assertIn("array['JHS','SHS']", sql)
        self.assertIn("status='published'", sql)
        self.assertNotIn("create table public.evaluation_targets", sql.lower())
        self.assertNotIn("create table public.student_evaluation_targets", sql.lower())
        self.assertNotIn("insert into public.evaluation_target_instruments", sql.lower())
        self.assertNotIn("insert into public.evaluation_period_instruments", sql.lower())

    def test_target_workflow_uses_catalog_but_does_not_reseed_questions(self):
        sql = TARGET_WORKFLOW.read_text(encoding="utf-8").lower()
        self.assertIn("create table public.evaluation_targets", sql)
        self.assertIn("create table public.student_evaluation_targets", sql)
        self.assertIn("create table public.evaluation_target_instruments", sql)
        self.assertNotIn("$instrument_seed$", sql)


if __name__ == "__main__":
    unittest.main()
