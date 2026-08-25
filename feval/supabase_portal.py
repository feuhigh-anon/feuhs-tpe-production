"""Authenticated Supabase data access for the student evaluation portal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

from supabase import Client, create_client

from feval.models import QuestionBlock, QuestionItem
from feval.student_portal import StudentProfile, SubmissionRecord, TeacherAssignment


class PortalConfigurationError(RuntimeError):
    """Raised when required Supabase connection settings are unsafe or incomplete."""


class PortalAuthenticationError(RuntimeError):
    """Raised when an authenticated student session cannot be established."""


class PortalDataError(RuntimeError):
    """Raised when the authenticated roster context is incomplete or inconsistent."""


class PortalSubmissionError(RuntimeError):
    """Raised when the database rejects an evaluation submission."""


@dataclass(frozen=True)
class SupabaseSettings:
    url: str
    publishable_key: str

    def validate(self) -> None:
        if not self.url.startswith("https://") or ".supabase.co" not in self.url:
            raise PortalConfigurationError("SUPABASE_URL must be a hosted Supabase HTTPS URL.")
        if not self.publishable_key:
            raise PortalConfigurationError("SUPABASE_PUBLISHABLE_KEY is required.")
        if self.publishable_key.startswith("sb_secret_"):
            raise PortalConfigurationError("A Supabase secret key cannot be used by the student app.")


@dataclass(frozen=True)
class AuthSession:
    access_token: str
    refresh_token: str
    user_id: str
    email: str


@dataclass(frozen=True)
class PortalSnapshot:
    student: StudentProfile
    assignments: tuple[TeacherAssignment, ...]
    submissions: tuple[SubmissionRecord, ...]
    question_block: QuestionBlock


def new_client(settings: SupabaseSettings) -> Client:
    settings.validate()
    return create_client(settings.url, settings.publishable_key)


def sign_in_with_password(
    settings: SupabaseSettings,
    email: str,
    password: str,
) -> tuple[Client, AuthSession]:
    client = new_client(settings)
    try:
        response = client.auth.sign_in_with_password(
            {"email": email.strip(), "password": password}
        )
    except Exception as exc:
        raise PortalAuthenticationError("Sign-in failed.") from exc
    return client, _auth_session_from_response(response)


def restore_session(
    settings: SupabaseSettings,
    session: AuthSession,
) -> tuple[Client, AuthSession]:
    client = new_client(settings)
    try:
        response = client.auth.set_session(session.access_token, session.refresh_token)
    except Exception as exc:
        raise PortalAuthenticationError("Your session has expired. Please sign in again.") from exc
    return client, _auth_session_from_response(response)


def sign_out(client: Client) -> None:
    try:
        client.auth.sign_out()
    except Exception:
        # Local state is still cleared by the caller if remote revocation is unavailable.
        pass


def load_portal_snapshot(
    client: Client,
    session: AuthSession,
    *,
    now: datetime | None = None,
) -> PortalSnapshot:
    current_time = now or datetime.now(timezone.utc)
    profile = _one(
        client.table("profiles")
        .select("id,display_name,role,is_active")
        .eq("id", session.user_id)
        .limit(1)
        .execute(),
        "No active student profile was found.",
    )
    if profile.get("role") != "student" or not profile.get("is_active", False):
        raise PortalDataError("This account is not an active student account.")

    student_row = _one(
        client.table("students")
        .select("profile_id,student_number,section_id")
        .eq("profile_id", session.user_id)
        .limit(1)
        .execute(),
        "This account has not been assigned to a student roster.",
    )
    section = _one(
        client.table("sections")
        .select("id,code,school_level,grade_level,strand,is_active")
        .eq("id", student_row["section_id"])
        .limit(1)
        .execute(),
        "The assigned section is unavailable.",
    )
    if not section.get("is_active", False):
        raise PortalDataError("The assigned section is inactive.")

    links = _rows(
        client.table("student_assignments")
        .select("teaching_assignment_id,is_active")
        .eq("student_id", session.user_id)
        .eq("is_active", True)
        .execute()
    )
    assignment_ids = [int(row["teaching_assignment_id"]) for row in links]
    if not assignment_ids:
        raise PortalDataError("No teacher assignments are available for this account.")

    teaching_rows = _rows(
        client.table("teaching_assignments")
        .select("id,evaluation_period_id,section_id,subject_id,teacher_id,is_active")
        .in_("id", assignment_ids)
        .eq("is_active", True)
        .execute()
    )
    teaching_rows = [
        row for row in teaching_rows if int(row["section_id"]) == int(section["id"])
    ]
    if not teaching_rows:
        raise PortalDataError("No active assignments match the student's roster section.")

    period_ids = sorted({int(row["evaluation_period_id"]) for row in teaching_rows})
    periods = _rows(
        client.table("evaluation_periods")
        .select("id,code,status,opens_at,closes_at")
        .in_("id", period_ids)
        .execute()
    )
    open_periods = [row for row in periods if _period_is_open(row, current_time)]
    if not open_periods:
        raise PortalDataError("There is no open evaluation period for this account.")
    active_period = min(open_periods, key=lambda row: _parse_datetime(row["closes_at"]))
    active_period_id = int(active_period["id"])
    teaching_rows = [
        row for row in teaching_rows if int(row["evaluation_period_id"]) == active_period_id
    ]

    subject_ids = sorted({int(row["subject_id"]) for row in teaching_rows})
    teacher_ids = sorted({int(row["teacher_id"]) for row in teaching_rows})
    subjects = {
        int(row["id"]): row
        for row in _rows(
            client.table("subjects")
                .select("id,code,name,is_active")
            .in_("id", subject_ids)
            .execute()
        )
    }
    teachers = {
        int(row["id"]): row
        for row in _rows(
            client.table("teachers")
            .select("id,display_name,email,is_active")
            .in_("id", teacher_ids)
            .execute()
        )
    }

    assignments = []
    for row in teaching_rows:
        subject = subjects.get(int(row["subject_id"]))
        teacher = teachers.get(int(row["teacher_id"]))
        if not subject or not teacher or not subject.get("is_active") or not teacher.get("is_active"):
            continue
        assignments.append(
            TeacherAssignment(
                id=str(row["id"]),
                school_level=str(section["school_level"]),
                grade_level=int(section["grade_level"]),
                strand=str(section.get("strand") or ""),
                section=str(section["code"]),
                subject=str(subject["name"]),
                subject_code=str(subject.get("code") or ""),
                teacher_name=str(teacher["display_name"]),
                teacher_email=str(teacher.get("email") or ""),
                evaluation_period=str(active_period["code"]),
                is_active=True,
            )
        )
    if not assignments:
        raise PortalDataError("The authorized assignments are incomplete or inactive.")

    instrument = _one(
        client.table("evaluation_period_instruments")
        .select("question_bank_id")
        .eq("evaluation_period_id", active_period_id)
        .eq("school_level", section["school_level"])
        .limit(1)
        .execute(),
        "No questionnaire is assigned to the current evaluation period.",
    )
    question_bank_id = int(instrument["question_bank_id"])
    question_rows = _rows(
        client.table("question_items")
        .select(
            "id,stable_key,section_key,prompt,response_type,position,is_required,use_for_rci"
        )
        .eq("question_bank_id", question_bank_id)
        .execute()
    )
    question_block = question_block_from_rows(
        str(section["school_level"]), question_bank_id, question_rows
    )

    submission_rows = _rows(
        client.table("evaluation_submissions")
        .select("teaching_assignment_id,submitted_at,evaluation_period_id")
        .eq("student_id", session.user_id)
        .eq("evaluation_period_id", active_period_id)
        .execute()
    )
    submissions = tuple(
        SubmissionRecord(
            student_id=session.user_id,
            assignment_id=str(row["teaching_assignment_id"]),
            evaluation_period=str(active_period["code"]),
            submitted_at=_parse_datetime(row["submitted_at"]),
        )
        for row in submission_rows
    )
    student = StudentProfile(
        id=session.user_id,
        name=str(profile["display_name"]),
        email=session.email,
        school_level=str(section["school_level"]),
        grade_level=int(section["grade_level"]),
        strand=str(section.get("strand") or ""),
        section=str(section["code"]),
        evaluation_period=str(active_period["code"]),
        student_number=str(student_row["student_number"]),
        evaluation_closes_at=_parse_datetime(active_period["closes_at"]),
    )
    return PortalSnapshot(
        student=student,
        assignments=tuple(sorted(assignments, key=lambda item: item.subject.casefold())),
        submissions=submissions,
        question_block=question_block,
    )


def question_block_from_rows(
    school_level: str,
    question_bank_id: int,
    rows: Sequence[Mapping[str, Any]],
) -> QuestionBlock:
    grouped: dict[str, list[QuestionItem]] = {
        "teacher_performance": [],
        "student_experience": [],
        "student_self_evaluation": [],
        "qualitative_feedback": [],
    }
    for row in sorted(rows, key=lambda item: (str(item["section_key"]), int(item["position"]))):
        section_key = str(row["section_key"])
        if section_key not in grouped:
            raise PortalDataError(f"Unsupported questionnaire section: {section_key}")
        grouped[section_key].append(
            QuestionItem(
                id=str(row["id"]),
                text=str(row["prompt"]),
                aliases=(str(row["stable_key"]),),
                required=bool(row["is_required"]),
                use_for_rci=bool(row["use_for_rci"]),
            )
        )

    missing_sections = [key for key, items in grouped.items() if not items]
    if missing_sections:
        raise PortalDataError(
            "The active questionnaire is missing sections: " + ", ".join(missing_sections)
        )

    return QuestionBlock(
        id=f"{school_level.lower()}-db-{question_bank_id}",
        label=f"{school_level} questionnaire",
        faculty_items=tuple(grouped["teacher_performance"]),
        self_eval_items=tuple(
            grouped["student_experience"] + grouped["student_self_evaluation"]
        ),
        open_ended_items=tuple(grouped["qualitative_feedback"]),
    )


def response_payload(
    question_block: QuestionBlock,
    assignment_id: str,
    answers: Mapping[str, Any],
    comments: Mapping[str, Any],
) -> list[dict[str, Any]]:
    payload = []
    for item in question_block.quantitative_items:
        key = f"rating_{assignment_id}_{item.id}"
        value = answers.get(key)
        if value is None:
            if item.required:
                raise PortalSubmissionError("Every required rating must be completed before submission.")
            continue
        payload.append(
            {
                "question_item_id": _database_question_id(item.id),
                "rating_value": int(value),
                "text_value": None,
            }
        )
    for item in question_block.open_ended_items:
        key = f"comment_{assignment_id}_{item.id}"
        value = str(comments.get(key, "")).strip()
        if not value:
            if item.required:
                raise PortalSubmissionError("Every required qualitative response must be completed.")
            continue
        payload.append(
            {
                "question_item_id": _database_question_id(item.id),
                "rating_value": None,
                "text_value": value,
            }
        )
    return payload


def submit_evaluation(
    client: Client,
    teaching_assignment_id: str,
    responses: Sequence[Mapping[str, Any]],
    *,
    client_version: str,
) -> int:
    try:
        result = client.rpc(
            "submit_evaluation",
            {
                "p_teaching_assignment_id": int(teaching_assignment_id),
                "p_responses": list(responses),
                "p_client_version": client_version,
            },
        ).execute()
    except Exception as exc:
        raise PortalSubmissionError(
            "The evaluation could not be accepted. It may already be submitted or the period may be closed."
        ) from exc
    data = result.data
    if isinstance(data, list):
        data = data[0] if data else None
    if data is None:
        raise PortalSubmissionError("The database did not return a submission identifier.")
    return int(data)


def _auth_session_from_response(response: Any) -> AuthSession:
    session = getattr(response, "session", None)
    user = getattr(response, "user", None)
    if session is None or user is None or not getattr(user, "id", None):
        raise PortalAuthenticationError("Supabase did not return an authenticated session.")
    return AuthSession(
        access_token=str(session.access_token),
        refresh_token=str(session.refresh_token),
        user_id=str(user.id),
        email=str(getattr(user, "email", "") or ""),
    )


def _rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return list(data) if isinstance(data, list) else []


def _one(response: Any, message: str) -> dict[str, Any]:
    rows = _rows(response)
    if len(rows) != 1:
        raise PortalDataError(message)
    return rows[0]


def _parse_datetime(value: Any) -> datetime:
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _period_is_open(row: Mapping[str, Any], now: datetime) -> bool:
    current = now if now.tzinfo else now.replace(tzinfo=timezone.utc)
    return (
        row.get("status") == "open"
        and _parse_datetime(row["opens_at"]) <= current
        and current < _parse_datetime(row["closes_at"])
    )


def _database_question_id(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise PortalSubmissionError("The questionnaire is not bound to database item IDs.") from exc
