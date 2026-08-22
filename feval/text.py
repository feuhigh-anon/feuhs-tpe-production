"""Semantic open-ended response aggregation."""

from __future__ import annotations

import re
import json
from collections import Counter
from typing import Iterable, Optional, Sequence

import pandas as pd

from feval.models import NormalizedExport


SEMANTIC_FRAMES = {
    "clarity of explanations and instructions": (
        "clear",
        "clarify",
        "explain",
        "instruction",
        "objective",
        "understand",
        "example",
        "simple",
    ),
    "classroom management and learning climate": (
        "manage",
        "behavior",
        "behave",
        "discipline",
        "listen",
        "order",
        "safe",
        "respect",
    ),
    "teaching strategies and class activities": (
        "strateg",
        "activity",
        "activities",
        "interactive",
        "engage",
        "discussion",
        "participat",
        "lesson",
    ),
    "student support and consultation": (
        "help",
        "support",
        "consult",
        "available",
        "approachable",
        "question",
        "patient",
        "guide",
    ),
    "feedback, assessment, and grading": (
        "feedback",
        "graded",
        "grade",
        "assessment",
        "test",
        "quiz",
        "return",
        "deadline",
    ),
    "learning materials and resources": (
        "material",
        "module",
        "resource",
        "readily",
        "accessible",
        "presentation",
        "slides",
        "handout",
    ),
    "timeliness and online responsiveness": (
        "time",
        "punctual",
        "late",
        "reply",
        "respond",
        "message",
        "online",
        "asynchronous",
    ),
    "pacing, workload, and difficulty": (
        "fast",
        "slow",
        "pace",
        "pacing",
        "difficult",
        "hard",
        "workload",
        "pressure",
    ),
    "motivation and confidence in learning": (
        "motivat",
        "confidence",
        "interest",
        "growth",
        "improve",
        "better",
        "learn",
        "excel",
    ),
}

STOPWORDS = {
    "about",
    "also",
    "and",
    "are",
    "because",
    "but",
    "can",
    "class",
    "for",
    "from",
    "has",
    "have",
    "her",
    "his",
    "how",
    "into",
    "our",
    "she",
    "sir",
    "student",
    "students",
    "teacher",
    "that",
    "the",
    "their",
    "them",
    "then",
    "there",
    "they",
    "this",
    "was",
    "with",
    "you",
}

SUPPORT_CUES = {
    "appreciate",
    "approachable",
    "clear",
    "effective",
    "encourage",
    "engaging",
    "enjoy",
    "fair",
    "fun",
    "helpful",
    "kind",
    "learn",
    "patient",
    "prepared",
    "respect",
    "support",
    "understand",
}

CONCERN_CUES = {
    "boring",
    "confusing",
    "delayed",
    "difficult",
    "hard",
    "late",
    "lacking",
    "need",
    "needs",
    "pressure",
    "rushed",
    "slow",
    "unclear",
    "unfair",
    "unavailable",
    "unresponsive",
}


FRAME_SHORT_LABELS: dict[str, str] = {
    "clarity of explanations and instructions": "clear explanations",
    "classroom management and learning climate": "class management",
    "teaching strategies and class activities": "teaching strategies",
    "student support and consultation": "student support",
    "feedback, assessment, and grading": "feedback & grading",
    "learning materials and resources": "learning materials",
    "timeliness and online responsiveness": "timeliness",
    "pacing, workload, and difficulty": "pacing & workload",
    "motivation and confidence in learning": "student motivation",
}

PROMPT_META: dict[str, dict] = {
    "shs": {
        "oe1": {
            "prompt": "What strategies and practices did you appreciate the most about your teacher?",
            "type": "appreciated",
            "polarity": "support",
        },
        "oe2": {
            "prompt": "What are some constructive suggestions you can give to help them handle students or teach better?",
            "type": "suggestion",
            "polarity": "concern",
        },
        "oe3": {
            "prompt": "Overall how was your learning experience with your teacher?",
            "type": "experience",
            "polarity": "mixed",
        },
    },
    "jhs": {
        "oe1": {
            "prompt": "What did you like the most about your teacher's way of teaching?",
            "type": "appreciated",
            "polarity": "support",
        },
        "oe2": {
            "prompt": "How do you think your teacher can be better at helping students like you?",
            "type": "suggestion",
            "polarity": "concern",
        },
        "oe3": {
            "prompt": "Overall, how was your learning experience with your teacher?",
            "type": "experience",
            "polarity": "mixed",
        },
    },
}

WORD_COUNT_FLAG_THRESHOLDS = {
    "appreciated": 80,
    "suggestion": 60,
    "experience": 100,
}


def analyze_open_ended(
    normalized: NormalizedExport,
    top_n: int = 5,
    block_id: str = "shs",
) -> pd.DataFrame:
    """
    Aggregate qualitative feedback into phrase summaries and evidence tables.

    Parameters
    ----------
    normalized : NormalizedExport
        SharePoint/MS Forms export normalized to canonical column names.
    top_n : int
        Maximum number of semantic frames to retain in the summary field.
    block_id : str
        Question-block identifier, usually "shs" or "jhs", used to select
        prompt labels and prompt polarity metadata.

    Returns
    -------
    pandas.DataFrame
        Teacher-level qualitative report with phrase summaries, deprecated
        statement aliases, frame-count JSON fields, representative evidence,
        qualitative evidence index, and verbose-response diagnostics.

    Methodological note
    -------------------
    The function uses semantic aspect detection rather than generic sentiment.
    It preserves all comments in aggregate counts and deliberately selects
    representative evidence that can include concerns when concerns exist.
    """

    text_columns = normalized.present_columns(normalized.text_columns)
    empty_columns = [
        "teacher",
        "comment_count",
        "semantic_themes",
        "appreciated_phrases",
        "suggestion_phrases",
        "experience_phrases",
        "appreciated_statement",
        "suggestion_statement",
        "experience_statement",
        "appreciated_frame_counts",
        "suggestion_frame_counts",
        "experience_frame_counts",
        "qualitative_evidence_raw",
        "qualitative_evidence_confidence",
        "qualitative_score_1_5",
        "qualitative_summary",
        "representative_evidence",
        "verbose_flag_count",
        "verbose_flag_detail",
    ]
    if not text_columns:
        return pd.DataFrame(columns=empty_columns)

    rows = []
    for teacher, group in normalized.responses.groupby("teacher", dropna=False):
        appreciated = _collect_comments(group, text_columns[0] if len(text_columns) > 0 else None)
        suggestions = _collect_comments(group, text_columns[1] if len(text_columns) > 1 else None)
        experience = _collect_comments(group, text_columns[2] if len(text_columns) > 2 else None)
        all_comments = appreciated + suggestions + experience

        appreciated_counts = semantic_frame_counts(appreciated)
        suggestion_counts = semantic_frame_counts(suggestions)
        experience_counts = semantic_frame_counts(experience)
        frame_counts = appreciated_counts + suggestion_counts + experience_counts
        frames = [frame for frame, _ in frame_counts.most_common(top_n)]
        appreciated_phrases = phrase_summary_for_prompt(
            "appreciated",
            appreciated,
            frame_counts=appreciated_counts,
            total_responses=len(appreciated),
        )
        suggestion_phrases = phrase_summary_for_prompt(
            "suggestion",
            suggestions,
            frame_counts=suggestion_counts,
            total_responses=len(suggestions),
        )
        experience_phrases = phrase_summary_for_prompt(
            "experience",
            experience,
            frame_counts=experience_counts,
            total_responses=len(experience),
        )
        rci_cols = normalized.present_columns(normalized.rci_columns)
        if rci_cols:
            self_means = group.loc[:, rci_cols].mean(axis=1, skipna=True).dropna().tolist()
        else:
            self_means = None
        evidence_raw = qualitative_evidence_index(
            appreciated,
            suggestions,
            experience,
            self_eval_means=self_means,
            n_respondents=len(group),
        )
        evidence_confidence = qualitative_evidence_confidence(all_comments)
        oe1_verbose_flags = flag_verbose_responses(appreciated, "appreciated")
        oe2_verbose_flags = flag_verbose_responses(suggestions, "suggestion")
        oe3_verbose_flags = flag_verbose_responses(experience, "experience")
        verbose_flags = []
        for prompt_key, flags in (("oe1", oe1_verbose_flags), ("oe2", oe2_verbose_flags), ("oe3", oe3_verbose_flags)):
            for flag in flags:
                verbose_flags.append({"prompt": prompt_key, **flag})

        rows.append(
            {
                "teacher": teacher,
                "comment_count": len(all_comments),
                "semantic_themes": "; ".join(FRAME_SHORT_LABELS.get(frame, frame) for frame in frames)
                if frames
                else "no dominant theme detected",
                "appreciated_phrases": appreciated_phrases,
                "suggestion_phrases": suggestion_phrases,
                "experience_phrases": experience_phrases,
                "appreciated_statement": appreciated_phrases,
                "suggestion_statement": suggestion_phrases,
                "experience_statement": experience_phrases,
                "appreciated_frame_counts": _frame_counts_json(appreciated_counts),
                "suggestion_frame_counts": _frame_counts_json(suggestion_counts),
                "experience_frame_counts": _frame_counts_json(experience_counts),
                "qualitative_evidence_raw": round(evidence_raw, 4),
                "qualitative_evidence_confidence": round(evidence_confidence, 4),
                "qualitative_score_1_5": round(max(1.0, min(5.0, 3.0 + evidence_raw)), 4),
                "qualitative_summary": " | ".join(
                    [
                        appreciated_phrases,
                        suggestion_phrases,
                        experience_phrases,
                    ]
                ),
                "representative_evidence": representative_evidence(all_comments, frames),
                "verbose_flag_count": len(verbose_flags),
                "verbose_flag_detail": json.dumps(verbose_flags, ensure_ascii=True),
            }
        )
    return pd.DataFrame(rows, columns=empty_columns)


def qualitative_evidence_index(
    appreciated: Sequence[str],
    suggestions: Sequence[str],
    experience: Sequence[str],
    self_eval_means: Sequence[float] | None = None,
    n_respondents: int | None = None,
) -> float:
    """
    Compute a bounded semantic evidence index in the range [-2.0, 2.0].

    Parameters
    ----------
    appreciated : Sequence[str]
        Responses to the appreciation prompt.
    suggestions : Sequence[str]
        Responses to the constructive-suggestion prompt.
    experience : Sequence[str]
        Responses to the overall-experience prompt.
    self_eval_means : Sequence[float] | None
        Optional respondent-level self-evaluation means on the 1-5 scale.
        When provided, the mean modulates concern evidence only.
    n_respondents : int | None
        Optional respondent count retained for audit readability; the current
        formula uses comment counts and self-evaluation means directly.

    Returns
    -------
    float
        Semantic evidence index where positive values indicate stronger
        support evidence and negative values indicate stronger concern evidence.

    Methodological note
    -------------------
    Concern signals from suggestion and experience comments are discounted
    when the respondent cohort reports low self-evaluation, but never below
    half weight. Support evidence is not discounted. This follows the task's
    rater-credibility rationale and Nulty's (2008) caution about interpreting
    online student-response evidence.
    """

    _ = n_respondents
    appreciated_support = _semantic_density(appreciated, SUPPORT_CUES)
    experience_support = _semantic_density(experience, SUPPORT_CUES)
    framed_appreciation = _frame_density(appreciated)

    suggestion_concern = _semantic_density(suggestions, CONCERN_CUES)
    experience_concern = _semantic_density(experience, CONCERN_CUES)

    if self_eval_means:
        clean_means = [float(value) for value in self_eval_means if pd.notna(value)]
        if clean_means:
            credibility = sum(clean_means) / (len(clean_means) * 5.0)
            credibility = max(0.0, min(1.0, credibility))
            discount = 0.5 + 0.5 * credibility
        else:
            discount = 1.0
    else:
        discount = 1.0

    effective_suggestion_concern = suggestion_concern * discount
    effective_experience_concern = experience_concern * discount
    support = (appreciated_support + experience_support + framed_appreciation) / 3.0
    concern = (effective_suggestion_concern + effective_experience_concern) / 2.0

    raw = support - concern
    return max(-2.0, min(2.0, raw))


def qualitative_evidence_confidence(comments: Sequence[str]) -> float:
    """Confidence grows with comment volume but remains bounded."""

    if not comments:
        return 0.0
    return min(1.0, len(comments) / 30.0)


def flag_verbose_responses(
    comments: Sequence[str],
    prompt_type: str,
    threshold: int | None = None,
) -> list[dict]:
    """
    Flag individual qualitative responses above a prompt-specific word limit.

    Parameters
    ----------
    comments : Sequence[str]
        Raw response strings for one open-ended prompt.
    prompt_type : str
        Prompt family: "appreciated", "suggestion", or "experience".
    threshold : int | None
        Optional word-count threshold. When omitted, the function uses
        WORD_COUNT_FLAG_THRESHOLDS for the prompt type.

    Returns
    -------
    list[dict]
        Flag dictionaries containing response index, word count, threshold,
        prompt type, and a review snippet.

    Methodological note
    -------------------
    Long qualitative responses can reflect high engagement or emotionally
    motivated grievance writing. Both warrant human review, but neither is
    automatically positive or negative. This informational flag follows the
    task's references to Sproull and Kiesler (1986) and Nulty (2008).
    """

    threshold = threshold or WORD_COUNT_FLAG_THRESHOLDS.get(prompt_type, 80)
    flagged = []
    for index, comment in enumerate(comments):
        words = len(tokenize(comment))
        if words > threshold:
            flagged.append(
                {
                    "response_index": index,
                    "word_count": words,
                    "threshold": threshold,
                    "prompt_type": prompt_type,
                    "snippet": clean_snippet(comment, limit=120),
                }
            )
    return flagged


def phrase_summary_for_prompt(
    prompt_type: str,
    comments: Sequence[str],
    frame_counts: Counter | None = None,
    total_responses: int | None = None,
    min_pct: float = 0.15,
) -> str:
    """
    Produce a compact phrase summarizing dominant themes for one prompt.

    Parameters
    ----------
    prompt_type : str
        Prompt family: "appreciated", "suggestion", or "experience".
    comments : Sequence[str]
        Raw response strings for the prompt.
    frame_counts : Counter | None
        Optional precomputed semantic-frame counts.
    total_responses : int | None
        Percentage denominator. Defaults to len(comments).
    min_pct : float
        Minimum proportion required for a frame to appear in the phrase.

    Returns
    -------
    str
        Phrase string without terminal punctuation, using middle-dot
        separators and short semantic-frame labels.

    Methodological note
    -------------------
    Phrases are designed for compact PDF/table cells. The method reports
    recurring instructional aspects, not sentiment labels, so a prompt's
    context remains visible in the report structure.
    """

    _ = prompt_type
    if frame_counts is None:
        frame_counts = semantic_frame_counts(comments)
    total = total_responses if total_responses is not None else len(comments)
    total = max(int(total), 0)
    if total > 0:
        qualifying = [(frame, count) for frame, count in frame_counts.most_common() if count / total >= min_pct]
    else:
        qualifying = []

    if qualifying:
        labels = []
        for index, (frame, count) in enumerate(qualifying):
            label = FRAME_SHORT_LABELS.get(frame, frame)
            if index == 0 and total > 0 and count / total >= 0.30:
                label = f"{label} ({round(count / total * 100):.0f}%)"
            labels.append(label)
        return " · ".join(labels)

    terms = top_terms(comments, top_n=4)
    if terms:
        return " · ".join(terms)
    return "no dominant theme detected"


def _frame_counts_json(frame_counts: Counter) -> str:
    """
    Serialize semantic frame counts with short labels for report tables.

    Parameters
    ----------
    frame_counts : Counter
        Counts keyed by long semantic-frame name.

    Returns
    -------
    str
        JSON object string sorted by descending count and using
        FRAME_SHORT_LABELS keys.

    Methodological note
    -------------------
    Count tables preserve the distribution of observed response themes rather
    than relying only on a single generated summary phrase.
    """

    ordered = {
        FRAME_SHORT_LABELS.get(frame, frame): int(count)
        for frame, count in frame_counts.most_common()
        if count > 0
    }
    return json.dumps(ordered, ensure_ascii=True)


def semantic_frame_counts(texts: Iterable[str]) -> Counter[str]:
    """Count instructional semantic frames found in the supplied comments."""

    counts: Counter[str] = Counter()
    for text in texts:
        for frame in matched_semantic_frames(text):
            counts[frame] += 1
    return counts


def matched_semantic_frames(text: str) -> list[str]:
    normalized = normalize_text(text)
    tokens = set(tokenize(normalized))
    matches = []
    for frame, cues in SEMANTIC_FRAMES.items():
        if any(_cue_matches(cue, normalized, tokens) for cue in cues):
            matches.append(frame)
    return matches


def representative_evidence(comments: Sequence[str], frames: Sequence[str], max_items: int = 3) -> str:
    """
    Select snippets that span the qualitative response distribution.

    Parameters
    ----------
    comments : Sequence[str]
        Raw comments from all open-ended prompts for one teacher.
    frames : Sequence[str]
        Semantic frames ranked by frequency, usually from
        semantic_frame_counts(...).most_common().
    max_items : int
        Maximum number of snippets to return.

    Returns
    -------
    str
        Cleaned snippets joined by " | ".

    Methodological note
    -------------------
    Selection prioritizes the highest-frequency frame, then a concern-bearing
    comment when one exists, then the next unrepresented frame or first unused
    comment. This reduces cherry-picking by ensuring critical feedback appears
    when present even if it does not dominate the distribution.
    """

    if not comments:
        return ""

    selected: list[str] = []
    selected_comments: set[int] = set()

    def add_comment(index: int) -> bool:
        snippet = clean_snippet(comments[index])
        if snippet and snippet not in selected:
            selected.append(snippet)
            selected_comments.add(index)
            return True
        return False

    def first_matching_frame(frame: str, exclude_selected: bool = True) -> Optional[int]:
        cues = SEMANTIC_FRAMES.get(frame, ())
        for index, comment in enumerate(comments):
            if exclude_selected and index in selected_comments:
                continue
            normalized = normalize_text(comment)
            tokens = set(tokenize(normalized))
            if any(_cue_matches(cue, normalized, tokens) for cue in cues):
                return index
        return None

    def first_concern(exclude_selected: bool = True) -> Optional[int]:
        for index, comment in enumerate(comments):
            if exclude_selected and index in selected_comments:
                continue
            normalized = normalize_text(comment)
            tokens = set(tokenize(normalized))
            if any(_cue_matches(cue, normalized, tokens) for cue in CONCERN_CUES):
                return index
        return None

    if frames:
        first_index = first_matching_frame(frames[0])
        if first_index is not None:
            add_comment(first_index)

    if len(selected) < max_items:
        concern_index = first_concern()
        if concern_index is not None:
            add_comment(concern_index)
        else:
            for frame in frames[1:]:
                frame_index = first_matching_frame(frame)
                if frame_index is not None and add_comment(frame_index):
                    break

    if len(selected) < max_items:
        for frame in frames[1:]:
            frame_index = first_matching_frame(frame)
            if frame_index is not None and add_comment(frame_index):
                break

    if len(selected) < max_items:
        for index, _comment in enumerate(comments):
            if index not in selected_comments and add_comment(index):
                break

    return " | ".join(snippet for snippet in selected[:max_items] if snippet)


def top_terms(texts: Iterable[str], top_n: int = 8) -> list[str]:
    counter: Counter[str] = Counter()
    for text in texts:
        counter.update(token for token in tokenize(text) if token not in STOPWORDS and len(token) > 2)
    return [term for term, _ in counter.most_common(top_n)]


def human_join(items: Sequence[str]) -> str:
    clean_items = [item for item in items if item]
    if not clean_items:
        return ""
    if len(clean_items) == 1:
        return clean_items[0]
    if len(clean_items) == 2:
        return f"{clean_items[0]} and {clean_items[1]}"
    return f"{', '.join(clean_items[:-1])}, and {clean_items[-1]}"


def clean_snippet(text: str, limit: int = 160) -> str:
    snippet = re.sub(r"\s+", " ", str(text)).strip()
    if len(snippet) <= limit:
        return snippet
    return snippet[: limit - 3].rstrip() + "..."


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", str(text).lower()).strip()


def is_substantive_comment(value: object) -> bool:
    """Return whether a required qualitative response contains actual feedback."""

    normalized = re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()
    return bool(normalized) and normalized not in {"n a", "na", "not applicable"}


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-zA-Z][a-zA-Z'-]*", str(text).lower())


def _collect_comments(group: pd.DataFrame, column: Optional[str]) -> list[str]:
    if not column or column not in group.columns:
        return []
    return [
        str(value).strip()
        for value in group[column].dropna()
        if is_substantive_comment(value)
    ]


def _cue_matches(cue: str, normalized_text: str, tokens: set[str]) -> bool:
    if " " in cue:
        return cue in normalized_text
    return any(token == cue or token.startswith(cue) for token in tokens)


def _semantic_density(comments: Sequence[str], cues: set[str]) -> float:
    if not comments:
        return 0.0
    matches = 0
    for comment in comments:
        normalized = normalize_text(comment)
        tokens = set(tokenize(normalized))
        if any(_cue_matches(cue, normalized, tokens) for cue in cues):
            matches += 1
    return matches / len(comments)


def _frame_density(comments: Sequence[str]) -> float:
    if not comments:
        return 0.0
    matches = sum(1 for comment in comments if matched_semantic_frames(comment))
    return matches / len(comments)
