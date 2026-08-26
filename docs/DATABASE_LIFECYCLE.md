# Database Lifecycle and Naming

This document defines the current Supabase table naming and data-lifecycle
conventions. The live schema intentionally keeps application-facing tables
short and domain-oriented. The `roster_stage_` prefix identifies temporary
import data; it is not necessary to add a `prod_` prefix to every application
table.

## Table Groups

### Application-facing tables

These tables are read by the authenticated Streamlit portal or used by the
submission backend:

| Tables | Purpose |
| --- | --- |
| `profiles`, `students` | Authenticated student identity and section placement |
| `teachers`, `subjects`, `sections` | Normalized academic entities |
| `teaching_assignments`, `student_assignments` | Period-specific teacher, subject, section, and student mappings |
| `evaluation_periods`, `evaluation_period_instruments` | Evaluation windows and their JHS/SHS question-bank selection |
| `question_banks`, `question_items` | Versioned evaluation instruments |
| `evaluation_submissions`, `evaluation_responses` | Submitted evaluation records and answers |
| `submission_audit_events` | Submission and administrator audit events |

These are production tables even when they temporarily contain only synthetic
alpha or pilot records. Test data is separated by evaluation period, not by
creating alternate table names.

### Roster staging tables

The `roster_stage_` prefix means that rows are private, imported, and not yet
active in the student portal:

| Tables | Purpose |
| --- | --- |
| `roster_import_batches` | Batch identity, source hash, period, and lifecycle status |
| `roster_stage_sections` | Imported section records |
| `roster_stage_teachers` | Imported teacher records |
| `roster_stage_subjects` | Imported subject records |
| `roster_stage_students` | Imported student records and section references |
| `roster_stage_teaching_assignments` | Imported teacher-subject-section rows |
| `roster_stage_student_assignments` | Imported student-to-assignment mappings |
| `roster_import_issues` | Database-generated validation findings |

Staging rows are never read by students. Validation and activation are
service-role-only operations.

## Lifecycle

1. Build and validate the private workbook locally.
2. Prepare owner-only CSV files under ignored `exports/`.
3. Upload the CSV files to `roster_stage_*` with a new batch code.
4. Run `validate_roster_import_batch`.
5. Resolve errors and review informational shared-class findings.
6. Create the required Auth accounts and finalize the question-bank mapping.
7. Activate the validated batch into the application-facing tables.
8. Retain the activated batch metadata for provenance; remove obsolete draft or rejected staging batches only after review and policy approval.

Activation is transactional and is blocked when the period is not draft, when
submissions already exist, or when validation errors remain.

## Test Data

Alpha and pilot records use separate `evaluation_periods` such as
`ALPHA-2026-01` and `PILOT-2026-Q1`. They do not receive separate table names.
Synthetic students and credentials must use synthetic identifiers and must not
be committed to Git. Pilot rows should be deleted after testing when their
audit value is no longer required.

## Current State

Batch `1` is the staged final roster import for the pilot period. The complete
roster is in the `roster_stage_*` tables. The application-facing tables still
contain earlier synthetic alpha data and have not been activated with the final
roster.

The read-only audit command is:

```bash
.venv/bin/python scripts/audit_supabase_roster.py \
  --url https://YOUR_PROJECT_REF.supabase.co \
  --batch-id 1
```

It writes redacted JSON and CSV summaries under ignored `exports/`; it does not
export names, email addresses, student numbers, or response contents.

## Naming Rules for Future Changes

- Keep application-facing tables domain-oriented and unprefixed.
- Use `roster_stage_` for imported roster rows that are not active.
- Use `roster_import_` for import metadata and validation findings.
- Separate alpha, pilot, and production test data with evaluation-period IDs and
  explicit period codes, not separate table names.
- Do not rename tables directly in the Supabase Table Editor. If a rename ever
  becomes necessary, add a versioned migration and update RLS policies,
  database functions, Streamlit adapters, scripts, and tests together.
