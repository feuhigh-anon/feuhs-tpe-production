import csv
from contextlib import redirect_stdout
import io
import os
from pathlib import Path
import tempfile
import unittest

from scripts.verify_live_security import (
    ALPHA_FIXTURES,
    ALPHA_SECTION_CODE,
    CheckReport,
    load_alpha_credentials,
    response_payload,
)
from scripts.provision_alpha import FIXTURES
from scripts.provision_mixed_alpha import COHORTS, planned_accounts


FIELDNAMES = (
    "email",
    "password",
    "display_name",
    "student_number",
    "section",
)


class LiveSecurityTest(unittest.TestCase):
    def write_credentials(
        self,
        directory: Path,
        *,
        section: str = ALPHA_SECTION_CODE,
        school_level: str = "SHS",
    ) -> Path:
        path = directory / "alpha_credentials.csv"
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDNAMES)
            writer.writeheader()
            for index in (1, 2):
                writer.writerow(
                    {
                        "email": (
                            f"alpha.{school_level.lower()}.student{index:02d}"
                            "@example.invalid"
                        ),
                        "password": f"Synthetic-{index}",
                        "display_name": f"Alpha Student {index:02d}",
                        "student_number": f"ALPHA-{school_level}-{index:04d}",
                        "section": section,
                    }
                )
        os.chmod(path, 0o600)
        return path

    def test_owner_only_alpha_credentials_are_loaded(self):
        with tempfile.TemporaryDirectory() as directory:
            credentials = load_alpha_credentials(
                self.write_credentials(Path(directory))
            )

        self.assertEqual(len(credentials), 2)
        self.assertTrue(credentials[0].email.endswith("@example.invalid"))
        self.assertEqual(credentials[1].section, ALPHA_SECTION_CODE)

    def test_non_alpha_section_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_credentials(Path(directory), section="11STEM-REAL")
            with self.assertRaises(SystemExit):
                load_alpha_credentials(path)

    def test_jhs_credentials_require_the_jhs_verifier_fixture(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_credentials(
                Path(directory),
                section=ALPHA_FIXTURES["JHS"].section_code,
                school_level="JHS",
            )
            credentials = load_alpha_credentials(path, ALPHA_FIXTURES["JHS"])
            with self.assertRaises(SystemExit):
                load_alpha_credentials(path, ALPHA_FIXTURES["SHS"])

        self.assertEqual(len(credentials), 2)
        self.assertEqual(credentials[0].section, "07JHS-ALPHA")

    def test_provisioning_fixtures_are_distinct_and_level_correct(self):
        shs = FIXTURES["SHS"]
        jhs = FIXTURES["JHS"]

        self.assertEqual(shs["section"]["school_level"], "SHS")
        self.assertEqual(shs["section"]["grade_level"], 11)
        self.assertEqual(jhs["section"]["school_level"], "JHS")
        self.assertEqual(jhs["section"]["grade_level"], 7)
        self.assertEqual(jhs["section"]["strand"], "")
        self.assertNotEqual(shs["section"]["code"], jhs["section"]["code"])
        self.assertTrue(
            {
                item["subject"]["code"] for item in shs["assignments"]
            }.isdisjoint(
                item["subject"]["code"] for item in jhs["assignments"]
            )
        )

    def test_mixed_alpha_cohort_covers_jhs_grade_11_and_grade_12(self):
        accounts = planned_accounts()

        self.assertEqual(len(accounts), 10)
        self.assertEqual(
            {cohort["key"]: cohort["student_count"] for cohort in COHORTS},
            {"JHS": 4, "G11": 3, "G12": 3},
        )
        self.assertEqual(
            {(row["section"]["school_level"], row["section"]["grade_level"]) for row in accounts},
            {("JHS", 7), ("SHS", 11), ("SHS", 12)},
        )
        self.assertEqual(sum(len(cohort["assignments"]) for cohort in COHORTS), 9)
        self.assertTrue(all(row["email"].endswith("@example.invalid") for row in accounts))
        self.assertTrue(
            all(row["student_number"].startswith("ALPHA-MIXED-") for row in accounts)
        )
        self.assertEqual(len({row["student_number"] for row in accounts}), 10)

    def test_credentials_accessible_to_other_users_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = self.write_credentials(Path(directory))
            os.chmod(path, 0o644)
            with self.assertRaises(SystemExit):
                load_alpha_credentials(path)

    def test_response_payload_supports_likert_and_required_text(self):
        payload = response_payload(
            [
                {"id": 10, "response_type": "likert_5"},
                {"id": 11, "response_type": "text"},
            ]
        )

        self.assertEqual(
            payload,
            [
                {"question_item_id": 10, "rating_value": 4, "text_value": None},
                {"question_item_id": 11, "rating_value": None, "text_value": "N/A"},
            ],
        )

    def test_report_counts_passes_and_failures(self):
        report = CheckReport()
        with redirect_stdout(io.StringIO()):
            report.record("allowed", True, "ok")
            report.record("denied", False, "unexpected")

        self.assertEqual(report.passed, 1)
        self.assertEqual(report.failed, 1)


if __name__ == "__main__":
    unittest.main()
