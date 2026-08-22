# Faculty Evaluation Platform: Master Handoff Summary

This is the authoritative implementation handoff for the `new_eval` repository. It consolidates the backend measurement plan with the current Streamlit student portal, deployment decisions, security boundary, technical file map, known limitations, and next implementation sequence. Future conversations should inspect the repository and this document before changing either the student workflow or the scoring pipeline.

## 1. Project Purpose

The project replaces the previous practice of averaging only the first ten teacher-performance items and selectively reading qualitative comments. The target output is one defensible teacher rating on a 1-5 scale, while retaining component scores and evidence for internal review.

The revised evaluation has separate SHS and JHS question blocks because the wording differs by school level. Both levels use four analytical parts:

1. Instructional performance: 10 quantitative statements about the teacher.
2. Overall experience: 10 quantitative statements about the student's experience in the class.
3. Student self-evaluation: 5 quantitative statements about the student's own behavior and engagement.
4. Qualitative feedback: 3 open-ended questions for teacher-specific comments.

The repository now contains two Streamlit applications:

1. `student_app.py`: the primary student-facing portal and current deployment target.
2. `app.py`: the internal administrator-facing aggregation and methodology prototype.

The project is no longer planning Power Apps as the primary frontend. The adopted direction is a public Streamlit application endpoint with an application-level login, Supabase Auth, and Supabase PostgreSQL. The public GitHub repository must contain source code and unmistakably synthetic demo records only. Raw rosters, historical evaluation exports, credentials, secrets, and production responses remain outside Git.

The student section will come from the authenticated database profile. Students will never select their section or teacher freely; they will see only active roster assignments for their school level, grade, strand, section, and evaluation period.

The repository now includes an initial Supabase migration with indexed foreign keys, RLS policies, explicit student-to-teaching-assignment authorization, immutable versioned question banks, a unique submission constraint, and an atomic `submit_evaluation` RPC. A second migration publishes the current SHS and JHS instruments as version 1. On 2026-08-23, both migrations were applied successfully to the linked hosted Supabase project through CLI `2.115.0`; the Table Editor shows all 14 expected tables. The Streamlit portal is not yet connected to Supabase and still uses synthetic in-memory data.

### 2026-08-23 implementation checkpoint

- The public GitHub repository is `ronmarccharlesms/new_eval`, branch `main`.
- The fictional student preview is deployed at `https://feuhighschool-teacher-performance-evaluation.streamlit.app/`.
- The Supabase CLI is installed for macOS ARM64 under `~/.supabase/bin` and added to the zsh path.
- `supabase/config.toml` was generated, and the repository is linked to the hosted `feu-faculty-evaluation` project. Machine-specific `supabase/.temp/` state is ignored.
- Migrations `202608230001_initial_schema.sql` and `202608230002_question_banks_v1.sql` are applied remotely.
- The database contains two published version-1 question banks and 56 seeded question items: 28 SHS and 28 JHS.
- All three qualitative prompts are required. Students must enter substantive feedback or `N/A`/`Not applicable`; these placeholders are stored but excluded from qualitative evidence scoring.
- The frontend header, mobile evaluation container, selected-rating yellow state, light-mode review expander, and required qualitative validation have been corrected.
- The local suite contains 20 passing tests. Five tests statically inspect the migration security/versioning contract, but live authenticated RLS and concurrency tests are still pending.

## 2. Requirements Established in the Conversation

### Evaluation structure

For both SHS and JHS:

- Part 1 is instructional performance, ten Likert items.
- Part 2 is overall experience, the ten items beginning with the student's feeling of respect/safety and ending with the class's contribution to learning at FEU High School.
- Part 3 is student self-evaluation, five Likert items.
- Part 4 is qualitative teacher feedback, three open-ended responses.

SHS and JHS question wording is maintained separately in `feval/questions.py` and the example configuration.

### Final rating

The final teacher rating must aggregate all substantive components into a single 1-5 result. The student self-evaluation is not silently discarded: it is currently used as a response-quality/context adjustment rather than as a fourth additive teacher-performance component. This distinction is important because self-report about student behavior is not a direct measure of teacher performance.

### Qualitative analysis

The qualitative layer must not use VADER or generic sentiment analysis. It should report comments as interpretable statements, such as appreciated practices, constructive suggestions, and overall experience. The intended direction is semantic/context-based NLP that identifies meaning and teaching-related aspects rather than simply positive or negative polarity.

The current implementation is a transparent rule-based semantic aspect prototype. It is not yet an embedding model or a fully context-aware NLP system.

### Class imbalance and unequal exposure

Teachers may have one or two classes or as many as seven classes. A typical class has approximately 30-40 students. A raw average can therefore give unstable small-class estimates the same apparent certainty as estimates supported by many responses, while a raw student-level pool can overrepresent teachers with many sections. The implementation must account for:

- unequal response counts;
- clustering of students within classes;
- the number of classes taught;
- effective sample size rather than raw N alone;
- uncertainty and shrinkage toward a reference mean;
- response-rate and coverage information when the enrollment denominator is available.

### Weighting

The fixed 50-30-20 policy was implemented as an operational default, not because literature establishes that exact allocation. The research-based recommendation is to treat weights as a model-selection question and validate candidate weights against an external criterion, with stability and fairness checks. If no external criterion is available, the weights must be labeled institutional policy rather than empirically optimal.

## 3. Current Repository Map

### Top-level files

| Path | Function |
| --- | --- |
| `app.py` | Admin Streamlit application for upload, scoring, review, methodology display, and CSV downloads. |
| `student_app.py` | Primary student-facing Streamlit app: home, assigned teachers, four-step instrument, review, submission confirmation, history, help, and light/dark FEU styling. |
| `README.md` | Existing project README, setup instructions, method summary, and partial code map. |
| `HANDOFF_SUMMARY.md` | Authoritative cross-conversation project context, architecture decisions, statistical cautions, deployment state, and implementation sequence. |
| `CHANGELOG.md` | Append-only, timestamped implementation history with verification and commit references. |
| `requirements.txt` | Python dependencies for Streamlit, pandas, NumPy, SciPy, openpyxl, reportlab, and related runtime needs. |
| `.gitignore` | Ignores virtual environments, caches, local source data, and generated artifacts. |
| `supabase/config.toml` | Supabase CLI project configuration. It contains no database password or API secret. |
| `supabase/migrations/202608230001_initial_schema.sql` | Relational schema, indexes, triggers, RLS policies, grants, immutable-question guards, and atomic submission RPC. |
| `supabase/migrations/202608230002_question_banks_v1.sql` | Published SHS/JHS version-1 question-bank seed with 56 items. |
| `docs/supabase_setup.md` | Hosted project, migration, authentication, secret, and verification procedure. |

### `feval/` package

| Path | Function |
| --- | --- |
| `feval/__init__.py` | Package marker and public package boundary. |
| `feval/models.py` | Dataclasses and normalized data structures shared by ingestion, scoring, reporting, and portal code. |
| `feval/questions.py` | Separate SHS/JHS question banks; part definitions, IDs, question text, aliases, and construct boundaries. |
| `feval/ingestion.py` | Reads SharePoint-exported Excel/CSV files, cleans headers, maps metadata and Likert responses, and produces normalized exports. |
| `feval/scoring.py` | Item weighting, reliability, response-quality adjustment, teacher aggregation, qualitative integration, class ICC, shrinkage, effective N, and approximate intervals. |
| `feval/text.py` | Qualitative aspect extraction and statement generation. Uses transparent semantic frames and evidence cues; no VADER. |
| `feval/reporting.py` | Orchestrates text analysis and quantitative scoring into an `AnalysisReport`. |
| `feval/pdf_report.py` | Builds confidential teacher PDF reports from analysis results. Not currently wired into the admin UI. |
| `feval/sample_data.py` | Generates or provides synthetic admin-side sample data for demonstrations and tests. |
| `feval/student_portal.py` | Roster-scoped student assignment models, submitted-assignment filtering, stable evaluation keys, and pending-workflow logic. |
| `feval/student_demo_data.py` | Public-safe synthetic student profile, teacher assignments, and demo submissions. No historical identities are permitted here. |

### `tests/`

| Path | Function |
| --- | --- |
| `tests/test_pipeline.py` | Backend tests for question blocks, normalization/scoring, response-quality handling, qualitative output, aggregation, and weighting behavior. |
| `tests/test_student_portal.py` | Tests roster filtering, absence of a student-side section picker, removal of submitted assignments, and period-scoped evaluation keys. |
| `tests/test_supabase_schema.py` | Static migration-contract tests for RLS/revokes, question versioning, duplicate prevention, RPC grants, and question-seed parity. |

### `config/` and `docs/`

| Path | Function |
| --- | --- |
| `config/question_blocks.example.json` | Example externalized SHS/JHS question configuration. |
| `docs/scoring_methodology.md` | Detailed methodology, rationale, formulas, validation plan, governance notes, and research references. |

### Generated or ignored paths

These are not source files and should not be treated as missing implementation modules:

- `.venv/`
- `.git/`
- `__pycache__/`, `feval/__pycache__/`, and `tests/__pycache__/`
- `.pycache/`
- `supabase/.temp/`
- `.DS_Store`
- local source-data directories ignored by the repository

This handoff, demo-data sanitation, tests, and README updates form the public-safe baseline. The Git remote is `https://github.com/ronmarccharlesms/new_eval.git`, branch `main`. The user changed the repository to public so Streamlit Community Cloud can deploy it without consuming the workspace's single private-app allowance. The current tree contains synthetic identities only. Earlier Git history should still be audited before production if any superseded demo value was derived from a real person; changing the current file does not remove content from prior commits.

## 4. Current Computation Pipeline

The intended data flow is:

```text
SharePoint Excel/CSV export
        |
        v
feval.ingestion: clean, identify, normalize, validate
        |
        v
NormalizedExport: teacher, class/section, subject, student/response identity,
                  school level, item responses, open-ended responses
        |
        v
feval.text: semantic aspect evidence and statement summaries
        |
        v
feval.scoring: item weights, response-quality weights, class adjustment,
               teacher component scores, qualitative score, shrinkage, intervals
        |
        v
feval.reporting: AnalysisReport
        |
        +--> app.py: administrator dashboard and CSV exports
        +--> feval.pdf_report: confidential PDF report path
        +--> deployed Supabase schema; Streamlit auth/persistence integration pending
```

### Ingestion behavior

`feval/ingestion.py` currently:

- accepts `.xlsx`, `.xlsm`, `.xls`, `.csv`;
- cleans and deduplicates headers;
- maps common numeric and text Likert values to 1-5;
- uses fuzzy matching for question columns and common metadata fields;
- returns a normalized representation for scoring;
- preserves SHS/JHS selection through the question-bank definitions.

The main production issue is that actual SHS exports are in a wide multi-strand format. Teacher fields are split into columns such as `Teacher's Name (A)`, `Teacher's Name (H)`, and `Teacher's Name (S)`. Sections are split by ABM, GAS, HUMSS, and STEM, while subjects are split by grade and strand. Each row has one populated teacher/section/subject branch, but the current inference selects only the first matching branch.

This caused the current default SHS normalization to mark 8,012 of 8,988 rows as `Unspecified`. An in-memory coalescing check showed that all 8,988 rows can be assigned using the populated branch. The next backend change should reshape these branch columns into one canonical teacher-assignment record per response before scoring.

The JHS first-semester workbook normalized cleanly: 733 responses, 18 teachers, 7 sections, and no unspecified teachers.

### Scoring policy currently implemented

The operational defaults in `feval/scoring.py` are:

```text
WEIGHT_INSTRUCTIONAL = 0.50
WEIGHT_EXPERIENCE    = 0.30
WEIGHT_QUALITATIVE   = 0.20
CITC_FLOOR           = 0.10
```

These defaults are exposed as review-time controls in `app.py`, constrained to sum to 1.0. The code allows alternative policy weights, but the displayed default should not be described as literature-derived.

### Part 1 and Part 2

For each quantitative construct:

1. Validate usable Likert responses.
2. Calculate item-level descriptive statistics.
3. Calculate corrected item-total correlations.
4. Use item-level weights where permitted by the configured CITC floor.
5. Calculate row-level construct scores.
6. Aggregate at teacher/class level with response-count and cluster information.

The current implementation uses corrected item-total correlations as a pragmatic item-weighting mechanism. This is useful for a prototype but is not a substitute for a validated ordinal item-response or factor model.

### Part 3: student self-evaluation and RCI

The final five self-evaluation items are transformed into a response-context index (RCI):

```text
base = 0.40 + 0.60 * ((self_eval_mean - 1) / 4)
RCI  = clip(base * quality_factor, 0.40, 1.00)
```

The RCI affects the weight of a student's quantitative response. It is intended to reduce the influence of low-quality or internally inconsistent response patterns, not to punish students for reporting lower engagement.

Current response-quality checks include:

- instructional/full straightlining;
- a mismatch pattern in which self-evaluation is very low while the teacher construct is very high;
- a strategic mismatch flag only when mismatch and straightlining co-occur;
- a Mahalanobis-style multivariate outlier check where available.

Important governance issue: the RCI is an unvalidated local rule. It could reduce the voice of lower-engagement students or be mistaken for evidence about teacher quality. It must undergo sensitivity testing, human review, and fairness review before high-stakes use.

### Qualitative score

`feval/text.py` extracts aspect evidence from comments using transparent semantic frames. Current aspects include:

- clarity;
- classroom management;
- teaching strategies;
- student support;
- feedback and grading;
- materials and resources;
- timeliness and online responsiveness;
- pacing and workload;
- motivation.

The layer emits:

- appreciated-practice statements;
- constructive-suggestion statements;
- overall-experience statements;
- aspect counts;
- evidence coverage and confidence;
- representative evidence;
- verbose or insufficient-evidence flags.

It intentionally does not use VADER or generic sentiment as the primary method. However, it is currently lexical/rule-based. It can miss negation, paraphrase, sarcasm, mixed comments, and context-dependent meanings. The recommended next stage is sentence-level embeddings, such as a Sentence-BERT-family model, combined with a validated aspect taxonomy, evidence-span extraction, and human adjudication. Generic sentiment can remain an optional descriptive field, but it should not determine the teacher's qualitative rating.

### Teacher-level aggregation and uncertainty

The current code calculates or approximates:

- class-level means and variation;
- one-way class ICC;
- Kish effective sample size;
- cluster-adjusted effective N;
- approximate empirical-Bayes-style partial pooling toward a school/reference mean;
- approximate normal-theory 95% intervals;
- rank/rating outputs and flags.

The current interval is an approximate uncertainty interval, not a fully specified Bayesian credible interval. The implementation should eventually move to a hierarchical model with students nested in classes nested in teachers, with explicit treatment of ordinal outcomes and missingness.

The final composite currently combines Part 1, Part 2, and the direct qualitative score. Part 3 affects response weights through RCI but is not added as a fourth teacher-performance component.

## 5. Empirical Findings From Supplied Exports

These figures are from the local supplied data and are time/export-specific. They must be recalculated after the SHS branch-column reshape and before operational use.

### SHS first-semester export

Source: local ignored first-semester SHS export. The exact filename is intentionally omitted from the public repository.

- 8,988 response rows;
- 49 columns;
- 13 sheets, with response data on the primary sheet;
- teacher branches: A = 976, H = 4,020, S = 3,992;
- strand/section branches together account for all rows;
- coalesced in-memory proxy: 8,988 responses, 115 teachers, 79 sections, 47 subjects;
- Part 1 alpha approximately .953;
- Part 2 alpha approximately .974;
- one-way class ICC approximately .061;
- coalesced teacher-level means: Part 1 approximately 4.698, Part 2 approximately 4.688, qualitative score approximately 3.390;
- current composite mean in the proxy approximately 4.466;
- correlations: Part 1/Part 2 approximately .974; Part 1/qualitative approximately -.051; Part 2/qualitative approximately -.054.

The near-zero quantitative/qualitative correlations should not be interpreted as proof that qualitative evidence is invalid. They may indicate calibration differences, a restricted quantitative range, distinct constructs, lexical extraction limitations, or qualitative coverage differences. They do show that adding a 20% uncalibrated qualitative score can materially change rankings.

### JHS first-semester export

Source: local ignored first-semester JHS export. The exact filename is intentionally omitted from the public repository.

- 733 response rows;
- 18 teachers;
- 7 sections;
- no unspecified teachers after normalization;
- Part 1 alpha approximately .958;
- Part 2 alpha approximately .962;
- one-way class ICC approximately .030;
- Part 1/Part 2 teacher-level correlation approximately .927;
- Part 1/qualitative approximately .496;
- Part 2/qualitative approximately .406;
- Part 1 mean approximately 4.773;
- Part 2 mean approximately 4.764;
- qualitative mean approximately 3.338;
- current final mean approximately 4.507;
- mean RCI approximately .803;
- effective N approximately 10.42 to 50.39 across teacher summaries;
- total flagged responses approximately 574;
- qualitative verbose flags: 2;
- final teacher ratings approximately 4.454 to 4.675 in the examined output.

### Interpretation for the weighting question

The supplied data show very strong overlap between Part 1 and Part 2. Reliability is similar for both, so reliability alone does not justify 50% for instructional performance and 30% for overall experience. The qualitative score is on a lower center and narrower scale, so a 20% contribution may partly reflect calibration rather than a validated difference in teacher quality.

The strongest current conclusion is not that another fixed set of weights is proven. It is that the institution needs a calibration and validation study before presenting any weights as empirically optimal.

## 6. Literature and Standards Basis

No credible body of literature establishes an exact universal 50-30-20 allocation for this instrument. The literature supports a defensible measurement process, multiple evidence sources, reliability/precision analysis, fairness review, and validation against intended uses.

### Key sources

- American Educational Research Association, American Psychological Association, and National Council on Measurement in Education. *Standards for Educational and Psychological Testing*. Core implications: validity is use-specific; reliability/precision and fairness are required; evidence and intended consequences must be documented. [APA Standards page](https://www.apa.org/science/programs/testing/standards?clearcache=true)
- Measures of Effective Teaching project, Gates Foundation. Multi-measure teacher evaluation research supports combining measures and studying stability and validity rather than relying on one score. [MET final research report](https://www.gatesfoundation.org/ideas/media-center/press-releases/2013/01/measures-of-effective-teaching-project-releases-final-research-report)
- Spooren, Brockx, and Mortelmans (2013). Review of student evaluation of teaching validity, including dimensionality, bias, questionnaire design, and online administration. [Review](https://journals.sagepub.com/doi/abs/10.3102/0034654313496870)
- Uttl, White, and Gonzalez (2017). Meta-analysis questioning the consistency of the relationship between student ratings and student learning. [Study](https://doi.org/10.1016/j.stueduc.2016.08.007)
- Nulty (2008). Response rates and the use of multiple evaluation methods. [Study](https://www.tandfonline.com/doi/abs/10.1080/02602930701293231)
- Secondary-school generalizability research. Indicates that the number of student ratings matters for precision and that complex nesting can reduce generalizability. [Generalizability study](https://www.sciencedirect.com/science/article/abs/pii/S0191491X17300640)
- 2024 systematic review of student evaluation of teaching. Reviews classical measurement theory, generalizability theory, item response theory, many-facet approaches, and multiple error sources. [Systematic review](https://www.frontiersin.org/journals/education/articles/10.3389/feduc.2024.1329734/full)
- Boring, Ottoboni, and Stark (2023). Evidence on gender bias and the role of course characteristics, class size, and response conditions in student evaluations. [Open study](https://pmc.ncbi.nlm.nih.gov/articles/PMC9942858/)
- Sun and Yan (2023). Topic modeling of student evaluation comments, relevant to qualitative theme extraction and the limitations of short comments. [Study](https://link.springer.com/article/10.1007/s44217-023-00051-0)
- Reimers and Gurevych (2019). Sentence-BERT semantic embeddings, a technical foundation for the next qualitative-analysis stage. [Sentence-BERT](https://aclanthology.org/D19-1410/)

### What this literature supports

- validate the score for its intended administrative use;
- report reliability and uncertainty, not just a point estimate;
- model class/teacher nesting;
- collect sufficient responses and report response rates;
- test bias, differential functioning, and subgroup sensitivity;
- use multiple measures if the institution intends to make high-stakes decisions;
- treat qualitative comments as evidence requiring semantic validation, not as a sentiment number;
- avoid treating a locally selected weight vector as a universal research finding.

## 7. Recommended Quantitative Weight-Selection Method

Define teacher-level component scores:

```text
P1 = instructional performance score
P2 = overall experience score
Q  = calibrated qualitative evidence score
Y  = external criterion, such as structured observation or peer review
```

For candidate weights `w1`, `w2`, and `w3`:

```text
Composite(w) = w1*P1 + w2*P2 + w3*Q
subject to w1 >= 0, w2 >= 0, w3 >= 0, and w1 + w2 + w3 = 1
```

Select weights at the teacher level using grouped cross-validation, ideally leave-one-teacher-out or school/term holdouts. The objective should combine:

- predictive or convergent validity with `Y`;
- correction for measurement error and uncertainty;
- rank stability under bootstrap resampling;
- stability across SHS/JHS, subjects, terms, and class-size bands;
- a fairness penalty when rating or rank changes are concentrated in protected or structurally different groups;
- interpretability and administrative usability.

Report bootstrap intervals for the selected weights and show how teacher ratings change under plausible alternatives. Do not tune weights on the same observations used to claim validity.

Candidate sensitivity scenarios to report:

- 50/30/20: current operational policy;
- 40/40/20: equal direct quantitative constructs, qualitative retained;
- 50/35/15: instructional emphasis with lower qualitative influence;
- 60/25/15: strong instructional emphasis;
- 45/35/20: balanced policy scenario.

If there is no external criterion, the appropriate output is a sensitivity analysis and an explicitly labeled policy choice. A data-driven optimizer without an external criterion would optimize internal agreement, not teacher effectiveness.

Before comparing weights, calibrate P1, P2, and Q onto a comparable teacher-level scale. Qualitative evidence should not be given a lower or higher influence merely because the current lexical score has a different mean or variance.

## 8. Statistics Required for the Revised Evaluation

### Administrator-facing statistics

Every teacher report should expose, in readable form:

- final rating on the 1-5 scale;
- rating band and benchmark interpretation;
- Part 1 score;
- Part 2 score;
- qualitative score and statement summary;
- weighted contribution from each direct component;
- number of responses and eligible students;
- response rate;
- number of classes/sections and subjects;
- effective N;
- uncertainty interval and precision status;
- reliability status for the applicable school-level instrument;
- response-quality flag count;
- qualitative evidence coverage and representative statements;
- comparison with school, level, department, or subject benchmark;
- evaluation period, model version, question-bank version, and weight version.

### Technical statistics

Data integrity and coverage:

- raw rows, valid rows, duplicate rows, and invalid rows;
- missingness by metadata and item;
- unique students, teachers, assignments, sections, subjects, and periods;
- teacher/section/subject mapping completeness;
- invalid Likert values and recoding counts;
- eligible-student denominator and response rate;
- one-response-per-student-per-assignment compliance;
- completion-time and duplicate-submission indicators where available.

Item and distribution statistics:

- N, mean, median, standard deviation, minimum, maximum;
- response-category frequencies;
- missingness, floor and ceiling effects;
- skewness and range restriction;
- corrected item-total correlation;
- inter-item correlation;
- ordinal/polychoric correlation where appropriate;
- item discrimination and item information for IRT development.

Reliability and precision:

- Cronbach alpha, with ordinal alpha where justified;
- McDonald's omega;
- standard error of measurement;
- bootstrap confidence intervals;
- item-deletion sensitivity;
- separate SHS/JHS and period estimates;
- teacher-level precision and minimum-reporting thresholds.

Construct validity:

- exploratory and confirmatory factor analysis;
- one-factor versus two-factor structure for Part 1 and Part 2;
- loadings and cross-loadings;
- CFI, TLI, RMSEA, and SRMR where CFA is appropriate;
- convergent and discriminant validity;
- SHS/JHS and period measurement invariance;
- differential item functioning.

Response quality:

- missing response rate;
- within-response standard deviation;
- straightlining and long-string length;
- completion time if captured;
- duplicate or suspicious identity patterns;
- multivariate outlier score;
- RCI distribution and threshold sensitivity;
- teacher/self mismatch rates;
- response-weight distribution and influence diagnostics.

Clustering and class imbalance:

- class-level and teacher-level means and variances;
- class, teacher, and subject ICCs;
- design effect;
- raw N versus Kish effective N;
- cluster-adjusted effective N;
- number of classes per teacher;
- standard error and uncertainty interval;
- shrinkage amount and reference mean;
- rating/rank stability after excluding one class;
- sensitivity to equal-class versus equal-student aggregation.

Qualitative evidence:

- comment count and comment coverage;
- empty-comment percentage;
- word/sentence length;
- aspect prevalence;
- unknown or unclassified comment rate;
- evidence-span coverage;
- semantic confidence;
- representative-statement reproducibility;
- qualitative score sensitivity to sparse comments;
- human-NLP agreement;
- precision, recall, and F1 for aspect/evidence extraction;
- Cohen kappa or Krippendorff alpha for human coding;
- false-positive and false-negative rates for concerns.

External validity and weight selection:

- correlations with observation or peer-review scores;
- incremental validity and change in R-squared;
- grouped cross-validation performance;
- leave-one-teacher-out validation;
- bootstrap weight intervals;
- convergence and discriminant validity;
- longitudinal stability;
- rating-band and ranking changes by candidate weight vector.

Fairness and sensitivity:

- response rate and missingness by relevant group;
- mean and variance by relevant group;
- DIF and measurement-invariance results;
- flag rates and RCI distributions by group;
- residual differences after accounting for class and subject;
- rating/rank changes under alternate weights;
- sensitivity with RCI disabled;
- sensitivity with qualitative component omitted or recalibrated;
- small-class versus large-class error and shrinkage comparisons.

Governance and reproducibility:

- data lineage from SharePoint export to report;
- data-export timestamp;
- question-bank version;
- scoring-model version;
- weight-policy version;
- calibration period;
- software/dependency versions;
- reproducible input hash or manifest;
- privacy/access audit trail;
- suppression rules for small or identifiable groups.

## 9. Current Limitations and Risks

1. SHS ingestion does not yet coalesce the strand/grade branch columns into a canonical long format. This is the highest-priority correctness fix.
2. The normalized backend model does not yet have a robust assignment identity containing student, teacher, subject, section, school level, term, academic year, and evaluation period.
3. The current class ICC and interval calculations are approximate and are not a full hierarchical ordinal model.
4. The RCI is a local, unvalidated response-quality rule and may reduce the voice of some students.
5. Qualitative analysis is transparent but lexical; it is not yet contextual embedding-based NLP.
6. The direct qualitative score is not yet calibrated to the quantitative latent scale.
7. The final composite uses only student-source evidence. It is not a complete multi-measure teacher evaluation system unless observations, peer review, or other valid evidence are added.
8. Response-rate denominators are not currently available in the evaluation export and must come from roster/enrollment data.
9. `feval/pdf_report.py` exists but is not wired into the admin interface.
10. The PDF report contains a hardcoded 0.50/0.30/0.20 formula note even when the admin sliders use another weight vector; it should display the actual run-time weights.
11. The deployed student app is still a synthetic, in-memory demonstration. Source reloads reset submissions. It has no production authentication, database, password reset, audit trail, or persistent response storage.
12. A public Streamlit endpoint is discoverable. No student profile, roster, teacher assignment, or evaluation content may be disclosed before successful application-level authentication in production.
13. Supabase RLS, grants, immutable-question guards, and duplicate-submission constraints are deployed, but they have not yet been exercised with real authenticated student/admin roles. Static SQL inspection is not a substitute for live policy tests.
14. Current tests are primarily unit-level and static migration-contract tests. Production readiness still requires fixture-based export tests, live database policy tests, concurrency/duplicate-submission tests, authentication tests, privacy tests, and repeated visual QA.

## 10. Student Streamlit and Supabase Handoff

### Implemented frontend

`student_app.py` implements the approved FEU High School mobile workflow:

1. Home with synthetic student profile, evaluation period, and progress.
2. My Teachers with six roster-authorized subject/teacher assignments.
3. Four evaluation steps: Teacher Performance (10), Student Experience (10), Student Self-Evaluation (5), and Additional Comments (3).
4. Review and explicit confirmation before submission.
5. Submission success, remaining assignments, history, help, fixed bottom navigation, and light/dark themes.

The interface does not contain a section selector. `feval/student_portal.py` filters assignments by active status, school level, grade, strand, section, and period. Unit tests include a deliberately out-of-section assignment and verify that it is excluded.

The public demo records use `Demo Student`, `Teacher Alpha` through `Teacher Eta`, `example.invalid` email addresses, and `*-DEMO` section identifiers. These values are deliberately synthetic and must not be replaced with production records in source code.

### Authentication decision

Streamlit Community Cloud sharing authentication is not the student identity system. The adopted production path is a custom FEU login screen in `student_app.py` backed by Supabase Auth email/password accounts. Microsoft Entra OIDC through Streamlit remains a possible later option if school IT can provide an app registration, tenant configuration, redirect URI, client ID, and client secret.

Passwords must be created and verified by Supabase Auth. Do not create a custom password table, store plaintext passwords, cache authenticated clients globally, or commit credentials. A batch account-provisioning script, when added, must run as an administrator-only local tool with its secret key supplied outside Git.

### Authorization and database boundary

Authentication answers who the student is. PostgreSQL Row Level Security and constraints must determine what that identity may access. The production flow is:

```text
Public Streamlit URL
        |
        v
FEU login screen -> Supabase Auth -> authenticated user UUID
        |
        v
student profile -> active roster assignments -> permitted evaluations
        |
        v
atomic submission transaction -> PostgreSQL responses and audit event
```

The deployed migration is designed to enforce all of the following independently
of the UI. These guarantees must still be verified using authenticated alpha-test
accounts before any real roster is imported:

- a student can read only their own active profile;
- a student can read only assignments connected to their roster;
- the assigned teacher/subject/section cannot be supplied freely by the client;
- a student can create only their own submission for an open period;
- one submission is allowed per student, assignment, and evaluation period;
- response items must belong to the submission and current question-bank version;
- students cannot read raw responses after submission unless policy explicitly permits it;
- teachers never receive student-identifiable raw responses;
- administrators use a separate role and interface;
- every accepted submission records timestamps and applicable instrument/model versions.

Use a composite unique constraint such as `(student_id, assignment_id, evaluation_period_id)` and an atomic database transaction or function for submission. A Streamlit button check is insufficient because concurrent requests can bypass it.

### Implemented relational model

- `profiles`: authenticated identity, role, active status;
- `students`: profile link, school level, grade, strand, section;
- `teachers`;
- `subjects`;
- `sections`;
- `teaching_assignments`: teacher, subject, section, academic period;
- `student_assignments`: student-to-teaching-assignment authorization;
- `evaluation_periods`: opening/closing dates and active status;
- `evaluation_period_instruments`: immutable period-to-question-bank selection;
- `question_banks` and `question_items`: versioned SHS/JHS instruments;
- `evaluation_submissions`: one row per authorized student assignment and period;
- `evaluation_responses`: version-bound Likert or text responses by question item, with `N/A` retained but marked non-substantive;
- `submission_audit_events`: accepted/rejected submission events without passwords or response text in logs.

Foreign-key columns and common RLS predicates are indexed in the initial
migration. Policies use the authenticated user ID and roster relationships.
Elevated Supabase secret/service-role credentials must remain server-side and
must not be used for ordinary student requests because they bypass RLS.

## 11. Recommended Next Implementation Sequence

### Completed deployment foundation

1. Public-safe synthetic records and repository exclusions are in place.
2. `student_app.py` is deployed from `main` on Streamlit Community Cloud as a fictional preview.
3. The hosted Supabase project is created and linked through the CLI.
4. The initial schema/RLS/RPC migration and the SHS/JHS question-bank migration are deployed.

### Authentication and persistence next

5. Configure Supabase email/password authentication for a small synthetic alpha cohort; keep public signup and anonymous access disabled.
6. Add only the project URL and publishable key to local/Streamlit secrets. Never expose the secret/service-role key to the student application.
7. Build custom login, logout, session refresh, and password-reset handling in `student_app.py` using per-session Supabase Auth tokens.
8. Replace demo roster reads with RLS-governed profile, student-assignment, teacher, subject, period, and question-bank queries.
9. Replace in-memory submission with the `submit_evaluation` RPC.
10. Run live cross-section, duplicate-submission, raw-response-read, expired-session, closed-period, and administrator-access policy tests using synthetic accounts.
11. Add an administrator-only provisioning/import script for synthetic alpha accounts, then an approved roster import path.
12. Complete alpha testing before importing real student records or accepting real responses.

### Backend correctness

13. Implement SHS branch-column coalescing and add a fixture test asserting complete teacher/section/subject assignment on the supplied SHS structure.
14. Add canonical assignment and evaluation-period identities to normalized administrator records.
15. Add enrollment denominators so response rates and coverage can be reported.
16. Make PDF formula text use actual run-time weights.

### Measurement validation

17. Add teacher/class/subject/period identifiers to all diagnostics.
18. Add ordinal reliability, omega, bootstrap intervals, and item-deletion reports.
19. Run EFA/CFA and measurement-invariance checks separately for SHS and JHS.
20. Fit a hierarchical model for student responses nested in classes and teachers.
21. Calibrate qualitative evidence against a human-coded sample and comparable reference scale.

### Weight, NLP, and governance

22. Define an external criterion with management and a psychometrician, then run candidate-weight sensitivity and grouped validation.
23. If no external criterion exists, document the selected weights as institutional policy pending validation.
24. Compare rules, embeddings, and supervised aspect/evidence extraction on a human-coded comment set.
25. Add model versioning, data manifests, privacy notices, retention rules, suppression thresholds, role-separated administration, and review logs.

## 12. Source Data Inventory

Local ignored data used in the earlier backend analysis include first- and second-semester SHS strand exports, combined SHS exports, JHS exports, and historical TPE CSV snapshots. Exact filenames are intentionally omitted from this public handoff. These files remain under the ignored `Students Evaluation/` directory on the authorized local machine and are not prerequisites for running the fictional frontend preview or unit tests.

A fresh checkout must not attempt to download or reconstruct these private exports. Backend recalculation requires an authorized operator to place approved source files in the ignored local directory, verify the export schema, and document the checkout-specific input manifest without committing the data.

## 13. Reproduction Commands

From the repository root:

```bash
./.venv/bin/python -m unittest discover -s tests
PYTHONPYCACHEPREFIX=/tmp/feval_pycache ./.venv/bin/python -m py_compile app.py student_app.py feval/*.py tests/*.py
./.venv/bin/streamlit run app.py
./.venv/bin/streamlit run student_app.py
```

The current suite contains 20 tests: 10 aggregation/scoring tests, 5
student-portal tests, and 5 static Supabase migration-contract tests. The suite
includes guards for synthetic public identities, required qualitative prompts,
question-seed parity, RLS/revokes, immutable question versions, RPC grants, and
database duplicate prevention. These SQL tests inspect migration text; live
authenticated policy and concurrency tests remain required. The compile command
uses a temporary bytecode location because the local macOS environment previously
encountered a cache-permission issue.

Streamlit Community Cloud deployment coordinates:

```text
Repository: ronmarccharlesms/new_eval
Branch: main
Main file path: student_app.py
Public URL: https://feuhighschool-teacher-performance-evaluation.streamlit.app/
```

No secrets are required for the fictional preview. When Supabase is connected, configure deployment credentials through Streamlit Community Cloud Secrets; never add them to the repository.

## 14. Handoff Prompt for the Next Conversation

Use this repository and this document as the starting context. The hosted
Supabase schema is deployed; the immediate product task is integrating Supabase
Auth and RLS-governed persistence into `student_app.py`, starting with synthetic
alpha accounts. Use the publishable key for ordinary student requests and the
`submit_evaluation` RPC for atomic submission. Do not connect real students or
responses until live RLS, role-separation, closed-period, session-expiry, and
concurrency tests pass. In parallel, the highest-priority scoring correctness
item remains SHS branch-column coalescing while preserving JHS behavior.
Recalculate historical statistics after that fix. Do not present 50-30-20 as
research-derived. Preserve the no-VADER requirement and keep qualitative
reporting as semantic statements supported by evidence.
