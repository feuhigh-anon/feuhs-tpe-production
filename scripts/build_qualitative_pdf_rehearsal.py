"""Build teacher PDFs from historical exports for qualitative workflow testing.

The displayed score is only an unweighted mean across the 20 teacher-
performance statements: ten instructional items and ten overall-experience
items. It is not the approved quantitative scoring model. Qualitative text is
the deterministic protocol rehearsal until an approved LLM provider is wired.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from types import SimpleNamespace

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from feval.ingestion import load_and_normalize
from feval.pdf_report import build_teacher_pdf_report
from feval.qualitative_summary import build_protocol_qualitative_summary
from feval.questions import get_question_block
from feval.text import analyze_open_ended


DEFAULT_SOURCES = {
    "shs": ROOT / "Students Evaluation" / "tpe" / "tpe_2024-2025_01.csv",
    "jhs": ROOT / "Students Evaluation" / "tpe" / "tpe_2024-2025_02.csv",
}
DEFAULT_OUTPUT = ROOT / "outputs" / "qualitative_pdf_rehearsal"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--block", choices=("shs", "jhs"), required=True)
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def teacher_average_table(normalized) -> pd.DataFrame:
    """Average the 20 teacher-performance items, ignoring missing item scores."""
    columns = normalized.present_columns(
        normalized.faculty_columns + normalized.overall_experience_columns
    )
    scores = normalized.responses.loc[:, columns].apply(pd.to_numeric, errors="coerce")
    result = pd.DataFrame(
        {
            "teacher": normalized.responses["teacher"],
            "responses": normalized.responses["teacher"].groupby(normalized.responses["teacher"]).transform("size"),
            "statement_count": scores.notna().sum(axis=1),
            "response_average_20_statements": scores.mean(axis=1),
        }
    )
    return (
        result.groupby("teacher", as_index=False)
        .agg(
            responses=("responses", "first"),
            statement_count=("statement_count", "sum"),
            final_teacher_rating_1_5=("response_average_20_statements", "mean"),
        )
        .assign(
            final_teacher_rating_1_5=lambda frame: frame["final_teacher_rating_1_5"].round(4),
        )
    )


def safe_filename(value: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", str(value)).strip("._") or "teacher"


def main() -> None:
    args = parse_args()
    source = args.source or DEFAULT_SOURCES[args.block]
    block = get_question_block(args.block)
    normalized = load_and_normalize(source, block)
    score_summary = teacher_average_table(normalized)
    open_ended = analyze_open_ended(normalized, block_id=args.block)
    qualitative_summary = build_protocol_qualitative_summary(normalized)
    report = SimpleNamespace(summary=score_summary, open_ended=open_ended, qualitative_summary=qualitative_summary)

    output_dir = args.output_dir / args.block
    output_dir.mkdir(parents=True, exist_ok=True)
    for teacher in score_summary["teacher"]:
        build_teacher_pdf_report(
            report,
            teacher,
            output_dir / f"{safe_filename(teacher)}.pdf",
            block_id=args.block,
            evaluation_period="Historical rehearsal data",
            score_label="Test average: 20 teacher-performance statements",
        )
    print(f"Generated {len(score_summary)} {args.block.upper()} teacher PDFs in {output_dir}")
    print("score_mode=unweighted_mean_of_20_teacher_performance_statements")
    print("qualitative_mode=deterministic_rehearsal; no LLM was called")


if __name__ == "__main__":
    main()