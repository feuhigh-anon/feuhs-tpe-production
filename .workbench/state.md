# Workbench State

- Status: Q2 roster candidate and synthetic pilot import package prepared locally; no Q2 roster/pilot data imported
- Last updated: 2026-11-03
- Current focus: deploy the target-aware student app, confirm pilot import prerequisites, then run the prepared import when authorized
- Profile/mode: edtech-admin; engineering with descriptive reconciliation and constrained allocation
- Completed: current schedule extraction, reviewed-XLSX contract, seeded allocation, private-staging uploader/proposal, live aggregate health check, storage-retention assessment
- Verification: pilot generator produced the 45-account/180-link SQL package; Python compilation and `git diff --check` passed during pilot preparation. No remote SQL or application acceptance test was run.
- Private artifacts: `exports/roster_v2_finals_review/Finals_Roster_Review.xlsx`; `outputs/roster_v2_health_review/roster_handoff.md`; `outputs/roster_v2_health_review/storage_and_health.md`
- Public workflow documentation: `docs/ROSTER_V2_IMPORT.md`
- Pending: the target-aware app is not deployed; the full 2,661-student Q2 roster is not uploaded; the 45-account Q2 pilot SQL is prepared but unrun. The pilot period has not been created; the import will leave it in draft.
- Deployment boundary: questionnaire catalog and target-aware migrations are applied. Target-specific portal rendering and RPC client remain local; pilot mappings, approved full-roster import, Supabase RLS/RPC acceptance checks and live promotion remain outstanding.
- Scoring boundary: preserve the existing pilot scorer. Questionnaire wording is finalized, while psychometric validation and any replacement scoring method remain pending. No measurement validity claim is established by roster or software tests.
- Next action: follow `docs/PILOT_TEST_WORKFLOW.md` and `PILOT_IMPORT_README.md`; do not use the legacy uploader or Q1 account-provisioning workflow for Q2.

## 2026-11-03 pilot preflight attempt
- The current 2,661-student local roster manifest reports 2,661 students, 107 teachers, 492 loads, exactly two subject allocations plus adviser and program per student, 10,644 targets total, zero local validation errors, and 27 excluded Canvas `_SM` courses. This is a source-based local validation, not a live Supabase verification; `database_compatible=false` remains in the manifest.
- The Q2 synthetic pilot package remains restricted to 45 existing synthetic accounts and 180 links. A separate read-only `PILOT_PREFLIGHT.sql` is available next to the guarded import SQL.
- Live preflight was not run: Supabase CLI is linked to production project `lnynxeugvfdqifrfotoa` but lacks `SUPABASE_ACCESS_TOKEN`; the already-signed-in dashboard was observable and showed the target tables have RLS enabled, but UI input failed with `noWindowsAvailable`. The prior saved query was left untouched. No pilot SQL or full-roster data was executed.
- Next step: run `PILOT_PREFLIGHT.sql` in a new SQL Editor query and inspect results before running `PILOT_IMPORT.sql`. Keep the period in draft; deploy the target-aware Streamlit app before opening it. Actual student account creation remains a later coordinated full-roster step.

## 2026-11-03 Q2 pilot live preflight result
- User ran the corrected read-only preflight against the linked production project. Eight checks passed; two are blocked: the 45 expected synthetic Auth/profile/student account joins returned 0, and active teaching sections returned 36/37. Programs (2), official sections (37), subjects (47), teachers (71), banks (6), tables (6), period state, and zero existing submissions passed.
- Do not run `PILOT_IMPORT.sql` yet. The generated account keys/emails are placeholders (`PILOT-*`, `pilot.*@example.invalid`) and do not match existing account records. The current import cannot create Auth users. Confirm the existing pilot identity mapping/project or explicitly choose new synthetic accounts before regenerating the pilot package.
- The user ran `PILOT_BLOCKER_DETAILS.sql`; the sole missing/inactive teaching section is `11ME02` (absent from `public.sections`). Keep this blocked until the mother-section row is represented in Supabase.
- User believes the 45 older questionnaire pilot accounts are in this same project. The failed join only rules out the generated placeholder identities; it does not rule out differently keyed older accounts. Added read-only `outputs/pilot_q2_target_import_preview_r02/PILOT_ACCOUNT_INVENTORY.sql` to inventory account-related schemas/tables and return aggregate Auth/profile/student/legacy-submission clues without listing names, emails, student numbers, credentials, or response text. It has not been run.
- User ran the inventory. It reports 66 Auth users, including 45 `pilot.*` emails; 66 active student profiles, 66 student rows, and 66 students with legacy assignments. There are no `PILOT-*` student numbers, while `PILOT-2026-Q1` has 2 submitters and 8 submissions. This strongly suggests the exact placeholder student-number join caused the 0/45 result, but the exact email/profile/student linkage is not yet confirmed.
- Added read-only `outputs/pilot_q2_target_import_preview_r02/PILOT_ACCOUNT_LINK_CHECK.sql` to confirm exact generated pilot-email matches and profile/student/legacy-assignment links using counts only. It has not been run. No database writes have occurred.

## 2026-10-23 assignment-priority correction
- Mode: edtech-admin / roster reconciliation and local implementation.
- Regular and overload assignments are primary; daily/LTS/unspecified substitutions are secondary. Conflicting current-workbook tags are excluded pending review.
- Restored the user-confirmed science overload through a private provenance-bearing correction, preserving both source workbooks. Finals assignment metadata supplements stale class aliases; teacher-header subject-specific overload applies only to the named subject.
- Latest private review: `exports/roster_v2_finals_primary_review_r03/Finals_Roster_Review.xlsx`; earlier versions preserved.
- 2,659 complete provisional four-target student rosters, 5,318 primary subject allocations, 97 teacher candidate pools. Four assignment-mode conflicts and other identity/shared-load issues remain; upload_ready=false. No cloud writes.

## 2026-10-23 target-instrument portal follow-up
- Local Streamlit flow now routes two subject-teacher targets plus one homeroom adviser and one homeroom program, with distinct instrument scales and optional qualitative prompts.
- Qualitative prompts accept a typed comment, `Not applicable`, `No other comments`, or blank. Only `Not applicable` is marked as N/A in the proposed database contract. Quantitative items have no per-item comments.
- Split the local SQL proposal into `202610230001_questionnaire_catalog.sql` (instrument metadata and six question banks only) and `202610230002_multi_target_instruments.sql` (target-aware workflow, still gated on roster approval). Both remain unapplied and unmapped; catalog-only deployment will not expose forms to legacy pilot accounts. No cloud writes.
- Fixed target-form text payload collection so newly named feedback sections submit. Python compilation and Git whitespace checks passed; no app-server/browser run, live acceptance check, or Git push.

## 2026-10-23 required typed qualitative feedback correction
- Supersedes the immediately previous optional/radio-button design: use the original text fields for every qualitative prompt, require typed input, and instruct students to type `Not applicable` or `No other comments` when appropriate.
- The local instrument definitions and migration seed now mark all qualitative items required. Supabase stores the typed phrase in `text_value` (trimming surrounding whitespace), with null `rating_value` and no special N/A flag; qualitative text does not enter rating calculations.
- Python compilation, response-payload checks for all three instruments, SQL seed inspection, and whitespace check passed. No live migration or push.

## 2026-10-23 homepage progress review
- Progress represents the number of submitted current assigned target IDs divided by the assigned target count. With the validated four-target roster, each form is 25%.
- Tightened the homepage numerator to intersect period-filtered submissions with current assignment IDs; this excludes stale same-period submissions from the percentage and completion count.
- Python compilation, a focused stale-target calculation check, and whitespace checks passed; no live database change.

## 2026-10-23 naming convention decision
- Preserve the repository's stable instrument-code plus integer-version pattern. The subject-teacher instrument advances from the existing `faculty-evaluation-{jhs,shs}` version 1 to version 2; homeroom adviser/program instruments start at version 1 with descriptive lowercase hyphenated codes.
- Keep synthetic evaluation periods under the established `PILOT-` prefix, include the school-year/term identifier, and retain the existing date/sequence/snake-case migration filename pattern. Proposed codes are documented locally only; no hosted period or batch was created.

## 2026-10-23 quarter correction
- The active evaluation cycle is Second Quarter of SY 2026-2027. The older synthetic pilot period `PILOT-2026-Q1` is a separate earlier period.
- Updated the local Streamlit login wording and test to say Second Quarter. `Finals` remains the teacher-schedule version; the review workbook's `SY2026-2027-S1-FINALS` period code is stale and must be corrected to Q2 and the workbook/bundle regenerated before upload.
- No Supabase period, roster, or question-bank mapping was changed.

## 2026-11-03 Q2 roster finalization
- User confirmed that Finals and Q2 are the same cycle for this school year; use period code `SY2026-2027-Q2` while retaining `schedule_version=Finals`.
- The finalizer reads the latest edited `SubjectLoads` workbook without modifying it. Canvas adds Collado to the seven `UCSP_NEWSOCSCIT3` sections, Galang to Science 7-1/8-1/10-1, resolves Mayorga for G08-2 Values Education, Sacdal for G09 TLE, and Santiago for G10 TLE. Manuel/Tarinay are removed from the linked UCSP evaluation targets; Science loads for G07-2/G08-2/G10-2 are omitted, with those students retained.
- Final local bundle: 2,659 students, 107 teachers, 492 subject loads, 5,318 subject targets, 2,659 adviser targets, 2,659 program targets, 10,636 total target rows and all 73 active teaching-section adviser mappings. One teacher has zero subject-target invitations and remains included in coverage output.
- Superseded correction: the user clarified that the small-class rule is to exclude Canvas courses whose identifiers end in `_SM`. It is not a low-teacher-load full-class assignment rule. The earlier invitation counts are invalid and must not guide deployment.
- Corrected output: `outputs/roster_v2_supabase_q2_final_20261103_sm_exclusion_r03/`. The finalizer excludes 27 Canvas `_SM` courses (273 active student-enrollment records) and balances eligible invitations without full-class forcing. Exactly two subject targets per student, advisory-secondary preference, and the 96 cap remain. Bundle validation passed; no teacher has zero subject invitations (range 7–80), with 5,285 regular-load and 33 advisory-secondary invitations.
- Files: `scripts/finalize_reviewed_roster.py`, corrected output folder above. Source workbook remains unchanged. Payload omits student names/emails; review CSVs retain adviser names and teacher coverage locally.
- No roster write or activation occurred. The schema migrations have since been applied; the final bundle remained local pending pilot setup.

## 2026-11-03 target-aware Q2 pilot preparation
- User supplied Supabase SQL Editor results confirming the questionnaire banks and target-aware RLS tables are present after applying migrations `202610230001` and `202610230002`.
- Rebuilt the local final Q2 bundle as `outputs/roster_v2_supabase_q2_final_20261103_target_schema_live_r05/`. It retains the reviewed workbook and uses the user-directed upload title `Health Optimizing Physical Education (HOPE) 4` for source code `HOPE3`; the XLSX was not edited.
- Prepared a synthetic 45-account pilot candidate with 180 target links in `outputs/pilot_q2_target_import_preview/`. The legacy `11GS02` synthetic slot maps to official section `11GS01`, with all four targets under mother/teaching section `11ME02`, consistent with the finalized Q2 roster. Period stays draft.
- The target-aware portal validator now permits an adviser to also appear among the two subject targets when the allocation labels that edge secondary; two subject teachers must remain distinct.
- Recommended close time is 2026-12-31 23:59:59 Asia/Manila (2026-12-31T15:59:59Z), matching the user's earlier production availability instruction. The new Q2 pilot period is not yet created.
- No live roster import occurred: this workspace has no Supabase project URL or service credential available, and the target-aware app changes remain local and are not in the last production commit. Do not use `upload_roster_v2_staging.py` for this pilot; it targets the legacy staging contract.

## 2026-11-03 Q2 subject catalog normalization
- User confirmed the two Grade 12 GAS PR loads use ABM teachers; normalize PR2 as ABM (`PR2A`) for Grade 12 ABM and GAS, HUMSS as `PR2H`, STEM as `PR2S`.
- Q2 finalizer now maps source `HOPE3` to Q2 catalog code `HOPE4`, `BASACC` to existing `BUS1`, standardizes `EC`/`MK` separately, and normalizes PG/PPG, PHILO, JHS grade-qualified titles, and other Canvas/catalog display names. The reviewed XLSX remains untouched.
- New local output: `outputs/roster_v2_supabase_q2_subject_catalog_r06/`; 2,659 students, 492 subject loads, 5,318 subject targets and 10,636 total target rows. All EC/MK combined labels are removed; all 32 PR2 loads are coded by strand; all 16 HOPE loads use HOPE4. The payload's 68 distinct subject codes are all represented in the local SQL proposal.
- The current Supabase subjects export has 77 active rows and 13 `ALPHA-*` subject rows. SQL proposal `supabase/proposals/202611030001_subject_catalog_cleanup.sql` upserts canonical Q2 subjects, deactivates HOPE3, deletes unreferenced ALPHA subject rows, and deactivates referenced ALPHA rows to preserve history. It has not been run; no live Supabase write occurred.
- Verification: regenerated bundle successfully, checked code/name coverage against the SQL proposal and current subject export, confirmed PPG/PG remain separate, and `git diff --check` passed. Alpha reference counts require live SQL Editor review before full deletion.

## 2026-11-03 Q2 entity relationship audit
- User supplied the full subject catalog export after applying the catalog update. It contains 82 rows: 68 active and 14 inactive (13 ALPHA subjects plus historical HOPE3). The 68 active codes exactly match the Q2 payload; no active subject names are duplicated.
- Relationship audit bundle: `outputs/roster_v2_supabase_q2_relationship_audit_r07/`. It contains 2,659 students across 74 official sections and 73 teaching sections, 107 teachers, 492 section-subject-teacher loads, 68 subject codes, and 10,636 student targets.
- Checked all target joins: each subject target matches an eligible section-subject-teacher load; each student retains their official section; all four target kinds/counts and adviser/program links match; no unknown teachers or broken links.
- User's earlier clarification confirms `11GS01` students are mixed into mother section `11ME02`. The finalizer now marks this one SectionGroups mapping approved in the generated payload, with provenance, without editing the workbook. Seven GS students join the 14 ME students for the shared 21-student teaching/adviser group.
- Local Python compilation and `git diff --check` passed. This is still a local audit only: Q2 relationships have not been staged or activated in Supabase. The current uploader is not compatible with the target-aware allocation; stage only after the target-aware workflow is implemented/deployed.
- Two included subject-load rows have no students in the current Q2 student roster: 11AD02 / ARTS1 / Basbas (202290076) and 11HS14 / LCS / Ignacio (202290164). Confirm whether these are empty/dissolved sections or a student-roster omission before final staging; do not silently remove or create students.
- User clarified that 11HS14 does not exist and directed us to use the Nov 2 Canvas provisioning export as the complete roster. Canvas has no current 11AD02 or 11HS14 sections; only 11AD01 exists for Arts and Design 1. Raw Canvas active enrollments across current official terms produce 2,708 unique students vs 2,659 in the workbook (49 Canvas IDs absent after SIS ID normalization); 40 student-section enrollment memberships differ from workbook sections. Canvas 11GE01 exactly matches the seven workbook 11GS01 IDs, while 11ME02 has 17 Canvas students vs 14 in the workbook. Request the grade/roster export without grade values to resolve student-course-section equivalence before regenerating or staging.

## 2026-11-03 grade export reconciliation
- Reviewed the Oct 28 JHS and SHS grade exports using only student/course/section/term SIS IDs and enrollment state; grade values were not used. The exports contain 20,163 active rows, including 244 `_SM` rows; excluding `_SM` leaves 19,919 regular-course enrollment rows and 2,708 unique students.
- All 2,659 students in the current Q2 payload appear in the regular-course export. It contains 49 additional active students (4 JHS, 45 SHS), also present in the Nov 2 provisioning snapshot; each has records in one normalized section, and all 49 sections exist in the reviewed roster. This is evidence they were active in the dated exports, not proof of current status after Nov 2. Do not silently exclude or import without making the roster decision explicit.
- The extra students map to 27 sections. Three are in 11ME02; if included, the shared 11ME02/11GS01 teaching group grows from 21 to 24 students. 11GE01 remains normalized to Supabase section 11GS01; JHS TLE `-FCS`/`-ICT` suffixes are treated as course subgroups for the section comparison.
- For the current 2,659 students, 2,656 have a modal regular-course section matching the reviewed workbook. Three section-change candidates need review: G10-2 vs G10-1; 11PSY02 vs 11PSY01; and 12A02b vs 12A03a. Other course-section differences can reflect legitimate irregular enrollments and must not automatically move a student's home section or override `SubjectLoads`.
- Source files were not edited. No roster payload was regenerated or uploaded. The user's follow-up confirms the final Q2 population remains 2,659.
- The imported Nov 2 `users.csv` matches all 49 unmatched IDs: 48 accounts are `suspended`, one is `active`. Their Oct 28 grade export has grade 60 on 339 of 347 regular-course rows, and all 49 have at least one grade-60 row. Grade 60 alone is not a safe exclusion rule: 214 students already in the 2,659 roster also have at least one grade-60 row, and 14 have 60 on all regular-course rows. Keep the 49 excluded per the confirmed list and flag the one active unmatched account for separate account-status reconciliation.
- `enrollments.csv` still marks 1,022 of the 1,023 enrollment rows for these students active and one invited, conflicting with user-level suspended statuses. Treat the grade/enrollment export as activity evidence, not the authoritative final roster. No roster payload or Supabase data changed.

## 2026-11-03 revised enrolled-student workbook
- User says the final Q2 population is 2,611 and supplied `List of Enrolled Students_Final Data_2661_SY26-27(1).xlsx` as the roster source. The workbook has 2,661 student rows, 2,661 unique student numbers, no duplicate IDs, and no hidden rows. It contains all 2,659 students in the prior reviewed roster plus two additional students.
- All 2,661 workbook IDs appear in the Oct 28 active non-`_SM` grade export. In the imported Nov 2 `users.csv`, 2,659 are `active` and two are `suspended`. Therefore the file and status snapshots do not identify 50 records to remove to reach 2,611. Grade 60 is not a safe filter. Do not rebuild or upload a 2,611-person roster until the 50 exclusion IDs or a corrected 2,611-row source are provided; source workbook remains unchanged.

## 2026-11-03 roster count follow-up
- A local 2,661-student candidate was generated after the user's direct instruction to use all 2,661. It contains 5,322 subject targets and 10,644 total targets, with 492 loads and 73 adviser mappings. It passed the finalizer's embedded linkage and four-target checks, but `database_compatible=false`; nothing was uploaded.
- The user then answered the earlier count question: keep 2,611 and provide the 50 exclusions or corrected roster. Treat the 2,661 bundle as provisional only and do not use it as the final roster. Await the exclusion IDs/corrected source before regenerating. The source files remain unchanged.

## 2026-11-03 master-list count confirmed
- User clarified that the master list's actual row count is authoritative. Recounted `List of Enrolled Students_Final Data_2661_SY26-27(1).xlsx`: 2,661 data rows, 2,661 unique student numbers, no blanks or duplicates. The prior 2,611 estimate was not an exclusion list; use all 2,661.
- The local candidate is `outputs/roster_v2_supabase_q2_final_enrolled_2661_r01/`. The user prefers a consolidated review rather than reviewing CSV files individually. The summary is `outputs/pilot_q2_target_import_preview_r02/PREUPLOAD_AND_PILOT_REVIEW.md`.
- Refreshed the existing 45-account synthetic pilot plan against the 2,661 bundle: 15 per JHS/G11/G12, 180 target rows. The old 11GS02 slot maps to official 11GS01 and teaching section 11ME02. Subject targets mirror a real allocation in the same section. No Auth users or database rows were created.
- Schema migrations are already applied; the roster manifest remains `database_compatible=false`, so no roster or pilot upload occurred. Do not use the legacy uploader. Supabase read-only migration/RLS checks are documented in `docs/ROSTER_V2_IMPORT.md`.

## 2026-11-03 target-aware pilot import prepared
- Generated `outputs/pilot_q2_target_import_preview_r02/PILOT_IMPORT.sql` and its guide, based on the refreshed preview and 2,661-student Q2 bundle.
- The script is a guarded transaction for 45 existing synthetic accounts and 180 links (90 subject, 45 adviser, 45 program). It validates Auth/profile/student identity, active current sections/teachers/subjects/program, and six published banks; it refuses to proceed if references do not match or submissions already exist for this period.
- It creates/reuses a draft period `PILOT-SY2026-2027-Q2-FINALS-01`, maps the six instruments, updates only the synthetic students' official section assignment, inserts target definitions and links, and leaves the period draft. It creates no Auth users and does not import the full 2,661-student master roster.
- Local generator checks validated the 45-account cohort structure and 2+1+1 target counts; SQL generation completed. No SQL was run against Supabase. The target-aware app still needs deployment before the pilot can be opened.

## 2026-11-04 pilot import correction
- User ran the aggregate account link check: all 45 expected pilot emails match active Auth users, student profiles, and `students` rows; none use the generated `PILOT-*` student-number keys. The old import's email-plus-placeholder-number join was therefore invalid.
- Regenerated the guarded `PILOT_IMPORT.sql` and read-only `PILOT_PREFLIGHT.sql` to resolve each synthetic account through Auth email → active profile → `students.profile_id`. The import now adds `11ME02` as SHS Grade 11 only if the section code is absent, then verifies the row; `11GS01` remains the official section for its sample students and `11ME02` is their teaching/adviser section.
- Updated the pilot guide and consolidated review. The SQL package still targets 45 existing synthetic accounts and 180 links (90 subject, 45 adviser, 45 program), and leaves the period draft. No remote SQL was run. Full student-roster reconciliation remains deferred; the target-aware Streamlit changes still need deployment before opening the pilot.
- User's refreshed preflight returned READY for all ten checks. Their import attempt then failed on PostgreSQL type inference for NULL values inserted into bigint `evaluation_targets` columns. Updated the SQL generator to cast those NULLs explicitly and regenerated the import file. The failed script used an explicit transaction; rerun the read-only preflight before retrying the corrected import. No successful import has been confirmed.
- The next import attempt reached the final guard but matched 0/45 accounts. Root cause: the guard joined each student's four links to staged targets by only email and target type, so each subject link multiplied across both staged subject rows. Updated the final validation join to also require the exact teacher and subject (or adviser/program) target; regenerated the import SQL. No successful import has been confirmed; the explicit transaction should roll back on this guard error.
