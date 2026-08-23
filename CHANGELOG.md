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

### 19:34:57 - Branded and verified the authenticated student login

- Rebuilt the Supabase login screen with a stronger FEU green/yellow identity,
  compact access form, visible light/dark mode control, and mobile-first layout.
- Replaced the temporary text monogram with the supplied official FEU High
  School seal.
- Extracted the recurring FEU building line drawing from the supplied Week 1
  educational-research PDF using a multi-page median composite, removing slide
  text while preserving the architectural artwork as a transparent local PNG.
- Embedded both local assets in the Streamlit banner without an external image
  host or changes to the authentication flow.
- Verified the light and dark screens at 390 x 844 and desktop width: both
  assets loaded at their expected dimensions, no horizontal overflow appeared,
  empty-form validation remained functional, and browser logs contained no
  errors or warnings.
- Hosted alpha status: two fictional student accounts and two synthetic teaching
  assignments were provisioned successfully; real student data remains excluded.
- Commit: pending.

### 14:37:14 - Implemented synthetic-alpha authentication and persistence boundary

- Added the official `supabase-py` client as a runtime dependency.
- Added `feval/supabase_portal.py` for publishable-key validation, password
  sign-in, token refresh, logout, RLS-governed roster/question loading, and
  atomic `submit_evaluation` RPC calls.
- Refactored `student_app.py` to retain fictional demo mode when Supabase values
  are absent and show the FEU student login boundary when both values are set.
- Disabled general and email self-signup in the tracked local Supabase config to
  mirror the administrator-provisioned account policy.
- Bound authenticated evaluations to database question-item IDs and the active
  immutable question-bank version instead of trusting in-code question text.
- Added `scripts/provision_alpha.py` to create 2-10 fictional accounts and a
  synthetic roster while keeping the secret key in a hidden terminal prompt and
  generated passwords in owner-only ignored output.
- Configured the provisioning client for non-persistent server-side Auth and
  added a concise diagnostic when Supabase rejects an invalid administrator key.
  Hidden key input now confirms receipt using only its length and a short
  one-way fingerprint.
- Added six offline adapter tests covering secret-key rejection, the current
  10/10/5/3 contract, future version count changes, complete 28-item payloads,
  required comments, and omission of unanswered optional items.
- Verification: Python compilation passed, all 26 tests passed, demo mode had no
  browser errors, and the desktop/mobile login layouts rendered correctly. A
  mobile button-contrast issue found during inspection was corrected.
- Hosted status: no Auth settings, users, secrets, or database rows were changed
  by this implementation step; live synthetic-alpha testing remains pending.
- Commit: pending.

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
