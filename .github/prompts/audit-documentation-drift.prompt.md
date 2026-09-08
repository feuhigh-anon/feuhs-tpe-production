---
description: "Audit selected project files for stale documentation and retired workflow references without editing them."
name: "Audit Documentation Drift"
agent: "Documentation Auditor"
argument-hint: "Scope, subsystem, or file paths to audit"
---
Audit the requested scope for documentation drift.

Compare docstrings, comments, user-facing labels, CLI help, Markdown, SQL annotations, and notebook Markdown with the current executable behavior and tests.

Return findings grouped as:

1. stale documentation;
2. missing documentation;
3. documentation that contradicts current behavior;
4. historical documentation that should remain unchanged;
5. actual implementation or schema drift requiring a separate engineering task.

Do not edit files. Include exact paths, symbols, evidence, and focused validation commands.
