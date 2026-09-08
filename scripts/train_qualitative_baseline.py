"""Train a review-seeded qualitative labeling baseline and score the local corpus."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import FeatureUnion, Pipeline

import build_qualitative_review_set as review_builder


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW_SET = ROOT / "exports" / "qualitative_review" / "review_set.csv"
DEFAULT_OUTPUT = ROOT / "exports" / "qualitative_review" / "auto_suggestions.csv"
DEFAULT_MANIFEST = ROOT / "exports" / "qualitative_review" / "auto_suggestions_manifest.json"
ABSTAIN_VALUES = {"", "nan", "n/a", "na", "none", "[redacted_metadata]"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-set", type=Path, default=DEFAULT_REVIEW_SET)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--priority-threshold", type=float, default=0.30)
    return parser.parse_args()


def make_features() -> FeatureUnion:
    return FeatureUnion(
        [
            (
                "word",
                TfidfVectorizer(
                    lowercase=True,
                    ngram_range=(1, 2),
                    min_df=1,
                    sublinear_tf=True,
                ),
            ),
            (
                "character",
                TfidfVectorizer(
                    analyzer="char_wb",
                    lowercase=True,
                    ngram_range=(3, 5),
                    min_df=1,
                    sublinear_tf=True,
                ),
            ),
        ]
    )


def model_pipeline() -> Pipeline:
    return Pipeline(
        [
            ("features", make_features()),
            (
                "classifier",
                LogisticRegression(
                    class_weight="balanced",
                    max_iter=300,
                    random_state=20260908,
                ),
            ),
        ]
    )


def review_training_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path).fillna("")
    included = frame[
        frame["review_decision"].eq("include")
        & frame["aspect_labels"].astype(str).str.strip().ne("")
        & frame["text"].astype(str).str.strip().ne("")
    ].copy()
    included["aspect"] = included["aspect_labels"].astype(str).str.split("|").str[0].str.strip()
    included["stance_label"] = included["stance"].astype(str).str.strip()
    included = included[included["aspect"].ne("")]
    return included


def corpus_comments() -> pd.DataFrame:
    seen: set[str] = set()
    rows: list[dict[str, str]] = []
    for path in review_builder.source_files():
        frame = review_builder.load_frame(path)
        text_columns = review_builder.find_text_columns(frame)
        level = review_builder.school_level(frame, path)
        for _, source_row in frame.iterrows():
            fingerprint = review_builder.frame_fingerprint(source_row)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            values = review_builder.redaction_values(source_row, set(text_columns.values()))
            for prompt_type, column in text_columns.items():
                text = review_builder.redact_text(
                    review_builder.normalize_cell(source_row[column]), values
                )
                if not text or text.lower() in ABSTAIN_VALUES:
                    continue
                rows.append(
                    {
                        "source_fingerprint": fingerprint,
                        "prompt_type": prompt_type,
                        "school_level": level,
                        "text": text,
                    }
                )
    return pd.DataFrame(rows)


def train_and_score(training: pd.DataFrame, corpus: pd.DataFrame, threshold: float) -> tuple[pd.DataFrame, dict]:
    training_text = (
        training["prompt_type"] + " [LEVEL=" + training["school_level"] + "] " + training["text"]
    )
    corpus_text = (
        corpus["prompt_type"] + " [LEVEL=" + corpus["school_level"] + "] " + corpus["text"]
    )
    aspect_model = model_pipeline()
    aspect_model.fit(training_text, training["aspect"])
    stance_training = training[training["stance_label"].isin({"strength", "concern", "mixed", "neutral"})]
    stance_model = model_pipeline()
    stance_model.fit(
        stance_training["text"],
        stance_training["stance_label"],
    )

    aspect_probabilities = aspect_model.predict_proba(corpus_text)
    aspect_indices = aspect_probabilities.argmax(axis=1)
    aspect_labels = aspect_model.classes_[aspect_indices]
    aspect_confidence = aspect_probabilities.max(axis=1)
    stance_probabilities = stance_model.predict_proba(corpus["text"])
    stance_indices = stance_probabilities.argmax(axis=1)
    stance_labels = stance_model.classes_[stance_indices]
    stance_confidence = stance_probabilities.max(axis=1)
    confidence = aspect_confidence * stance_confidence
    priorities = ["high" if value >= threshold else "normal" for value in confidence]

    output = corpus.copy()
    output.insert(0, "auto_review_id", [f"AUTO-{index:07d}" for index in range(1, len(output) + 1)])
    output["aspect"] = aspect_labels
    output["stance"] = stance_labels
    output["aspect_confidence"] = aspect_confidence.round(4)
    output["stance_confidence"] = stance_confidence.round(4)
    output["combined_confidence"] = confidence.round(4)
    output["auto_decision"] = "needs_review"
    output["review_priority"] = priorities
    output["model_status"] = "baseline_suggestion_only"
    output = output[
        [
            "auto_review_id",
            "prompt_type",
            "school_level",
            "text",
            "aspect",
            "stance",
            "aspect_confidence",
            "stance_confidence",
            "combined_confidence",
            "auto_decision",
            "review_priority",
            "model_status",
            "source_fingerprint",
        ]
    ]
    metadata = {
        "training_rows": len(training),
        "training_aspect_counts": dict(Counter(training["aspect"])),
        "training_stance_counts": dict(Counter(stance_training["stance_label"])),
        "scored_rows": len(output),
        "decision_counts": {"needs_review": len(output)},
        "priority_counts": dict(Counter(priorities)),
        "priority_threshold": threshold,
        "features": "word and character TF-IDF",
        "models": "multiclass logistic regression for aspect and stance",
        "label_source": "manually reviewed rows with review_decision=include",
        "intended_use": "reviewer suggestions and descriptive aggregation only",
        "limitations": [
            "No held-out accuracy estimate is reported because the seed is small and sparse.",
            "Predictions below the threshold require human review.",
            "This output is not a teacher score, ranking, or validated measurement.",
        ],
    }
    return output, metadata


def main() -> None:
    args = parse_args()
    training = review_training_frame(args.review_set)
    if training.empty:
        raise SystemExit("No included labeled rows were found in the review set.")
    if training["aspect"].nunique() < 2:
        raise SystemExit("At least two aspect labels are required to train the baseline.")
    corpus = corpus_comments()
    output, metadata = train_and_score(training, corpus, args.priority_threshold)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    output.to_csv(args.output, index=False)
    args.manifest.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
