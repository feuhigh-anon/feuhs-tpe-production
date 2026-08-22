"""Curated mock records for the student frontend prototype."""

from __future__ import annotations

from datetime import datetime

from feval.student_portal import StudentProfile, SubmissionRecord, TeacherAssignment


DEMO_STUDENT = StudentProfile(
    id="DEMO-STUDENT-001",
    name="Demo Student",
    email="demo.student@example.invalid",
    school_level="SHS",
    grade_level=11,
    strand="STEM",
    section="11STEM-DEMO",
    evaluation_period="Q2 2026",
)


DEMO_ASSIGNMENTS = (
    TeacherAssignment(
        id="DEMO-Q2-2026-STEM-CALC",
        school_level="SHS",
        grade_level=11,
        strand="STEM",
        section="11STEM-DEMO",
        subject="Basic Calculus",
        teacher_name="Teacher Alpha",
        teacher_email="teacher.alpha@example.invalid",
        evaluation_period="Q2 2026",
    ),
    TeacherAssignment(
        id="DEMO-Q2-2026-STEM-EARTH",
        school_level="SHS",
        grade_level=11,
        strand="STEM",
        section="11STEM-DEMO",
        subject="Earth Science",
        teacher_name="Teacher Beta",
        teacher_email="teacher.beta@example.invalid",
        evaluation_period="Q2 2026",
    ),
    TeacherAssignment(
        id="DEMO-Q2-2026-STEM-EMTECH",
        school_level="SHS",
        grade_level=11,
        strand="STEM",
        section="11STEM-DEMO",
        subject="Empowerment Technologies",
        teacher_name="Teacher Gamma",
        teacher_email="teacher.gamma@example.invalid",
        evaluation_period="Q2 2026",
    ),
    TeacherAssignment(
        id="DEMO-Q2-2026-STEM-EAPP",
        school_level="SHS",
        grade_level=11,
        strand="STEM",
        section="11STEM-DEMO",
        subject="English for Academic and Professional Purposes",
        teacher_name="Teacher Delta",
        teacher_email="teacher.delta@example.invalid",
        evaluation_period="Q2 2026",
    ),
    TeacherAssignment(
        id="DEMO-Q2-2026-STEM-MIL",
        school_level="SHS",
        grade_level=11,
        strand="STEM",
        section="11STEM-DEMO",
        subject="Media and Information Literacy",
        teacher_name="Teacher Epsilon",
        teacher_email="teacher.epsilon@example.invalid",
        evaluation_period="Q2 2026",
    ),
    TeacherAssignment(
        id="DEMO-Q2-2026-STEM-PR1",
        school_level="SHS",
        grade_level=11,
        strand="STEM",
        section="11STEM-DEMO",
        subject="Practical Research 1",
        teacher_name="Teacher Zeta",
        teacher_email="teacher.zeta@example.invalid",
        evaluation_period="Q2 2026",
    ),
    TeacherAssignment(
        id="DEMO-Q2-2026-ABM-STAT",
        school_level="SHS",
        grade_level=11,
        strand="ABM",
        section="11ABM-DEMO",
        subject="Statistics and Probability",
        teacher_name="Teacher Eta",
        teacher_email="teacher.eta@example.invalid",
        evaluation_period="Q2 2026",
    ),
)


DEMO_SUBMISSIONS = (
    SubmissionRecord(
        student_id=DEMO_STUDENT.id,
        assignment_id="DEMO-Q2-2026-STEM-EAPP",
        evaluation_period="Q2 2026",
        submitted_at=datetime(2026, 5, 18, 9, 10),
    ),
    SubmissionRecord(
        student_id=DEMO_STUDENT.id,
        assignment_id="DEMO-Q2-2026-STEM-MIL",
        evaluation_period="Q2 2026",
        submitted_at=datetime(2026, 5, 19, 14, 35),
    ),
)
