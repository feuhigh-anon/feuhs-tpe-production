# Teacher Performance Evaluation Prototype

A mobile-first Streamlit prototype for a structured teacher performance
evaluation workflow.

This repository contains synthetic demonstration data only. Do not use it for
real student information or live evaluation responses without an approved
production configuration.

## Current Questionnaire and Q2 Pilot Status

As of 2026-11-03, the subject-teacher, homeroom-adviser, and homeroom-program
questionnaires are finalized. Supabase migrations
`202610230001_questionnaire_catalog.sql` and
`202610230002_multi_target_instruments.sql` have been applied. This installs
the six versioned JHS/SHS banks and the target-aware tables; it does not create
a Q2 period, import the full roster, or link students to targets.

The local Q2 master-list candidate contains 2,661 students and is not uploaded.
The prepared pilot import uses 45 existing synthetic accounts and 180 target
links. Its SQL is under the ignored `outputs/pilot_q2_target_import_preview_r02/`
directory, remains unrun, and leaves the period in draft. The target-aware
Streamlit changes are local and need deployment before the period is opened.
See [`docs/TARGET_EVALUATION_PORTAL.md`](docs/TARGET_EVALUATION_PORTAL.md),
[`docs/PILOT_TEST_WORKFLOW.md`](docs/PILOT_TEST_WORKFLOW.md), and
[`docs/DATABASE_LIFECYCLE.md`](docs/DATABASE_LIFECYCLE.md) for the current
schema, naming, and import boundaries.
