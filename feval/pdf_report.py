"""Faculty-facing PDF report generation."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any, Mapping
from xml.sax.saxutils import escape

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from feval.text import PROMPT_META


LOGO_PATH = Path(__file__).resolve().parent.parent / "assets" / "feu-high-school-logo.png"


def summarize_teacher_qualitative_feedback(open_ended: pd.DataFrame | pd.Series) -> str:
    """Return a compact teacher-specific qualitative summary in sentence form."""
    if isinstance(open_ended, pd.DataFrame):
        if open_ended.empty:
            return "Pros: no dominant strengths. Cons: no dominant concerns."
        row = open_ended.iloc[0]
    else:
        row = open_ended

    pros = _normalize_phrase_list(row.get("appreciated_phrases", ""))
    if not pros:
        pros = _normalize_phrase_list(row.get("experience_phrases", ""))
    cons = _normalize_phrase_list(row.get("suggestion_phrases", ""))
    if not cons:
        cons = _normalize_phrase_list(row.get("experience_phrases", ""))

    pros_text = "; ".join(pros[:3]) if pros else "no dominant strengths"
    cons_text = "; ".join(cons[:3]) if cons else "no dominant concerns"
    return f"Pros: {pros_text}. Cons: {cons_text}."


def qualitative_feedback_sections(
    open_ended: pd.DataFrame | pd.Series,
    block_id: str = "shs",
) -> list[tuple[str, str]]:
    """Return one three-sentence aggregate summary for each open-ended prompt."""
    if isinstance(open_ended, pd.DataFrame):
        row = open_ended.iloc[0] if not open_ended.empty else pd.Series(dtype=object)
    else:
        row = open_ended

    prompt_meta = PROMPT_META.get(block_id.lower(), PROMPT_META["shs"])
    prompts = (
        ("appreciated_phrases", "oe1", "appreciated"),
        ("suggestion_phrases", "oe2", "suggestion"),
        ("experience_phrases", "oe3", "experience"),
    )
    sections = []
    for field, prompt_key, prompt_type in prompts:
        themes = _normalize_phrase_list(row.get(field, ""))
        theme_text = ", ".join(themes[:3]) if themes else "no dominant theme was identified"
        if prompt_type == "appreciated":
            sentences = (
                f"Students most often appreciated {theme_text}.",
                f"The recurring positive themes were {theme_text}.",
                "These comments identify the teaching practices students valued most.",
            )
        elif prompt_type == "suggestion":
            sentences = (
                f"Students suggested attention to {theme_text}.",
                f"The recurring improvement themes were {theme_text}.",
                "These suggestions identify areas for continued teaching development.",
            )
        else:
            sentences = (
                f"Students described their learning experience through {theme_text}.",
                f"The recurring experience themes were {theme_text}.",
                f"Overall, the feedback reflects {theme_text}.",
            )
        sections.append((prompt_meta[prompt_key]["prompt"], " ".join(sentences)))
    return sections


def structured_qualitative_feedback_sections(
    qualitative_summary: pd.DataFrame | None,
    teacher: str,
    block_id: str = "shs",
) -> list[tuple[str, str, str]]:
    """Format isolated teacher/prompt summaries for PDF rendering."""
    if qualitative_summary is None or qualitative_summary.empty:
        return []
    required = {"teacher", "prompt_type", "statement_1", "statement_2", "statement_3"}
    if not required.issubset(qualitative_summary.columns):
        return []

    prompt_meta = PROMPT_META.get(block_id.lower(), PROMPT_META["shs"])
    prompt_keys = {"appreciation": "oe1", "appreciated": "oe1", "suggestion": "oe2", "experience": "oe3"}
    sections = []
    rows = qualitative_summary[qualitative_summary["teacher"] == teacher]
    for _, row in rows.iterrows():
        prompt_key = prompt_keys.get(str(row.get("prompt_type", "")).strip().lower())
        if not prompt_key:
            continue
        statements = [str(row.get(f"statement_{index}", "")).strip() for index in range(1, 4)]
        statements = [statement for statement in statements if statement and statement.lower() != "nan"]
        if not statements:
            continue
        metadata = "; ".join(
            value
            for value in (
                _structured_count_text(row),
                str(row.get("status", "")).strip(),
                str(row.get("model_status", "")).strip(),
            )
            if value and value.lower() != "nan"
        )
        sections.append((prompt_meta[prompt_key]["prompt"], " ".join(statements), metadata))
    return sections


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
    evaluation_date: str = "",
) -> Path:
    """Build a single-page confidential faculty report using only aggregate results."""

    output = Path(output_path)
    summary_row = _one_teacher_row(report.summary, teacher)
    qualitative_row = _one_teacher_row(report.open_ended, teacher, required=False)
    qualitative_summary = getattr(report, "qualitative_summary", None)

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
        _single_page_report(
            styles,
            teacher=teacher,
            subject=subject,
            section=section,
            institution=institution,
            academic_year=academic_year,
            term=term,
            evaluation_period=evaluation_period,
            evaluation_date=evaluation_date,
            summary_row=summary_row,
            qualitative_row=qualitative_row,
            qualitative_summary=qualitative_summary,
            block_id=block_id,
        )
    )
    doc.build(story)
    return output


def rating_band(score: float) -> str:
    if score >= 4.50:
        return "Outstanding"
    if score >= 3.50:
        return "Proficient"
    if score >= 2.50:
        return "Developing"
    return "Needs Support"


def _single_page_report(
    styles: Mapping[str, ParagraphStyle],
    *,
    teacher: str,
    subject: str,
    section: str,
    institution: str,
    academic_year: str,
    term: str,
    evaluation_period: str,
    evaluation_date: str,
    summary_row: pd.Series,
    qualitative_row: pd.Series,
    qualitative_summary: pd.DataFrame | None,
    block_id: str,
) -> list[Any]:
    final_score = _number(summary_row.get("final_teacher_rating_1_5"))
    evaluator_count = int(_number(summary_row.get("responses")))
    report_date = evaluation_date or date.today().isoformat()
    structured_sections = structured_qualitative_feedback_sections(
        qualitative_summary, teacher, block_id=block_id
    )
    qualitative_sections = structured_sections or [
        (prompt, summary, "") for prompt, summary in qualitative_feedback_sections(qualitative_row, block_id=block_id)
    ]
    logo = Image(str(LOGO_PATH), width=0.42 * inch, height=0.512 * inch)
    header = Table(
        [[logo, Paragraph("Teacher Performance Evaluation by Students", styles["report_title"])]],
        colWidths=[0.6 * inch, 5.9 * inch],
    )
    header.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
                ("LINEBELOW", (0, 0), (-1, -1), 0.7, colors.Color(0.10, 0.36, 0.18)),
            ]
        )
    )

    story = [
        header,
        Spacer(1, 0.12 * inch),
        Paragraph(escape(teacher), styles["cover_title"]),
        Paragraph(
            f"Evaluation period: {escape(evaluation_period or 'Not specified')} | "
            f"Report date: {escape(report_date)} | Evaluators: {evaluator_count}",
            styles["normal"],
        ),
        Spacer(1, 0.25 * inch),
        Paragraph("Final evaluation score", styles["h2"]),
        Paragraph(f"{final_score:.2f} / 5.00", styles["score"]),
        Spacer(1, 0.14 * inch),
    ]
    for prompt, summary, metadata in qualitative_sections:
        story.append(Paragraph(escape(prompt), styles["h2"]))
        if metadata:
            story.append(Paragraph(escape(metadata), styles["metadata"]))
        story.extend([Paragraph(escape(summary), styles["summary_text"]), Spacer(1, 0.06 * inch)])
    story.extend(
        [
        Paragraph(
            "This report summarizes the teacher's aggregated student feedback for confidential faculty review. "
            "Student identities, section-level detail, and raw response snippets are intentionally excluded.",
            styles["footer_note"],
        ),
        ]
    )
    return story


def _normalize_phrase_list(raw_value: object) -> list[str]:
    if raw_value is None or pd.isna(raw_value):
        return []
    cleaned = str(raw_value).replace("|", ";")
    parts = [part.strip() for part in cleaned.split(";") if part.strip() and part.strip() != "no dominant theme detected"]
    normalized = []
    for part in parts:
        if len(part) > 140:
            part = part[:137].rstrip() + "..."
        normalized.append(part)
    return normalized


def _structured_count_text(row: pd.Series) -> str:
    """Format deterministic counts without exposing raw response text."""
    interpretable = row.get("interpretable_count", row.get("comment_count", ""))
    abstained = row.get("abstained_count", "")
    total = row.get("response_count", "")
    parts = []
    if _has_value(interpretable):
        parts.append(f"Interpretable comments: {int(_number(interpretable))}")
    if _has_value(abstained):
        parts.append(f"Abstained: {int(_number(abstained))}")
    if _has_value(total):
        parts.append(f"Responses: {int(_number(total))}")
    return "; ".join(parts)


def _has_value(value: object) -> bool:
    return value is not None and not (isinstance(value, str) and not value.strip()) and not pd.isna(value)


def _one_teacher_row(table: pd.DataFrame, teacher: str, required: bool = True) -> pd.Series:
    rows = table[table["teacher"] == teacher] if "teacher" in table.columns else pd.DataFrame()
    if rows.empty:
        if required:
            raise ValueError(f"Teacher {teacher!r} was not found in the report.")
        return pd.Series(dtype=object)
    return rows.iloc[0]


def _styles() -> dict[str, ParagraphStyle]:
    sample = getSampleStyleSheet()
    return {
        "report_title": ParagraphStyle(
            "ReportTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=15,
            leading=18,
            textColor=colors.Color(0.08, 0.17, 0.25),
        ),
        "cover_title": ParagraphStyle(
            "CoverTitle",
            parent=sample["Title"],
            fontName="Helvetica-Bold",
            fontSize=18,
            leading=22,
            spaceAfter=5,
            textColor=colors.Color(0.08, 0.17, 0.25),
        ),
        "h2": ParagraphStyle(
            "Heading2",
            parent=sample["Heading2"],
            fontName="Helvetica-Bold",
            fontSize=11,
            leading=14,
            spaceAfter=4,
        ),
        "normal": ParagraphStyle(
            "Normal",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=13,
        ),
        "metadata": ParagraphStyle(
            "Metadata",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.Color(0.35, 0.35, 0.35),
        ),
        "score": ParagraphStyle(
            "Score",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=22,
            leading=24,
            textColor=colors.Color(0.10, 0.36, 0.18),
        ),
        "summary_text": ParagraphStyle(
            "SummaryText",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=10,
            leading=14,
            spaceBefore=4,
            spaceAfter=6,
        ),
        "footer_note": ParagraphStyle(
            "FooterNote",
            parent=sample["Normal"],
            fontName="Helvetica",
            fontSize=8,
            leading=10,
            textColor=colors.grey,
        ),
        "confidential": ParagraphStyle(
            "Confidential",
            parent=sample["Normal"],
            fontName="Helvetica-Bold",
            fontSize=9,
            alignment=1,
            textColor=colors.Color(0.42, 0.42, 0.42),
        ),
    }


def _number(value: object, default: float = 0.0) -> float:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return float(numeric) if pd.notna(numeric) else default
