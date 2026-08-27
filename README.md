# Teacher Performance Evaluation Prototype

This repository contains a mobile-first Streamlit prototype for a structured
teacher performance evaluation workflow.

## Scope

- Authenticated student access
- Roster-constrained subject and teacher assignments
- Separate JHS and SHS questionnaire paths
- Five-point rating items and qualitative feedback
- Review, submission confirmation, and evaluation history
- Responsive light and dark display modes

## Development Status

This is a software prototype and contains synthetic demonstration data only.
It is not an official student-data repository and must not be used to submit
real evaluations without an approved production configuration.

## Run Locally

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run student_app.py
```

The administrator analysis prototype can be started with:

```bash
streamlit run app.py
```

## Configuration

Local authenticated development requires the appropriate Streamlit secrets
for the configured backend. Keep credentials, rosters, exports, evaluation
responses, and private review materials outside version control.

The repository intentionally does not document deployment URLs, backend
identifiers, account credentials, or operational import commands.

## Repository Hygiene

Private files are excluded through `.gitignore`. Review the ignore rules before
adding data or configuration files, and do not commit secrets or identifiable
student information.
