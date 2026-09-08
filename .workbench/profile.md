# Profile: EdTech and Administrative Engineering

## Primary purpose

Build and maintain reliable work-related software, dashboards, data workflows, Canvas/SIS tools, evaluation systems, and administrator-facing artifacts.

## Default standards

- Inspect the repository and data contract before changing behavior.
- Preserve separate data domains when their semantics differ, such as JHS versus SHS or regular versus irregular classes.
- Normalize semester, course, section, teacher, and identifier variants explicitly.
- Investigate conflicting identifiers before deduplicating.
- Treat institutional records as sensitive by default; use synthetic or deidentified data for examples and tests.
- Keep administrative risk scores distinct from calibrated probabilities unless calibration has been demonstrated.
- Do not describe feature importance as causal.
- Keep source-system meaning visible in labels and documentation.
- Test authentication, authorization, privacy suppression, duplicate submissions, exports, and failure paths where relevant.
- Validate the rendered interface, not only unit tests.
- Document deployment assumptions, environment variables, migrations, rollback, and operational ownership.

## Preferred deliverables

- repository map and implementation plan
- data-contract or schema review
- tested feature implementation
- security/privacy review
- rendered UI QA report
- administrator-ready guide or handoff
