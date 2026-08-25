"""Student-facing evaluation assignment and submission models."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Sequence


@dataclass(frozen=True)
class StudentProfile:
    id: str
    name: str
    email: str
    school_level: str
    grade_level: int
    strand: str
    section: str
    evaluation_period: str
    student_number: str = ""
    evaluation_closes_at: datetime | None = None


@dataclass(frozen=True)
class TeacherAssignment:
    id: str
    school_level: str
    grade_level: int
    strand: str
    section: str
    subject: str
    teacher_name: str
    teacher_email: str
    evaluation_period: str
    subject_code: str = ""
    is_active: bool = True


@dataclass(frozen=True)
class SubmissionRecord:
    student_id: str
    assignment_id: str
    evaluation_period: str
    submitted_at: datetime


def assignments_for_student(
    student: StudentProfile,
    assignments: Iterable[TeacherAssignment],
) -> tuple[TeacherAssignment, ...]:
    """Return only active assignments authorized for the student's roster record."""

    matches = [
        assignment
        for assignment in assignments
        if assignment.is_active
        and assignment.school_level.casefold() == student.school_level.casefold()
        and assignment.grade_level == student.grade_level
        and assignment.strand.casefold() == student.strand.casefold()
        and assignment.section.casefold() == student.section.casefold()
        and assignment.evaluation_period.casefold() == student.evaluation_period.casefold()
    ]
    return tuple(sorted(matches, key=lambda assignment: assignment.subject.casefold()))


def submitted_assignment_ids(
    student: StudentProfile,
    submissions: Iterable[SubmissionRecord],
) -> frozenset[str]:
    """Return assignment IDs already submitted by this student in the active period."""

    return frozenset(
        submission.assignment_id
        for submission in submissions
        if submission.student_id == student.id
        and submission.evaluation_period.casefold() == student.evaluation_period.casefold()
    )


def pending_assignments(
    assignments: Sequence[TeacherAssignment],
    submitted_ids: Iterable[str],
) -> tuple[TeacherAssignment, ...]:
    submitted = set(submitted_ids)
    return tuple(assignment for assignment in assignments if assignment.id not in submitted)


def evaluation_key(student: StudentProfile, assignment: TeacherAssignment) -> str:
    """Stable key mirrored by the future PostgreSQL uniqueness constraint."""

    return f"{student.id}:{assignment.id}:{student.evaluation_period}".lower()

