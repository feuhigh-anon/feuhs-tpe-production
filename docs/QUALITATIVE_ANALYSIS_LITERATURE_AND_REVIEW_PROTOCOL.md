# Qualitative Feedback Analysis and Review Protocol

**Status:** Design and review artifact; not a validated measurement model

**Scope:** Historical student-evaluation comments used to design and validate a
controlled, descriptive qualitative-analysis workflow.

## Decision

Use model-assisted, multi-label aspect analysis with an explicit abstention
option. Use sentence embeddings for discovery and retrieval, not as a teacher
quality score. Keep qualitative findings separate from the numeric evaluation
score until criterion validity and governance approval exist.

### Agreed teacher-summary design

The qualitative output will be organized by teacher and by the three source
prompt types: `appreciation`, `suggestion`, and `experience`. Each teacher and
prompt type is an isolated analysis unit. Comments from other teachers and the
other prompt types must not enter that unit's analysis or summary.

Each unit produces up to three bounded statements:

1. **Dominant pattern:** the most recurring interpretable theme.
2. **Secondary pattern or variation:** another recurring theme or meaningful
  difference in the feedback.
3. **Context and limitation:** abstentions, contradictory feedback, response
  volume, or other limits on interpretation.

Statements include verified counts and denominators where reporting is
permitted. Counts are calculated by deterministic code from structured labels;
the language model may phrase the statements but may not invent or recalculate
the numbers.

The minimum-data rule is:

- fewer than 3 interpretable comments: do not produce a thematic claim;
- 3-9 interpretable comments: produce only cautious statements supported by the
  available evidence;
- 10 or more interpretable comments: produce up to three statements.

Unused statement slots use a controlled message such as `Insufficient
interpretable feedback for a thematic summary.` The output is descriptive
only. It must not produce a qualitative score, rank teachers, recommend
personnel action, or replace the numeric evaluation instrument.

The first review set is a blinded, stratified sample. It is not a complete
export of the historical evaluation corpus and it must not be used to rank
teachers.

## Literature and standards

### Thematic analysis

Braun and Clarke's thematic-analysis framework supports familiarization,
systematic coding, theme development, review, definition, and transparent
reporting. The relevant implication here is to freeze a codebook and retain an
audit trail rather than treating an automatically generated topic list as a
validated construct.

- Braun, V. and Clarke, V. (2006). *Using thematic analysis in psychology*.
  **Qualitative Research in Psychology, 3**(2), 77-101.
  https://doi.org/10.1191/1478088706qp063oa

### Aspect-based sentiment and multi-label text classification

Aspect-based analysis separates the object of discussion from polarity or
stance. This is more appropriate than generic sentiment for comments that can
contain both a strength and a concern. Multi-label classification is required
when one sentence legitimately concerns more than one aspect.

The local aspect list remains an instrument-and-context decision. Literature
supports the separation of aspect and stance; it does not prove that these
specific school-defined aspects are valid without local review.

### Active learning

Active learning supports selecting the next examples for review based on model
uncertainty, disagreement, or underrepresented labels. It reduces annotation
work compared with random review, but it does not remove the need for a
held-out evaluation sample or bias checks.

- Settles, B. (2009). *Active Learning Literature Survey*. University of
  Wisconsin-Madison, Computer Sciences Technical Report 1648.
  https://minds.wisconsin.edu/handle/1793/60660

### LLM-assisted thematic analysis

LLM-assisted thematic analysis can reduce coding effort when the human retains
control of the codebook and adjudication process. The evidence supports using
the model as a coding assistant, not as an authority that determines teacher
quality.

- Dai, S.-C., Xiong, A., and Ku, L.-W. (2023). *LLM-in-the-loop: Leveraging
  Large Language Model for Thematic Analysis*. Findings of EMNLP 2023,
  9993-10001. https://doi.org/10.18653/v1/2023.findings-emnlp.669

### Bias, governance, and intended use

Bias can enter through the source data, task definition, labels, model,
interface, and downstream decision. The workflow therefore records intended
use, data provenance, uncertainty, abstentions, and reviewer decisions. These
controls are informed by:

- Suresh, H. and Guttag, J. (2021). *A Framework for Understanding Sources of
  Harm throughout the Machine Learning Life Cycle*. FAccT 2021,
  48-63. https://doi.org/10.1145/3461702.3462572
- National Institute of Standards and Technology. (2023). *AI Risk
  Management Framework 1.0*. https://www.nist.gov/itl/ai-risk-management-framework
- AERA, APA, and NCME. (2014). *Standards for Educational and Psychological
  Testing*. https://www.testingstandards.net/

These sources support the process and governance safeguards. They do not
validate the school's instrument, aspect definitions, or teacher-level claims.

## Provenance and definitions of review terms

The review fields combine three different kinds of terminology. First, some
terms describe established methods: thematic analysis, aspect-based analysis,
multi-label coding, abstention, and audit trails. Second, some fields are
ordinary measurement and data-governance concepts: observability, evidence
quality, actionability, and safety status. Third, the aspect names and their
allowed values are a local provisional codebook for this school's comments.
They are informed by the literature and by the survey context, but they are
not validated educational constructs or published scales.

| Term or field | Operational definition for this review | Literature status and basis |
| --- | --- | --- |
| `prompt_type` | The open-ended survey question that elicited the comment: appreciation, suggestion, or experience. | Directly inherited from the source instrument; not a literature-derived construct. |
| `aspect` | The instructional or classroom topic discussed in the comment, such as clarity, teaching strategy, or student support. A comment may have more than one aspect. | Aspect-based analysis supports separating the object of discussion from stance or polarity. The specific aspect list is locally proposed and needs content review. |
| `stance` | The direction of the comment toward one aspect: strength, concern, mixed, or neutral. It is not an overall teacher rating. | Consistent with sentiment/stance separation in aspect-based analysis. The four labels and their use in this context are local operational definitions. |
| `evidence_quality` | How much observable detail supports the comment: specific, general, vague, or insufficient. | A defensible qualitative-coding safeguard, but these thresholds are locally defined and require reviewer calibration. |
| `observability` | Whether a student could reasonably observe the behavior or condition described: direct, partial, or not observable. | Based on validity and intended-use reasoning from educational measurement; not a validated student-evaluation scale. |
| `actionability` | Whether the comment identifies a teaching practice or context that could reasonably be addressed: actionable, contextual, or unclear. | A reporting and decision-usefulness criterion; locally defined, not a published score. |
| `safety_status` | Whether the comment is safe to retain in a report: safe, identifying, or sensitive. | A privacy and harm-screening control informed by NIST AI RMF, Suresh and Guttag, and the testing standards; it is not a sentiment label. |
| `review_decision` | Whether the annotation should be used: include, abstain, or needs review. | Abstention is supported as a way to represent uncertainty; the decision labels and reporting rules are local governance choices. |
| `reviewer_confidence` | The reviewer's confidence that the assigned coding is appropriate: high, medium, or low. | An uncertainty record, not a probability and not confidence in teacher quality. The scale is local. |
| `reviewer_notes` | A short explanation of ambiguity, evidence, correction, or a possible codebook change. | Audit-trail practice consistent with thematic analysis and human-in-the-loop review. |

The following terms describe the workflow rather than individual columns:

- **Codebook:** The frozen list of labels, definitions, inclusion rules, and
  exclusion rules used for consistent annotation.
- **Thematic analysis:** A structured qualitative process of familiarization,
  coding, theme development, review, definition, and reporting. Braun and
  Clarke support the process, not the validity of this local codebook.
- **Aspect-based analysis:** Analysis that identifies what a comment is about
  separately from the comment's stance toward that aspect.
- **Multi-label coding:** Assigning multiple aspects when one comment contains
  evidence about multiple topics.
- **Abstention:** Deliberately leaving a comment or aspect uncoded when the
  evidence is insufficient, ambiguous, unsafe, or outside the codebook.
- **Audit trail:** A record of the source version, codebook version, reviewer
  decision, uncertainty, and rationale needed to reconstruct the review.
- **De-identification:** Removing or masking direct identifiers and known
  metadata while recognizing that free-text anecdotes may still permit
  re-identification.

These definitions are suitable for a first manual review. They should be
tested on a pilot subset, revised through documented disagreements, and frozen
before any model-assisted classification. Agreement or repeatability results
would support annotation consistency; they would not by themselves validate a
teacher-quality measure.

## Review codebook

Each comment may receive multiple aspect labels.

| Field | Allowed values | Rule |
| --- | --- | --- |
| `prompt_type` | `appreciation`, `suggestion`, `experience` | Inherited from the survey prompt; not inferred by the model. |
| `aspect` | `clarity`, `teaching_strategy`, `classroom_climate`, `student_support`, `feedback_assessment`, `materials_resources`, `responsiveness`, `pacing_workload`, `engagement_motivation` | Assign only when the comment provides evidence relevant to the aspect. |
| `stance` | `strength`, `concern`, `mixed`, `neutral` | Describe the comment's stance toward the aspect, not the teacher overall. |
| `evidence_quality` | `specific`, `general`, `vague`, `insufficient` | `specific` requires an observable practice or example. |
| `observability` | `direct`, `partial`, `not_observable` | Use `not_observable` for claims outside a student's reasonable opportunity to observe. |
| `actionability` | `actionable`, `contextual`, `unclear` | `actionable` means a reasonable teaching practice could respond to it. |
| `safety_status` | `safe`, `identifying`, `sensitive` | Suppress or redact identifying or sensitive material before reporting. |
| `review_decision` | `include`, `abstain`, `needs_review` | Do not force uncertain comments into an aspect. |
| `reviewer_confidence` | `high`, `medium`, `low` | Confidence in the coding decision, not confidence in the teacher. |

## Solo-review procedure

1. Review the anonymized comment before seeing any model suggestion.
2. Record aspect, stance, evidence quality, observability, actionability, and
   confidence.
3. Re-open the model suggestion and mark it `accept`, `correct`, or `reject`.
4. Record a short rationale for corrections and codebook changes.
5. Re-review a masked 10-20% subset after a delay to estimate intra-reviewer
   consistency.
6. Freeze the codebook before full-corpus classification.

This is single-reviewer validation with repeatability safeguards. It is not
inter-rater reliability.

## Sampling and leakage controls

The review builder selects a deterministic, stratified sample after removing
exact duplicate rows across source exports. Source identifiers, student
identifiers, teacher metadata, subject, section, scores, and timestamps are not
included in the review CSV.

The initial target is 100 comments: 40 appreciation, 40 suggestions, and 20
experience comments, with SHS/JHS coverage where the source schema supports it.
The sample is a starting point, not a claim that 100 labels establish validity.
Later additions should prioritize model uncertainty and underrepresented
aspects. Evaluation splits must be separated by source period or export when a
classifier is trained, so repeated or near-duplicate comments cannot leak
between training and evaluation.

## Administrative reporting boundary

The approved first output is descriptive:

> Among eligible comments, 31 mentioned clarity, 18 described student support
> positively, and 12 raised pacing concerns.

Reports must show denominators, prompt type, abstention counts, suppression
rules, and review/model status. Small groups and identifying excerpts must be
suppressed. The output must not produce a qualitative teacher score, infer
causality, or make personnel recommendations.

## Reproducibility

The local builder is `scripts/build_qualitative_review_set.py`. It records the
sampling seed, source manifest, deduplication method, and redaction policy in a
JSON manifest beside the review CSV. Source files remain local and ignored by
git. The generated review artifact is also ignored because it contains
de-identified but still sensitive student text.

The review-seeded baseline in `scripts/train_qualitative_baseline.py` uses the
included reviewed rows as labeled examples for word- and character-level TF-IDF
features with logistic-regression classifiers for aspect and stance. It scores
the larger de-identified corpus, but every prediction remains
`needs_review`; confidence is used only to prioritize human review. This is a
triage and retrieval aid, not a validated classifier. The de-identified output
also cannot support teacher-level aggregation by itself because teacher linkage
is deliberately excluded. Any authorized aggregation must occur in a separate
privacy-controlled layer with suppression rules and retained source provenance.

## Known limitations

- PII redaction uses deterministic patterns and known metadata values; it
  cannot guarantee that every identifying anecdote is removed.
- Historical exports do not all use the same instrument or prompt set. SHS and
  JHS must remain separate, and one JHS export currently exposes only one
  detectable open-ended prompt.
- Exact-row deduplication prevents repeated exports from being counted twice,
  but it does not prove that two similar comments came from different students.
- Embedding similarity and model confidence are not validity evidence.