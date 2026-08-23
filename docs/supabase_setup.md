# Supabase Setup and Questionnaire Versioning

## Current State

The repository contains two ordered migrations:

1. `202608230001_initial_schema.sql` creates the relational model, indexes,
   Row Level Security policies, immutable-questionnaire guards, and atomic
   `submit_evaluation` database function.
2. `202608230002_question_banks_v1.sql` installs and publishes the current SHS
   and JHS version 1 questionnaires.

Both migrations were applied to the hosted project on 2026-08-23. They contain
no real student roster, password, credential, or evaluation response. The
Streamlit authentication/data adapter, synthetic alpha provisioner, and
alpha-only live security verifier are implemented. The hosted login and normal
student workflow have passed manual testing with synthetic accounts. The
automated hosted verifier subsequently passed 26 of 26 checks with cleanup for
each of SHS and JHS on 2026-08-23. See `live_security_verification_20260823.md`
and `live_security_verification_jhs_20260823.md` for sanitized evidence.

## Create the Hosted Project

1. Sign in to the [Supabase Dashboard](https://supabase.com/dashboard).
2. Select the organization that will own the school project.
3. Create a project named `feu-faculty-evaluation`.
4. Select the free plan for the alpha test unless institutional requirements
   require a paid plan.
5. Choose the available region nearest the users, normally Singapore for a
   Manila-based deployment. Confirm the actual available regions in the
   dashboard before selecting one.
6. Generate a strong database password and store it in a password manager. Do
   not place it in Git, Streamlit code, screenshots, or chat messages.
7. Wait for project provisioning to finish.

Do not load real students yet.

## Apply the Migrations

The recommended workflow uses the Supabase CLI so the hosted database and Git
migration history remain synchronized. Docker is needed only for a full local
Supabase stack; it is not required merely to link and push migrations to the
hosted project.

After the CLI is installed:

```bash
supabase login
supabase link --project-ref YOUR_PROJECT_REF
supabase db push --dry-run
supabase db push
```

The project reference appears in the dashboard URL. Enter the database password
only into the CLI prompt. Do not add it to shell history or source files.

Avoid making table changes directly in the Dashboard Table Editor after adopting
migrations. Supabase documents that direct remote changes can put migration
history out of sync with `db push`.

## Configure Authentication for Alpha Testing

In **Authentication -> Sign In / Providers**:

1. Keep email/password authentication enabled.
2. Disable public user sign-up. Student accounts will be provisioned by an
   administrator, not self-created.
3. Keep anonymous sign-ins disabled.
4. Create only 5-10 synthetic alpha accounts initially.
5. Configure production SMTP and password recovery before real-student rollout;
   the built-in trial email service is not suitable for thousands of accounts.

The auth-user trigger creates a basic `profiles` row with role `student`. Roster
provisioning must separately create the `students` row and authorized
`student_assignments` rows. Never accept an administrator role from user-supplied
signup metadata.

## Streamlit Connection Values

The student app will use only the project URL and publishable key together with
each student's authenticated session token:

```toml
SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_..."
```

Configure these in `.streamlit/secrets.toml` locally and Streamlit Community
Cloud Secrets to enable authenticated mode. With neither value configured, the
application intentionally remains in fictional demo mode. The publishable key
does not grant student access by itself; authenticated JWTs and RLS determine
which rows a student can read.

Do not place a Supabase secret key or legacy service-role key in the student app.
Elevated keys bypass RLS and are reserved for a separate, tightly controlled
administrator provisioning process.

## Provision the Synthetic Alpha Cohort

Complete the authentication settings above before provisioning. Find the
project URL under **Project Settings -> API Keys**. Run the local administrator
script from the repository root:

```bash
source .venv/bin/activate
python scripts/provision_alpha.py \
  --school-level SHS \
  --url https://YOUR_PROJECT_REF.supabase.co \
  --students 2 \
  --open-days 7
```

The script asks for the current `sb_secret_...` key through a hidden terminal
prompt. Do not put that key in the command, `.env`, Streamlit Secrets, GitHub, a
screenshot, or chat. It is used only by this local administrator process.

The script creates:

- 2-10 fictional `example.invalid` student accounts with confirmed emails;
- one synthetic SHS section;
- two fictional teachers and subjects;
- one open synthetic evaluation period linked to SHS question bank version 1;
- roster-authorized teaching and student assignments.

Generated passwords are written to
`exports/alpha_<school-level>_credentials_<timestamp>.csv`. The earlier SHS
alpha run may still use the legacy `alpha_credentials_<timestamp>.csv` name.
The directory is ignored by Git and the file is created with owner-only
permissions. Delete the users and credential file after testing.

To create the separate Grade 7 JHS fixture, run:

```bash
.venv/bin/python scripts/provision_alpha.py \
  --school-level JHS \
  --url https://YOUR_PROJECT_REF.supabase.co \
  --students 2
```

This creates distinct `alpha.jhs.*@example.invalid` accounts, section
`07JHS-ALPHA`, JHS teachers and subjects, and an
`alpha_jhs_credentials_<timestamp>.csv` file. It links the shared synthetic
period to the published JHS question bank without modifying the SHS fixture.

## Verify Hosted Security With Synthetic Accounts

Run the verifier from the repository root after the two synthetic students can
sign in successfully:

```bash
.venv/bin/python scripts/verify_live_security.py \
  --school-level SHS \
  --url https://YOUR_PROJECT_REF.supabase.co \
  --credentials exports/alpha_credentials_YYYYMMDD_HHMMSS.csv
```

Paste the current `sb_publishable_...` key at the first hidden prompt and the
current `sb_secret_...` key at the second. Hidden input intentionally displays
no characters while pasting. The script prints only key lengths and one-way
fingerprints; it never prints or saves either key.

The verifier refuses credentials outside the selected synthetic level's
`example.invalid`, `ALPHA-*`, and alpha-section fixture. It creates a temporary
assignment authorized only for the second synthetic student, checks
unauthenticated access, cross-student and
cross-roster reads, raw-response isolation, direct-write rejection, closed
period rejection, successful atomic submission, duplicate prevention, audit
visibility through the elevated operator key, and logout behavior. It restores
the period and removes temporary rows in a `finally` cleanup path even when a
check fails.

Do not run this utility against real students. Preserve the terminal pass/fail
output as alpha-test evidence, but do not preserve or share the entered keys.

For JHS, use the generated JHS credential file and change the level explicitly:

```bash
.venv/bin/python scripts/verify_live_security.py \
  --school-level JHS \
  --url https://YOUR_PROJECT_REF.supabase.co \
  --credentials exports/alpha_jhs_credentials_YYYYMMDD_HHMMSS.csv
```

## Enable Authenticated Streamlit Mode

For local testing, create the ignored `.streamlit/secrets.toml` file:

```toml
SUPABASE_URL = "https://YOUR_PROJECT_REF.supabase.co"
SUPABASE_PUBLISHABLE_KEY = "sb_publishable_..."
```

Use the same two values in the deployed app's **Settings -> Secrets** panel.
After saving them, the public preview changes to the FEU student login screen.
Do not add the secret key. The student app rejects keys beginning with
`sb_secret_` as a defense against accidental configuration.

## How Questionnaire Changes Work

Question text is data, not a database column. Each response points to a
`question_item`, and every item belongs to one immutable `question_bank`
version.

Use this lifecycle:

1. Create a new question bank in `draft` status with version `2`, `3`, and so on.
2. Add, remove, reorder, or rewrite items only while that version is a draft.
3. Review the draft and publish it. Published items cannot be edited or deleted.
4. Attach the new version only to a future `evaluation_period`.
5. Keep the previous bank published or retire it after its periods close.

Never update version 1 to change a question after a student has submitted.
Historical submissions retain their original `question_bank_id` and
`question_item_id`, so reports always know exactly what wording and scale were
used.

Changing punctuation without changing meaning still creates a new version once
the bank is published. Changing the response scale or construct is a substantive
instrument revision and also requires a new version plus statistical review.

## Security Guarantees in the Initial Migration

- Students can read only their own profile, roster authorization, and assigned
  teachers/subjects/periods/questions.
- Raw response rows are not readable by students after submission.
- Direct student writes to submissions and responses are revoked.
- `submit_evaluation` validates the authenticated student, active roster,
  section, open period, published questionnaire version, response types, and
  required-answer completeness in one transaction.
- A database unique constraint prevents duplicate submissions for the same
  student, teaching assignment, and period.
- Foreign-key and RLS predicate columns are indexed.
- Administrators are a separate database role recorded in `profiles`; promotion
  is performed only through an elevated provisioning process.

## Required Verification Before Real Accounts

1. Run both migrations successfully on an empty project.
2. Review all findings in Supabase Security Advisor.
3. Create two synthetic students in different sections.
4. Confirm each student sees only their own assigned teachers.
5. Attempt cross-section reads and submissions and confirm the database rejects
   them.
6. Submit once, then confirm a duplicate submission is rejected.
7. Confirm students cannot select raw rows from `evaluation_responses`.
8. Confirm the elevated operator can read the reporting data. Test a separately
   authenticated `admin` profile before deploying an administrator interface.
9. Export and retain the applied migration identifiers and test evidence.

Only after these checks pass should approved roster data be imported.
