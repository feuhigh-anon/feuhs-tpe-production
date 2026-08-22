"""Streamlit app for faculty evaluation aggregation."""

from __future__ import annotations

import io

import pandas as pd
import streamlit as st

from feval.ingestion import build_column_matches, infer_best_column, normalize_responses, read_sharepoint_export
from feval.questions import DEFAULT_QUESTION_BLOCKS
from feval.reporting import build_analysis_report
from feval.sample_data import make_demo_sharepoint_export
from feval.scoring import WEIGHT_EXPERIENCE, WEIGHT_INSTRUCTIONAL, WEIGHT_QUALITATIVE


st.set_page_config(page_title="Faculty Evaluation Aggregator", layout="wide")


def main() -> None:
    st.title("Faculty Evaluation Aggregator")
    st.caption("SharePoint exports · policy-weighted composite scoring · bounded rater credibility · partial pooling")

    weights = render_weight_controls()

    shs_tab, jhs_tab, method_tab = st.tabs(["Senior High School", "Junior High School", "Methodology"])
    with shs_tab:
        render_block(DEFAULT_QUESTION_BLOCKS["shs"], weights)
    with jhs_tab:
        render_block(DEFAULT_QUESTION_BLOCKS["jhs"], weights)
    with method_tab:
        render_methodology()


def render_weight_controls() -> tuple[float, float, float]:
    """Render sidebar policy-weight controls that sum to 1.0."""

    st.sidebar.header("Policy weights")
    instructional_pct = st.sidebar.slider(
        "Instructional Performance",
        min_value=0,
        max_value=100,
        value=int(round(WEIGHT_INSTRUCTIONAL * 100)),
        step=1,
        key="weight_instructional_pct",
    )
    max_experience_pct = 100 - instructional_pct
    default_experience_pct = min(int(round(WEIGHT_EXPERIENCE * 100)), max_experience_pct)
    experience_pct = st.sidebar.slider(
        "Overall Learning Experience",
        min_value=0,
        max_value=max_experience_pct,
        value=min(st.session_state.get("weight_experience_pct", default_experience_pct), max_experience_pct),
        step=1,
        key="weight_experience_pct",
    )
    qualitative_pct = 100 - instructional_pct - experience_pct
    st.session_state["weight_qualitative_pct"] = qualitative_pct
    st.sidebar.slider(
        "Qualitative Feedback",
        min_value=0,
        max_value=100,
        value=qualitative_pct,
        step=1,
        disabled=True,
        key="weight_qualitative_display_pct",
    )
    st.sidebar.caption(
        f"Used weights: {instructional_pct / 100:.2f} + {experience_pct / 100:.2f} + "
        f"{qualitative_pct / 100:.2f} = 1.00"
    )
    return instructional_pct / 100.0, experience_pct / 100.0, qualitative_pct / 100.0


def render_block(block, weights: tuple[float, float, float]) -> None:
    st.subheader(block.label)
    use_demo = st.toggle("Use demo data", value=False, key=f"{block.id}-demo")
    uploaded = st.file_uploader(
        "SharePoint export",
        type=["xlsx", "xls", "csv"],
        key=f"{block.id}-upload",
    )

    raw = None
    if use_demo:
        raw = make_demo_sharepoint_export(block)
    elif uploaded is not None:
        raw = read_sharepoint_export(uploaded)

    if raw is None:
        st.info("Upload a SharePoint export or switch on demo data.")
        return

    st.dataframe(raw.head(8), use_container_width=True)

    columns = list(raw.columns)
    teacher_guess = infer_best_column(columns, block.teacher_aliases)
    section_guess = infer_best_column(columns, block.section_aliases)
    respondent_guess = infer_best_column(columns, block.respondent_aliases)

    col_a, col_b, col_c = st.columns(3)
    teacher_column = col_a.selectbox(
        "Teacher column",
        columns,
        index=columns.index(teacher_guess) if teacher_guess in columns else 0,
        key=f"{block.id}-teacher",
    )
    section_column = col_b.selectbox(
        "Section column",
        [""] + columns,
        index=([""] + columns).index(section_guess) if section_guess in columns else 0,
        key=f"{block.id}-section",
    )
    respondent_column = col_c.selectbox(
        "Respondent column",
        [""] + columns,
        index=([""] + columns).index(respondent_guess) if respondent_guess in columns else 0,
        key=f"{block.id}-respondent",
    )

    matches = build_column_matches(columns, block)
    column_map = {}
    select_options = [""] + columns
    with st.expander("Question mapping", expanded=False):
        st.markdown("**Part 1: Instructional performance**")
        for item in block.faculty_items:
            column_map[item.id] = mapping_select(block.id, item, matches, select_options)
        st.markdown("**Part 2: Overall learning experience**")
        for item in block.overall_experience_items:
            column_map[item.id] = mapping_select(block.id, item, matches, select_options)
        st.markdown("**Part 3: Student self-evaluation**")
        for item in block.rci_items:
            column_map[item.id] = mapping_select(block.id, item, matches, select_options)
        st.markdown("**Part 4: Qualitative feedback to teachers**")
        for item in block.open_ended_items:
            column_map[item.id] = mapping_select(block.id, item, matches, select_options)

    required_missing = [
        item.id
        for item in block.faculty_items + block.self_eval_items
        if not column_map.get(item.id)
    ]
    if required_missing:
        st.warning(f"Missing required mappings: {', '.join(required_missing)}")
        return

    normalized = normalize_responses(
        raw=raw,
        block=block,
        teacher_column=teacher_column,
        section_column=section_column or None,
        respondent_column=respondent_column or None,
        column_map=column_map,
    )
    report = build_analysis_report(
        normalized,
        w_instructional=weights[0],
        w_experience=weights[1],
        w_qualitative=weights[2],
    )
    render_report(report, block.id)


def mapping_select(block_id: str, item, matches, options):
    detected = matches[item.id].column
    index = options.index(detected) if detected in options else 0
    selected = st.selectbox(
        f"{item.id} · {item.text}",
        options,
        index=index,
        key=f"{block_id}-{item.id}",
    )
    return selected or None


def render_report(report, block_id: str) -> None:
    summary = report.summary
    metric_cols = st.columns(5)
    metric_cols[0].metric("Teachers", int(summary["teacher"].nunique()) if not summary.empty else 0)
    metric_cols[1].metric("Responses", int(summary["responses"].sum()) if not summary.empty else 0)
    mean_rating = summary["final_teacher_rating_1_5"].mean() if "final_teacher_rating_1_5" in summary else None
    metric_cols[2].metric("Mean final rating", f"{mean_rating:.2f}" if pd.notna(mean_rating) else "n/a")
    class_icc = report.reliability.loc[0, "class_icc"] if "class_icc" in report.reliability.columns else None
    metric_cols[3].metric("Class ICC", class_icc if class_icc is not None else "n/a")
    metric_cols[4].metric("Flagged", int(summary["flagged_responses"].sum()) if not summary.empty else 0)

    st.dataframe(summary, use_container_width=True, hide_index=True)

    detail_tab, item_tab, component_tab, qualitative_tab, reliability_tab = st.tabs(
        ["Responses", "Item weights", "Component weights", "Qualitative feedback", "Reliability"]
    )
    with detail_tab:
        st.dataframe(report.per_response, use_container_width=True, hide_index=True)
        st.download_button(
            "Download response scores",
            data=to_csv(report.per_response),
            file_name=f"{block_id}_response_scores.csv",
            mime="text/csv",
        )
    with item_tab:
        st.dataframe(report.item_weights, use_container_width=True, hide_index=True)
    with component_tab:
        st.dataframe(report.component_weights, use_container_width=True, hide_index=True)
    with qualitative_tab:
        st.dataframe(report.open_ended, use_container_width=True, hide_index=True)
        st.download_button(
            "Download qualitative statements",
            data=to_csv(report.open_ended),
            file_name=f"{block_id}_qualitative_feedback.csv",
            mime="text/csv",
        )
    with reliability_tab:
        st.dataframe(report.reliability, use_container_width=True, hide_index=True)
        st.download_button(
            "Download teacher summary",
            data=to_csv(summary),
            file_name=f"{block_id}_teacher_summary.csv",
            mime="text/csv",
        )


def render_methodology() -> None:
    st.markdown(
        """
        ### Methodology for Administrative Review

        This tool produces one final teacher rating from 1.00 to 5.00 while
        preserving the evidence behind the rating for internal review. The
        method is built for a common administrative reality: administrators may
        want one score, but the score should not be a plain average of only the
        first 10 items or a manual reading of selected comments.

        The implementation follows measurement practice from educational
        testing, item response theory, rater-quality analysis, semantic NLP,
        and hierarchical modeling. SHS and JHS are scored separately because
        the wording of their instruments differs.

        #### Instrument structure

        | Part | Construct | Scoring role |
        | --- | --- | --- |
        | Part 1 | Instructional Performance, 10 items | Direct teacher-performance construct |
        | Part 2 | Overall Learning Experience, 10 items | Direct learner-experience construct |
        | Part 3 | Student Self-Evaluation, 5 items | Rater credibility and response-quality weight |
        | Part 4 | Qualitative Feedback, 3 questions | Semantic NLP evidence and narrative statements |

        #### Policy component weights

        The system uses explicit institutional policy weights. By default,
        instructional performance receives 50%, overall learning experience
        receives 30%, and qualitative feedback receives 20%. These values are
        visible in the sidebar and can be adjusted for review scenarios while
        remaining constrained to sum to 1.00:

        ```text
        Composite =
          0.50 * instructional performance
        + 0.30 * overall learning experience
        + 0.20 * qualitative feedback
        ```

        The weights are institutional policy, not data-derived. Item-level
        scores, rater credibility, qualitative evidence, and partial pooling
        remain data-driven.

        #### Quantitative scoring

        The Part 1 and Part 2 item blocks are scored separately. Within each
        block, items receive empirical item-discrimination weights based on
        corrected item-total relationships. Items that behave more consistently
        with the construct receive slightly more influence, while weak or noisy
        items receive less influence.

        The report keeps `naive_instructional_1_5` as a familiar comparison,
        but the official score is `final_teacher_rating_1_5`.

        #### Student self-evaluation as credibility evidence

        The five Part 3 items describe the student's own learning behavior:
        punctuality, participation, collaboration, submission of work, and
        effort. They are not treated as teacher performance. They are used to
        compute a bounded response weight:

        ```text
        response_weight = bounded self-evaluation evidence * response-pattern quality
        ```

        The floor is 0.40, so no student voice is erased. The cap is 1.00, so
        no response receives exaggerated influence. The tool also flags
        straight-lining, unusual self-rating and teacher-rating mismatch, and
        multivariate outliers as review signals.

        #### Semantic qualitative NLP

        The qualitative section does not use VADER and does not use generic
        sentiment as the main interpretation. It uses a semantic instructional
        taxonomy to identify what students are talking about: clarity,
        classroom management, teaching strategies, student support, assessment
        and feedback, learning materials, responsiveness, pacing, and
        motivation.

        Comments are reported as administrator-readable statements:

        1. What students most often appreciated.
        2. What students most often suggested improving.
        3. How students described the overall learning experience.

        The same semantic evidence is converted into a cautious qualitative
        indicator. Sparse or ambiguous comments remain near the neutral center.
        Consistent evidence across many comments can move the qualitative
        indicator upward or downward. Its contribution to the composite is
        controlled by the qualitative policy weight.

        #### Class imbalance and partial pooling

        Teachers with seven classes can have hundreds of responses, while
        teachers with one or two classes may have only 30 to 80 responses. A
        raw average makes those estimates look equally stable. This tool
        corrects that by estimating an effective response count and applying
        partial pooling:

        ```text
        final teacher rating =
          shrinkage * observed teacher signal
        + (1 - shrinkage) * school mean
        ```

        The shrinkage is weaker when a teacher has more independent evidence
        and stronger when a teacher has fewer classes or less stable response
        evidence. The confidence interval columns show the remaining
        uncertainty.

        #### How to read the main columns

        | Column | Administrative meaning |
        | --- | --- |
        | `final_teacher_rating_1_5` | Official 1-5 teacher rating after policy weighting and partial pooling. |
        | `rating_ci_low_1_5` and `rating_ci_high_1_5` | Uncertainty interval for the final rating. |
        | `observed_teacher_rating_1_5` | Teacher signal before partial pooling. |
        | `instructional_performance_1_5` | Part 1 score after item weighting and rater weighting. |
        | `overall_experience_1_5` | Part 2 score after item weighting and rater weighting. |
        | `qualitative_score_1_5` | Cautious semantic NLP evidence indicator. |
        | `student_self_eval_1_5` | Student self-evaluation context, used for response weighting. |
        | `effective_response_count` | Stability-adjusted response count after credibility and class clustering. |
        | `partial_pooling_shrinkage` | How much the teacher's observed signal is trusted relative to the school mean. |
        | `mean_rci_weight` | Average response credibility weight. |
        | `flagged_responses` | Number of responses with caution flags. |
        | `semantic_themes` | Recurring instructional themes in comments. |
        | `representative_evidence` | Short comment snippets supporting the qualitative statements. |

        The detailed methodology file in `docs/scoring_methodology.md` provides
        the internal-review rationale and the research-grade calibration path.
        """
    )


def to_csv(data: pd.DataFrame) -> bytes:
    buffer = io.StringIO()
    data.to_csv(buffer, index=False)
    return buffer.getvalue().encode("utf-8")


if __name__ == "__main__":
    main()
