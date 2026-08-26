# Synthetic Pilot Test Workflow

This workflow supports technical testing before the final production question
set is approved. It is not an official student pilot and must use synthetic
student identities and credentials.

## Purpose

The current published JHS and SHS question banks may be used for technical
testing. A later finalized question set will be introduced as a new immutable
question-bank version and linked to a separate evaluation period. Testing now
does not commit the project to the current questions for production.

## Current Boundary

- Final roster batch `1` remains in `roster_stage_*`.
- The batch must not be activated until the production question banks and
  student Auth accounts are ready.
- Alpha and pilot records must use separate period codes, such as
  `ALPHA-2026-01` and `PILOT-2026-Q1`.
- Synthetic students may use real school-year teachers, subjects, and sections,
  but must not use real student names, numbers, or email addresses.

## Test Sequence

1. Confirm the staging batch and roster counts with:

   ```bash
   .venv/bin/python scripts/audit_supabase_roster.py \
     --url https://YOUR_PROJECT_REF.supabase.co \
     --batch-id 1
   ```

2. Create or use a draft pilot period and associate the current published JHS
   and SHS question banks with it.

3. Prepare 45 synthetic student accounts: 15 JHS, 15 Grade 11, and 15 Grade
   12. Scatter them across the available sections and use actual staged
   teacher-subject assignments for their temporary mappings. The offline plan
   can be generated with:

   ```bash
   python scripts/prepare_pilot_cohort.py \
     --bundle exports/roster_import_SY2026_Q1_pilot \
     --output-dir exports/pilot_cohort_plan
   ```

   This command creates no users and changes no database rows. It excludes the
   four shared-UCSP section-subjects under the current approved policy.

   Provision the approved plan only after reviewing its CSV:

   ```bash
   .venv/bin/python scripts/provision_roster_pilot.py \
     --url https://YOUR_PROJECT_REF.supabase.co \
     --plan exports/pilot_cohort_plan/pilot_cohort_plan_20260826_121655.csv \
     --bundle exports/roster_import_SY2026_Q1_pilot
   ```

   This creates 45 reserved `example.invalid` accounts, opens only the pilot
   period, and leaves the full roster staging batch untouched. The command
   writes an owner-only credentials CSV under `exports/`.

4. Run the Streamlit app with those synthetic credentials and verify:

   - login and logout;
   - correct JHS/SHS instrument selection;
   - section and grade placement;
   - only assigned subjects and teachers are visible;
   - no shared-UCSP student mappings are exposed;
   - required Likert and qualitative responses are enforced;
   - review and confirmation display the selected responses;
   - duplicate submission is rejected;
   - another synthetic student cannot read the first student's roster or
     responses;
   - administrator export can read responses only with the service key.

5. Record the result, period code, question-bank IDs, synthetic credential file,
   and cleanup status locally. Do not commit credentials or response exports.

6. Delete the synthetic pilot users, temporary assignments, submissions, and
   credentials after testing, unless a documented test record must be retained.

   Cleanup is explicit and safety-checked:

   ```bash
   .venv/bin/python scripts/cleanup_roster_pilot.py \
     --url https://YOUR_PROJECT_REF.supabase.co \
     --credentials exports/pilot_credentials_YYYYMMDD_HHMMSS.csv
   ```

## Current Question Bank Limitation

The current question banks are appropriate for interface, authorization, and
submission testing. They are not the final production instrument while
management review is pending. When the questions arrive:

1. add a new versioned question-bank migration;
2. publish and verify the JHS and SHS question items;
3. link those banks to the official evaluation period;
4. rerun the end-to-end checks; and
5. activate the approved roster only after all checks pass.

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
