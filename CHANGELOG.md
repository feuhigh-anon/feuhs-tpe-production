# Implementation Change Log

This file is the durable, append-only record of implemented changes for the
FEU High School Faculty Evaluation Platform. Times use Asia/Manila (UTC+08:00).

## Maintenance Rule

- Add new entries at the top under the current date.
- Include the local date and time, affected area, verification, and commit ID
  when available.
- Do not replace older entries when plans change. Add a later correction or
  superseding entry so the implementation history remains visible.
- Do not include passwords, API keys, student rosters, response data, or other
  private information.

## 2026-08-23

### 04:14:02 - Added persistent implementation log

- Added this `CHANGELOG.md` so completed work remains traceable independently
  of the README and handoff summary.
- Seeded the log from Git history and the verified Supabase deployment state.
- Commit: pending.

### 04:12:21 - Documented hosted Supabase deployment and CLI configuration

- Updated `README.md` and `HANDOFF_SUMMARY.md` with the deployed database state,
  current security boundary, test count, and next implementation sequence.
- Added the generated `supabase/config.toml` and `supabase/.gitignore`.
- Ignored machine-specific `supabase/.temp/` CLI state.
- Recorded the public Streamlit preview URL and the requirement to keep it on
  synthetic in-memory data until authentication and persistence are connected.
- Verification: Python compilation passed, all 20 tests passed, and
  `git diff --check` passed.
- Commit: `df7e543` (`Document Supabase deployment and add CLI configuration`).

### 03:55:30 - Linked repository to hosted Supabase project

- Initialized Supabase CLI configuration in the repository.
- Linked the local repository to the hosted `feu-faculty-evaluation` project.
- Previewed the deployment with `supabase db push --dry-run`.
- Applied both source-controlled migrations to the hosted database.
- Confirmed all 14 expected public tables in the Supabase Table Editor.
- Confirmed the intended starting question data: 2 published question banks
  and 56 question items, with 28 items for each school level.
- Commit: deployment operation; source migrations are tracked in `e9e023f`.

### 03:29:35 - Added Supabase schema and versioned question banks

- Added the initial PostgreSQL schema for profiles, students, teachers,
  subjects, sections, periods, assignments, submissions, responses, and audit
  events.
- Added indexes, Row Level Security policies, explicit grants/revokes,
  immutable question-bank guards, and database-level duplicate prevention.
- Added the atomic authenticated `submit_evaluation` RPC.
- Added SHS and JHS version-1 question banks with 56 seeded items.
- Made all three qualitative prompts required and excluded `N/A` and
  `Not applicable` from substantive qualitative evidence.
- Added Supabase setup documentation, an environment-variable example, and
  five static migration-contract tests.
- Verification: 20 tests passed after this foundation was completed.
- Commit: `e9e023f` (`update on the addition of database`).

### 03:14:53 - Corrected review styling and qualitative validation

- Fixed the light-mode review expander so expanded content remains readable.
- Required completion of all three qualitative prompts before review.
- Added visible guidance to enter `N/A` or `Not applicable` when no additional
  feedback is available.
- Added semantic filtering so those placeholders are not scored as feedback.
- Added regression coverage for substantive-comment detection.
- Commit: `d0674fa` (`update on visual inconsistencies`).

### 02:58:54 - Fixed cloud rating highlight and header width

- Extended the FEU green header across the full student-app content width.
- Added selectors for Streamlit's cloud-rendered segmented-control markup so a
  selected Likert response displays the FEU yellow state consistently.
- Commit: `47afe19` (`Fix cloud rating highlight and header width`).

### 02:48:24 - Corrected mobile evaluation layout

- Prevented the mobile white application surface from clipping long evaluation
  sections.
- Stabilized form columns and segmented rating controls on narrow screens.
- Expanded selected-state selectors for Streamlit rendering variations.
- Commit: `c5fc915` (`Update student_app.py`).

### 00:18:25 - Created initial Streamlit evaluation platform

- Added the FEU-branded, mobile-first student portal with light/dark modes,
  assigned-teacher filtering, four evaluation stages, review, confirmation,
  history, help, and synthetic demonstration records.
- Added the administrator analysis prototype and reusable `feval` package for
  ingestion, SHS/JHS question definitions, scoring, qualitative analysis,
  reporting, PDF generation, and student assignment rules.
- Added the initial methodology, tests, public-repository sanitation rules,
  README, and master handoff summary.
- Commit: `b5549ad` (`Initial Streamlit evaluation prototype`).
