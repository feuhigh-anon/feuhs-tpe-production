# Target-based student evaluation portal

Status: the questionnaire catalog and target-aware schema migrations have been
applied in Supabase. The matching Streamlit changes and Q2 roster are local;
no target period, bank mapping, or pilot target links have been imported.

## Student flow

Each student receives four separately submitted forms for the active evaluation
period:

1. Two distinct subject-teacher evaluations.
2. One homeroom-adviser evaluation.
3. One homeroom-program evaluation.

The homepage completion percentage is `completed assigned targets / assigned
targets`. With the expected four-target roster, each submission adds 25%. The
count is restricted to the student's current target IDs, so a stale submission
from the same period cannot increase the displayed percentage. The Supabase
loader validates two subject-teacher targets, one adviser, and one program
before returning the portal snapshot.

Subject teachers are drawn from approved regular and overload schedule
assignments; daily and long-term substitutes remain secondary evidence.
Overload loads remain eligible. Regular-load assignments are prioritized, and
an adviser may also be one of the two subject targets through a secondary
`advisory_secondary` assignment. The user has confirmed both questionnaires
and the finalized Q2 roster decisions.

## Forms and scales

| Target | Quantitative items | Scale | Qualitative prompts |
| --- | ---: | --- | ---: |
| Subject teacher | 15 teacher-performance + 5 student self-evaluation | 1–5 agreement | 3 |
| Homeroom adviser | 10 | 1–5 agreement | 2 |
| Homeroom program | 16 | 1–4 agreement, no neutral option | 4 |

Quantitative statements are presented in their own sections. No written-notes
field is attached to each rating. Written feedback is grouped under the form's
Qualitative Feedback section. The subject-teacher self-evaluation remains a
student reflection component and is not presented as a teacher-performance
rating.

Every qualitative prompt requires a typed response. Students type a comment,
**Not applicable**, or **No other comments** directly into the existing text
field; there are no radio buttons or separate choice controls. The form does
not accept a blank response and does not instruct students to type the
abbreviation `N/A`. Ratings remain required.

Supabase receives each qualitative answer in `text_value` with a null
`rating_value`. It remains ordinary text, apart from trimming surrounding
whitespace; it is not rewritten, converted to a rating, or classified through
the `is_not_applicable` flag. This keeps qualitative collection separate from
quantitative scoring.

## Local database and application changes

`feval/portal_instruments.py` supplies local fallback definitions for the
three instrument types. The migration
`supabase/migrations/202610230001_questionnaire_catalog.sql` adds the three
target-specific instrument types and seeds six versioned question banks (three
instrument types for each school level). It does not create period mappings,
roster assignments, or target tables, so adding the catalog alone does not make
the new forms visible to student accounts.

`supabase/migrations/202610230002_multi_target_instruments.sql` adds period and
target routing, per-target student links, and target submissions and responses.
It is gated on an approved and imported roster. All qualitative items are
required in the form and RPC contract. Existing pilot tables and submissions
are retained. Written response text is stored once per answered qualitative
prompt; no full source XLSX is stored in Supabase by these migrations.

**Pilot-account visibility:** the existing pilot accounts use the legacy
`student_assignments` path. They will not see the new questionnaire from the
catalog alone. The target-aware schema is now applied, but the matching app
code still needs to be deployed and the 45 accounts must be linked to four
Q2 pilot targets each. Keep the pilot in its own period, separate from the
older `PILOT-2026-Q1` period.

## Naming and versioning

Follow the existing `question_banks` convention: keep a stable lowercase,
hyphenated instrument code and increment the integer `version` when its wording
or response contract changes. The new subject-teacher questionnaire uses the
existing `faculty-evaluation-jhs` and `faculty-evaluation-shs` codes at version
2; the new homeroom adviser and program instruments use descriptive codes at
version 1. Do not put the year or version number into the bank code.

Evaluation-period codes are uppercase and hyphenated. Keep the established
`PILOT-` prefix for synthetic test periods and include the school year,
evaluation quarter, schedule version, and sequence. The prepared pilot period
code is `PILOT-SY2026-2027-Q2-FINALS-01`. `Q2` is the evaluation term;
`FINALS` identifies the teacher-schedule version. The period has not yet been
created remotely; the guarded import SQL is prepared under
`outputs/pilot_q2_target_import_preview_r02/` and leaves it in draft.

Future roster batch codes use
`SY2026-2027-Q2-FINALS-PILOT-01` (school year, evaluation quarter, schedule
version, purpose, sequence). No Q2 full-roster batch with this code has been
uploaded. Schema objects follow the lowercase `snake_case`, domain-oriented
table and column naming described in `docs/DATABASE_LIFECYCLE.md`. New
migrations follow `YYYYMMDDNNNN_snake_case.sql`; applied migrations are not
edited.

The current evaluation cycle is the second quarter of SY 2026-2027. `Finals`
identifies the selected schedule version, not the evaluation term. The applied
questionnaire migrations do not attach banks to a period, import the approved
roster, or open a period. The prepared pilot import maps banks and links the
existing 45 synthetic accounts, but has not been run. The production
availability date previously requested is December 31, 2026 at 11:59:59 p.m.
Manila time. Keep the separate Q2 pilot period in draft until the matching app
version is deployed and acceptance checks are complete.

## Review and deployment boundary

- The source wording and scale definitions are transcribed from the
  `Teacher_Performance_Evaluation_by_Students_10Sept2026.docx` and
  `BE_BRAVE_Evaluation_Tools.xlsx` files. The user confirmed both instruments
  are final for this rollout.
- No scoring, weighting, or psychometric interpretation was changed here.
- The user applied both migrations and supplied SQL Editor results showing the
  new banks and RLS-enabled target tables. No pilot roster, target period,
  account, response, or target bank mapping has been imported.
- Keep the pilot period in draft until the existing-account audit, target
  import, and matching app deployment are ready. Then configure its bank
  mappings, run authorized RLS/RPC acceptance checks, and open the period.
- The six-bank seed is intentionally additive but currently creates a new bank
  on each migration execution. Apply it once through the migration history; do
  not rerun the SQL manually after partial execution without inspecting state.

