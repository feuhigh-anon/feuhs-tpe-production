# FEU High School Teacher Performance Evaluation

The FEU High School Teacher Performance Evaluation is a student-facing app for
collecting structured feedback on subject teachers, homeroom advisers, and the
Be Brave Homeroom Program. The current release is intended for deployment on
Streamlit Community Cloud's free service tier.

## Student access

Students sign in with the evaluation account issued to them by the school.
Self-registration is disabled. Each student receives the evaluations assigned
to their account: two subject teachers, one Homeroom Adviser, and the Be Brave
Homeroom Program. Written-feedback fields require a typed response; students
may enter “Not applicable” or “No other comments” when appropriate.

## Deployment

- Streamlit entry point: `student_app.py`
- Python dependencies: `requirements.txt`
- Required Streamlit secrets:

  ```toml
  SUPABASE_URL = "https://<project-ref>.supabase.co"
  SUPABASE_PUBLISHABLE_KEY = "<publishable-key>"
  ```

The Supabase project must already contain the evaluation schema, published
questionnaire banks, evaluation period, student accounts, and target
assignments. The app does not create accounts or import rosters. Never put a
Supabase secret/service-role key, student roster, account credentials, or
evaluation responses in this repository.

## Source layout

- `student_app.py` — student login and evaluation workflow.
- `feval/` — questionnaire definitions, student assignment models, and the
  Supabase portal adapter used by the app.
- `assets/` — FEU High School branding used by the login page.
- `supabase/migrations/` — versioned database migrations for maintainers.

The current source tree contains the app runtime and schema migrations.
Student data, account credentials, generated exports, and internal review
materials are excluded from this deployment snapshot.
