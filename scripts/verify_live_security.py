"""Run destructive-but-reversible security checks against the synthetic alpha data.

The verifier refuses non-alpha credentials, creates one disposable teaching
assignment, exercises student RLS and the submission RPC, then removes every
temporary row. Supabase keys are entered through hidden terminal prompts.
"""

from __future__ import annotations

import argparse
import csv
import getpass
import hashlib
import os
import secrets
import stat
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping, Sequence

from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions


ALPHA_PERIOD_CODE = "ALPHA-2026-01"
ALPHA_SECTION_CODE = "11STEM-ALPHA"
CLIENT_VERSION = "live-security-v1"
REQUIRED_CREDENTIAL_COLUMNS = {
    "email",
    "password",
    "display_name",
    "student_number",
    "section",
}


class LiveSecurityError(RuntimeError):
    """Raised when the live verifier cannot safely continue."""


@dataclass(frozen=True)
class AlphaCredential:
    email: str
    password: str
    display_name: str
    student_number: str
    section: str


@dataclass(frozen=True)
class SignedInStudent:
    client: Client
    user_id: str
    credential: AlphaCredential


@dataclass(frozen=True)
class CheckResult:
    name: str
    passed: bool
    detail: str


class CheckReport:
    def __init__(self) -> None:
        self.results: list[CheckResult] = []

    def record(self, name: str, passed: bool, detail: str) -> bool:
        result = CheckResult(name=name, passed=passed, detail=detail)
        self.results.append(result)
        marker = "PASS" if passed else "FAIL"
        print(f"[{marker}] {name}: {detail}")
        return passed

    def require(self, name: str, condition: bool, detail: str) -> bool:
        return self.record(name, bool(condition), detail)

    @property
    def passed(self) -> int:
        return sum(result.passed for result in self.results)

    @property
    def failed(self) -> int:
        return len(self.results) - self.passed


@dataclass
class TemporaryFixture:
    teacher_id: int | None = None
    subject_id: int | None = None
    assignment_id: int | None = None
    student_id: str | None = None
    submission_id: int | None = None
    original_period_status: str | None = None
    period_id: int | None = None
    period_status_changed: bool = False


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.getenv("SUPABASE_URL", ""),
        help="Hosted project URL; defaults to SUPABASE_URL.",
    )
    parser.add_argument(
        "--credentials",
        type=Path,
        help="Owner-only alpha credentials CSV; defaults to the newest ignored export.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    url = args.url.strip()
    validate_project_url(url)
    credential_path = resolve_credentials_path(args.credentials)
    credentials = load_alpha_credentials(credential_path)

    publishable_key = hidden_key(
        "Supabase publishable key (input hidden): ",
        "sb_publishable_",
    )
    secret_key = hidden_key(
        "Supabase secret key (input hidden): ",
        "sb_secret_",
    )

    print(f"Using synthetic credentials from {credential_path}.")
    admin = new_client(url, secret_key)
    anonymous = new_client(url, publishable_key)
    fixture = TemporaryFixture()
    report = CheckReport()
    cleanup_errors: list[str] = []

    try:
        students = [
            sign_in_student(url, publishable_key, credential)
            for credential in credentials[:2]
        ]
        student_a, student_b = students
        alpha_context = validate_alpha_context(admin, students)
        period = alpha_context["period"]
        section = alpha_context["section"]
        question_items = alpha_context["question_items"]
        fixture.period_id = int(period["id"])
        fixture.original_period_status = str(period["status"])

        report.require(
            "alpha period is open",
            fixture.original_period_status == "open",
            f"{ALPHA_PERIOD_CODE} status is {fixture.original_period_status!r}",
        )
        if fixture.original_period_status != "open":
            raise LiveSecurityError("Open the synthetic alpha period before running this test.")

        test_public_and_identity_boundaries(
            report,
            anonymous,
            student_a,
            student_b,
        )
        fixture = create_temporary_fixture(
            admin,
            fixture,
            section_id=int(section["id"]),
            period_id=int(period["id"]),
            student_id=student_b.user_id,
        )
        payload = response_payload(question_items)
        test_roster_and_submission_boundaries(
            report,
            admin,
            student_a,
            student_b,
            fixture,
            payload,
        )
        test_logout_boundary(report, student_a)
    except Exception as exc:
        report.record("verifier completed", False, safe_error(exc))
    finally:
        cleanup_errors = cleanup_fixture(admin, fixture)
        for message in cleanup_errors:
            report.record("fixture cleanup", False, message)
        if not cleanup_errors:
            report.record("fixture cleanup", True, "temporary rows removed and period restored")

    print()
    print(f"Live security result: {report.passed} passed, {report.failed} failed.")
    if report.failed:
        raise SystemExit(1)
    print("Synthetic live-security verification passed.")


def validate_project_url(url: str) -> None:
    if not url.startswith("https://") or ".supabase.co" not in url:
        raise SystemExit("Provide the hosted Supabase project URL with --url or SUPABASE_URL.")


def hidden_key(prompt: str, prefix: str) -> str:
    value = getpass.getpass(prompt).strip()
    if not value.startswith(prefix):
        raise SystemExit(f"Expected a current key beginning with {prefix}.")
    fingerprint = hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]
    print(f"Key received ({len(value)} characters; fingerprint {fingerprint}).")
    return value


def resolve_credentials_path(path: Path | None) -> Path:
    if path is not None:
        return path.expanduser().resolve()
    candidates = sorted(
        Path("exports").glob("alpha_credentials_*.csv"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )
    if not candidates:
        raise SystemExit("No exports/alpha_credentials_*.csv file was found.")
    return candidates[0].resolve()


def load_alpha_credentials(path: Path) -> list[AlphaCredential]:
    if not path.is_file():
        raise SystemExit(f"Credentials file does not exist: {path}")
    mode = stat.S_IMODE(path.stat().st_mode)
    if mode & (stat.S_IRWXG | stat.S_IRWXO):
        raise SystemExit("Credentials file must be owner-only. Run: chmod 600 <file>")

    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        missing = REQUIRED_CREDENTIAL_COLUMNS - set(reader.fieldnames or ())
        if missing:
            raise SystemExit(
                "Credentials file is missing columns: " + ", ".join(sorted(missing))
            )
        rows = [
            AlphaCredential(
                email=str(row["email"]).strip(),
                password=str(row["password"]),
                display_name=str(row["display_name"]).strip(),
                student_number=str(row["student_number"]).strip(),
                section=str(row["section"]).strip(),
            )
            for row in reader
        ]

    if len(rows) < 2:
        raise SystemExit("At least two synthetic alpha credentials are required.")
    for row in rows:
        if not row.email.casefold().endswith("@example.invalid"):
            raise SystemExit("The verifier accepts only example.invalid accounts.")
        if not row.student_number.startswith("ALPHA-"):
            raise SystemExit("The verifier accepts only ALPHA student numbers.")
        if row.section != ALPHA_SECTION_CODE:
            raise SystemExit(f"The verifier accepts only section {ALPHA_SECTION_CODE}.")
        if not row.password:
            raise SystemExit("A synthetic credential has a blank password.")
    return rows


def new_client(url: str, key: str) -> Client:
    return create_client(
        url,
        key,
        options=SyncClientOptions(
            auto_refresh_token=False,
            persist_session=False,
        ),
    )


def sign_in_student(
    url: str,
    publishable_key: str,
    credential: AlphaCredential,
) -> SignedInStudent:
    client = new_client(url, publishable_key)
    response = client.auth.sign_in_with_password(
        {"email": credential.email, "password": credential.password}
    )
    if response.user is None:
        raise LiveSecurityError(f"Sign-in returned no user for {credential.email}.")
    return SignedInStudent(
        client=client,
        user_id=str(response.user.id),
        credential=credential,
    )


def validate_alpha_context(
    admin: Client,
    students: Sequence[SignedInStudent],
) -> dict[str, Any]:
    period = one(
        admin.table("evaluation_periods")
        .select("id,code,status,opens_at,closes_at")
        .eq("code", ALPHA_PERIOD_CODE)
        .execute(),
        "The synthetic alpha period was not found.",
    )
    section = one(
        admin.table("sections")
        .select("id,code,school_level,grade_level,strand,is_active")
        .eq("code", ALPHA_SECTION_CODE)
        .execute(),
        "The synthetic alpha section was not found.",
    )
    if section.get("school_level") != "SHS" or int(section.get("grade_level", 0)) != 11:
        raise LiveSecurityError("The alpha section no longer matches the SHS Grade 11 fixture.")

    instrument = one(
        admin.table("evaluation_period_instruments")
        .select("question_bank_id")
        .eq("evaluation_period_id", period["id"])
        .eq("school_level", "SHS")
        .execute(),
        "The SHS alpha questionnaire assignment was not found.",
    )
    question_items = rows(
        admin.table("question_items")
        .select("id,response_type,is_required,position,section_key")
        .eq("question_bank_id", instrument["question_bank_id"])
        .execute()
    )
    if len(question_items) != 28:
        raise LiveSecurityError(
            f"Expected 28 SHS alpha questions but found {len(question_items)}."
        )

    for student in students:
        profile = one(
            admin.table("profiles")
            .select("id,display_name,role,is_active")
            .eq("id", student.user_id)
            .execute(),
            f"Profile not found for {student.credential.email}.",
        )
        roster = one(
            admin.table("students")
            .select("profile_id,student_number,section_id")
            .eq("profile_id", student.user_id)
            .execute(),
            f"Roster row not found for {student.credential.email}.",
        )
        if profile.get("role") != "student" or not profile.get("is_active"):
            raise LiveSecurityError("An alpha account is not an active student profile.")
        if str(roster.get("student_number")) != student.credential.student_number:
            raise LiveSecurityError("An alpha student number does not match the credential file.")
        if int(roster.get("section_id")) != int(section["id"]):
            raise LiveSecurityError("An alpha account is assigned to a non-alpha section.")

    return {
        "period": period,
        "section": section,
        "question_items": question_items,
    }


def test_public_and_identity_boundaries(
    report: CheckReport,
    anonymous: Client,
    student_a: SignedInStudent,
    student_b: SignedInStudent,
) -> None:
    expect_rejection(
        report,
        "unauthenticated profile read",
        lambda: anonymous.table("profiles").select("id").limit(1).execute(),
    )
    for label, student, other in (
        ("student 01", student_a, student_b),
        ("student 02", student_b, student_a),
    ):
        visible_profiles = rows(
            student.client.table("profiles")
            .select("id,display_name,role")
            .execute()
        )
        report.require(
            f"{label} profile isolation",
            {str(row["id"]) for row in visible_profiles} == {student.user_id},
            "only the signed-in profile is visible",
        )
        visible_students = rows(
            student.client.table("students")
            .select("profile_id,student_number,section_id")
            .execute()
        )
        report.require(
            f"{label} roster isolation",
            {str(row["profile_id"]) for row in visible_students} == {student.user_id},
            "only the signed-in roster row is visible",
        )
        cross_profile = rows(
            student.client.table("profiles")
            .select("id")
            .eq("id", other.user_id)
            .execute()
        )
        report.require(
            f"{label} cross-profile denial",
            not cross_profile,
            "the other synthetic student is hidden",
        )
        raw_responses = rows(
            student.client.table("evaluation_responses")
            .select("submission_id,question_item_id,rating_value,text_value")
            .execute()
        )
        report.require(
            f"{label} raw-response denial",
            not raw_responses,
            "no raw ratings or comments are readable",
        )
        audit_events = rows(
            student.client.table("submission_audit_events")
            .select("id,submission_id,event_type")
            .execute()
        )
        report.require(
            f"{label} audit-log denial",
            not audit_events,
            "administrator audit events are hidden",
        )


def create_temporary_fixture(
    admin: Client,
    fixture: TemporaryFixture,
    *,
    section_id: int,
    period_id: int,
    student_id: str,
) -> TemporaryFixture:
    token = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + secrets.token_hex(2)
    teacher = one(
        admin.table("teachers")
        .insert(
            {
                "employee_number": f"LIVESEC-T-{token}",
                "display_name": "Live Security Teacher",
                "email": f"live.security.{token}@example.invalid",
                "is_active": True,
            }
        )
        .execute(),
        "Unable to create the temporary security-test teacher.",
    )
    fixture.teacher_id = int(teacher["id"])
    subject = one(
        admin.table("subjects")
        .insert(
            {
                "code": f"LIVESEC-{token}",
                "name": "Live Security Test Subject",
                "is_active": True,
            }
        )
        .execute(),
        "Unable to create the temporary security-test subject.",
    )
    fixture.subject_id = int(subject["id"])
    assignment = one(
        admin.table("teaching_assignments")
        .insert(
            {
                "evaluation_period_id": period_id,
                "section_id": section_id,
                "subject_id": fixture.subject_id,
                "teacher_id": fixture.teacher_id,
                "is_active": True,
            }
        )
        .execute(),
        "Unable to create the temporary security-test assignment.",
    )
    fixture.assignment_id = int(assignment["id"])
    fixture.student_id = student_id
    one(
        admin.table("student_assignments")
        .insert(
            {
                "student_id": student_id,
                "teaching_assignment_id": fixture.assignment_id,
                "is_active": True,
            }
        )
        .execute(),
        "Unable to authorize the temporary assignment for Alpha Student 02.",
    )
    return fixture


def test_roster_and_submission_boundaries(
    report: CheckReport,
    admin: Client,
    student_a: SignedInStudent,
    student_b: SignedInStudent,
    fixture: TemporaryFixture,
    payload: Sequence[Mapping[str, Any]],
) -> None:
    if fixture.assignment_id is None or fixture.period_id is None:
        raise LiveSecurityError("The temporary assignment is incomplete.")

    hidden_assignment = rows(
        student_a.client.table("teaching_assignments")
        .select("id")
        .eq("id", fixture.assignment_id)
        .execute()
    )
    report.require(
        "cross-roster assignment denial",
        not hidden_assignment,
        "Student 01 cannot read Student 02's temporary assignment",
    )
    visible_assignment = rows(
        student_b.client.table("teaching_assignments")
        .select("id")
        .eq("id", fixture.assignment_id)
        .execute()
    )
    report.require(
        "authorized assignment read",
        len(visible_assignment) == 1,
        "Student 02 can read the explicitly assigned fixture",
    )
    hidden_teacher = rows(
        student_a.client.table("teachers")
        .select("id")
        .eq("id", fixture.teacher_id)
        .execute()
    )
    hidden_subject = rows(
        student_a.client.table("subjects")
        .select("id")
        .eq("id", fixture.subject_id)
        .execute()
    )
    report.require(
        "cross-roster metadata denial",
        not hidden_teacher and not hidden_subject,
        "the unauthorized teacher and subject are hidden from Student 01",
    )
    expect_rejection(
        report,
        "unauthorized submission denial",
        lambda: submit(student_a.client, fixture.assignment_id, payload),
        required_text=("no open authorized evaluation",),
    )
    expect_rejection(
        report,
        "direct student write denial",
        lambda: student_b.client.table("teachers")
        .update({"display_name": "Live Security Teacher"})
        .eq("id", fixture.teacher_id)
        .execute(),
    )

    fixture.period_status_changed = True
    admin.table("evaluation_periods").update({"status": "closed"}).eq(
        "id", fixture.period_id
    ).execute()
    expect_rejection(
        report,
        "closed-period submission denial",
        lambda: submit(student_b.client, fixture.assignment_id, payload),
        required_text=("no open authorized evaluation",),
    )
    admin.table("evaluation_periods").update(
        {"status": fixture.original_period_status}
    ).eq("id", fixture.period_id).execute()
    fixture.period_status_changed = False

    fixture.submission_id = submit(student_b.client, fixture.assignment_id, payload)
    report.require(
        "authorized atomic submission",
        fixture.submission_id > 0,
        "Student 02 submitted the temporary assignment through the RPC",
    )
    expect_rejection(
        report,
        "duplicate submission denial",
        lambda: submit(student_b.client, fixture.assignment_id, payload),
        required_text=("already been submitted",),
    )

    own_submission = rows(
        student_b.client.table("evaluation_submissions")
        .select("id,student_id,teaching_assignment_id")
        .eq("id", fixture.submission_id)
        .execute()
    )
    cross_submission = rows(
        student_a.client.table("evaluation_submissions")
        .select("id,student_id,teaching_assignment_id")
        .eq("id", fixture.submission_id)
        .execute()
    )
    report.require(
        "submission ownership visibility",
        len(own_submission) == 1 and not cross_submission,
        "only Student 02 can read the temporary submission metadata",
    )
    student_raw = rows(
        student_b.client.table("evaluation_responses")
        .select("submission_id,question_item_id,rating_value,text_value")
        .eq("submission_id", fixture.submission_id)
        .execute()
    )
    report.require(
        "submitted raw-response denial",
        not student_raw,
        "Student 02 still cannot read submitted ratings or comments",
    )
    admin_raw = rows(
        admin.table("evaluation_responses")
        .select("submission_id,question_item_id,rating_value,text_value")
        .eq("submission_id", fixture.submission_id)
        .execute()
    )
    admin_audit = rows(
        admin.table("submission_audit_events")
        .select("id,submission_id,event_type")
        .eq("submission_id", fixture.submission_id)
        .execute()
    )
    report.require(
        "elevated operator response visibility",
        len(admin_raw) == len(payload),
        f"the secret-key operator can read all {len(payload)} stored responses",
    )
    report.require(
        "elevated operator audit visibility",
        len(admin_audit) == 1 and admin_audit[0].get("event_type") == "submitted",
        "the secret-key operator can read the submission audit event",
    )


def test_logout_boundary(report: CheckReport, student: SignedInStudent) -> None:
    student.client.auth.sign_out()
    expect_rejection(
        report,
        "signed-out session denial",
        lambda: student.client.table("profiles").select("id").execute(),
    )


def response_payload(question_items: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    payload = []
    for item in question_items:
        response_type = str(item["response_type"])
        if response_type == "likert_5":
            payload.append(
                {
                    "question_item_id": int(item["id"]),
                    "rating_value": 4,
                    "text_value": None,
                }
            )
        elif response_type == "text":
            payload.append(
                {
                    "question_item_id": int(item["id"]),
                    "rating_value": None,
                    "text_value": "N/A",
                }
            )
        else:
            raise LiveSecurityError(f"Unsupported question response type: {response_type}")
    return payload


def submit(
    client: Client,
    assignment_id: int,
    payload: Sequence[Mapping[str, Any]],
) -> int:
    result = client.rpc(
        "submit_evaluation",
        {
            "p_teaching_assignment_id": assignment_id,
            "p_responses": list(payload),
            "p_client_version": CLIENT_VERSION,
        },
    ).execute()
    data = result.data
    if isinstance(data, list):
        data = data[0] if data else None
    if data is None:
        raise LiveSecurityError("Submission RPC returned no identifier.")
    return int(data)


def expect_rejection(
    report: CheckReport,
    name: str,
    action: Callable[[], Any],
    *,
    required_text: Iterable[str] = (),
) -> None:
    expected = tuple(text.casefold() for text in required_text)
    try:
        action()
    except Exception as exc:
        message = safe_error(exc).casefold()
        matched = not expected or any(text in message for text in expected)
        detail = "request was rejected"
        if expected and not matched:
            detail = "request failed, but not for the expected policy reason"
        report.record(name, matched, detail)
        return
    report.record(name, False, "request unexpectedly succeeded")


def cleanup_fixture(admin: Client, fixture: TemporaryFixture) -> list[str]:
    errors = []
    if fixture.period_status_changed and fixture.period_id is not None:
        try:
            admin.table("evaluation_periods").update(
                {"status": fixture.original_period_status}
            ).eq("id", fixture.period_id).execute()
            fixture.period_status_changed = False
        except Exception as exc:
            errors.append("unable to restore alpha period status: " + safe_error(exc))

    submission_ids: list[int] = []
    if fixture.submission_id is not None:
        submission_ids.append(fixture.submission_id)
    elif fixture.assignment_id is not None and fixture.student_id is not None:
        try:
            discovered = rows(
                admin.table("evaluation_submissions")
                .select("id")
                .eq("student_id", fixture.student_id)
                .eq("teaching_assignment_id", fixture.assignment_id)
                .execute()
            )
            submission_ids.extend(int(row["id"]) for row in discovered)
            if len(submission_ids) == 1:
                fixture.submission_id = submission_ids[0]
        except Exception as exc:
            errors.append("unable to locate temporary submission: " + safe_error(exc))

    cleanup_steps: list[tuple[str, Callable[[], Any]]] = []
    for submission_id in submission_ids:
        cleanup_steps.extend(
            [
                (
                    "audit events",
                    lambda submission_id=submission_id: admin.table(
                        "submission_audit_events"
                    )
                    .delete()
                    .eq("submission_id", submission_id)
                    .execute(),
                ),
                (
                    "submission and responses",
                    lambda submission_id=submission_id: admin.table(
                        "evaluation_submissions"
                    )
                    .delete()
                    .eq("id", submission_id)
                    .execute(),
                ),
            ]
        )
    if fixture.assignment_id is not None and fixture.student_id is not None:
        cleanup_steps.append(
            (
                "student assignment",
                lambda: admin.table("student_assignments")
                .delete()
                .eq("student_id", fixture.student_id)
                .eq("teaching_assignment_id", fixture.assignment_id)
                .execute(),
            )
        )
    if fixture.assignment_id is not None:
        cleanup_steps.append(
            (
                "teaching assignment",
                lambda: admin.table("teaching_assignments")
                .delete()
                .eq("id", fixture.assignment_id)
                .execute(),
            )
        )
    if fixture.subject_id is not None:
        cleanup_steps.append(
            (
                "subject",
                lambda: admin.table("subjects")
                .delete()
                .eq("id", fixture.subject_id)
                .execute(),
            )
        )
    if fixture.teacher_id is not None:
        cleanup_steps.append(
            (
                "teacher",
                lambda: admin.table("teachers")
                .delete()
                .eq("id", fixture.teacher_id)
                .execute(),
            )
        )

    for label, action in cleanup_steps:
        try:
            action()
        except Exception as exc:
            errors.append(f"unable to remove {label}: {safe_error(exc)}")
    errors.extend(verify_cleanup(admin, fixture))
    return errors


def verify_cleanup(admin: Client, fixture: TemporaryFixture) -> list[str]:
    errors = []
    checks = (
        ("evaluation_submissions", "id", fixture.submission_id),
        ("teaching_assignments", "id", fixture.assignment_id),
        ("subjects", "id", fixture.subject_id),
        ("teachers", "id", fixture.teacher_id),
    )
    for table, column, identifier in checks:
        if identifier is None:
            continue
        try:
            remaining = rows(
                admin.table(table).select(column).eq(column, identifier).execute()
            )
            if remaining:
                errors.append(f"temporary row remains in {table}")
        except Exception as exc:
            errors.append(f"unable to verify cleanup for {table}: {safe_error(exc)}")

    if fixture.period_id is not None and fixture.original_period_status is not None:
        try:
            period = one(
                admin.table("evaluation_periods")
                .select("status")
                .eq("id", fixture.period_id)
                .execute(),
                "unable to reload the alpha period after cleanup",
            )
            if period.get("status") != fixture.original_period_status:
                errors.append("alpha period status was not restored")
        except Exception as exc:
            errors.append("unable to verify alpha period status: " + safe_error(exc))
    return errors


def rows(response: Any) -> list[dict[str, Any]]:
    data = getattr(response, "data", None)
    return list(data) if isinstance(data, list) else []


def one(response: Any, message: str) -> dict[str, Any]:
    data = rows(response)
    if len(data) != 1:
        raise LiveSecurityError(message)
    return data[0]


def safe_error(exc: Exception) -> str:
    message = str(exc).replace("\n", " ").strip()
    return message[:240] or exc.__class__.__name__


if __name__ == "__main__":
    main()
