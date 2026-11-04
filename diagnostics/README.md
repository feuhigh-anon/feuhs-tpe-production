# Temporary Streamlit Cloud probe

This page helps separate a Community Cloud app-route or built-in asset problem
from behavior specific to the evaluation portal. It does not import the portal,
connect to Supabase, read secrets, or persist the text entered in its test field.

## Deploy separately

1. Push this folder on a temporary branch. Keep the production `main` branch and
   its `student_app.py` deployment unchanged.
2. In Streamlit Community Cloud, create a separate app from the same repository
   and the temporary branch. Set the entrypoint to
   `diagnostics/streamlit_cloud_probe.py`.
3. Use the same Python version shown in the production app's current Cloud log.
   The probe uses the repository's root `requirements.txt`, including its pinned
   Streamlit version. It needs no Supabase secrets.
4. Open the probe from a fresh browser session. Check whether the page renders,
   whether the text input works, and whether **Check app interaction** returns
   the success message. Record any failed request URL, status, and duration,
   while redacting cookies and authorization values.

Interpretation:

- If the probe has the same long spinner or built-in JavaScript asset failures,
  the evaluation page's custom HTML and Supabase calls are not required to
  trigger the failure. Give Streamlit support both app URLs and the matching
  timestamps.
- If the probe works, compare its Cloud logs and dependency/runtime details with
  the evaluation app. That points toward an app-specific import, dependency,
  resource, or render path; it does not by itself identify which one.

Delete the temporary Cloud app and remove this folder after the comparison.
