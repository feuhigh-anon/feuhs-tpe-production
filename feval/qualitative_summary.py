"""Protocol-driven qualitative summary contracts and rehearsal generation."""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping

import pandas as pd

from feval.models import NormalizedExport
from feval.text import analyze_open_ended, is_substantive_comment


PROMPT_TYPES = ("appreciation", "suggestion", "experience")
PROMPT_FIELDS = {
    "appreciation": "appreciated",
    "suggestion": "suggestion",
    "experience": "experience",
}
STATEMENT_ROLES = ("dominant_pattern", "secondary_pattern", "context_and_limitation")
INSUFFICIENT_MESSAGE = "Insufficient interpretable feedback for a thematic summary."


def build_protocol_qualitative_summary(
    normalized: NormalizedExport,
    *,
    generator: Callable[[Mapping[str, object]], Mapping[str, object]] | None = None,
) -> pd.DataFrame:
    """Build one validated summary row per teacher and prompt type.

    ``generator`` is the future LLM boundary. It receives only one isolated
    teacher/prompt unit and may supply statement text, while counts and
    minimum-data status remain deterministic. With no generator, this function
    produces a clearly marked deterministic rehearsal from the existing
    semantic-frame output so the PDF contract can be exercised before an LLM
    provider is approved.
    """
    legacy = analyze_open_ended(normalized, block_id=normalized.block.id)
    rows: list[dict[str, object]] = []
    for _, teacher_row in legacy.iterrows():
        teacher = teacher_row["teacher"]
        for prompt_type in PROMPT_TYPES:
            field_prefix = PROMPT_FIELDS[prompt_type]
            response_count = _integer(teacher_row.get(f"{field_prefix}_response_count"))
            interpretable_count = _integer(teacher_row.get(f"{field_prefix}_interpretable_count"))
            abstained_count = _integer(teacher_row.get(f"{field_prefix}_abstained_count"))
            frame_counts = _parse_frame_counts(teacher_row.get(f"{field_prefix}_frame_counts"))
            comments = _comments_for_unit(normalized, teacher, prompt_type)
            unit = {
                "teacher": teacher,
                "prompt_type": prompt_type,
                "response_count": response_count,
                "interpretable_count": interpretable_count,
                "abstained_count": abstained_count,
                "comments": comments,
                "verified_themes": [
                    {"label": label, "count": count, "denominator": interpretable_count}
                    for label, count in frame_counts
                ],
            }
            minimum_status = _minimum_status(interpretable_count)
            if minimum_status == "insufficient_data":
                generated = _insufficient_result()
            elif generator is None:
                generated = _rehearsal_result(unit, frame_counts)
            else:
                generated = _validate_generator_result(generator(unit), minimum_status)
            rows.append(
                {
                    "teacher": teacher,
                    "prompt_type": prompt_type,
                    "response_count": response_count,
                    "interpretable_count": interpretable_count,
                    "abstained_count": abstained_count,
                    "statement_1": generated["statements"][0]["text"],
                    "statement_2": generated["statements"][1]["text"],
                    "statement_3": generated["statements"][2]["text"],
                    "statement_role_1": STATEMENT_ROLES[0],
                    "statement_role_2": STATEMENT_ROLES[1],
                    "statement_role_3": STATEMENT_ROLES[2],
                    "status": generated["status"],
                    "model_status": generated["model_status"],
                    "generation_mode": "deterministic_rehearsal" if generator is None else "llm_provider",
                }
            )
    return pd.DataFrame(rows, columns=SUMMARY_COLUMNS)


SUMMARY_COLUMNS = [
    "teacher",
    "prompt_type",
    "response_count",
    "interpretable_count",
    "abstained_count",
    "statement_1",
    "statement_2",
    "statement_3",
    "statement_role_1",
    "statement_role_2",
    "statement_role_3",
    "status",
    "model_status",
    "generation_mode",
]


def _rehearsal_result(unit: Mapping[str, object], frame_counts: list[tuple[str, int]]) -> dict[str, object]:
    interpretable_count = int(unit["interpretable_count"])
    cautious = interpretable_count < 10
    first = _theme_text(frame_counts[0]) if frame_counts else "no recurring theme"
    second = _theme_text(frame_counts[1]) if len(frame_counts) > 1 else "no distinct secondary pattern"
    qualifier = "A small number of comments" if cautious else "Students frequently"
    return {
        "status": "cautious" if cautious else "complete",
        "model_status": "not_run_rehearsal",
        "statements": [
            {"role": STATEMENT_ROLES[0], "text": f"{qualifier} described {first}."},
            {"role": STATEMENT_ROLES[1], "text": f"The available feedback also indicated {second}."},
            {
                "role": STATEMENT_ROLES[2],
                "text": (
                    f"This summary is based on {interpretable_count} interpretable comments out of "
                    f"{int(unit['response_count'])} responses; {int(unit['abstained_count'])} were abstained."
                ),
            },
        ],
    }


def build_llm_prompt(unit: Mapping[str, object]) -> dict[str, str]:
    """Build the provider-neutral request for one isolated analysis unit.

    The comments are deliberately included here because the model must
    interpret what students mean, not merely restate frequency counts. The
    caller must invoke this function separately for each teacher and prompt
    type and must not combine its inputs.
    """
    prompt_type = str(unit["prompt_type"])
    comments = unit.get("comments", [])
    if not isinstance(comments, list):
        raise ValueError("The isolated qualitative unit must contain a comment list.")
    serialized_comments = "\n".join(f"- {str(comment).strip()}" for comment in comments)
    return {
        "system": (
            "You are a careful qualitative-analysis assistant. Analyze only the "
            "student comments in this one isolated unit. Do not infer teacher "
            "quality overall, rank the teacher, assign a score, or recommend "
            "personnel action. Synthesize meaning rather than paraphrasing a "
            "frequency table. Return JSON only."
        ),
        "user": (
            f"Prompt type: {prompt_type}.\n"
            f"Verified response count: {int(unit['response_count'])}.\n"
            f"Verified interpretable count: {int(unit['interpretable_count'])}.\n"
            f"Verified abstained count: {int(unit['abstained_count'])}.\n\n"
            "Produce exactly three statements with these roles:\n"
            "1. dominant_pattern: explain the most meaningful recurring pattern "
            "and what students appear to value, experience, or need.\n"
            "2. secondary_pattern: explain a second pattern, variation, or "
            "constructive tension when supported by the comments.\n"
            "3. context_and_limitation: state the practical implication or "
            "actionable teaching consideration, together with the evidence "
            "limits. For appreciation, phrase the implication as a practice "
            "to sustain. For suggestion, phrase it as a concrete area for "
            "teaching improvement. For experience, describe a condition that "
            "could support learning.\n\n"
            "Do not invent counts, causes, motives, or facts. Do not mention "
            "comments from any other prompt type or teacher.\n\n"
            "Isolated comments:\n"
            f"{serialized_comments}"
        ),
    }


def _comments_for_unit(normalized: NormalizedExport, teacher: object, prompt_type: str) -> list[str]:
    text_columns = normalized.present_columns(normalized.text_columns)
    position = PROMPT_TYPES.index(prompt_type)
    if position >= len(text_columns):
        return []
    group = normalized.responses[normalized.responses["teacher"] == teacher]
    column = text_columns[position]
    return [str(value).strip() for value in group[column].tolist() if is_substantive_comment(value)]


def _insufficient_result() -> dict[str, object]:
    return {
        "status": "insufficient_data",
        "model_status": "not_run",
        "statements": [
            {"role": role, "text": INSUFFICIENT_MESSAGE} for role in STATEMENT_ROLES
        ],
    }


def _validate_generator_result(result: Mapping[str, object], minimum_status: str) -> dict[str, object]:
    if minimum_status == "insufficient_data":
        return _insufficient_result()
    statements = result.get("statements")
    if not isinstance(statements, list) or len(statements) != 3:
        raise ValueError("Qualitative generator must return exactly three statements.")
    validated_statements = []
    for expected_role, statement in zip(STATEMENT_ROLES, statements):
        if not isinstance(statement, Mapping) or statement.get("role") != expected_role:
            raise ValueError(f"Qualitative generator returned an invalid role for {expected_role}.")
        text = statement.get("text")
        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Qualitative generator returned empty text for {expected_role}.")
        validated_statements.append({"role": expected_role, "text": text.strip()})
    status = result.get("status")
    if status not in {"complete", "cautious"}:
        raise ValueError("Qualitative generator returned an invalid status.")
    return {
        "status": status,
        "model_status": str(result.get("model_status", "validated")),
        "statements": validated_statements,
    }


def _minimum_status(interpretable_count: int) -> str:
    return "insufficient_data" if interpretable_count < 3 else "cautious" if interpretable_count < 10 else "complete"


def _parse_frame_counts(raw_value: object) -> list[tuple[str, int]]:
    if raw_value is None or pd.isna(raw_value):
        return []
    try:
        parsed = json.loads(str(raw_value))
    except (TypeError, ValueError):
        return []
    if not isinstance(parsed, dict):
        return []
    return sorted(
        ((str(label), _integer(count)) for label, count in parsed.items() if _integer(count) > 0),
        key=lambda item: (-item[1], item[0]),
    )


def _theme_text(theme: tuple[str, int]) -> str:
    label, count = theme
    return f"{label} ({count} of the interpretable comments)"


def _integer(value: object) -> int:
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    return int(numeric) if pd.notna(numeric) else 0