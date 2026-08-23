# JHS Hosted Security Verification Evidence

## Run Record

- Date: 2026-08-23 (Asia/Manila)
- School level: JHS
- Synthetic fixture: Grade 7, section `07JHS-ALPHA`
- Verifier: `scripts/verify_live_security.py --school-level JHS`
- Client version: `live-security-v1`
- Instrument: published JHS version 1 question bank, 28 required items
- Result: 26 passed, 0 failed
- Fixture cleanup: passed; temporary rows were removed and the shared alpha
  period was restored

No API keys, passwords, credential values, user UUIDs, or response content are
recorded in this evidence file.

## Verified Controls

- Anonymous profile reads are rejected.
- Each JHS synthetic student can read only their own profile and roster row.
- Cross-student profile, assignment, teacher, and subject access is hidden.
- Explicitly authorized JHS assignments remain readable to their student.
- Students cannot read raw response rows or submission audit events.
- Direct student writes to protected tables are rejected.
- Unauthorized and closed-period submissions are rejected.
- An authorized atomic 28-response JHS submission succeeds.
- A duplicate JHS submission is rejected.
- Submission metadata is visible only to its owning student.
- The elevated secret-key operator can read stored responses and the audit event.
- Reads are rejected after logout.
- The temporary submission, responses, audit event, student assignment,
  teaching assignment, subject, and teacher are removed after the run.

## Remaining JHS Check

Use one JHS synthetic account in the deployed Streamlit app to confirm the
Grade 7 profile, JHS teacher/subject roster, JHS-specific wording, review page,
submission confirmation, responsive layout, and light/dark themes visually.

The broader production security tests listed in the SHS evidence record remain
applicable: simultaneous-request concurrency, token expiry and refresh,
password recovery, authenticated administrator role, reporting privacy, and
planned-cohort load.
