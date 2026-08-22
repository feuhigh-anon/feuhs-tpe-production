"""Faculty-facing PDF report generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping, Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from feval.text import PROMPT_META


def build_teacher_pdf_report(
    report,
    teacher: str,
    output_path: str | Path,
    *,
    block_id: str = "shs",
    subject: str = "",
    section: str = "",
    institution: str = "FEU High School",
    academic_year: str = "",
    term: str = "",
    evaluation_period: str = "",
) -> Path:
    """
    Build a confidential faculty-use PDF report for one teacher.

    Parameters
    ----------
    report : object
        AnalysisReport-like object with summary, reliability, open_ended, and
        component_weights DataFrames.
    teacher : str
        Teacher name as it appears in the report summary.
    output_path : str | Path
        Destination PDF path.
    block_id : str
        Prompt metadata block, usually "shs" or "jhs".
    subject : str
        Subject name for the cover page.
    section : str
        Section or class label for the cover page.
    institution : str
        Institution label for the cover page.
    academic_year : str
        Academic year label.
    term : str
        Academic term label.
    evaluation_period : str
        Evaluation period label.

    Returns
    -------
    pathlib.Path
        The written PDF path.

    Methodological note
    -------------------
    The PDF discloses the institutional composite formula and separates score
    evidence from qualitative diagnostics so faculty receive both a concise
    rating and the context needed for instructional reflection.
    """

    output = Path(output_path)
    summary_row = _one_teacher_row(report.summary, teacher)
    qualitative_row = _one_teacher_row(report.open_ended, teacher, required=False)
    reliability = report.reliability.iloc[0] if not report.reliability.empty else pd.Series(dtype=object)
    weights = _component_weight_lookup(report.component_weights)

    doc = SimpleDocTemplate(
        str(output),
        pagesize=letter,
        rightMargin=inch,
        leftMargin=inch,
        topMargin=inch,
        bottomMargin=inch,
        title=f"Faculty Evaluation Report - {teacher}",
    )
    styles = _styles()
    story = []

    story.extend(
        _cover_page(
            styles,
            teacher=teacher,
            subject=subject,
            section=section,
            institution=institution,
            academic_year=academic_year,
            term=term,
            evaluation_period=evaluation_period,
        )
    )
    story.append(PageBreak())
    story.extend(_score_summary_page(styles, summary_row, reliability, weights))
    story.append(PageBreak())
    story.extend(_qualitative_page(styles, qualitative_row, block_id))
    story.append(PageBreak())
    story.extend(_diagnostic_page(styles, qualitative_row))

    doc.build(story)
    return output


def rating_band(score: float) -> str:
    """
    Convert a 1-5 final score into an administrator-readable band.

    Parameters
    ----------
    score : float
        Final teacher rating on the 1-5 scale.

    Returns
    -------
    str
        One of Outstanding, Proficient, Developing, or Needs Support.
    """

    if score >= 4.50:
        return "Outstanding"
    if score >= 3.50:
        return "Proficient"
    if score >= 2.50:
        return "Developing"
    return "Needs Support"


def _cover_page(
    styles: Mapping[str, ParagraphStyle],
    *,
    teacher: str,
    subject: str,
    section: str,
    institution: str,
    academic_year: str,
    term: str,
    evaluation_period: str,
) -> list[Any]:
    story = [
        Paragraph(teacher, styles["cover_title"]),
        Spacer(1, 0.35 * inch),
        Paragraph(f"Subject: {subject or 'Not specified'}", styles["normal"]),
        Paragraph(f"Section: {section or 'Not specified'}", styles["normal"]),
        Paragraph(f"Institution: {institution or 'Not specified'}", styles["normal"]),
        Paragraph(f"Academic Year: {academic_year or 'Not specified'}", styles["normal"]),
        Paragraph(f"Term: {term or 'Not specified'}", styles["normal"]),
        Paragraph(f"Evaluation Period: {evaluation_period or 'Not specified'}", styles["normal"]),
        Spacer(1, 5.2 * inch),
        Paragraph("CONFIDENTIAL - FOR FACULTY USE ONLY", styles["confidential"]),
    ]
    return story


def _score_summary_page(
    styles: Mapping[str, ParagraphStyle],
    row: pd.Series,
    reliability: pd.Series,
    weights: Mapping[str, float],
) -> list[Any]:
    final_score = _number(row.get("final_teacher_rating_1_5"))
    instructional = _number(row.get("instructional_performance_1_5"))
    experience = _number(row.get("overall_experience_1_5"))
    qualitative = _number(row.get("qualitative_score_1_5"))

    score_rows = [
        ["Component", "Policy Weight", "Weighted Score", "Contribution"],
        [
            "Instructional Performance (Part 1)",
            _pct(weights["instructional_performance"]),
            _fmt(instructional),
            _fmt(instructional * weights["instructional_performance"]),
        ],
        [
            "Overall Learning Experience (Part 2)",
            _pct(weights["overall_experience"]),
            _fmt(experience),
            _fmt(experience * weights["overall_experience"]),
        ],
        [
            "Qualitative Feedback (Part 4)",
            _pct(weights["qualitative_evidence"]),
            _fmt(qualitative),
            _fmt(qualitative * weights["qualitative_evidence"]),
        ],
        ["COMPOSITE", "100%", "-", _fmt(final_score)],
    ]
    table = Table(score_rows, colWidths=[2.8 * inch, 1.1 * inch, 1.2 * inch, 1.2 * inch])
    table.setStyle(_table_style(header=True, composite_row=4))

    alpha_1 = reliability.get("cronbach_alpha_instructional_block")
    alpha_2 = reliability.get("cronbach_alpha_overall_experience_block")
    alpha_1_text = _alpha_text(alpha_1)
    alpha_2_text = _alpha_text(alpha_2)

    story = [
        Paragraph("Score Summary", styles["h1"]),
        Spacer(1, 0.15 * inch),
        table,
        Spacer(1, 0.25 * inch),
        Paragraph(f"Final Rating: {_fmt(final_score)} / 5.00   Band: {rating_band(final_score)}", styles["normal"]),
        Paragraph(
            f"95% CI: [{_fmt(row.get('rating_ci_low_1_5'))} - {_fmt(row.get('rating_ci_high_1_5'))}]",
            styles["normal"],
        ),
        Spacer(1, 0.2 * inch),
        Paragraph("Reliability", styles["h2"]),
        Paragraph(f"Part 1 Cronbach alpha: {alpha_1_text}", styles["normal"]),
        Paragraph(f"Part 2 Cronbach alpha: {alpha_2_text}", styles["normal"]),
        Spacer(1, 0.2 * inch),
        Paragraph("Response Quality", styles["h2"]),
        Paragraph(
            "N responses: "
            f"{int(_number(row.get('responses'), default=0))}   "
            f"Effective N: {_fmt(row.get('effective_response_count'))}   "
            f"Mean RCI: {_fmt(row.get('mean_rci_weight'))}",
            styles["normal"],
        ),
        Paragraph(f"Flagged responses: {int(_number(row.get('flagged_responses'), default=0))}", styles["normal"]),
        Spacer(1, 0.2 * inch),
        Paragraph(
            "Composite = 0.50 x Instructional + 0.30 x Experience + 0.20 x Qualitative. "
            "Weights are institutional policy, not data-derived.",
            styles["italic"],
        ),
    ]
    return story


def _qualitative_page(styles: Mapping[str, ParagraphStyle], qualitative: pd.Series, block_id: str) -> list[Any]:
    prompts = PROMPT_META.get(block_id, PROMPT_META["shs"])
    story = [Paragraph("Qualitative Feedback Summary", styles["h1"]), Spacer(1, 0.15 * inch)]
    for prompt_key, phrase_key, counts_key in (
        ("oe1", "appreciated_phrases", "appreciated_frame_counts"),
        ("oe2", "suggestion_phrases", "suggestion_frame_counts"),
        ("oe3", "experience_phrases", "experience_frame_counts"),
    ):
        meta = prompts[prompt_key]
        story.append(Paragraph(meta["prompt"], styles["h2"]))
        story.append(Paragraph(str(qualitative.get(phrase_key, "no dominant theme detected")), styles["normal"]))
        story.append(Spacer(1, 0.08 * inch))
        story.append(_frame_count_table(qualitative.get(counts_key, "{}")))
        story.append(Spacer(1, 0.08 * inch))

    evidence = [snippet.strip() for snippet in str(qualitative.get("representative_evidence", "")).split("|") if snippet.strip()]
    if evidence:
        story.append(Paragraph("Representative snippets", styles["h2"]))
        for snippet in evidence:
            story.append(Paragraph(f"Student response: {snippet}", styles["normal"]))
    story.append(Spacer(1, 0.2 * inch))
    story.append(
        Paragraph(
            "Statements reflect the full distribution of responses received. Representative snippets were selected "
            "to include both appreciative and critical feedback where present.",
            styles["footer_note"],
        )
    )
    return story


def _diagnostic_page(styles: Mapping[str, ParagraphStyle], qualitative: pd.Series) -> list[Any]:
    flags = _verbose_flags(qualitative.get("verbose_flag_detail", "[]"))
    story = [Paragraph("Diagnostic Appendix", styles["h1"]), Spacer(1, 0.15 * inch)]
    if not flags:
        story.append(Paragraph("No verbose qualitative responses were flagged for review.", styles["normal"]))
        return story

    story.append(Paragraph(f"Verbose qualitative responses flagged for review: {len(flags)}", styles["h2"]))
    rows = [["Prompt", "Response index", "Word count", "Threshold", "Snippet"]]
    for flag in flags:
        rows.append(
            [
                str(flag.get("prompt", "")),
                str(flag.get("response_index", "")),
                str(flag.get("word_count", "")),
                str(flag.get("threshold", "")),
                str(flag.get("snippet", "")),
            ]
        )
    table = Table(rows, colWidths=[0.8 * inch, 0.9 * inch, 0.8 * inch, 0.8 * inch, 3.0 * inch])
    table.setStyle(_table_style(header=True))
    story.append(table)
    story.append(Spacer(1, 0.15 * inch))
    story.append(
        Paragraph(
            "These responses exceeded the expected length for their prompt type and are provided for human review. "
            "Length alone does not indicate problematic content.",
            styles["footer_note"],
        )
    )
    return story


def _frame_count_table(count_json: object) -> Table:
    counts = _json_object(count_json)
    rows = [["Frame", "Responses", "Percentage"]]
    total = sum(int(value) for value in counts.values())
    for frame, count in counts.items():
        pct = f"{(int(count) / total * 100):.0f}%" if total else "0%"
        rows.append([frame, str(count), pct])
    if len(rows) == 1:
        rows.append(["No detected frame", "0", "0%"])
    table = Table(rows, colWidths=[3.4 * inch, 1.2 * inch, 1.2 * inch])
    table.setStyle(_table_style(header=True))
    return table


def _one_teacher_row(table: pd.DataFrame, teacher: str, required: bool = True) -> pd.Series:
    rows = table[table["teacher"] == teacher] if "teacher" in table.columns else pd.DataFrame()
    if rows.empty:
        if required:
            raise ValueError(f"Teacher {teacher!r} was not found in the report.")
        return pd.Series(dtype=object)
    return rows.iloc[0]


def _component_weight_lookup(component_weights: pd.DataFrame) -> dict[str, float]:
    if component_weights.empty:
        return {
            "instructional_performance": 0.50,
            "overall_experience": 0.30,
            "qualitative_evidence": 0.20,
        }
    return {
        str(row["component"]): float(row["weight"])
        for _, row in component_weights.iterrows()
    }


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "cover_title": ParagraphStyle("CoverTitle", parent=sample["Title"], fontName="Helvetica-Bold", fontSize=16),
        "h1": ParagraphStyle("Heading1", parent=sample["Heading1"], fontName="Helvetica-Bold", fontSize=14),
        "h2": ParagraphStyle("Heading2", parent=sample["Heading2"], fontName="Helvetica-Bold", fontSize=11),
        "normal": ParagraphStyle("Normal", parent=sample["Normal"], fontName="Helvetica", fontSize=10, leading=13),
        "italic": ParagraphStyle("Italic", parent=sample["Italic"], fontName="Helvetica-Oblique", fontSize=9, leading=12),
        "footer_note": ParagraphStyle("FooterNote", parent=sample["Normal"], fontName="Helvetica", fontSize=8, leading=10),
        "confidential": ParagraphStyle(
            "Confidential",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=9,
            alignment=1,
        ),
    }


def _table_style(header: bool = False, composite_row: Optional[int] = None) -> TableStyle:
    commands = [
        ("GRID", (0, 0), (-1, -1), 0.25, colors.grey),
        ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
        ("FONTSIZE", (0, 0), (-1, -1), 8),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
    ]
    if header:
        commands.extend(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ]
        )
    if composite_row is not None:
        commands.extend(
            [
                ("FONTNAME", (0, composite_row), (-1, composite_row), "Helvetica-Bold"),
                ("BACKGROUND", (0, composite_row), (-1, composite_row), colors.whitesmoke),
            ]
        )
    return TableStyle(commands)


def _number(value: object, default: float = 0.0) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(numeric) if pd.notna(numeric) else default


def _fmt(value: object) -> str:
    return f"{_number(value):.2f}"


def _pct(value: float) -> str:
    return f"{value * 100:.0f}%"


def _alpha_text(value: object) -> str:
    numeric = _number(value, default=float("nan"))
    if pd.isna(numeric):
        return "n/a"
    warning = " (review: below 0.70)" if numeric < 0.70 else ""
    return f"{numeric:.2f}{warning}"


def _json_object(value: object) -> dict[str, int]:
    try:
        data = json.loads(str(value))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(key): int(val) for key, val in data.items()}


def _verbose_flags(value: object) -> list[dict[str, Any]]:
    try:
        data = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    return [item for item in data if isinstance(item, dict)]
