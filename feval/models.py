"""Shared data models for faculty evaluation processing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Iterable, Optional, Tuple

import pandas as pd


@dataclass(frozen=True)
class QuestionItem:
    """One survey item and the column names that may identify it in exports."""

    id: str
    text: str
    aliases: Tuple[str, ...] = ()
    required: bool = True
    use_for_rci: bool = True

    @property
    def match_terms(self) -> Tuple[str, ...]:
        return (self.id, self.text, *self.aliases)


@dataclass(frozen=True)
class QuestionBlock:
    """A level-specific evaluation instrument."""

    id: str
    label: str
    faculty_items: Tuple[QuestionItem, ...]
    self_eval_items: Tuple[QuestionItem, ...]
    open_ended_items: Tuple[QuestionItem, ...]
    teacher_aliases: Tuple[str, ...] = (
        "Teacher",
        "Teacher Name",
        "Faculty",
        "Faculty Name",
        "Instructor",
        "Name of Teacher",
        "Subject Teacher",
        "Teacher Evaluated",
    )
    section_aliases: Tuple[str, ...] = ("Section", "Class", "Grade and Section", "Course Section")
    respondent_aliases: Tuple[str, ...] = (
        "ID",
        "Response ID",
        "Email",
        "Respondent",
        "Student ID",
        "Student Email",
    )

    @property
    def all_items(self) -> Tuple[QuestionItem, ...]:
        return self.faculty_items + self.self_eval_items + self.open_ended_items

    @property
    def quantitative_items(self) -> Tuple[QuestionItem, ...]:
        return self.faculty_items + self.self_eval_items

    @property
    def rci_items(self) -> Tuple[QuestionItem, ...]:
        return tuple(item for item in self.self_eval_items if item.use_for_rci)

    @property
    def overall_experience_items(self) -> Tuple[QuestionItem, ...]:
        return tuple(item for item in self.self_eval_items if not item.use_for_rci)


@dataclass
class ColumnMatch:
    """Detected or user-supplied mapping between an item and a data column."""

    item_id: str
    column: Optional[str]
    confidence: str


@dataclass
class NormalizedExport:
    """A SharePoint/MS Forms export normalized into analysis-ready columns."""

    block: QuestionBlock
    raw: pd.DataFrame
    responses: pd.DataFrame
    teacher_column: str
    section_column: Optional[str]
    respondent_column: Optional[str]
    column_map: Dict[str, str]

    @property
    def faculty_columns(self) -> Tuple[str, ...]:
        return tuple(item.id for item in self.block.faculty_items)

    @property
    def self_eval_columns(self) -> Tuple[str, ...]:
        return tuple(item.id for item in self.block.self_eval_items)

    @property
    def rci_columns(self) -> Tuple[str, ...]:
        return tuple(item.id for item in self.block.rci_items)

    @property
    def overall_experience_columns(self) -> Tuple[str, ...]:
        return tuple(item.id for item in self.block.overall_experience_items)

    @property
    def text_columns(self) -> Tuple[str, ...]:
        return tuple(item.id for item in self.block.open_ended_items)

    @property
    def quantitative_columns(self) -> Tuple[str, ...]:
        return self.faculty_columns + self.self_eval_columns

    def present_columns(self, columns: Iterable[str]) -> Tuple[str, ...]:
        return tuple(column for column in columns if column in self.responses.columns)
