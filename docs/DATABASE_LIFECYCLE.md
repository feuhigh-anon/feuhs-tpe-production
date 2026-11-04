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
| `homeroom_programs` | Homeroom-program catalog by school level |
| `evaluation_targets`, `student_evaluation_targets` | Period-scoped subject/adviser/program targets and each student's authorized targets |
| `evaluation_target_instruments` | Period, school-level, target-type, and question-bank mapping |
| `evaluation_target_submissions`, `evaluation_target_responses` | Target-specific submissions and answers |

These are production tables even when they temporarily contain only synthetic
alpha or pilot records. Test data is separated by evaluation period, not by
creating alternate table names.

### Target-aware questionnaire tables (applied)

The finalized subject-teacher, homeroom-adviser, and homeroom-program
questionnaires are defined and seeded by
`202610230001_questionnaire_catalog.sql` as six versioned JHS/SHS banks. The
catalog migration adds question content but no period mappings or student
assignments. The applied `202610230002_multi_target_instruments.sql` migration
adds target-based assignments, routing, and submissions. Both migrations were
applied to the hosted project on 2026-11-03, as confirmed by the user. Their
deployment did not import the Q2 roster, create a Q2 period, map banks to that
period, or link pilot accounts. The target-aware app changes remain local.

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

## Legacy roster-stage lifecycle

The following CSV batch sequence describes the earlier `roster_stage_*`
workflow. It is not the import process for the current Q2 target-aware roster;
the legacy uploader cannot load its secondary-adviser allocations. Keep the
design for maintenance of existing staged batches, and follow
`docs/PILOT_TEST_WORKFLOW.md` for the separate synthetic pilot process.

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

## Current State (2026-11-03)

The Q2 master-list candidate has 2,661 unique students and remains local. Do not
assume an older `roster_import_batches` record or staging batch is the current
Q2 roster. The legacy uploader does not support the current target-aware
allocation format.

The synthetic pilot preview and guarded SQL are under the ignored
`outputs/pilot_q2_target_import_preview_r02/` directory. They cover 45 existing
synthetic accounts and 180 target links. The SQL has not been run; no Q2 pilot
period or target links have been created. The script keeps the period in draft
and does not create Auth users or import the 2,661-student roster.

The read-only audit command is:

```bash
.venv/bin/python scripts/audit_supabase_roster.py \
  --url https://YOUR_PROJECT_REF.supabase.co \
  --batch-id 1
```

It writes redacted JSON and CSV summaries under ignored `exports/`; it does not
export names, email addresses, student numbers, or response contents.

## Naming Rules for Future Changes

- Use lowercase `snake_case` for table, column, index, policy, and function
  names. Keep application-facing tables domain-oriented and unprefixed; retain
  established plural table names such as `teachers`, `subjects`, and
  `evaluation_periods`.
- Name foreign-key columns `<referenced_entity>_id`; use explicit link-table
  names such as `student_evaluation_targets` for many-to-many relationships.
- Use checked lowercase `snake_case` values for target types:
  `subject_teacher`, `homeroom_adviser`, and `homeroom_program`.
- Name unique indexes with a descriptive purpose and `_uq` suffix, ordinary
  indexes with `_idx`, and RLS policies with the table plus action/scope. Keep
  database function names verb-oriented, for example
  `submit_target_evaluation`.
- Use `roster_stage_` for imported roster rows that are not active.
- Use `roster_import_` for import metadata and validation findings.
- Separate alpha, pilot, and production test data with evaluation-period IDs and
  explicit period codes, not separate table names.
- Keep questionnaire-bank codes lowercase and hyphenated; store the integer
  version separately. For example, `faculty-evaluation-jhs` version `2` and
  `homeroom-adviser-evaluation-jhs` version `1`.
- Use uppercase hyphenated codes for evaluation periods. The current pilot code
  is `PILOT-SY2026-2027-Q2-FINALS-01`: prefix, school year, quarter, schedule
  version, sequence. `Q2` is the term; `FINALS` is the schedule version.
- For a future roster batch, use
  `SY2026-2027-Q2-FINALS-PILOT-01` (school year, quarter, schedule version,
  purpose, sequence). No Q2 full-roster batch with this code has been uploaded.
- Name new migration files
  `YYYYMMDDNNNN_snake_case.sql` (date, four-digit sequence, description); never
  edit an already-applied migration to change the hosted schema.
- Do not rename tables directly in the Supabase Table Editor. If a rename ever
  becomes necessary, add a versioned migration and update RLS policies,
  database functions, Streamlit adapters, scripts, and tests together.
