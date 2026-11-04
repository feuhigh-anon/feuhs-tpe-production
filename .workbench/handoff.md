# Handoff

## Completed

- Q2 candidate generated from the reviewed SubjectLoads, Canvas resolutions and the 2,661-student master list. Each student has two subject targets, one adviser, and one program target; no Q2 roster import occurred.
- Questionnaire catalog and target-aware migrations applied to Supabase. The target-aware Streamlit implementation remains local.
- Local synthetic pilot package prepared for 45 existing accounts and 180 target links. Its SQL is guarded and leaves `PILOT-SY2026-2027-Q2-FINALS-01` in draft; it has not been run.

## Files or artifacts changed

- Current import and naming references: `docs/DATABASE_LIFECYCLE.md`, `docs/ROSTER_V2_IMPORT.md`, `docs/TARGET_EVALUATION_PORTAL.md`, and `docs/PILOT_TEST_WORKFLOW.md`.
- Pilot import package: `outputs/pilot_q2_target_import_preview_r02/PILOT_IMPORT.sql` and `PILOT_IMPORT_README.md` (ignored local outputs).
- Current implementation and historical artifacts are recorded below; use only current sections when preparing the Q2 rollout.

## Verification

- No Supabase write was performed for the Q2 roster or pilot. Current docs were synchronized; Python compilation and whitespace checks passed for pilot preparation. No live app acceptance check was performed.

## Limitations and open decisions

- The target-aware Streamlit code has not been deployed; the current production app cannot yet display the four target types.
- The 2,661-student master roster has not been imported. The legacy roster uploader cannot load this target-aware allocation.
- The pilot SQL requires current active sections, teachers, subjects, the Be Brave program, and six published banks to exist; it validates these conditions before writing.
- No Q2 pilot period or links exist yet. The prepared import leaves the period draft; opening it is a separate action after app deployment and acceptance checks.

## Recommended next action

Deploy the matching target-aware Streamlit revision, confirm the pilot SQL prerequisites are present, then use the prepared import and run the acceptance checks. Keep the pilot period draft until those checks pass; open it separately when student testing is authorized. Plan a compatible full-roster import as its own step.

## 2026-10-23 quarter clarification
The active cycle is Second Quarter of SY 2026-2027. The existing `PILOT-2026-Q1` credentials/period are from the earlier pilot and cannot represent the current cycle. The current review workbook still has `SY2026-2027-S1-FINALS`; correct it to the approved Q2 code and regenerate/validate the bundle before upload. `Finals` is the selected schedule version. The Streamlit login text now says Second Quarter. No hosted records were changed.

## 2026-10-23 assignment priority follow-up
Use `exports/roster_v2_finals_primary_review_r03/Finals_Roster_Review.xlsx` for the latest review. Inspect SubjectLoads assignment_mode/allocation_priority, AssignmentEvidence source tags, and TeacherCoverage primary_load_count separately from allocated student invitations. Four conflicting DS/LTS/OL classifications remain blocked from primary selection. Daily/LTS substitutes are retained as secondary evidence, never automatic quota fillers. Some teachers may legitimately have only one primary load; validate source assignments rather than inventing another load. Private load corrections are in exports/roster_v2_load_corrections.json. Production schema/runtime integration and source approval remain outstanding. No live changes made.

## 2026-10-23 target-instrument portal follow-up
Local work adds three target-specific questionnaire types and the four-target student flow. See `docs/TARGET_EVALUATION_PORTAL.md` for form counts/scales, required typed feedback, migration boundaries, and review gates. The catalog and target-workflow SQL are split into sequential migrations; both remain unapplied and unmapped, and the roster remains unapproved. Catalog-only deployment does not expose forms to legacy pilot accounts. The portal client and rendering are local only. Python compilation and whitespace checks passed; no app-server/browser run, live database check, GitHub push, or hosted write occurred.

### Required typed qualitative feedback correction
The latest UI restores text-only entry and requires a typed response for every qualitative prompt. Students type `Not applicable` or `No other comments` when appropriate. Supabase stores the submitted phrase in `text_value` after trimming surrounding whitespace, with no `rating_value` and no N/A-flag interpretation. This supersedes the earlier optional/radio-button behavior recorded above. The migration remains unapplied. Python compilation, response-payload checks for all three instruments, SQL seed inspection, and whitespace checks passed; no live database test occurred.

### Homepage evaluation-period progress correction
The displayed progress is completed current assignment targets divided by all current assignment targets. For the expected four targets, each evaluation contributes 25%. The numerator now intersects submitted IDs with currently assigned IDs, excluding stale period submissions. Supabase portal loading validates exactly two subject targets, one adviser, and one program before rendering.

## 2026-11-03 finalized local Q2 roster

The current local data bundle is generated by `scripts/finalize_reviewed_roster.py` from `exports/roster_v2_finals_primary_review_r03/Finals_Roster_Review.xlsx` and the November 2 Canvas provisioning export. The source workbook is unchanged. Use period `SY2026-2027-Q2` and schedule label `Finals`.

The bundle has 2,659 students, 107 teachers, 492 eligible subject loads, 5,318 subject targets, 2,659 adviser targets and 2,659 program targets. All 73 occupied teaching sections have adviser mappings; `11GS01` students inherit `11ME02` teaching/adviser mapping. `BE_BRAVE` is the homeroom program code at both levels.

Canvas-backed changes: Collado (`202290226`) is the only UCSP target teacher on sections linked to `UCSP_NEWSOCSCIT3`; the conflicting UCSP teacher targets are omitted. Galang (`202290227`) is added for G07-1, G08-1 and G10-1 Science. The G07-2, G08-2 and G10-2 Science loads are omitted, while students remain eligible for other subjects. Mayorga (`202290188`) resolves G08-2 Values Education; the Canvas course handles resolve Grade 9 TLE to Sacdal (`202290176`) and Grade 10 TLE to Santiago (`202290192`).

Superseded allocation counts: the previous generation incorrectly forced full coverage for teachers with few sections or small pools. The user clarified that the small-class rule refers only to Canvas `_SM` courses being excluded from evaluation. The corrected bundle lists excluded `_SM` courses in a local audit and balances eligible subject invitations without full-class forcing.

Review the regenerated coverage counts before staging. Exactly two subject targets per student and the 96 maximum remain in effect; there is no rule assigning an entire class to a teacher based on teacher load size.

The corrected upload archive is `outputs/roster_v2_supabase_q2_final_20261103_sm_exclusion_r03/supabase_payload.zip`. The individual CSVs and manifest are under `supabase_payload/`. Student names/emails are excluded from the Supabase transport payload. Adviser names, all-teacher invitation counts, excluded-load audit, and `_SM` course audit are local review CSVs. No Supabase staging or production write occurred. Before staging, deploy/review the private-staging proposal and target-aware migration, then use the matching uploader; do not activate this roster solely from the existence of the bundle.

## 2026-11-03 Q2 subject catalog corrections

The user confirmed that Grade 12 GAS PR2 teachers are ABM teachers. The updated finalizer maps PR2 to PR2A for ABM/GAS, PR2H for HUMSS and PR2S for STEM; it also maps HOPE3 source rows to the distinct HOPE4 catalog code and maps BASACC to existing BUS1. EC/MK and PG/PPG remain distinct subjects, with canonical titles. The new local bundle is `outputs/roster_v2_supabase_q2_subject_catalog_r06/`; it keeps the workbook unchanged and retains the same student and allocation counts.

`supabase/proposals/202611030001_subject_catalog_cleanup.sql` is the owner-run SQL Editor proposal. It upserts the canonical Q2 subject catalog, marks historical HOPE3 inactive, deletes only unreferenced ALPHA subjects, and deactivates referenced ALPHA subjects to preserve assignment history. The snippet 16 export showed 13 active ALPHA subject codes. The proposal has not been executed, and the workspace has no configured live Supabase write access. Review remaining ALPHA references after running it before deciding whether to delete associated synthetic assignments or submissions.

## 2026-11-03 Q2 relationship audit

The user supplied the post-update full subject export: 82 rows, 68 active, 14 inactive (13 ALPHA rows and HOPE3). The 68 active subject codes exactly match the Q2 payload, and active subject names are unique.

The latest local bundle is `outputs/roster_v2_supabase_q2_relationship_audit_r07/`. It contains 2,659 students, 74 official sections, 73 teaching sections, 107 teachers, 492 unique section-subject-teacher loads, and 10,636 target links. Local checks found zero broken subject-load links, mismatched official sections, unknown teacher IDs, or adviser/program mismatches. Every student has two distinct subject teachers plus one adviser and one homeroom program.

The user confirmed that 11GS01 students share the mother section 11ME02 for subject and homeroom assignments. The finalizer marks that mapping approved in generated data only; the workbook stays unchanged. The seven GS students plus 14 ME students form the shared 21-student group. Q2 data still have not been staged or activated. The legacy roster v2 uploader is not compatible with the new target-aware policy; do not use it for this bundle. Implement and deploy the target-aware staging/activation workflow before uploading Q2 targets.

Two SubjectLoads records are not connected to any Q2 students in the reviewed student roster: 11AD02 / ARTS1 / Basbas (202290076), and 11HS14 / LCS / Ignacio (202290164). Confirm whether these sections are empty/dissolved or whether students are missing from the student export before staging. Do not fabricate student links or drop these schedule records without review.

The user clarified that 11HS14 does not exist and asked us to use the November 2 Canvas provisioning export as the complete roster. Canvas confirms no current 11AD02 or 11HS14 sections; `11AD01` is the only current Arts and Design 1 section. Comparing active student enrollments in the current official SHS/JHS terms with the workbook finds 2,708 unique Canvas student IDs versus 2,659 in the workbook, with 49 Canvas IDs absent after removing the leading `H` from numeric SIS IDs. Forty student-section enrollment memberships differ from workbook section assignments. Canvas `11GE01` contains exactly the seven students listed under workbook `11GS01`; `11ME02` has 17 Canvas students versus 14 in the workbook. Await a grade/roster export (student ID, course/section IDs and names, teacher ID/name, active status; grade values can be omitted) to resolve the exact student-course-section-teacher equivalence before updating the roster or staging.

## 2026-11-03 grade export reconciliation

Reviewed the Oct 28 JHS/SHS grade exports using student, course, section, term SIS IDs and enrollment state; grade values were not used. The exports have 20,163 active rows, of which 244 are in `_SM` courses and excluded under the user's rule. The remaining 19,919 regular-course rows cover 2,708 unique students. All 2,659 current Q2 roster students appear; 49 additional active students (4 JHS, 45 SHS) appear in one normalized section each, and every section is already represented in the reviewed roster. This confirms active status in the dated exports, not later status. Three additional students map to 11ME02; including them would make the shared 11ME02/11GS01 teaching group 24 rather than 21.

For 2,656 of the 2,659 current roster students, the modal regular-course section matches the reviewed workbook. Three possible section changes need human review: G10-2/G10-1, 11PSY02/11PSY01, and 12A02b/12A03a. Other course-section differences can be legitimate irregular enrollments and do not automatically change official home section or supersede `SubjectLoads`. The source workbooks were not edited; no payload was regenerated or uploaded.

The user confirmed that the final Q2 student list remains 2,659. The imported Nov 2 `users.csv` lists 48 of the 49 unmatched accounts as `suspended` and one as `active`. The Oct 28 grade export shows 60 on 339 of 347 non-small-class rows for these students, but 214 current roster students also have at least one grade-60 row (14 have 60 on all such rows); therefore grade 60 alone is not a safe dropout rule. Keep all 49 outside the Q2 roster per the confirmed list, and flag the one active unmatched account for separate account-status reconciliation. The provisioning `enrollments.csv` has 1,022 active and one invited enrollment rows for these 49, conflicting with user-level statuses. No roster bundle or Supabase data were changed.

## 2026-11-03 revised enrolled-student workbook

The user updated the stated final population to 2,611 and supplied `List of Enrolled Students_Final Data_2661_SY26-27(1).xlsx`. The file itself has 2,661 unique student rows, no duplicate IDs, and no hidden rows. It contains all 2,659 prior roster IDs plus two additional students. All 2,661 appear in the Oct 28 active regular-course grade export. The Nov 2 imported `users.csv` lists 2,659 as active and two as suspended. These sources do not identify 50 exclusions or yield a 2,611-person roster; do not use grade 60 as an exclusion rule. Await the 50 exclusion IDs or an authoritative corrected 2,611-row roster before rebuilding the payload. Nothing was changed in the workbook or Supabase.

The user next instructed us to use all 2,661; a local candidate was generated at `outputs/roster_v2_supabase_q2_final_enrolled_2661_r01/` with 2,661 students, 492 loads, 5,322 subject targets and 10,644 total targets. The finalizer's checks passed, but the manifest marks it `database_compatible=false`, and no upload occurred. A later answer to the pending count question said to keep 2,611 and provide the 50 exclusions or a corrected file. Treat the 2,661 candidate as provisional, not final; wait for exclusions/corrected roster before rebuilding.

The user clarified that the actual master-list count is correct. Recounted the supplied workbook: 2,661 nonblank, unique student numbers, no duplicates. Use all 2,661; 2,611 was not a real exclusion list. The 2,661 candidate contains 5,322 subject allocations, 2,661 adviser targets, 2,661 program targets and 10,644 total targets. The user prefers a consolidated summary; see `outputs/pilot_q2_target_import_preview_r02/PREUPLOAD_AND_PILOT_REVIEW.md`.

Refreshed the synthetic pilot preview at `outputs/pilot_q2_target_import_preview_r02/` using the old 45-account plan (15 each JHS, G11, G12) and the current 2,661 bundle. It has 180 links: 90 subject, 45 adviser and 45 program. The old 11GS02 synthetic slot maps to official 11GS01 and teaching section 11ME02. Subject pairs mirror a real-student allocation from each same section. No Auth accounts or database rows were created. Migrations are already applied, but no target-aware uploader is available and the main bundle is `database_compatible=false`.

## 2026-11-03 Q2 synthetic pilot import preparation

Prepared `outputs/pilot_q2_target_import_preview_r02/PILOT_IMPORT.sql` and `PILOT_IMPORT_README.md`. The import is restricted to the 45 existing synthetic accounts and their 180 target links. The SQL checks that accounts, active sections, teachers, subjects, the Be Brave program, and six published questionnaire banks already exist; it aborts if references do not match or if submissions already exist for the period. It updates only those synthetic students to current official sections, while their target rows follow the teaching section. It inserts the six period mappings and leaves `PILOT-SY2026-2027-Q2-FINALS-01` in draft. It creates no Auth accounts and does not import the 2,661-person roster. No database SQL has been run. Deploy the target-aware app before opening the period for student testing.
