# Verification Log

| Date | Task/revision | Check | Result | Evidence/limitations |
|---|---|---|---|---|
| <!-- date --> | initialization | project capsule created | passed | application code unchanged |
| 2026-10-23 | roster v2 | Full unittest suite | 73 passed | Includes allocation, mixed-group, adviser-exclusion and checksum tests; not live RLS/load validation |
| 2026-10-23 | Supabase health | Dashboard and aggregate SELECT queries | Healthy; 21 MB | 0 Health Advisor errors/warnings; Security Advisor has 3 warnings and 8 info; no row/schema/Auth mutation |
| 2026-10-23 | roster v2 | Compilation, command help, whitespace | passed | New staging SQL remains an undeployed proposal |
| 2026-11-03 | documentation synchronization | Search for stale migration status, period/batch codes, and pilot steps; `git diff --check` | passed | Historical dated changelog and archived internal guide intentionally retained; no Supabase or GitHub operation |

## 2026-10-23 assignment-priority correction
- Full unittest suite: 76 tests passed; synthetic regression checks reject secondary inclusion and accept overload inclusion.
- Independent real-data assertions: every student has 2+1+1 targets; subject teachers distinct, adviser excluded, all selected loads primary. User-confirmed science regular/overload pair present; named WR overload classified per subject.
- All current source-file hashes match previous review. Diff whitespace check passed. Workbook rendering/read-back recorded in private handoff.

## 2026-10-23 target-instrument portal follow-up
- Python compilation passed for the Streamlit app, portal models/client, and local instrument definitions.
- `git diff --check` passed.
- No unittest suite, Streamlit browser run, Supabase migration, or live RLS/RPC acceptance check was performed for this follow-up. No hosted write occurred.

## 2026-10-23 required typed qualitative feedback correction
- Python compilation passed for the Streamlit app and portal modules.
- Focused payload checks confirmed the three instruments send 3, 2, and 4 required qualitative answers as `text_value`, each with a null `rating_value` and no N/A flag.
- SQL seed inspection confirmed all 9 qualitative items are required and the RPC stores text without setting `is_not_applicable`.
- `git diff --check` passed. No live Supabase migration or RLS/RPC test was performed.

## 2026-10-23 homepage evaluation-period progress review
- Python compilation and `git diff --check` passed.
- Focused calculation confirmed 2/4 current targets renders 50% and excludes an extra stale target ID.
- No browser or live Supabase check was performed.

## 2026-10-23 questionnaire catalog split
- Split the unshipped target-aware SQL into a catalog migration and a roster-gated operational migration; confirmed the catalog seeds three instrument types for each of JHS and SHS without inserting period mappings or student targets.
- Full unittest suite: 78 passed. Python compilation and `git diff --check` passed.
- No migration was applied or linted against Supabase; no live account-visibility/RLS check or hosted write was performed. Existing pilot accounts cannot see the banks from catalog-only deployment because access requires period mappings and target assignments.

## 2026-10-23 Markdown synchronization
- Updated the README, handoff, Supabase setup/lifecycle, synthetic pilot workflow, roster import, target portal, changelog, and Workbench notes to distinguish the three hosted migrations from the two unapplied proposals and to record the pilot-account visibility requirements.
- Marked the ignored internal guide as a historical snapshot and clarified that final questionnaire wording does not establish psychometric validity or approve a new scoring method.
- `git diff --check` passed; no application or database behavior changed in this documentation-only pass.

## 2026-11-03 Q2 roster finalization
- Finalized a private local payload from the latest edited SubjectLoads workbook and the 2026-2027 SHS/JHS Canvas terms. Source workbook unchanged; no Supabase write.
- Bundle checks passed: 2,659 students, 107 teachers, 492 active loads, 5,318 subject targets, 2,659 adviser targets, 2,659 program targets, 10,636 total targets, and 73 adviser sections with no missing adviser IDs.
- Importer read/manifest/checksum and allocation validations passed. All students have exactly two distinct subject teachers plus adviser/program targets. Collado is sole UCSP target teacher on the seven linked sections; the three specified section-2 Science loads are absent. Student names/emails are omitted from the payload.
- New finalization/uploader scripts compiled successfully; `git diff --check` passed for changed tracked files.
- Final payload rebuild after subject-name inclusion passed the uploader's local checksum/allocation validation. CSV archive is 74,327 bytes; serialized JSON request is 3,593,302 bytes. The latter is not a measurement of stored Postgres size.
- Superseded: 5,211/107 counts and the forced low-load full-coverage rule were incorrect; the user's small-class rule excludes Canvas `_SM` courses.
- Corrected local bundle validation: 27 `_SM` Canvas course records excluded; 2,659 students, 107 teachers, 492 loads, 5,318 subject targets, 2,659 adviser targets, 2,659 program targets, 10,636 total targets; all students have exactly two distinct subject teachers. Subject allocation basis is 5,285 regular / 33 advisory-secondary. All 107 teachers have 7–80 subject invitations. `read_bundle` checksum/row counts and student target distribution passed. No database write occurred.
- The Supabase staging proposal and target-aware migration remain unapplied; no live Supabase staging, activation, account provisioning, or app deployment check was performed.

## 2026-11-03 Q2 subject catalog normalization
- Regenerated `outputs/roster_v2_supabase_q2_subject_catalog_r06/` without modifying the reviewed workbook. The output retains 2,659 students, 492 subject loads, 5,318 subject targets, and 10,636 total targets.
- Verified all 68 payload subject codes are included in `supabase/proposals/202611030001_subject_catalog_cleanup.sql`; no canonical-name mismatches remain against the finalizer mapping.
- Verified PR2 variants: PR2A 7 loads (ABM and GAS), PR2H 5, PR2S 20; HOPE4 16 loads and HOPE3 0; EC/MK combined labels 0; PG and PPG titles remain distinct.
- Python compilation and `git diff --check` passed. This is local verification only; no SQL was executed against Supabase and ALPHA reference counts remain unknown until reviewed in SQL Editor.

## 2026-11-03 Q2 entity relationship audit
- Subject export: 82 rows; 68 active, 14 inactive. Active code set exactly equals the Q2 payload's 68 subject codes; no active subject titles duplicate.
- Local target/link audit: 2,659 students, 74 official sections, 73 teaching sections, 107 teachers, 492 unique section-subject-teacher loads, and 10,636 targets. Zero missing load links, official-section mismatches, unknown teacher references, adviser mismatches, or program mismatches.
- Confirmed the user-directed `11GS01` -> `11ME02` shared teaching/adviser mapping and marked it approved in generated output only. The XLSX remains unchanged.
- Python compilation and `git diff --check` passed. No roster data have been staged or activated in Supabase; the legacy v2 uploader is not compatible with this target-aware bundle.
- Two active schedule loads have no enrolled students in this Q2 roster: 11AD02 / ARTS1 / Basbas (202290076) and 11HS14 / LCS / Ignacio (202290164). These are pending source review before upload.
- Oct 28 JHS/SHS grade export reconciliation used only SIS IDs for student/course/section/term and enrollment state, not grade values. Of 20,163 active rows, 244 `_SM` rows were excluded; 19,919 regular rows represent 2,708 unique students. Compared with the 2,659-student Q2 bundle, 49 active students are additional (4 JHS, 45 SHS), all with a single normalized section that exists in the reviewed roster. Three students show strong section-change candidates: G10-2/G10-1, 11PSY02/11PSY01, 12A02b/12A03a. This is dated evidence and does not establish status after the exports; no roster bundle was regenerated or uploaded.
- User confirmed the Q2 population remains 2,659. The imported Nov 2 `users.csv` has 48 of the 49 unmatched accounts suspended and one active. All 49 have at least one grade-60 row, but 214 of the current 2,659 students also have at least one grade-60 row; 14 have grade 60 across all regular-course rows. Thus grade 60 alone cannot identify dropped students. Keep the 49 excluded per the approved list and flag the one active unmatched account separately. The enrollment CSV has 1,022 active and one invited rows, which conflict with user-level status. No roster or Supabase changes.
- The user then updated the final population to 2,611 and supplied a new workbook. Inspection found 2,661 unique rows, no duplicates or hidden rows; it includes the prior 2,659 plus two students. All 2,661 appear in the active non-small-class grade export. The imported user CSV shows 2,659 active and two suspended. This does not identify 50 exclusions; no roster payload was rebuilt and no Supabase changes were made.
- A 2,661-student candidate was subsequently generated after the direct instruction to use all rows: 5,322 subject targets, 2,661 adviser targets, 2,661 program targets, and 10,644 total. The finalizer's embedded checks completed; the manifest remains `database_compatible=false`, and no upload occurred. The user's later answer to the pending count question says to keep 2,611 and provide exclusions/corrected list, so this candidate is provisional, not final.
- The user clarified the master list's actual count is authoritative. Recounted it: 2,661 nonblank unique student numbers, zero duplicates; use all 2,661. Refreshed the synthetic pilot preview: 45 existing accounts, 180 target links, 15 per JHS/G11/G12, including the approved 11GS02 -> 11GS01/11ME02 mapping. The preview is local only. No Auth or database writes occurred; the full roster is still not compatible with the available legacy uploader.

## 2026-11-03 Q2 synthetic pilot import preparation
- Rendered the SQL package from `pilot_target_import_preview.csv` using `scripts/render_target_pilot_import_sql.py`. Embedded local checks confirmed 45 distinct synthetic keys, 15 accounts in each JHS/G11/G12 cohort, and exactly two distinct subject teachers plus one adviser and one program per account (180 links total).
- Confirmed the output period is draft-only, target type counts are 90/45/45, and SQL checks required account and roster references and six published banks, with transaction guards for missing references or existing period submissions.
- Static artifact preparation only; no Supabase connection, account creation, migration, SQL execution, or remote write occurred. SQL Editor execution remains a later user action after the target-aware app is deployed and prerequisites are present.
