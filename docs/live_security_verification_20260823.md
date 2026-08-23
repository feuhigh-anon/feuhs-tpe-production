# Hosted Security Verification Evidence

## Run Record

- Date: 2026-08-23 (Asia/Manila)
- Project: hosted synthetic alpha environment
- Verifier: `scripts/verify_live_security.py`
- Client version: `live-security-v1`
- Result: 26 passed, 0 failed
- Fixture cleanup: passed; temporary rows were removed and the alpha period was
  restored

No API keys, passwords, credential values, user UUIDs, or response content are
recorded in this evidence file.

## Verified Controls

- Anonymous profile reads are rejected.
- Each synthetic student can read only their own profile and roster row.
- Cross-student profile access is hidden.
- A student cannot read another student's assignment, teacher, or subject.
- A student can read an assignment explicitly authorized to them.
- Students cannot read raw response rows or submission audit events.
- Direct student writes to protected tables are rejected.
- Unauthorized and closed-period submissions are rejected.
- An authorized atomic 28-response submission succeeds.
- A second submission for the same student, assignment, and period is rejected.
- Submission metadata is visible only to its owning student.
- The elevated secret-key operator can read stored responses and the audit event.
- Reads are rejected after logout.
- The temporary submission, responses, audit event, student assignment,
  teaching assignment, subject, and teacher are removed after the run.

## Remaining Security Tests

This run does not establish complete production readiness. Before real rollout,
separately test simultaneous duplicate requests, access-token expiry and refresh,
password recovery after production SMTP is configured, a signed-in `admin`
profile, privacy/suppression behavior in administrator reporting, and expected
load under the planned student cohort.
