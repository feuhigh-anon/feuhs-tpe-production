# Finals roster preparation and import

Status: a local Second Quarter roster bundle is prepared. The questionnaire
catalog and target-aware schema migrations are applied in Supabase. The Q2
full-roster import is not connected to the target tables. The separate
45-account pilot import is prepared but unrun, and matching Streamlit changes
remain local.

## Current master-list candidate and consolidated review (2026-11-03)

The user confirmed that the correct student count is the actual count in
`List of Enrolled Students_Final Data_2661_SY26-27(1).xlsx`: 2,661 unique
student numbers, with no blank or duplicate IDs. This supersedes the earlier
2,611 estimate. The 2,661-student local candidate is
`outputs/roster_v2_supabase_q2_final_enrolled_2661_r01/`; the consolidated
summary and refreshed synthetic pilot preview are in
`outputs/pilot_q2_target_import_preview_r02/PREUPLOAD_AND_PILOT_REVIEW.md`.

The candidate uses the master workbook only for student numbers and official
sections. It uses the reviewed Finals workbook for SubjectLoads, adviser and
program mappings, and the November 2 Canvas export for the confirmed teacher
identity resolutions. The Political Science labels in the master list map to
the existing official section codes 11PS01 and 11PS02. The source workbooks
were not changed.

Rebuild the local candidate with:

```bash
.venv/bin/python scripts/finalize_reviewed_roster.py \
  --workbook exports/roster_v2_finals_primary_review_r03/Finals_Roster_Review.xlsx \
  --student-roster "/Users/ronmarccharlesms/Downloads/List of Enrolled Students_Final Data_2661_SY26-27(1).xlsx" \
  --canvas-zip /Users/ronmarccharlesms/Downloads/provisioning_csv_02_Nov_2026_2486.zip \
  --output outputs/roster_v2_supabase_q2_final_enrolled_2661_r01
```

The current counts are 2,661 students, 107 teachers, 492 eligible subject
loads, 5,322 subject targets, 2,661 adviser targets, 2,661 program targets,
and 10,644 total target links. Each student has two distinct subject teachers,
one adviser, and one Be Brave program. All 27 Canvas `_SM` courses are
excluded. The subject-allocation basis is 5,289 regular-load assignments and
33 advisory-secondary assignments; no teacher has zero subject invitations.
The imported Canvas user list has two suspended accounts among the 2,661
students; keep their roster targets, but confirm login status before enabling
those accounts.

The full Q2 roster remains a local candidate; no 2,661-student Q2 import has
been run. A separate guarded SQL package for the 45 existing synthetic pilot
accounts is prepared at
`outputs/pilot_q2_target_import_preview_r02/PILOT_IMPORT.sql`. It is not a
full-roster importer and does not use the legacy staging uploader. It requires
the current Q2 sections, teachers, subjects, program, and published banks to
exist before it can add the draft pilot period and 180 target links.

The roster and pilot previews are local only. The roster manifest marks the
bundle `database_compatible=false`, the target-aware importer is not ready,
and no roster or pilot rows were uploaded. Do not use the legacy
`upload_roster_v2_staging.py` for this target-aware bundle. The questionnaire
and target-aware schema migrations are already applied; do not reapply them.

### Single-summary review

The user does not want to review the generated CSV files one at a time. Use
the consolidated `PREUPLOAD_AND_PILOT_REVIEW.md` for the summary counts and
checks. It records the four-target validation, SubjectLoads linkage, section
group handling, small-class exclusions, invitation basis, pilot count, and
the fact that no live import occurred. Review the full student-level CSVs only
if a particular exception needs investigation.

### Refreshed synthetic pilot preview

`outputs/pilot_q2_target_import_preview_r02/` reuses the existing 45 synthetic
pilot accounts (15 JHS, 15 Grade 11, 15 Grade 12) and maps them to 180 current
target links. It uses the current 2,661-student bundle; for each pilot account,
the two subject targets mirror an actual allocation from the same official
and teaching section. The former 11GS02 pilot slot is mapped to official
11GS01 and teaching section 11ME02. This creates no Auth users or database
rows. Keep the pilot period draft until the target-aware app is deployed and
the acceptance checks pass. The earlier preview directory is superseded.

### Schema read-only checks

Run these queries in Supabase SQL Editor, not in a terminal. They confirm the
two migrations are recorded and the target tables have RLS enabled; they do
not write data:

```sql
select version
from supabase_migrations.schema_migrations
where version in ('202610230001', '202610230002')
order by version;
```

```sql
select c.relname as table_name, c.relrowsecurity as rls_enabled
from pg_class c
join pg_namespace n on n.oid = c.relnamespace
where n.nspname = 'public'
  and c.relkind = 'r'
  and c.relname in (
    'homeroom_programs', 'evaluation_targets',
    'student_evaluation_targets', 'evaluation_target_instruments',
    'evaluation_target_submissions', 'evaluation_target_responses'
  )
order by c.relname;
```

## Earlier 2,659-student bundle (superseded)

This section supersedes the earlier adviser-exclusion rules below for the
current SY 2026-2027 roster. `Finals` is retained as the schedule source label;
the evaluation period is `SY2026-2027-Q2`, as Finals and Q2 refer to the same
school-year cycle here.

The finalization used the latest reviewed workbook at
`exports/roster_v2_finals_primary_review_r03/Finals_Roster_Review.xlsx` and the
November 2 Canvas export. It did not edit the workbook. SubjectLoads decisions,
color-coded exclusions and regular/overload classifications remain primary.
Canvas resolved Collado (`202290226`) for UCSP in the seven sections linked to
`UCSP_NEWSOCSCIT3`, Galang (`202290227`) for Science 7-1, 8-1 and 10-1,
Mayorga (`202290188`) for Grade 8 Values Education, Sacdal (`202290176`) for
Grade 9 TLE and Santiago (`202290192`) for Grade 10 TLE. The latter two use
the teacher handle in the Canvas course identifier. The conflicting UCSP
teachers were removed from those students' UCSP targets; the three specified
Science section-2 loads were omitted while those students remain in the roster.

The finalization command is:

```bash
./.venv/bin/python scripts/finalize_reviewed_roster.py \
  --workbook exports/roster_v2_finals_primary_review_r03/Finals_Roster_Review.xlsx \
  --canvas-zip /Users/ronmarccharlesms/Downloads/provisioning_csv_02_Nov_2026_2486.zip \
  --output outputs/roster_v2_supabase_q2_relationship_audit_r07
```

The corrected local bundle has 2,659 students, 107 teacher records, 492 active
section loads, 5,318 subject targets, 2,659 adviser targets, 2,659 program
targets, and 10,636 total student-target rows. It includes all 73 active
teaching sections in the adviser roster and all teachers in the invitation
count file. Students receive targets
through their teaching section, preserving the 11GS01-to-11ME02 group mapping.
The reviewed workbook was not edited. The upload preparation now normalizes
Q2 HOPE rows from source code `HOPE3` to catalog code `HOPE4`, preserving the
old `HOPE3` catalog row as inactive for historical assignments. It also maps reviewed
`PR2` loads to `PR2A` for ABM and GAS, `PR2H` for HUMSS, and `PR2S` for STEM;
the two GAS teacher-section assignments remain as recorded in SubjectLoads.
`BASACC` maps to `BUS1` because the user confirmed Basic Accounting and
Business 1 are the same subject. Program code is `BE_BRAVE` for JHS and SHS.

The upload payload uses canonical course titles. Effective Communication
(`EC`) and Mabisang Komunikasyon (`MK`) remain separate; Philippine Governance
(`PG`) and Philippine Politics and Governance (`PPG`) remain separate. Their
catalog titles are normalized independently. The local subject-catalog SQL
proposal is `supabase/proposals/202611030001_subject_catalog_cleanup.sql`.
It inserts or corrects Q2 catalog rows and safely deletes unreferenced
`ALPHA-*` subject rows; referenced synthetic rows are deactivated so historical
assignments and evaluations remain intact. No Supabase write has been made by
this local preparation.

The latest relationship audit is `outputs/roster_v2_supabase_q2_relationship_audit_r07/`.
It confirms 2,659 students across 74 official sections and 73 teaching
sections, 107 teachers, 492 unique section-subject-teacher loads, and 10,636
targets. Every subject target resolves to a load; each student has two
distinct subject teachers, one adviser and one program; no teacher, section,
or subject links are missing. The user-confirmed `11GS01` to `11ME02` mapping
is marked approved in this generated payload only; the source workbook remains
unchanged. The 7 students in `11GS01` join the 14 `11ME02` students for the
shared teaching/adviser group of 21.

The bundle's Supabase payload removes student names and email addresses and
stores teacher identities once, rather than repeating names on assignment
rows. `supabase_payload.zip` contains the payload and manifest;
`adviser_roster_review.csv`, `teacher_coverage_review.csv`,
`excluded_loads_audit.csv`, and `excluded_sm_courses_audit.csv` are local review files and are not part of the
payload. The compressed payload archive is approximately 74 KB. The staging
uploader submits the structured records as JSON (about 3.6 MB serialized for
this bundle) to the private draft payload table; this request size is not a
measurement of stored database size. No live insert was made to measure the
Postgres footprint.

Adviser-as-subject assignments are permitted as `advisory_secondary` and are
penalized behind regular-load edges. Canvas courses whose course identifier or
short name ends in `_SM` are excluded from student evaluation; the generated
`excluded_sm_courses_audit.csv` lists those course records and their enrollment
counts. The 27 matching courses have 273 active student-enrollment records and
course-title section labels rather than official roster section codes. Students
remain eligible through their regular section-based subject loads. The `_SM`
tag does not trigger assignment of an entire section to a
teacher, and teacher section count or pool size does not trigger full-class
coverage. Invitations are balanced across eligible subject-teacher edges,
with no minimum invitation floor and a 96 maximum. The coverage report
includes all teachers so any zero invitation result is visible for review.
In this build, 5,285 subject invitations are from regular loads and 33 are
advisory-secondary. Every teacher has at least 7 subject invitations; the
maximum is 80. Collado receives 69 invitations and Galang receives 19. These
are allocation counts, not evaluation response counts.

This is a local, hashed final roster bundle. It has not been uploaded to
Supabase. The target-aware operational tables are live, but the roster
importer and account-specific target links are not configured; this bundle is
not an activation instruction.

## Input mechanism

Use the current student class timetable, the teacher timetable's Finals
version, and the approved student_master sheet. Do not rebuild from the old
UCSP reconciliation workbook. Teacher identity records may be reused as an
identity registry; old teaching assignments are not reused as source schedules.

The timetable parser selects current class tabs and department tabs explicitly.
SOCSCI (Midterm), earlier SOCSCI versions, templates and daily-substitution
tabs are excluded. ROOM ASSIGNMENT is explicitly read for adviser mappings,
even though that sheet is hidden. Hidden state alone is not a source-date rule.

Run the offline extraction with explicit paths:

```bash
.venv/bin/python scripts/build_schedule_roster.py \
  --students <student-master.xlsx> \
  --classes <student-class-schedule.xlsx> \
  --teachers <teacher-schedule.xlsx> \
  --identity-registry <teacher-identities.csv> \
  --aliases <reviewed-or-proposed-name-aliases.json> \
  --section-groups <section-groups.json> \
  --output-dir exports/<new-review-version>
```

The last two mapping inputs are optional. Any proposed resolutions still need
review in the output workbook. A source hash, mapping hashes, seed, counts and
issue classifications are recorded. Use a new output folder for each run.

The existing script render_roster_workbook.mjs converts workbook_data.json to
a review XLSX through the bundled spreadsheet runtime. Keep its dependencies
outside the public source tree. The generated workbook and every private CSV
must remain under ignored exports/ or outputs/ with restricted permissions.

## Flat XLSX contract

The review workbook replaces the timetable layout as the future upload input.
After review, administrators can maintain these flat sheets directly, rather
than repeatedly parsing presentation-oriented timetables.

| Sheet | Meaning and required fields |
| --- | --- |
| Students | student_number, display_name, institutional email, official section_code, teaching_section_code, review_status |
| Teachers | employee_number, display_name, email, review_status |
| SubjectLoads | section_code, subject_code, teacher_employee_number, decision, review_status, review_notes; retain source references |
| Homeroom | section_code, adviser_employee_number, program_code, review_status |
| Programs | program_code, program_name, school_level, review_status |
| SectionGroups | official section_code, teaching_section_code, review_status, provenance notes; empty when no group exceptions |
| Settings | key/value rows for period_code, schedule_version, exclude_adviser, seed, minimum_teacher_count, maximum_teacher_count, review_status |

Additional Allocations, TeacherCoverage, TeacherAliases and Issues sheets are
review outputs. They are not blindly accepted as authoritative upload input.
Preparation recomputes the allocation from the approved canonical sheets.

Keep the official student section distinct from a shared teaching group. A
SectionGroups exception must be explicit, approved and documented; no chained
or cyclic grouping is permitted. The future database authorization must support
this relationship rather than allowing arbitrary cross-section submissions.

Every import row needs review_status=approved. Each subject load needs an
include or exclude decision; excluded loads need an explanation. Unknown
identities, duplicate or shared section-subject loads, missing homeroom mappings,
and fewer than two non-adviser subject teachers block preparation. Timetable
placeholders are not real teachers. Combined language labels require resolution.
Numeric IDs are strings. Import data sheets must not contain formulas.

## Four targets per student

Prepare exactly two distinct subject teachers, one homeroom adviser and one
homeroom program. Regular-load subject assignments take priority. An adviser
may also be one of the two subject teachers when selected through a secondary
advisory edge, recorded as `advisory_secondary`. If the same teacher teaches
multiple subjects, choose one eligible subject context deterministically and
retain it in the allocation record.

The candidate allocation is a constrained bipartite assignment. A fixed seed
randomizes tie costs. This is not a uniform random sample of all feasible
rosters. A tight trial teacher cap is checked first. If infeasible, a separately
labelled review scenario keeps the declared minimum and searches for the lowest
feasible global cap, then minimizes departures from capped equal-count targets.
Record the failed trial and the selected bounds. Review the resulting teacher
counts and class coverage before approving the policy.

The current Q2 allocation has no minimum invitation floor and a maximum of 96
subject invitations per teacher. These are allocation controls, not response
count targets or demonstrated reliability thresholds. Teachers with no
eligible pool must be investigated separately. Allocation does not validate
the questionnaire.

The seed and source version must remain frozen after release. Do not reshuffle
on page load or after individual students submit. Review changes require a new
version and cannot silently replace an in-progress evaluation allocation.

## Build the upload bundle

```bash
.venv/bin/python scripts/prepare_roster_v2.py <approved-flat-roster.xlsx> \
  --output-dir exports/<new-validated-bundle>
```

Rejected workbooks create no release directory. Successful preparation writes
students, teachers, subject_loads, homeroom, programs, evaluation_allocations,
teacher_coverage, and any section_groups CSV. The manifest contains source and
per-file SHA-256 hashes, counts, period and seed. The complete student-subject
eligibility cross-product stays local: section loads plus explicit groups can
reconstruct it. Store only actual evaluation allocations in operational tables.

The bundle is not compatible with the old six-table uploader. Do not pass it
to upload_roster_staging.py or manually import it into teaching_assignments.

## Private staging proposal (legacy path; not for the current Q2 roster)

supabase/proposals/roster_v2_private_staging.sql is a reviewed-design proposal,
not an automatically applied migration. It adds two service-role-only tables:

- roster_v2_batches: period, source/manifest hashes, counts and lifecycle metadata;
- roster_v2_payloads: one compressed JSONB payload per batch.

This avoids another set of staging tables and repeated full eligibility links.
The source XLSX is retained in a private local archive, not Supabase Storage.
After operational import and archive verification, remove obsolete payload rows
under the retention policy while retaining small batch metadata records.

After the staging proposal is reviewed and deployed, the draft-only uploader is:

```bash
.venv/bin/python scripts/upload_roster_v2_staging.py exports/<validated-bundle> \
  --url https://YOUR_PROJECT_REF.supabase.co \
  --batch-code <legacy-batch-code> \
  --period-code <same-as-reviewed-workbook>
```

This legacy staging uploader was designed for the earlier adviser-exclusion
allocation. It is not compatible with the Q2 secondary-adviser policy or the
target-aware tables. Do not run it for the Q2 pilot. It does not create
accounts, activate a roster, or open an evaluation period.

## Required operational changes before activation

The deployed pilot still accepts a teaching_assignment_id and maps one bank per
school level. The migrations in
`supabase/migrations/202610230001_questionnaire_catalog.sql` and
`supabase/migrations/202610230002_multi_target_instruments.sql` have been
applied, with a matching local student portal client and rendering. The
operational target migration is not yet connected to the roster importer. See
`docs/TARGET_EVALUATION_PORTAL.md` for the form and feedback behavior. Before
activation, complete and review these operational steps:

1. Preserve the reviewed workbook and finalized Q2 bundle as the approved
   source version. Later corrections must create a new version rather than
   silently changing an in-progress pilot.
2. Connect the reviewed upload bundle to operational period-specific student
   enrollment and target rows. The local migration creates target links and
   uniqueness constraints, but it does not import an approved roster, record a
   separately immutable allocation version, or activate a period.
3. Map the approved bank versions by period, school level, and target type;
   those mappings are intentionally not seeded automatically.
4. Run authorized Supabase checks for RLS visibility, adviser overlap only on
   secondary allocations,
   exactly two distinct subject-teacher targets, duplicate submission
   prevention, required ratings and required typed qualitative answers,
   including literal `Not applicable`/`No other comments` text, both levels, and
   concurrent submissions.
5. Promote the matching app revision and keep the legacy pilot path available
   until the replacement has passed acceptance checks. Both schema migrations
   are already applied; the app and Q2 roster targets remain pending.

## Verification and ownership

The local suite exercises identifier normalization, ambiguous surnames,
Spanish n matching, official versus teaching section, program-level boundaries,
adviser exclusion, deterministic allocation, quotas, failed approvals, four-
target bundle preparation and checksum tampering. Run:

```bash
.venv/bin/python -m unittest discover -s tests
```

Source reconciliation is an administrative review. The roster owner approves
identities and mappings, the evaluation owner approves instruments and dates,
and the database operator handles archives, migrations, staging and activation.
No production-readiness claim follows from an offline successful allocation.

### Assignment priority correction (2026-10-23)

Regular teaching assignments and explicitly tagged overload (`OL`/`Overload`) assignments belong to the primary candidate pool. Daily substitutes (`DS`/`Daily Sub`), long-term substitutes (`LTS`), and unspecified `Sub:` assignments are secondary. Secondary assignments are retained as evidence but never automatically used to meet quotas or fill a student's two subject slots. An approved import cannot include a secondary or conflicting assignment as primary.

Classification is assignment-specific: a teacher's substitute work does not disqualify their regular teaching or overload assignments. Global teacher-header load counts are not evidence that every cell is overload. Untagged confirmed timetable relationships retain a provisional regular classification, subject to review.

The selected Finals tab's substitution register and the same workbook's hidden Finals summary are retained with cell references in `AssignmentEvidence`. Conflicting tags are flagged and excluded from the primary pool rather than silently choosing a tab. This does not reuse the obsolete separate UCSP reconciliation workbook. `SubjectLoads` includes assignment mode, allocation priority, and mode provenance; `TeacherCoverage` distinguishes primary load count from allocated student evaluations.

Explicit user corrections can be supplied with `--load-overrides`: a private JSON list of section_code, subject_code, subject_name, teacher_employee_number, assignment_mode, and provenance. IDs must exist in the identity registry. Corrections replace the section-subject mapping and their hash is recorded in the review manifest. These are still review records, not automatic production approval. The reviewed import requires `assignment_mode` for every included subject load, with only regular/overload accepted.
