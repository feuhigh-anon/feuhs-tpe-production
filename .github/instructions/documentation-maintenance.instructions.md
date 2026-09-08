---
description: "Use when maintaining documentation, docstrings, comments, CLI help, Markdown, SQL annotations, or notebook documentation in this evaluation project."
name: "Documentation Maintenance"
applyTo:
  - "**/*.py"
  - "**/*.ipynb"
  - "**/*.sql"
  - "**/*.md"
  - "**/*.toml"
  - "**/*.json"
---
# Documentation Maintenance

- Read the active implementation and nearby tests before changing documentation.
- Treat current source code and deployed schema behavior as evidence.
- Keep historical migrations, changelogs, security-verification records, and archived handoffs append-only or unchanged.
- Separate documentation drift from actual behavior, schema, or product drift.
- Preserve the distinct SHS and JHS instruments and workflows.
- Describe the current student workflow as Supabase-backed when that is the active path; do not describe retired SharePoint workflows as production behavior.
- Do not describe prototype psychometric scoring or qualitative NLP as validated measurement.
- Use synthetic or deidentified examples only.
- Do not include credentials, student identities, raw evaluation responses, or private roster data.
- For notebooks, preserve valid JSON, existing cell metadata, and notebook structure; do not rewrite notebooks as plain `.py` files.
- After edits, run the narrowest relevant executable validation and report unrelated failures separately.
