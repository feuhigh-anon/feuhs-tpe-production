"""SharePoint/MS Forms export ingestion and normalization."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Sequence

import pandas as pd

from feval.models import ColumnMatch, NormalizedExport, QuestionBlock, QuestionItem


LIKERT_MAP = {
    "strongly disagree": 1.0,
    "sd": 1.0,
    "disagree": 2.0,
    "d": 2.0,
    "neutral": 3.0,
    "neither agree nor disagree": 3.0,
    "n": 3.0,
    "agree": 4.0,
    "a": 4.0,
    "strongly agree": 5.0,
    "sa": 5.0,
    "very poor": 1.0,
    "poor": 2.0,
    "fair": 3.0,
    "good": 4.0,
    "excellent": 5.0,
    "not applicable": float("nan"),
    "n/a": float("nan"),
    "na": float("nan"),
    "": float("nan"),
}


def read_sharepoint_export(source) -> pd.DataFrame:
    """Read a SharePoint/MS Forms export from CSV or Excel."""

    name = str(getattr(source, "name", source)).lower()
    if hasattr(source, "seek"):
        source.seek(0)

    if name.endswith((".xlsx", ".xlsm", ".xls")):
        data = pd.read_excel(source)
    elif name.endswith(".csv"):
        data = pd.read_csv(source)
    else:
        try:
            data = pd.read_excel(source)
        except Exception:
            if hasattr(source, "seek"):
                source.seek(0)
            data = pd.read_csv(source)

    data = data.dropna(how="all").copy()
    data.columns = _dedupe_columns([_clean_header(column) for column in data.columns])
    return data


def normalize_header(value: object) -> str:
    """Canonical form used for fuzzy column matching."""

    text = str(value or "").strip().lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def score_likert_value(value: object) -> float:
    """Convert common 5-point Likert labels or numeric values to 1..5."""

    if pd.isna(value):
        return float("nan")
    if isinstance(value, (int, float)):
        numeric = float(value)
        return numeric if 1.0 <= numeric <= 5.0 else float("nan")

    text = str(value).strip()
    if not text:
        return float("nan")

    numeric_match = re.match(r"^\s*([1-5])(?:\.0)?(?:\s*[-:.)].*)?$", text)
    if numeric_match:
        return float(numeric_match.group(1))

    key = normalize_header(text)
    if key in LIKERT_MAP:
        return LIKERT_MAP[key]

    for label, score in LIKERT_MAP.items():
        if label and label in key:
            return score

    return float("nan")


def infer_best_column(columns: Sequence[str], aliases: Iterable[str]) -> Optional[str]:
    """Find a likely metadata column from a set of aliases."""

    alias_terms = [normalize_header(alias) for alias in aliases if normalize_header(alias)]
    normalized = {column: normalize_header(column) for column in columns}
    for alias in alias_terms:
        for column, column_key in normalized.items():
            if alias == column_key:
                return column
    for alias in alias_terms:
        for column, column_key in normalized.items():
            if alias and (alias in column_key or column_key in alias):
                return column
    return None


def build_column_matches(
    columns: Sequence[str],
    block: QuestionBlock,
    overrides: Optional[Mapping[str, Optional[str]]] = None,
) -> Dict[str, ColumnMatch]:
    """Map question items to export columns using aliases plus optional overrides."""

    overrides = overrides or {}
    matches: Dict[str, ColumnMatch] = {}
    for item in block.all_items:
        if overrides.get(item.id):
            matches[item.id] = ColumnMatch(item.id, str(overrides[item.id]), "manual")
            continue

        column = _find_item_column(item, columns)
        confidence = "auto" if column else "missing"
        matches[item.id] = ColumnMatch(item.id, column, confidence)
    return matches


def normalize_responses(
    raw: pd.DataFrame,
    block: QuestionBlock,
    teacher_column: str,
    column_map: Mapping[str, Optional[str]],
    section_column: Optional[str] = None,
    respondent_column: Optional[str] = None,
) -> NormalizedExport:
    """Normalize a SharePoint export into canonical item-id columns."""

    if teacher_column not in raw.columns:
        raise ValueError(f"Teacher column {teacher_column!r} was not found in the export.")

    normalized = pd.DataFrame()
    normalized["teacher"] = raw[teacher_column].fillna("Unspecified").astype(str).str.strip()
    normalized["teacher"] = normalized["teacher"].replace("", "Unspecified")

    if section_column and section_column in raw.columns:
        normalized["section"] = raw[section_column].astype(str).str.strip()
    if respondent_column and respondent_column in raw.columns:
        normalized["respondent"] = raw[respondent_column].astype(str).str.strip()

    resolved_map: Dict[str, str] = {}
    missing_required = []
    for item in block.all_items:
        source_column = column_map.get(item.id)
        if not source_column:
            if item.required:
                missing_required.append(item.id)
            continue
        if source_column not in raw.columns:
            if item.required:
                missing_required.append(item.id)
            continue

        resolved_map[item.id] = source_column
        if item in block.quantitative_items:
            normalized[item.id] = raw[source_column].map(score_likert_value)
        else:
            normalized[item.id] = raw[source_column].fillna("").astype(str).str.strip()

    if missing_required:
        missing = ", ".join(missing_required)
        raise ValueError(f"Missing required question columns: {missing}")

    normalized = normalized[normalized["teacher"].notna()].copy()
    return NormalizedExport(
        block=block,
        raw=raw,
        responses=normalized,
        teacher_column=teacher_column,
        section_column=section_column,
        respondent_column=respondent_column,
        column_map=resolved_map,
    )


def load_and_normalize(
    source,
    block: QuestionBlock,
    teacher_column: Optional[str] = None,
    section_column: Optional[str] = None,
    respondent_column: Optional[str] = None,
    column_overrides: Optional[Mapping[str, Optional[str]]] = None,
) -> NormalizedExport:
    """Convenience helper for one-shot reading, matching, and normalization."""

    raw = read_sharepoint_export(source)
    teacher_column = teacher_column or infer_best_column(raw.columns, block.teacher_aliases)
    if not teacher_column:
        raise ValueError("Could not infer the teacher column. Please provide one explicitly.")

    section_column = section_column or infer_best_column(raw.columns, block.section_aliases)
    respondent_column = respondent_column or infer_best_column(raw.columns, block.respondent_aliases)
    matches = build_column_matches(raw.columns, block, column_overrides)
    return normalize_responses(
        raw=raw,
        block=block,
        teacher_column=teacher_column,
        section_column=section_column,
        respondent_column=respondent_column,
        column_map={item_id: match.column for item_id, match in matches.items()},
    )


def _clean_header(column: object) -> str:
    text = str(column or "").strip()
    return re.sub(r"\s+", " ", text) or "Unnamed"


def _dedupe_columns(columns: Sequence[str]) -> list[str]:
    seen: Dict[str, int] = {}
    result = []
    for column in columns:
        count = seen.get(column, 0)
        seen[column] = count + 1
        result.append(column if count == 0 else f"{column}.{count}")
    return result


def _find_item_column(item: QuestionItem, columns: Sequence[str]) -> Optional[str]:
    normalized_columns = {column: normalize_header(column) for column in columns}
    terms = [normalize_header(term) for term in item.match_terms if normalize_header(term)]

    for term in terms:
        for column, column_key in normalized_columns.items():
            if term == column_key:
                return column

    for term in terms:
        if len(term) < 4:
            continue
        for column, column_key in normalized_columns.items():
            if term in column_key:
                return column

    compact_columns = {column: key.replace(" ", "") for column, key in normalized_columns.items()}
    for term in terms:
        compact_term = term.replace(" ", "")
        if len(compact_term) < 4:
            continue
        for column, compact_column in compact_columns.items():
            if compact_term in compact_column:
                return column

    return None
