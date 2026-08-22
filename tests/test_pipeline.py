import math
import unittest

import pandas as pd

from feval.ingestion import build_column_matches, normalize_responses, score_likert_value
from feval.questions import DEFAULT_QUESTION_BLOCKS
from feval.reporting import build_analysis_report
from feval.sample_data import make_demo_sharepoint_export
from feval.text import (
    flag_verbose_responses,
    is_substantive_comment,
    phrase_summary_for_prompt,
    qualitative_evidence_index,
    representative_evidence,
)


class PipelineTest(unittest.TestCase):
    def test_likert_mapping(self):
        self.assertEqual(score_likert_value("Strongly Agree"), 5.0)
        self.assertEqual(score_likert_value("1 - Strongly Disagree"), 1.0)
        self.assertTrue(math.isnan(score_likert_value("Not Applicable")))

    def test_shs_demo_pipeline(self):
        block = DEFAULT_QUESTION_BLOCKS["shs"]
        raw = make_demo_sharepoint_export(block, rows=45)
        matches = build_column_matches(raw.columns, block)
        normalized = normalize_responses(
            raw=raw,
            block=block,
            teacher_column="Teacher Name",
            section_column="Section",
            respondent_column="Email",
            column_map={item_id: match.column for item_id, match in matches.items()},
        )
        report = build_analysis_report(normalized)
        self.assertEqual(len(report.summary), 3)
        self.assertIn("final_teacher_rating_1_5", report.summary.columns)
        self.assertIn("instructional_performance_1_5", report.summary.columns)
        self.assertIn("overall_experience_1_5", report.summary.columns)
        self.assertIn("qualitative_score_1_5", report.summary.columns)
        self.assertIn("appreciated_statement", report.summary.columns)
        self.assertIn("suggestion_statement", report.summary.columns)
        self.assertIn("experience_statement", report.summary.columns)
        self.assertIn("appreciated_phrases", report.summary.columns)
        self.assertIn("appreciated_frame_counts", report.open_ended.columns)
        self.assertIn("verbose_flag_count", report.open_ended.columns)
        self.assertNotIn("sentiment_100", report.summary.columns)
        self.assertTrue(report.summary["final_teacher_rating_1_5"].between(1, 5).all())
        self.assertAlmostEqual(report.component_weights["weight"].sum(), 1.0, places=5)
        self.assertTrue((report.component_weights["weight"] >= 0).all())
        self.assertEqual(set(report.component_weights["estimation_method"]), {"fixed_policy_weights"})

    def test_blocks_keep_teacher_performance_items_separate(self):
        shs = DEFAULT_QUESTION_BLOCKS["shs"]
        jhs = DEFAULT_QUESTION_BLOCKS["jhs"]
        self.assertEqual(len(shs.faculty_items), 10)
        self.assertEqual(len(jhs.faculty_items), 10)
        self.assertEqual(len(shs.overall_experience_items), 10)
        self.assertEqual(len(jhs.overall_experience_items), 10)
        self.assertEqual(len(shs.self_eval_items), 15)
        self.assertEqual(len(jhs.self_eval_items), 15)
        self.assertEqual(len(shs.open_ended_items), 3)
        self.assertEqual(len(jhs.open_ended_items), 3)
        self.assertEqual(len(shs.rci_items), 5)
        self.assertEqual(len(jhs.rci_items), 5)
        self.assertNotEqual(shs.faculty_items[0].id, jhs.faculty_items[0].id)
        self.assertNotEqual(shs.faculty_items[1].text, jhs.faculty_items[1].text)
        self.assertEqual(shs.faculty_items[0].text, "My teacher starts and ends the class on time.")
        self.assertEqual(
            jhs.open_ended_items[0].text,
            "What did you like the most about your teacher's way of teaching?",
        )

    def test_manual_column_override_with_sharepoint_headers(self):
        block = DEFAULT_QUESTION_BLOCKS["jhs"]
        raw = pd.DataFrame(
            {
                "Teacher Evaluated": ["Teacher A", "Teacher A", "Teacher B"],
                **{item.text: ["Agree", "Strongly Agree", "Neutral"] for item in block.faculty_items},
                **{item.text: ["Agree", "Agree", "Neutral"] for item in block.self_eval_items},
                **{item.text: ["clear and helpful", "", "unclear"] for item in block.open_ended_items},
            }
        )
        matches = build_column_matches(raw.columns, block)
        normalized = normalize_responses(
            raw,
            block,
            teacher_column="Teacher Evaluated",
            column_map={item_id: match.column for item_id, match in matches.items()},
        )
        report = build_analysis_report(normalized)
        self.assertEqual(set(report.summary["teacher"]), {"Teacher A", "Teacher B"})
        self.assertIn("semantic_themes", report.open_ended.columns)
        self.assertIn("representative_evidence", report.open_ended.columns)

    def test_partial_pooling_reflects_unequal_class_loads(self):
        block = DEFAULT_QUESTION_BLOCKS["shs"]
        records = []

        def add_response(teacher, section, index, teacher_score):
            record = {
                "Teacher Evaluated": teacher,
                "Section": section,
                "Email": f"{teacher}-{section}-{index}@example.edu",
            }
            for item in block.faculty_items:
                record[item.text] = teacher_score
            for item in block.overall_experience_items:
                record[item.text] = teacher_score
            for item in block.rci_items:
                record[item.text] = 5
            for position, item in enumerate(block.open_ended_items):
                if position == 1:
                    record[item.text] = "More examples would help during difficult lessons."
                else:
                    record[item.text] = "The teacher is clear, helpful, and supportive."
            records.append(record)

        for class_index in range(7):
            for student_index in range(8):
                add_response("Teacher Many", f"SHS-{class_index + 1}", student_index, 4)
        for student_index in range(8):
            add_response("Teacher Few", "SHS-Only", student_index, 5)

        raw = pd.DataFrame(records)
        matches = build_column_matches(raw.columns, block)
        normalized = normalize_responses(
            raw,
            block,
            teacher_column="Teacher Evaluated",
            section_column="Section",
            respondent_column="Email",
            column_map={item_id: match.column for item_id, match in matches.items()},
        )
        report = build_analysis_report(normalized)
        summary = report.summary.set_index("teacher")

        self.assertLessEqual(
            summary.loc["Teacher Few", "partial_pooling_shrinkage"],
            summary.loc["Teacher Many", "partial_pooling_shrinkage"],
        )
        self.assertTrue((report.summary["effective_response_count"] <= report.summary["responses"]).all())
        self.assertTrue(report.summary["final_teacher_rating_1_5"].between(1, 5).all())

    def test_phrase_output_contains_no_terminal_punctuation(self):
        phrase = phrase_summary_for_prompt(
            "appreciated",
            [
                "The teacher gives clear explanations and examples.",
                "The activities are interactive and helpful.",
            ],
        )
        self.assertFalse(phrase.endswith("."))
        self.assertFalse(phrase.endswith("!"))

    def test_self_eval_modulation_reduces_low_credibility_concern_signal(self):
        suggestions = ["The lessons are confusing and rushed."] * 10
        index_low_self_eval = qualitative_evidence_index(
            appreciated=[],
            suggestions=suggestions,
            experience=[],
            self_eval_means=[1.0] * 10,
        )
        index_high_self_eval = qualitative_evidence_index(
            appreciated=[],
            suggestions=suggestions,
            experience=[],
            self_eval_means=[5.0] * 10,
        )
        self.assertLessEqual(index_high_self_eval, index_low_self_eval)

    def test_verbose_flag_fires_above_threshold_not_below(self):
        long_comment = " ".join(["concern"] * 90)
        short_comment = " ".join(["concern"] * 40)
        self.assertEqual(len(flag_verbose_responses([long_comment], "suggestion")), 1)
        self.assertEqual(len(flag_verbose_responses([short_comment], "suggestion")), 0)

    def test_representative_evidence_includes_concern_snippet(self):
        comments = [
            "The teacher is always clear and helpful.",
            "The lessons are confusing and rushed.",
            "I appreciate the interactive activities.",
        ]
        result = representative_evidence(comments, frames=["teaching strategies"])
        self.assertTrue("confusing" in result or "rushed" in result)

    def test_not_applicable_responses_are_not_qualitative_evidence(self):
        self.assertFalse(is_substantive_comment("N/A"))
        self.assertFalse(is_substantive_comment("Not applicable"))
        self.assertFalse(is_substantive_comment("   "))
        self.assertTrue(is_substantive_comment("The worked examples were helpful."))


if __name__ == "__main__":
    unittest.main()
