---
description: "Apply an approved documentation audit to specified Python, notebook, SQL, Markdown, or configuration files without changing runtime behavior."
name: "Sync Approved Documentation"
agent: "Documentation Maintainer"
argument-hint: "Approved findings and file paths to update"
---
Apply only the approved documentation findings supplied in this request.

Before editing, verify each finding against the current implementation and nearby tests. Update only docstrings, comments, labels, CLI help, Markdown, SQL annotations, or notebook Markdown cells. Do not change runtime behavior, public data contracts, migration history, scoring formulas, or tests.

Validate the touched files and report:

- documentation changes;
- runtime files intentionally unchanged;
- validation results;
- unresolved behavior or schema conflicts.
