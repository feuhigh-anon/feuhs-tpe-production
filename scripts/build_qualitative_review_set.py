"""Build a de-identified, stratified qualitative review set from local exports."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from pathlib import Path
from typing import Iterable

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
SOURCE_ROOT = ROOT / "Students Evaluation"
DEFAULT_OUTPUT = ROOT / "exports" / "qualitative_review"
TEXT_PATTERNS = {
    "appreciation": r"what strategies and practices.*appreciate|what did you like the most",
    "suggestion": r"what are some constructive suggestions|how do you think your teacher can be better",
    "experience": r"overall[, ]+how was your learning experience",
}
NAME_PATTERNS = r"name|teacher|faculty|student|email|section|subject|grade|strand|id|time|date"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20260908)
    parser.add_argument("--appreciation", type=int, default=40)
    parser.add_argument("--suggestion", type=int, default=40)
    parser.add_argument("--experience", type=int, default=20)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args()


def source_files() -> list[Path]:
    return sorted(
        path
        for path in SOURCE_ROOT.rglob("*")
        if path.suffix.lower() in {".csv", ".xlsx", ".xlsm", ".xls"}
    )


def load_frame(path: Path) -> pd.DataFrame:
    return pd.read_csv(path) if path.suffix.lower() == ".csv" else pd.read_excel(path)


def normalize_cell(value: object) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip())


def frame_fingerprint(row: pd.Series) -> str:
    values = "\x1f".join(normalize_cell(value) for value in row.tolist())
    return hashlib.sha256(values.encode("utf-8")).hexdigest()


def find_text_columns(frame: pd.DataFrame) -> dict[str, str]:
    columns: dict[str, str] = {}
    for column in frame.columns:
        header = normalize_cell(column).lower()
        for prompt_type, pattern in TEXT_PATTERNS.items():
            if prompt_type not in columns and re.search(pattern, header) and not looks_like_likert(frame[column]):
                columns[prompt_type] = column
    return columns


def looks_like_likert(series: pd.Series) -> bool:
    values = series.dropna().astype(str).str.strip()
    values = values[values.ne("")]
    if not len(values):
        return False
    numeric = pd.to_numeric(values, errors="coerce")
    numeric_ratio = numeric.notna().mean()
    return numeric_ratio >= 0.9 and numeric.dropna().nunique() <= 10


def school_level(frame: pd.DataFrame, path: Path) -> str:
    headers = " ".join(str(column).lower() for column in frame.columns)
    if "jhs" in str(path).lower() or "junior" in headers:
        return "JHS"
    return "SHS"


def redaction_values(row: pd.Series, excluded_columns: set[object]) -> list[str]:
    values = []
    for column, value in row.items():
        if column in excluded_columns:
            continue
        if re.search(NAME_PATTERNS, str(column), re.I):
            text = normalize_cell(value)
            if len(text) >= 3:
                values.append(text)
    return sorted(set(values), key=len, reverse=True)


def redact_text(text: str, values: Iterable[str]) -> str:
    result = text
    result = re.sub(
        r"\b(?:sir|ma'am|mr\.?|ms\.?|mrs\.?|mx\.?)\s+[A-Z][A-Za-z]+(?:\s+[A-Z][A-Za-z]+)?\b",
        "[REDACTED_PERSON]",
        result,
        flags=re.I,
    )
    result = re.sub(r"[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}", "[REDACTED_EMAIL]", result)
    result = re.sub(r"https?://\S+|www\.\S+", "[REDACTED_URL]", result, flags=re.I)
    result = re.sub(r"\b(?:09\d{9}|\+639\d{9})\b", "[REDACTED_PHONE]", result)
    result = re.sub(r"\b(?:grade\s*\d+|\d{1,2}\s*(?:abm|stem|humss|gas)|\d{1,2}[a-z]{2,6}-\d+[a-z]?)\b", "[REDACTED_SECTION]", result, flags=re.I)
    for value in values:
        result = re.sub(re.escape(value), "[REDACTED_METADATA]", result, flags=re.I)
    return re.sub(r"\s+", " ", result).strip()


def build_review_set(seed: int, quotas: dict[str, int]) -> tuple[pd.DataFrame, dict]:
    rng = random.Random(seed)
    seen: set[str] = set()
    candidates: list[dict[str, str]] = []
    manifest_sources = []
    for path in source_files():
        frame = load_frame(path)
        text_columns = find_text_columns(frame)
        manifest_sources.append(
            {
                "file": str(path.relative_to(ROOT)),
                "rows": len(frame),
                "text_columns": text_columns,
            }
        )
        level = school_level(frame, path)
        for _, row in frame.iterrows():
            fingerprint = frame_fingerprint(row)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            values = redaction_values(row, set(text_columns.values()))
            for prompt_type, column in text_columns.items():
                text = redact_text(normalize_cell(row[column]), values)
                if not text or text.lower() in {"nan", "n/a", "na", "none", "[redacted_metadata]"}:
                    continue
                candidates.append({"prompt_type": prompt_type, "school_level": level, "text": text})

    selected = []
    for prompt_type, quota in quotas.items():
        pool = [item for item in candidates if item["prompt_type"] == prompt_type]
        rng.shuffle(pool)
        if prompt_type == "experience":
            jhs_pool = [item for item in pool if item["school_level"] == "JHS"]
            shs_pool = [item for item in pool if item["school_level"] == "SHS"]
            jhs_quota = min(quota // 2, len(jhs_pool))
            selected.extend(jhs_pool[:jhs_quota])
            selected.extend(shs_pool[: quota - jhs_quota])
        else:
            selected.extend(pool[:quota])
    rng.shuffle(selected)
    rows = []
    for index, item in enumerate(selected, start=1):
        row = {"review_id": f"QR-{index:04d}", **item}
        row.update(
            {
                "aspect_labels": "",
                "stance": "",
                "evidence_quality": "",
                "observability": "",
                "actionability": "",
                "safety_status": "",
                "reviewer_confidence": "",
                "review_decision": "",
                "reviewer_notes": "",
            }
        )
        rows.append(row)
    output = pd.DataFrame(
        rows,
        columns=[
            "review_id",
            "prompt_type",
            "school_level",
            "text",
            "aspect_labels",
            "stance",
            "evidence_quality",
            "observability",
            "actionability",
            "safety_status",
            "reviewer_confidence",
            "review_decision",
            "reviewer_notes",
        ],
    )
    metadata = {
        "seed": seed,
        "quotas": quotas,
        "source_file_count": len(manifest_sources),
        "source_manifest": manifest_sources,
        "deduplication": "exact full-row SHA-256 fingerprint before text extraction",
        "review_columns": list(output.columns),
        "excluded_metadata": "student and teacher identifiers, sections, subjects, scores, timestamps",
        "redaction": "known metadata values plus email, URL, phone, and common section patterns",
        "candidate_count_after_deduplication": len(candidates),
        "selected_count": len(output),
    }
    return output, metadata


def main() -> None:
    args = parse_args()
    quotas = {"appreciation": args.appreciation, "suggestion": args.suggestion, "experience": args.experience}
    review, metadata = build_review_set(args.seed, quotas)
    args.output.mkdir(parents=True, exist_ok=True)
    review.to_csv(args.output / "review_set.csv", index=False)
    (args.output / "manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps({"output": str(args.output), "selected_count": len(review), "by_prompt": review["prompt_type"].value_counts().to_dict()}, indent=2))


if __name__ == "__main__":
    main()