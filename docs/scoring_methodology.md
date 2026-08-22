# Faculty Evaluation Aggregator: Research-Grounded Scoring Methodology

## Purpose

The Faculty Evaluation Aggregator is designed to replace a narrow practice of averaging only the first 10 quantitative items and selectively reading qualitative comments. The system produces one administrator-facing final teacher rating on a 1-5 scale, while preserving an internal audit trail for psychometric review, data-quality monitoring, and methodological defense.

The guiding principle is simple: administrators may need one score, but the score should be produced from all available evidence using a defensible measurement model rather than convenience averaging.

## Instrument Structure

Each SHS and JHS instrument is treated as a separate form. The wording differs by student level, so SHS and JHS should not share item parameters unless future linking evidence supports it.

| Part | Construct | Role in scoring |
| --- | --- | --- |
| Part 1 | Instructional Performance, 10 items | Direct teacher-performance construct |
| Part 2 | Overall Learning Experience, 10 items | Direct learner-experience construct |
| Part 3 | Student Self-Evaluation, 5 items | Rater credibility / response-quality weight |
| Part 4 | Qualitative Feedback, 3 open-ended items | Semantic NLP evidence and narrative interpretation |

## Research Basis

The design follows five research traditions:

1. **Educational and psychological measurement standards.** The scoring system should document validity, reliability/precision, fairness, score interpretation, and intended use. These are central concerns in the Standards for Educational and Psychological Testing, published by AERA, APA, and NCME.
2. **Item Response Theory.** IRT is appropriate when item-level categorical or ordinal responses are used to infer latent constructs. It avoids assuming that every item contributes equally.
3. **Transparent weighting of teaching-quality indicators.** Teaching-quality indicators should not receive hidden or accidental weights. The current implementation uses disclosed institutional policy weights, while future validation can test whether data-derived weights should replace them.
4. **Rater credibility and response quality.** Student evaluations can be affected by biased, careless, emotional, or strategic responding. The system therefore uses student self-evaluation and response-pattern checks as weighting evidence, not as a direct teacher-quality score.
5. **NLP for student evaluation comments.** Open-ended comments should not be cherry-picked. They should be organized through semantic analysis, aspect extraction, and summarization so that all comments contribute systematically.

## Scoring Overview

The official output is:

```text
Final Teacher Rating: 1.00 to 5.00
```

The current operational implementation uses explicit institutional policy weights:

```text
Final Teacher Rating =
  0.50 * Instructional Performance
+ 0.30 * Overall Learning Experience
+ 0.20 * Qualitative Feedback
```

These weights are policy choices, not data-derived estimates. The application exposes sidebar sliders for internal review scenarios, but the active weights remain constrained to be positive and to sum to 1:

```text
component_weight_instructional >= 0
component_weight_experience >= 0
component_weight_qualitative >= 0

component weights sum to 1
```

The model reports a single final 1-5 score to administrators, but internally it retains component weights, uncertainty intervals, item diagnostics, response-quality diagnostics, and qualitative evidence tables.

The Student Self-Evaluation part is not added as a teacher-quality component. Instead, it determines how much weight each student response receives:

```text
response_weight = bounded_rater_credibility * response_pattern_quality
```

This keeps all components involved in the final aggregate while avoiding the methodological error of treating student effort as teacher performance.

## Why The Current Weights Are Policy Weights

The current deployment uses fixed institutional weights because administrators need a stable and explainable composite: 50% instructional performance, 30% overall learning experience, and 20% qualitative feedback. This makes the policy choice visible rather than hiding it inside a data-derived model.

The defensibility of this approach depends on documenting the policy choice and keeping the technical audit trail available:

```text
Policy weights are fixed and disclosed.
Item weights are estimated within quantitative blocks.
Rater credibility is bounded and documented.
Partial pooling handles unequal class loads.
Qualitative evidence is summarized systematically rather than cherry-picked.
```

For future validation, the school may compare the policy-weighted composite against a research-grade model that estimates weights from historical data:

1. **Current deployment:** fixed institutional policy weights with transparent diagnostics.
2. **Historical-data deployment:** Bayesian hierarchical / multidimensional IRT model calibrated on historical SHS and JHS exports separately.

Any future data-derived weights should be reviewed internally before they replace the policy weights in official reporting.

## Why Self-Evaluation Is A Weight, Not A Direct Score

The self-evaluation items describe the student's behavior: attendance, participation, collaboration, submission of work, and effort. These items matter because they affect how much confidence the system should place in the student's evaluation. They do not, by themselves, show whether the teacher performed well.

For example, two students may give the same low teacher rating. If one reports high participation, timely submissions, and strong effort, while the other reports low engagement and weak participation, the two ratings should not necessarily carry identical evidential weight. Both responses are retained, but the response from the more engaged student receives greater weight.

The weight is bounded so that no student voice is erased:

```text
self_eval_mean = mean(student self-evaluation items)
self_eval_normalized = (self_eval_mean - 1) / 4
base_weight = 0.40 + 0.60 * self_eval_normalized
```

Then response-quality safeguards may reduce the weight modestly:

```text
final_response_weight = clamp(base_weight * quality_factor, 0.40, 1.00)
```

The floor of 0.40 prevents exclusion. The cap of 1.00 prevents exaggerated influence.

## Quantitative Construct Scoring

### Prototype Stage

For the first operational version, the system estimates construct scores and applies disclosed policy component weights:

```text
instructional_score_i = item-discrimination weighted score from Part 1
experience_score_i = item-discrimination weighted score from Part 2

component weights = fixed institutional policy weights
```

Item weights are estimated using corrected item-total relationships or ordinal factor loadings. Items that align better with the construct receive slightly higher influence. Items that are weak, noisy, or poorly aligned receive lower influence.

The component weights are constrained:

```text
weight_k >= 0
sum(weight_k) = 1
```

The Streamlit sidebar allows internal review scenarios, but the default operational weights remain 0.50, 0.30, and 0.20.

### Research-Grade Stage

With enough historical SharePoint exports, the quantitative blocks should move to a multidimensional Graded Response Model or another polytomous IRT model:

```text
Instructional Performance theta = GRM(IP items)
Overall Experience theta = GRM(OE items)
Teacher Quality theta = higher-order / bifactor latent score
```

This allows the final score to be learned from item-level evidence:

```text
Part 1 and Part 2 items load onto their intended constructs.
The constructs load onto a general teacher-quality factor.
The learned loadings determine the effective contribution of each construct.
```

These latent scores are transformed back to the 1-5 reporting scale:

```text
scaled_score = 1 + 4 * percentile_or_expected_score(theta)
```

SHS and JHS should be calibrated separately. If the school later wants to compare SHS and JHS scores directly, a linking study is needed.

## Qualitative NLP Evidence

The qualitative section should be processed with semantic NLP rather than generic sentiment analysis. The goal is not to decide whether a comment is positive or negative. The goal is to understand what the student is talking about and whether the evidence supports instructional strengths, concerns, or improvement areas.

Recommended NLP pipeline:

1. Clean and segment comments into meaningful statements.
2. Encode statements using sentence embeddings.
3. Classify or cluster statements into teaching aspects:
   - clarity of explanations and instructions
   - classroom management and learning climate
   - teaching strategies and activities
   - student support and consultation
   - feedback, assessment, and grading
   - learning materials and resources
   - timeliness and online responsiveness
   - pacing, workload, and difficulty
   - motivation and confidence in learning
4. Generate teacher-level qualitative statements:
   - what students appreciated
   - what students suggested improving
   - how students described the overall learning experience
5. Convert semantic evidence into a cautious 1-5 qualitative evidence score or latent semantic indicator.

The qualitative score should be conservative and uncertainty-aware:

```text
qualitative_score = 3.00 + semantic_evidence_adjustment
```

where the adjustment is bounded:

```text
1.00 <= qualitative_score <= 5.00
```

The score should move upward only when many comments consistently identify strengths, and downward only when many comments consistently identify concerns. Sparse or ambiguous comments should remain near 3.00.

In the research-grade version, qualitative evidence should enter as another observed indicator of the latent teacher-quality factor. Its influence is learned from historical alignment with quantitative patterns and human-coded validation samples, not fixed by policy preference.

## Class Imbalance And Unequal Teaching Loads

The scoring system must correct for imbalance between teachers with many classes and teachers with only one or two classes. A teacher with 7 classes may have 210-280 student responses. A teacher with 1 class may have only 30-40 responses. Raw averages make these two estimates look equally stable even though they are not.

The system should use partial pooling through a Bayesian hierarchical model or empirical Bayes estimator.

For teacher `t` in class `c`, student `s`:

```text
observed_response_signal_sct =
  teacher_effect_t
+ class_effect_ct
+ student_response_style_s
+ item_effect_j
+ residual_error
```

The teacher effect is estimated with shrinkage:

```text
teacher_effect_t ~ Normal(school_mean, teacher_variance)
```

Teachers with many independent class observations are allowed to move farther from the school mean because the data contain more evidence. Teachers with only one or two classes are pulled more strongly toward the school mean because their estimate is more vulnerable to class-specific noise.

```text
posterior_teacher_score =
  shrinkage_factor_t * observed_teacher_signal
+ (1 - shrinkage_factor_t) * school_or_department_mean
```

The shrinkage factor increases when the teacher has more reliable evidence:

```text
shrinkage_factor_t =
  teacher_variance / (teacher_variance + standard_error_t^2)
```

The standard error must account for both number of student responses and number of classes. Students inside the same class are not fully independent because they share the same teacher, section climate, schedule, subject, assessment experience, and peer context.

The effective response count should therefore be adjusted for clustering:

```text
effective_n =
  raw_n / (1 + (average_class_size - 1) * class_intraclass_correlation)
```

This prevents a teacher with one unusually happy or unusually frustrated class from being treated as equally stable as a teacher evaluated across seven separate classes.

## Final Teacher Rating Model

The final teacher score should be the posterior estimate of the teacher's latent quality, transformed to the 1-5 scale:

```text
teacher_final_rating =
  transform_to_1_5_scale(posterior_mean(teacher_quality_t))
```

The administrator-facing report may show only:

```text
Final Teacher Rating: 4.32 / 5.00
```

The internal report should retain:

```text
posterior_mean
credible_interval
effective_response_count
number_of_classes
policy_component_weights
component diagnostics
qualitative semantic phrases
response-quality flags
```

This resolves the administrative need for a single score while preserving a defensible methodology for internal review.

## Recommended Internal Review Outputs

Even if administrators prefer one number, the internal review package should preserve:

| Output | Purpose |
| --- | --- |
| Final rating | Official administrator-facing score |
| Instructional performance score | Audit of direct teaching-performance evidence |
| Overall experience score | Audit of learner-experience evidence |
| Qualitative NLP score | Audit of text-derived evidence |
| Policy component weights | Shows the disclosed institutional contribution of each evidence stream |
| Qualitative phrases and count tables | Human-readable interpretation and distributional evidence from open-ended comments |
| Mean response weight | Indicates response credibility profile |
| Effective response count | Better than raw count when weights vary |
| Number of evaluated classes | Identifies instability from low class coverage |
| Flagged response count | Indicates response-pattern concerns |
| Reliability estimates | Checks whether item blocks behave consistently |
| Item diagnostics | Identifies weak, redundant, or misfitting items |
| Credible/confidence interval | Prevents overinterpreting unstable scores |

## Reliability, Validity, And Fairness Checks

Before full administrative adoption, the system should produce an internal validation report.

### Reliability

- Cronbach's alpha or McDonald's omega for each quantitative construct.
- Item-total relationships.
- Posterior standard error or bootstrap confidence interval for teacher-level ratings.
- Effective response count adjusted for response weights and class clustering.

### Construct Validity

- Confirm that Part 1 and Part 2 behave as related but distinct constructs.
- Use exploratory/confirmatory factor analysis, structural equation modeling, or multidimensional IRT when enough data are available.
- Check whether items cluster according to the intended instrument structure.
- Compare policy component weights against loadings or constrained latent regression when enough validation data are available.

### Item Diagnostics

- Identify items with weak discrimination.
- Identify items with ceiling effects or very low variance.
- Identify items that behave differently in SHS and JHS.

### Response Quality

- Detect straight-lining.
- Detect extreme response patterns.
- Detect unusual mismatch between self-evaluation and teacher ratings.
- Report flags as caution indicators, not accusations.

### Fairness

- Avoid automatic exclusion of students.
- Use bounded weights.
- Keep SHS and JHS calibration separate.
- Use partial pooling so teachers with fewer classes are not overrewarded or overpenalized by unstable averages.
- Report uncertainty wider for teachers with one or two evaluated classes.
- If demographic or section-level data are available and ethically approved for use, test for differential item functioning.

### Qualitative NLP Validation

- Manually code a sample of comments.
- Compare human-coded themes against NLP themes.
- Check whether the qualitative score is too sensitive to a small number of comments.
- Require a minimum comment count before qualitative evidence strongly moves the final score.

## Implementation Roadmap

### Phase 1: Defensible Composite

- Restructure the app into four parts.
- Produce a final 1-5 teacher rating.
- Use item-discrimination weighted quantitative scoring.
- Apply disclosed institutional policy component weights.
- Use bounded self-evaluation response weights.
- Use semantic NLP statements and conservative qualitative score.
- Add effective response count and class-count adjustment.
- Keep internal audit tables.

### Phase 2: Historical Calibration

- Pool historical SharePoint exports by SHS and JHS.
- Estimate construct reliability and item diagnostics.
- Evaluate whether historical data support revising the policy component weights.
- Compare raw means, item-weighted scores, and partial-pooled teacher scores.
- Estimate class-level variance and intraclass correlation.
- Validate whether qualitative semantic evidence improves prediction of the latent teacher-quality signal.

### Phase 3: Psychometric Upgrade

- Fit separate Graded Response Models for Instructional Performance and Overall Experience.
- Fit a higher-order or bifactor teacher-quality model.
- Add Bayesian partial pooling for teacher and class effects.
- Anchor item parameters for future semesters.
- Add teacher-level credible intervals.
- Add item-fit and response-pattern diagnostics.

### Phase 4: Administrative Review Package

- One-page administrator report with final ratings.
- Internal methodology appendix.
- Technical appendix for psychometric review.
- Versioned calibration files.
- Change log for scoring model revisions.

## Suggested Policy Statement

The Faculty Evaluation Aggregator produces a single teacher rating from quantitative ratings, student response-quality evidence, and qualitative feedback. The method is designed to reduce overreliance on simple averages and selective comment reading. Student self-evaluation is used to weight response credibility, not to directly judge teacher quality. Component contributions follow disclosed institutional policy weights. Qualitative feedback is processed through semantic NLP so that all comments are considered systematically. Teacher ratings are adjusted for unequal numbers of classes through partial pooling, so teachers with fewer evaluated classes are not overrewarded or overpenalized by unstable averages. The final score is intended as one source of evidence for instructional review and should be interpreted with professional judgment, especially when class coverage is low or uncertainty intervals are wide.

## Key References

- American Educational Research Association, American Psychological Association, & National Council on Measurement in Education. *Standards for Educational and Psychological Testing*. https://www.testingstandards.net/
- Chen, Y., Li, X., Liu, J., & Ying, Z. (2021). *Item Response Theory: A Statistical Framework for Educational and Psychological Measurement*. https://arxiv.org/abs/2108.08604
- Dorta-González, P., & Dorta-González, M. I. (2013). *The student evaluation of teaching and the competence of students as evaluators*. https://arxiv.org/abs/1301.7628
- Fouskakis, D., Petrakos, G., & Vavouras, I. (2014). *A Bayesian Hierarchical Model for Comparative Evaluation of Teaching Quality Indicators in Higher Education*. https://arxiv.org/abs/1404.1710
- Hu, Y., Zhang, S., Sathy, V., Panter, A. T., & Bansal, M. (2022). *SETSum: Summarization and Visualization of Student Evaluations of Teaching*. https://arxiv.org/abs/2207.03640
- Knutas, A., Hynninen, T., & Hujala, M. (2021). *To get good student ratings should you only teach programming courses? Investigation and implications of student evaluations of teaching in a software engineering context*. https://arxiv.org/abs/2102.08179
- Reimers, N., & Gurevych, I. (2019). *Sentence-BERT: Sentence Embeddings using Siamese BERT-Networks*. https://arxiv.org/abs/1908.10084
- Grootendorst, M. (2022). *BERTopic: Neural topic modeling with a class-based TF-IDF procedure*. https://arxiv.org/abs/2203.05794
- Lalor, J. P., & Rodriguez, P. (2022). *py-irt: A Scalable Item Response Theory Library for Python*. https://arxiv.org/abs/2203.01282
- Shavelson, R. J., & Webb, N. M. (1991). *Generalizability Theory: A Primer*. Sage.
- Wang, J., Stelmakh, I., Wei, Y., & Shah, N. B. (2020). *Debiasing Evaluations That are Biased by Evaluations*. https://arxiv.org/abs/2012.00714
