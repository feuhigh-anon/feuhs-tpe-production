"""Report composition helpers."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from feval.models import NormalizedExport
from feval.scoring import EvaluationScoreResult, score_evaluations
from feval.text import analyze_open_ended


@dataclass
class AnalysisReport:
    """All report tables produced by the pipeline."""

    summary: pd.DataFrame
    per_response: pd.DataFrame
    item_weights: pd.DataFrame
    component_weights: pd.DataFrame
    reliability: pd.DataFrame
    open_ended: pd.DataFrame


def build_analysis_report(
    normalized: NormalizedExport,
    w_instructional: float | None = None,
    w_experience: float | None = None,
    w_qualitative: float | None = None,
) -> AnalysisReport:
    open_ended = analyze_open_ended(normalized, block_id=normalized.block.id)
    scores = score_evaluations(
        normalized,
        qualitative=open_ended,
        w_instructional=w_instructional,
        w_experience=w_experience,
        w_qualitative=w_qualitative,
    )
    qualitative_columns = [
        column for column in open_ended.columns if column != "teacher" and column not in scores.summary.columns
    ]
    summary = scores.summary.merge(open_ended[["teacher", *qualitative_columns]], on="teacher", how="left")
    reliability = reliability_table(normalized, scores)
    return AnalysisReport(
        summary=summary,
        per_response=scores.per_response,
        item_weights=scores.item_weights,
        component_weights=scores.component_weights,
        reliability=reliability,
        open_ended=open_ended,
    )


def reliability_table(normalized: NormalizedExport, scores: EvaluationScoreResult) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "question_block": normalized.block.label,
                "instructional_performance_items": len(normalized.faculty_columns),
                "overall_experience_items": len(normalized.overall_experience_columns),
                "rci_items": len(normalized.rci_columns),
                "open_ended_items": len(normalized.text_columns),
                "responses": len(normalized.responses),
                "teachers": normalized.responses["teacher"].nunique(),
                "cronbach_alpha_instructional_block": round(scores.reliability_alpha, 4)
                if pd.notna(scores.reliability_alpha)
                else None,
                "cronbach_alpha_overall_experience_block": round(scores.overall_experience_alpha, 4)
                if pd.notna(scores.overall_experience_alpha)
                else None,
                "class_icc": round(scores.class_icc, 4),
                "rci_floor": 0.40,
                "low_discrimination_items": "; ".join(scores.low_discrimination_items),
                "verbose_response_flags": int(
                    scores.summary["verbose_response_flags"].sum()
                    if "verbose_response_flags" in scores.summary.columns
                    else 0
                ),
                "scoring_basis": (
                    "fixed policy weights, bounded rater credibility, and partial pooling by effective n"
                ),
            }
        ]
    )
