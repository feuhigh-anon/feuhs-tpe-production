# Psychometric Pipeline Validation and Replacement Plan

**Date:** 2026-09-08  
**Status:** Validation complete; replacement design pending instrument approval  
**Scope:** Current SHS/JHS analysis pipeline and the attached provisional TPE candidate

## Executive Decision

The current pipeline is operationally testable, but it is still a measurement prototype rather than a validated psychometric scoring system. Keep the current pilot period and its scoring version stable for auditability. Do not replace the scorer or reinterpret pilot scores until the revised instrument is approved and a versioned validation study is complete.

The attached PDF is a plausible candidate for a future TPE question-bank version, but it must remain provisional. It should not be mapped into the current scorer by column position or silently mixed with the current question bank.

## Required Measurement Preflight

### Task classification

Measurement/psychometric analysis with descriptive teacher-level reporting. The intended use is evaluation and instructional improvement; personnel or disciplinary use has not been established by the current evidence.

### Target or estimand

The desired future estimand is a teacher-level, context-adjusted estimate of observed student-perceived teaching practice for a defined evaluation period, subject, section, and school level. It is not currently justified as a causal estimate of teacher impact, student learning gain, or an employment-risk probability.

### Unit of analysis

- Response: one student's evaluation of one teacher assignment in one period.
- Cluster: responses are nested within section/class, teaching assignment, teacher, subject, grade, and school level.
- Text: three prompt-specific responses per student-assignment evaluation.
- Report: teacher-period aggregate with class coverage and uncertainty.

### Primary risks

- The current item structure and the attached candidate instrument are different.
- Current item weights are estimated from the same data used for scoring, creating instability and possible overfitting.
- Student self-evaluation is converted into response credibility weights without validation that this improves measurement or fairness.
- The current qualitative score is heuristic and automatically contributes 20% of the final rating without human-coded criterion validation.
- Cronbach's alpha is reported, but no factor structure, ordinal reliability, measurement invariance, or item-fit evidence is available.
- The current empirical shrinkage is not a fully specified multilevel measurement model.
- Small or nonrepresentative teacher/class groups can produce unstable comparisons.
- Student ratings may reflect subject, class climate, schedule, workload, modality, or opportunity to observe rather than teacher performance alone.

### Minimum evidence for claims

Before an official replacement score is used for comparative or personnel decisions, require approved content specifications, cognitive review, pilot response evidence, domain-level reliability/precision, dependence-aware uncertainty, subgroup/invariance checks where sample sizes permit, and documented governance approval.

## Current Pipeline Validation

### Source-of-truth implementation

The current pipeline is:

1. `feval.questions` defines separate SHS and JHS version-1 blocks.
2. `feval.ingestion` maps export columns and normalizes Likert/text responses.
3. `feval.scoring` calculates item-discrimination-weighted quantitative scores, bounded self-evaluation response weights, heuristic response flags, fixed component weights, empirical class adjustment, and partial-pooled teacher ratings.
4. `feval.text` detects semantic frames and produces prompt-specific phrase summaries plus a bounded qualitative evidence score.
5. `feval.reporting` assembles the analysis tables.
6. `feval.pdf_report` produces the teacher-facing aggregate report.

### Current instrument contract

The current version-1 model contains:

| Current block | Current count | Current role |
| --- | ---: | --- |
| Faculty / instructional performance | 10 | Direct teacher-performance score |
| Overall learning experience | 10 | Direct component of teacher score |
| Student self-evaluation / RCI | 5 | Response-weight input, not direct score |
| Qualitative feedback | 3 | Heuristic text evidence and report narrative |

### Current scoring behavior

The current default composite is:

```text
0.50 * instructional performance
+ 0.30 * overall learning experience
+ 0.20 * qualitative evidence
```

Within the two quantitative teacher-facing blocks, item weights are derived from corrected item-total correlations with a floor of `0.10`. Student self-evaluation is transformed into a bounded response weight with a floor of `0.40`, then reduced by response-pattern flags. Qualitative evidence is converted to a bounded 1-5 score using cue dictionaries, semantic frames, comment volume, and shrinkage toward a quantitative reference mean. Teacher ratings are then partially pooled using an empirical standard-error calculation and class ICC adjustment.

These are transparent prototype rules, but transparency does not establish validity. The current code does not fit an ordinal IRT model, CFA/SEM, multilevel latent model, generalizability model, or human-validated qualitative scoring rubric.

### Executed validation

Using the repository's synthetic demo exports:

- Full unittest suite: **48 tests passed**.
- SHS pipeline: 90 rows, 3 teachers, 10 faculty items, 10 experience items, 5 RCI items, 3 text prompts.
- JHS pipeline: same synthetic structure and same resulting diagnostics, so the demo does not validate SHS/JHS measurement differences.
- Synthetic instructional alpha: approximately **0.664**.
- Synthetic experience alpha: approximately **0.949**.
- Synthetic class ICC: **0.0000** for the demo arrangement.
- Synthetic item-weight range: approximately **0.045 to 0.186**.
- Synthetic mean response-weight range by teacher: approximately **0.806 to 0.849**.
- Synthetic effective-response-count range by teacher: approximately **29.2 to 29.5**.
- Synthetic qualitative-score range: approximately **3.484 to 3.570**.

These numbers are smoke-test outputs, not population estimates. The demo generator is not an external validation sample and should not be used to justify score thresholds or reliability claims.

## Attached Candidate Instrument Review

The attached PDF has:

- 15 teacher-evaluation Likert items in Part I.
- 5 student self-evaluation Likert items in Part II.
- 3 qualitative prompts in Part III.
- Alignment labels such as PPST, FEUHS.BB, FEUHS.SCL, FEUHS.BL, and FEUVM.

### Contract mismatch

The candidate cannot be passed through the current version-1 scorer without a new instrument adapter because:

- Candidate Part I has 15 teacher items, while current version 1 has 10 faculty items plus a separate 10-item experience block.
- Candidate Part II has 5 self-evaluation items, while current version 1 has 15 self-related items: 10 experience items and 5 RCI items.
- The candidate's 5 self-evaluation items resemble the current RCI purpose, but wording and stable keys differ.
- Candidate Part III prompts are similar but not identical to the current SHS prompts.
- Alignment labels are content-map metadata; they must not become hidden score weights.

### Content and response-design risks

The candidate contains useful domains, but several items are multi-construct or conditional. Examples include clarity plus real-life connection, strategy variety plus effectiveness, questioning plus student voice plus independent reasoning, punctuality plus preparation plus engagement, and fairness plus respect plus safety. Canvas use, attendance follow-up, differentiation, and institutional-value alignment may not be equally observable for every student or subject.

Recommended candidate changes before freezing:

1. Define domains and an item blueprint before deciding score weights.
2. Split or narrow double-barreled items where the interpretation matters.
3. Add `Not observed / Not applicable` when a student lacks a fair opportunity to observe the behavior.
4. Keep institutional-alignment items separate from the core teaching-practice score unless governance explicitly defines that construct.
5. Avoid causal wording such as motivation being caused by the teacher.
6. Provide clear anchors and confidentiality instructions in the digital form.
7. Preserve separate SHS and JHS wording and calibration unless linking evidence is later established.
8. Keep the three qualitative prompts, but request specific examples and allow `N/A` when no additional comment is available.

## Replacement Design

### Phase 0: Protect the current pilot

- Keep the current question-bank version immutable.
- Label current reports with the instrument/scoring version.
- Do not combine current-pilot responses with future-instrument responses.
- Preserve raw responses, normalized exports, scoring configuration, and generated reports.
- Treat current scores as formative/provisional unless institutional policy states otherwise.

### Phase 1: Approve the instrument contract

Create a new versioned SHS and JHS question bank only after approval of:

- item wording and stable keys;
- domain membership;
- required and N/A behavior;
- response anchors;
- alignment metadata;
- intended use and score interpretation;
- minimum response and suppression rules;
- confidentiality and student-safety language.

The current Supabase schema already supports immutable question-bank versions. The future instrument should use a new version rather than editing version 1 in place.

### Phase 2: Establish a transparent baseline scorer

Before fitting a complex model, implement a simple interpretable baseline:

- equal item weights within pre-specified domains;
- domain scores reported separately;
- no self-evaluation-based deletion or credibility penalty;
- student self-evaluation reported descriptively or used only in a pre-specified sensitivity analysis;
- qualitative feedback summarized separately and not automatically added to the numeric score;
- minimum response/class coverage rules and uncertainty intervals.

This baseline is necessary for detecting whether a replacement model materially changes decisions.

### Phase 3: Validate the measurement structure

For SHS and JHS separately, and only with adequate sample size:

- inspect response distributions, missingness, N/A use, ceiling effects, and completion time;
- conduct cognitive interviews with students;
- use EFA only for exploration and CFA/ordinal factor modeling for a pre-specified structure;
- compare competing domain structures rather than assuming one total factor;
- evaluate ordinal reliability using omega or model-based precision alongside alpha;
- inspect item-rest relationships and local dependence;
- evaluate measurement invariance or differential item functioning across school level, grade, subject, modality, and approved student groups where sample sizes permit;
- do not interpret high internal consistency as proof of validity.

### Phase 4: Account for clustered data

Use a pre-specified multilevel model or generalizability framework with teacher and class/section structure. The model should distinguish, as supported by data:

- teacher-period signal;
- class/section context;
- student response tendencies;
- item effects;
- subject/grade/modality context.

Use cluster-aware uncertainty and report the number of classes, raw respondents, effective information, and interval width. Do not treat every student response as independent evidence of teacher quality.

### Phase 5: Validate qualitative interpretation

- Sample comments from all three prompts and relevant school levels.
- Create a human coding rubric based on the approved domains.
- Use at least two trained coders for a validation subset.
- Measure agreement and adjudicate disagreements.
- Compare human-coded themes with the automated aspect output.
- Use NLP for organization and retrieval first; do not make it an automatic numeric component until criterion validity, stability, and governance are demonstrated.
- Preserve the original text for authorized review and suppress identifying details in teacher reports.

### Phase 6: Decision and reporting validation

Compare the baseline and candidate models using held-out periods or group-aware resampling where possible. Report:

- score correlation and rank changes;
- teacher-level interval changes;
- sensitivity to missingness, N/A handling, item weighting, and class clustering;
- subgroup and subject/grade patterns;
- false precision or unstable classifications;
- examples where the model changes an administrative decision.

No verbal score bands should be introduced until score-use policy and validation evidence are approved.

## Replacement Acceptance Criteria

A replacement is ready for controlled pilot use only when:

- the instrument version is approved and immutable;
- SHS/JHS mappings are explicit and tested;
- current and candidate responses cannot be mixed accidentally;
- domain definitions and scoring rules are documented before fitting;
- a simple baseline exists;
- clustering and uncertainty are represented;
- missing/N/A behavior is tested;
- qualitative coding has human validation evidence;
- fairness/invariance checks are documented or explicitly marked as not estimable;
- reports distinguish formative evidence from personnel decisions;
- rollback to the current pilot version is tested.

## Decision

**Proceed with design and validation preparation. Do not replace the current scorer yet.** The next implementation should be a versioned candidate-instrument adapter and validation harness, not a new production score. The attached PDF should be treated as a draft TPE specification until content owners approve its wording, domains, observability rules, and intended use.

## Evidence Boundary

This memo is grounded in the current repository implementation, synthetic smoke-test output, the attached provisional instrument text, and the measurement/fairness principles already documented in [TPE_INSTRUMENT_REVIEW.md](TPE_INSTRUMENT_REVIEW.md) and [scoring_methodology.md](scoring_methodology.md). No claim here establishes validity for live student data or the attached instrument.
