# Synthetic Pilot Test Workflow

This workflow supports technical testing with synthetic student identities and
credentials. It is not an official student pilot. The subject-teacher,
homeroom-adviser, and homeroom-program questionnaires are finalized. The
questionnaire catalog and target-aware Supabase schema migrations have been
applied; Q2 pilot assignments and the matching app deployment remain pending.

## Purpose

The existing published JHS and SHS question banks may still be used with the
legacy pilot workflow. The new questionnaires are in a separate catalog
migration as immutable versions; the catalog alone does not link them to a
period or make them visible to existing pilot accounts. Technical testing of
the old forms does not automatically test the new target-aware forms.

## Current Boundary

- The 2,661-student Q2 master-list candidate remains local. Do not treat an
  older staging batch as the current Q2 roster or activate it as such.
- Alpha and pilot records must use separate period codes, such as
  `ALPHA-2026-01` and `PILOT-2026-Q1`.
- The current evaluation cycle is Second Quarter SY 2026-2027. The older pilot
  period is separate and must not be treated as the Q2 production period.
- Synthetic students may use real school-year teachers, subjects, and sections,
  but must not use real student names, numbers, or email addresses.

## Q2 Target-Aware Pilot Plan (2026-11-03)

The refreshed candidate is `outputs/pilot_q2_target_import_preview_r02/`. It
reuses the existing 45 synthetic accounts (15 JHS, 15 Grade 11, 15 Grade 12)
and assigns four Q2 targets each: two subject teachers, one adviser, and one
Be Brave program. The preview contains 180 links and uses the current
2,661-student Q2 bundle. It does not include real student names, numbers, or
emails.

The old account plan has a synthetic account labeled `11GS02`, but the finalized
Q2 roster has no students or adviser under that code. Its seven `11GS01`
students all use `11ME02` as their shared teaching and homeroom section. The
candidate therefore retains `11GS01` as the synthetic student's official
section and assigns the four targets under `11ME02`.

Each synthetic account's subject targets mirror an actual student allocation
in that same official and teaching section. The preview is offline-only: it
creates no Auth users and imports no target rows. The earlier
`outputs/pilot_q2_target_import_preview/` is superseded and must not be used.

The prepared target-aware period code is
`PILOT-SY2026-2027-Q2-FINALS-01`. Keep it in draft after import. Use a close
time of `2026-12-31 23:59:59` Asia/Manila, matching the previously requested
production availability date; open it only when the matching app is deployed.
No target import or period creation has occurred yet. The SQL package is
`outputs/pilot_q2_target_import_preview_r02/PILOT_IMPORT.sql`; it has not been
run.

## Current Q2 Pilot Sequence

1. Review the consolidated summary in
   `outputs/pilot_q2_target_import_preview_r02/PREUPLOAD_AND_PILOT_REVIEW.md`
   and the instructions in `PILOT_IMPORT_README.md`. The current preview
   assigns four targets to each of 45 existing synthetic accounts (15 each
   JHS, Grade 11, Grade 12).

2. Confirm the current Q2 master entities required by the pilot import are in
   Supabase: active official and teaching sections, teachers, subjects, the
   Be Brave program, and all six published question banks. The SQL checks these
   prerequisites and stops if any are missing. It does not import the full
   2,661-student roster.

3. Deploy the target-aware Streamlit changes before students test. The import
   leaves its period in `draft`; opening the period is a separate action after
   deployment and acceptance checks.

4. When prerequisites and the app are ready, run the complete
   `PILOT_IMPORT.sql` in SQL Editor for the intended Supabase project. It reuses
   existing Auth accounts and student profiles; it does not create or reset
   accounts. It updates only those synthetic students' official section
   assignments and inserts their 180 Q2 links. It also maps the six banks and
   keeps period `PILOT-SY2026-2027-Q2-FINALS-01` in draft.

5. Confirm the SQL result reports 45 accounts and 180 active links: 90 subject,
   45 adviser, and 45 program. If a guard reports a missing or inconsistent
   reference, resolve it before retrying the complete script. Do not open the
   period through the import script.

6. After deployment, verify login, the four-target display, the correct JHS/SHS
   instrument, required ratings and typed qualitative responses, progress,
   duplicate-submission prevention, and cross-account access restrictions.
   Keep the period in draft until those checks pass and opening the pilot is
   intentionally authorized.

The older `prepare_pilot_cohort.py`, `provision_roster_pilot.py`, and related
credential/reset/cleanup commands describe the superseded Q1 workflow. Do not
use them for this Q2 pilot: the current plan reuses existing accounts and
must not create accounts or automatically open a period.

## Target-Aware Questionnaire Visibility

The new question-bank catalog is in
`supabase/migrations/202610230001_questionnaire_catalog.sql`; the operational
tables and routing are in
`supabase/migrations/202610230002_multi_target_instruments.sql`. The user
confirmed both migrations were applied and supplied SQL Editor results showing
the question banks and RLS-enabled target tables. The older pilot accounts use
`student_assignments`; they still need explicit links in
`student_evaluation_targets` to see target-based forms.

The target-aware app implementation is present locally but is not part of the
last production commit. The two target-aware schema migrations have been
applied. Before testing, deploy the matching app and run the prepared import
for a separate Q2 pilot period. Do not reuse the older `PILOT-2026-Q1` period.

The local-only Q2 pilot import package is in
`outputs/pilot_q2_target_import_preview_r02/`. Review its
`PILOT_IMPORT_README.md` before any import. `PILOT_IMPORT.sql` targets only the
45 existing synthetic accounts and their 180 Q2 links. It validates that the
referenced accounts, current sections, teachers, subjects, program, and six
published questionnaire banks already exist; it does not create accounts or
upload the 2,661-student master roster. It also aligns those synthetic accounts
to current official sections, leaves the period in draft, and refuses to
replace links if submissions already exist. It has not been run.

## Table Export

Existing tables can be exported from Terminal with the administrator utility:

```bash
.venv/bin/python scripts/export_supabase_table.py evaluation_periods \
  --url https://YOUR_PROJECT_REF.supabase.co
```

For the staged final roster:

```bash
.venv/bin/python scripts/export_supabase_table.py roster_stage_sections \
  --batch-id 1 \
  --url https://YOUR_PROJECT_REF.supabase.co
```

Sensitive tables require the explicit `--include-sensitive` flag. Exports are
written under ignored `exports/` and must never be committed to the public
repository.
