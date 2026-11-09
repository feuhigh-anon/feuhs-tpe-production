"""Authenticated Supabase data access for the student evaluation portal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping, Optional, Sequence

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


def is_meaningful_text_response(value: object) -> bool:
    """Require at least one letter or number in a qualitative response.

    This rejects empty/space-only answers and punctuation-only placeholders such
    as a single dot, while allowing punctuation within an actual response.
    """

    return any(character.isalnum() for character in str(value or ""))


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
    question_blocks: Mapping[str, QuestionBlock]


@dataclass(frozen=True)
class AdminEvaluationSummary:
    """Privacy-preserving quantitative summary for one teaching assignment."""

    teaching_assignment_id: str
    teacher_name: str
    school_level: str
    subject: str
    section_code: str
    evaluation_period: str
    response_count: int
    faculty_mean: float | None
    experience_mean: float | None
    self_evaluation_mean: float | None


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
    client: Optional[Client] = None,
) -> tuple[Client, AuthSession]:
    existing_client = client is not None
    client = client if client is not None else new_client(settings)
    try:
        if existing_client:
            # Keep the auth client's in-memory session across Streamlit reruns.
            # Re-applying the same token pair with set_session() on every rerun
            # can make concurrent refreshes compete over a rotating refresh token.
            response = client.auth.get_session()
        else:
            # A new Streamlit session has no in-memory auth state, so hydrate it
            # once from the last token pair retained in this browser session.
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
        .select("id,code,school_level,grade_level,is_active")
        .eq("id", student_row["section_id"])
        .limit(1)
        .execute(),
        "The assigned section is unavailable.",
    )
    if not section.get("is_active", False):
        raise PortalDataError("The assigned section is inactive.")

    links = _rows(client.table("student_evaluation_targets")
        .select("evaluation_target_id,is_active").eq("student_id", session.user_id)
        .eq("is_active", True).execute())
    target_ids = [int(row["evaluation_target_id"]) for row in links]
    if not target_ids:
        raise PortalDataError("No evaluation targets are available for this account.")
    target_rows = _rows(client.table("evaluation_targets")
        .select("id,evaluation_period_id,section_id,target_type,target_label,teacher_id,subject_id,program_id,is_active")
        .in_("id", target_ids).eq("is_active", True).execute())
    if not target_rows:
        raise PortalDataError("No active evaluation targets match this roster.")
    period_ids = sorted({int(row["evaluation_period_id"]) for row in target_rows})
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
    target_rows = [row for row in target_rows if int(row["evaluation_period_id"]) == active_period_id]
    target_types = {row["target_type"] for row in target_rows}
    subject_targets = [r for r in target_rows if r["target_type"] == "subject_teacher"]
    if len(subject_targets) != 2 or target_types != {"subject_teacher", "homeroom_adviser", "homeroom_program"}:
        raise PortalDataError("The active roster must contain two subject teachers, one adviser, and one homeroom program.")
    if sum(r["target_type"] == "homeroom_adviser" for r in target_rows) != 1 or sum(r["target_type"] == "homeroom_program" for r in target_rows) != 1:
        raise PortalDataError("The active roster has duplicate or missing homeroom targets.")
    subject_teacher_ids = {int(r["teacher_id"]) for r in subject_targets if r.get("teacher_id") is not None}
    if len(subject_teacher_ids) != 2:
        raise PortalDataError("The two subject-teacher targets must name distinct teachers.")

    subject_ids = sorted({int(row["subject_id"]) for row in target_rows if row.get("subject_id") is not None})
    teacher_ids = sorted({int(row["teacher_id"]) for row in target_rows if row.get("teacher_id") is not None})
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

    target_types_order = ("subject_teacher", "homeroom_adviser", "homeroom_program")
    target_rows.sort(key=lambda r: (target_types_order.index(r["target_type"]), str(r.get("target_label") or "")))
    assignments = []
    for row in target_rows:
        teacher = teachers.get(int(row["teacher_id"])) if row.get("teacher_id") is not None else None
        subject = subjects.get(int(row["subject_id"])) if row.get("subject_id") is not None else None
        target_type = row["target_type"]
        if target_type in {"subject_teacher", "homeroom_adviser"} and (not teacher or not teacher.get("is_active")):
            raise PortalDataError("An assigned teacher target is unavailable.")
        if target_type == "subject_teacher" and (not subject or not subject.get("is_active")):
            raise PortalDataError("An assigned subject target is unavailable.")
        if target_type == "subject_teacher":
            subject_name = str(subject["name"])
            teacher_name = str(teacher["display_name"])
            display_subject = subject_name
            target_label = row.get("target_label") or subject_name
        elif target_type == "homeroom_adviser":
            teacher_name = str(teacher["display_name"])
            display_subject = "Homeroom Adviser"
            target_label = row.get("target_label") or teacher_name
        else:
            teacher_name = "Homeroom Program"
            display_subject = str(row.get("target_label") or "Be Brave Homeroom Program")
            target_label = display_subject
        assignments.append(TeacherAssignment(
            id=str(row["id"]), school_level=str(section["school_level"]),
            grade_level=int(section["grade_level"]), strand="", section=str(section["code"]),
            subject=display_subject, subject_code=str(subject.get("code") or "") if subject else "",
            teacher_name=teacher_name, teacher_email=str(teacher.get("email") or "") if teacher else "",
            evaluation_period=str(active_period["code"]), target_type=target_type,
            target_label=str(target_label),
        ))

    instrument_rows = _rows(client.table("evaluation_target_instruments")
        .select("target_type,question_bank_id").eq("evaluation_period_id", active_period_id)
        .eq("school_level", section["school_level"]).execute())
    bank_ids = {row["target_type"]: int(row["question_bank_id"]) for row in instrument_rows}
    if set(bank_ids) != set(target_types_order):
        raise PortalDataError("One or more target-specific questionnaires are not configured.")
    question_blocks = {}
    for target_type in target_types_order:
        bank_id = bank_ids[target_type]
        bank = _one(client.table("question_banks").select("id,title,rating_labels")
            .eq("id", bank_id).limit(1).execute(), "The assigned questionnaire is unavailable.")
        question_rows = _rows(client.table("question_items")
            .select("id,stable_key,section_key,section_title,section_position,prompt,response_type,position,is_required,use_for_rci,rating_max")
            .eq("question_bank_id", bank_id).execute())
        question_blocks[target_type] = question_block_from_rows(
            str(section["school_level"]), bank_id, question_rows,
            target_type=target_type, label=str(bank["title"]), rating_labels=bank.get("rating_labels") or {},
        )

    submission_rows = _rows(
        client.table("evaluation_target_submissions")
        .select("evaluation_target_id,submitted_at,evaluation_period_id")
        .eq("student_id", session.user_id)
        .eq("evaluation_period_id", active_period_id)
        .execute()
    )
    submissions = tuple(
        SubmissionRecord(
            student_id=session.user_id,
            assignment_id=str(row["evaluation_target_id"]),
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
        # Strand is retained for model/schema compatibility; section is authoritative.
        strand="",
        section=str(section["code"]),
        evaluation_period=str(active_period["code"]),
        student_number=str(student_row["student_number"]),
        evaluation_closes_at=_parse_datetime(active_period["closes_at"]),
    )
    return PortalSnapshot(
        student=student,
        assignments=tuple(assignments),
        submissions=submissions,
        question_blocks=question_blocks,
    )


def load_admin_evaluation_summary(
    client: Client,
    session: AuthSession,
    period_id: int,
) -> tuple[AdminEvaluationSummary, ...]:
    """Load admin-scoped quantitative summaries without student or comment data.

    The aggregation key is the teaching assignment, preserving separate sections
    for a teacher who teaches the same subject more than once. Only numeric
    ratings are selected; free-text responses and student identifiers never
    enter the returned objects.
    """

    profile = _one(
        client.table("profiles")
        .select("id,role,is_active")
        .eq("id", session.user_id)
        .limit(1)
        .execute(),
        "No active administrator profile was found.",
    )
    if profile.get("role") != "admin" or not profile.get("is_active", False):
        raise PortalDataError("This account is not an active administrator account.")

    period = _one(
        client.table("evaluation_periods")
        .select("id,code")
        .eq("id", int(period_id))
        .limit(1)
        .execute(),
        "The evaluation period was not found.",
    )
    submissions = _rows(
        client.table("evaluation_submissions")
        .select("id,teaching_assignment_id")
        .eq("evaluation_period_id", int(period_id))
        .execute()
    )
    if not submissions:
        return ()

    submission_ids = [int(row["id"]) for row in submissions]
    assignment_ids = sorted({int(row["teaching_assignment_id"]) for row in submissions})
    assignments = {
        int(row["id"]): row
        for row in _rows(
            client.table("teaching_assignments")
            .select("id,section_id,subject_id,teacher_id,is_active")
            .in_("id", assignment_ids)
            .execute()
        )
        if row.get("is_active", False)
    }
    if not assignments:
        return ()

    section_ids = sorted({int(row["section_id"]) for row in assignments.values()})
    subject_ids = sorted({int(row["subject_id"]) for row in assignments.values()})
    teacher_ids = sorted({int(row["teacher_id"]) for row in assignments.values()})
    sections = {
        int(row["id"]): row
        for row in _rows(
            client.table("sections")
            .select("id,code,school_level")
            .in_("id", section_ids)
            .execute()
        )
    }
    subjects = {
        int(row["id"]): row
        for row in _rows(
            client.table("subjects")
            .select("id,name")
            .in_("id", subject_ids)
            .execute()
        )
    }
    teachers = {
        int(row["id"]): row
        for row in _rows(
            client.table("teachers")
            .select("id,display_name")
            .in_("id", teacher_ids)
            .execute()
        )
    }
    responses = _rows(
        client.table("evaluation_responses")
        .select("submission_id,question_item_id,rating_value,is_not_applicable")
        .in_("submission_id", submission_ids)
        .execute()
    )
    question_ids = sorted({int(row["question_item_id"]) for row in responses})
    questions = {
        int(row["id"]): row
        for row in _rows(
            client.table("question_items")
            .select("id,section_key")
            .in_("id", question_ids or [-1])
            .execute()
        )
    }

    ratings_by_submission: dict[int, dict[str, list[float]]] = {}
    for response in responses:
        rating = response.get("rating_value")
        question = questions.get(int(response["question_item_id"]))
        if rating is None or not question:
            continue
        component = {
            "teacher_performance": "faculty",
            "student_experience": "experience",
            "student_self_evaluation": "self_evaluation",
        }.get(str(question["section_key"]))
        if not component:
            continue
        submission_ratings = ratings_by_submission.setdefault(
            int(response["submission_id"]),
            {"faculty": [], "experience": [], "self_evaluation": []},
        )
        submission_ratings[component].append(float(rating))

    by_assignment: dict[int, list[dict[str, float]]] = {}
    submission_assignment = {
        int(row["id"]): int(row["teaching_assignment_id"]) for row in submissions
    }
    for submission_id, assignment_id in submission_assignment.items():
        if assignment_id not in assignments:
            continue
        component_means = {}
        for component, values in ratings_by_submission.get(submission_id, {}).items():
            if values:
                component_means[component] = sum(values) / len(values)
        by_assignment.setdefault(assignment_id, []).append(component_means)

    summaries = []
    for assignment_id in sorted(by_assignment):
        assignment = assignments[assignment_id]
        section = sections.get(int(assignment["section_id"]))
        subject = subjects.get(int(assignment["subject_id"]))
        teacher = teachers.get(int(assignment["teacher_id"]))
        if not section or not subject or not teacher:
            continue
        component_rows = by_assignment[assignment_id]
        summaries.append(
            AdminEvaluationSummary(
                teaching_assignment_id=str(assignment_id),
                teacher_name=str(teacher["display_name"]),
                school_level=str(section["school_level"]),
                subject=str(subject["name"]),
                section_code=str(section["code"]),
                evaluation_period=str(period["code"]),
                response_count=len(component_rows),
                faculty_mean=_mean_component(component_rows, "faculty"),
                experience_mean=_mean_component(component_rows, "experience"),
                self_evaluation_mean=_mean_component(component_rows, "self_evaluation"),
            )
        )
    return tuple(summaries)


def question_block_from_rows(
    school_level: str,
    question_bank_id: int,
    rows: Sequence[Mapping[str, Any]],
    *,
    target_type: str = "subject_teacher",
    label: str | None = None,
    rating_labels: Mapping[str, Any] | None = None,
) -> QuestionBlock:
    grouped: dict[str, list[QuestionItem]] = {
        "teacher_performance": [],
        "student_experience": [],
        "student_self_evaluation": [],
        "qualitative_feedback": [],
    }
    sections: dict[str, list[QuestionItem]] = {}
    titles: dict[str, str] = {}
    section_positions: dict[str, int] = {}
    for row in sorted(rows, key=lambda item: (int(item.get("section_position") or 1), int(item["position"]))):
        section_key = str(row["section_key"])
        if section_key not in grouped and not row.get("section_title"):
            raise PortalDataError(f"Unsupported questionnaire section: {section_key}")
        question = QuestionItem(
                id=str(row["id"]),
                text=str(row["prompt"]),
                aliases=(str(row["stable_key"]),),
                required=bool(row["is_required"]),
                use_for_rci=bool(row["use_for_rci"]),
                response_type=str(row.get("response_type") or "likert_5"),
                rating_max=int(row.get("rating_max") or 5),
            )
        sections.setdefault(section_key, []).append(question)
        titles[section_key] = str(row.get("section_title") or {
            "teacher_performance": "Teacher Performance",
            "student_experience": "Student Experience",
            "student_self_evaluation": "Student Self-Evaluation",
            "qualitative_feedback": "Qualitative Feedback",
        }.get(section_key, section_key.replace("_", " ").title()))
        section_positions[section_key] = int(row.get("section_position") or 1)
        if section_key in grouped:
            grouped[section_key].append(question)

    missing_sections = [key for key, items in grouped.items() if not items]
    if target_type == "subject_teacher" and not rows and missing_sections:
        raise PortalDataError(
            "The active questionnaire is missing sections: " + ", ".join(missing_sections)
        )

    form_sections = tuple(
        (titles[key], tuple(items), "comments" if items[0].response_type == "text" else "rating")
        for key, items in sorted(sections.items(), key=lambda pair: (section_positions[pair[0]], pair[0]))
    )
    labels = tuple(sorted((int(k), str(v)) for k, v in (rating_labels or {}).items()))
    if not labels:
        labels = ((1, "Strongly Disagree"), (2, "Disagree"), (3, "Neutral"), (4, "Agree"), (5, "Strongly Agree"))

    return QuestionBlock(
        id=f"{school_level.lower()}-db-{question_bank_id}",
        label=label or f"{school_level} questionnaire",
        faculty_items=tuple(grouped["teacher_performance"]),
        self_eval_items=tuple(
            grouped["student_experience"] + grouped["student_self_evaluation"]
        ),
        open_ended_items=tuple(grouped["qualitative_feedback"]),
        target_type=target_type,
        form_sections=form_sections,
        rating_labels=labels,
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
        if not 1 <= int(value) <= item.rating_max:
            raise PortalSubmissionError("A rating is outside the response scale for this questionnaire.")
        payload.append(
            {
                "question_item_id": _database_question_id(item.id),
                "rating_value": int(value),
                "text_value": None,
            }
        )
    text_items = (
        item for item in question_block.all_items if item.response_type == "text"
    )
    for item in text_items:
        key = f"comment_{assignment_id}_{item.id}"
        value = str(comments.get(key, "")).strip()
        if not is_meaningful_text_response(value):
            if item.required:
                raise PortalSubmissionError(
                    "Each written-feedback prompt needs a comment or “Not applicable” / "
                    "“No other comments.” Spaces or punctuation alone (such as a dot) "
                    "do not count as a response."
                )
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


def submit_target_evaluation(
    client: Client,
    evaluation_target_id: str,
    responses: Sequence[Mapping[str, Any]],
    *,
    client_version: str,
) -> int:
    """Submit one target-specific form through the atomic roster-authorized RPC."""
    try:
        result = client.rpc("submit_target_evaluation", {
            "p_evaluation_target_id": int(evaluation_target_id),
            "p_responses": list(responses),
            "p_client_version": client_version,
        }).execute()
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
    session = getattr(response, "session", None) or response
    user = getattr(response, "user", None) or getattr(session, "user", None)
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


def _mean_component(rows: Sequence[Mapping[str, float]], component: str) -> float | None:
    values = [row[component] for row in rows if component in row]
    return round(sum(values) / len(values), 4) if values else None


def _database_question_id(value: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise PortalSubmissionError("The questionnaire is not bound to database item IDs.") from exc
