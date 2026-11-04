# Student portal deployment

The student portal can use a smaller Python environment than the analytics and
roster-preparation tools. Its Community Cloud entrypoint is
`portal_app/app.py`; its dependencies are in `portal_app/requirements.txt`.
That dependency file intentionally omits SciPy, scikit-learn, OpenPyXL, and
ReportLab, which are used by other project workflows and are not imported by
the student login/response path.

## Streamlit Community Cloud settings

For the existing student app, set the app's **Main file path** to
`portal_app/app.py`. Community Cloud looks for a dependency file beside the
entrypoint before checking the repository root, so it will use
`portal_app/requirements.txt` while leaving the root `requirements.txt` for the
analytics app. Keep the repository root as the working directory; the launcher
adds it to Python's import path so `student_app.py`, `feval/`, and `assets/`
continue to resolve from their current locations.

The production app must still be reviewed and deployed from its intended GitHub
branch. Changing this local entrypoint does not change the hosted app by itself.

## What this addresses

The previous production environment log showed installation of SciPy and
scikit-learn even though the student portal does not import them. A dedicated
dependency file should reduce environment setup and package replacement during
redeploys. Local import profiling of `student_app` completed in about 2.3
seconds on the current development machine; that is not a measurement of
Streamlit Cloud cold-start or browser rendering time. Compare the Cloud build
logs and first/second page load after deploying this entrypoint to confirm the
effect.

The portal loads roster and questionnaire records only after authentication.
Those Supabase reads therefore do not explain a delay that occurs before the
login screen appears.
