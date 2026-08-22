"""Student-facing Streamlit prototype for faculty evaluations."""

from __future__ import annotations

import html
from datetime import datetime

import streamlit as st

from feval.questions import DEFAULT_QUESTION_BLOCKS
from feval.student_demo_data import DEMO_ASSIGNMENTS, DEMO_STUDENT, DEMO_SUBMISSIONS
from feval.student_portal import (
    SubmissionRecord,
    TeacherAssignment,
    assignments_for_student,
    pending_assignments,
    submitted_assignment_ids,
)


st.set_page_config(
    page_title="FEU High School Faculty Evaluation",
    page_icon=":material/rate_review:",
    layout="centered",
    initial_sidebar_state="collapsed",
)


RATING_LABELS = {
    1: "Strongly Disagree",
    2: "Disagree",
    3: "Neutral",
    4: "Agree",
    5: "Strongly Agree",
}


def initialize_state() -> None:
    defaults = {
        "portal_page": "home",
        "portal_theme": "light",
        "selected_assignment_id": None,
        "evaluation_section": 0,
        "answers": {},
        "comments": {},
        "submissions": list(DEMO_SUBMISSIONS),
        "last_submission": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def navigate(page: str) -> None:
    st.session_state.portal_page = page
    st.rerun()


def select_assignment(assignment_id: str) -> None:
    st.session_state.selected_assignment_id = assignment_id
    st.session_state.evaluation_section = 0
    navigate("evaluation")


def portal_data():
    student = DEMO_STUDENT
    assignments = assignments_for_student(student, DEMO_ASSIGNMENTS)
    submitted = submitted_assignment_ids(student, st.session_state.submissions)
    return student, assignments, submitted


def current_assignment(assignments: tuple[TeacherAssignment, ...]) -> TeacherAssignment | None:
    selected_id = st.session_state.selected_assignment_id
    return next((item for item in assignments if item.id == selected_id), None)


def inject_styles(theme: str) -> None:
    if theme == "dark":
        colors = {
            "primary": "#008A55",
            "deep": "#005A38",
            "gold": "#FFC72C",
            "bg": "#09130F",
            "surface": "#111E18",
            "surface-raised": "#17271F",
            "text": "#F5F8F6",
            "muted": "#AAB8B0",
            "border": "#31443A",
            "soft-green": "#123A29",
            "shadow": "rgba(0, 0, 0, 0.32)",
        }
    else:
        colors = {
            "primary": "#006B3F",
            "deep": "#004C2C",
            "gold": "#FFC72C",
            "bg": "#F4F7F5",
            "surface": "#FFFFFF",
            "surface-raised": "#FFFFFF",
            "text": "#142019",
            "muted": "#64706A",
            "border": "#D8E0DB",
            "soft-green": "#E5F2EB",
            "shadow": "rgba(20, 32, 25, 0.10)",
        }

    css_vars = ";".join(f"--{key}:{value}" for key, value in colors.items())
    st.markdown(
        f"""
        <style>
        :root {{{css_vars};}}
        html, body, [class*="css"] {{ font-family: Inter, "Segoe UI", Arial, sans-serif; }}
        .stApp, [data-testid="stAppViewContainer"] {{
            background: var(--bg);
            color: var(--text);
        }}
        header[data-testid="stHeader"], [data-testid="stToolbar"],
        [data-testid="stDecoration"], #MainMenu, footer {{ display: none !important; }}
        [data-testid="stMainBlockContainer"] {{
            max-width: 480px;
            min-height: 100vh;
            height: max-content !important;
            flex-shrink: 0;
            padding: 0 1rem 5.75rem;
            background: var(--surface);
            box-shadow: 0 0 28px var(--shadow);
        }}
        h1, h2, h3, p, label, [data-testid="stMarkdownContainer"] {{ color: var(--text); }}
        h1 {{ font-size: 1.7rem; line-height: 1.2; letter-spacing: 0; }}
        h2 {{ font-size: 1.25rem; line-height: 1.3; letter-spacing: 0; }}
        h3 {{ font-size: 1rem; line-height: 1.35; letter-spacing: 0; }}
        .st-key-portal_header {{
            position: sticky;
            top: 0;
            z-index: 50;
            width: calc(100% + 2rem) !important;
            min-width: calc(100% + 2rem);
            max-width: none !important;
            flex: 0 0 calc(100% + 2rem) !important;
            margin: 0 -1rem 1rem;
            padding: .72rem .8rem;
            background: var(--deep);
            border-bottom: 2px solid var(--gold);
        }}
        .st-key-portal_header [data-testid="stHorizontalBlock"] {{ align-items: center; }}
        .st-key-portal_header [data-testid="stHorizontalBlock"],
        [data-testid="stForm"] [data-testid="stHorizontalBlock"],
        .st-key-bottom_nav [data-testid="stHorizontalBlock"] {{
            flex-direction: row !important;
            flex-wrap: nowrap !important;
        }}
        .st-key-portal_header [data-testid="stColumn"],
        [data-testid="stForm"] [data-testid="stColumn"],
        .st-key-bottom_nav [data-testid="stColumn"] {{
            min-width: 0 !important;
            width: auto !important;
        }}
        .st-key-portal_header .stButton button {{
            min-height: 2.55rem;
            border: 0;
            background: transparent;
            color: #FFFFFF;
            box-shadow: none;
            padding: .3rem;
        }}
        .st-key-portal_header .stButton button:hover {{ color: var(--gold); background: transparent; }}
        .header-title {{ color: #FFFFFF; font-size: .94rem; font-weight: 700; line-height: 1.15; }}
        .header-title span {{ display: block; font-size: .82rem; font-weight: 500; opacity: .92; }}
        [data-testid="stVerticalBlockBorderWrapper"] {{
            border: 1px solid var(--border) !important;
            border-radius: 6px !important;
            background: var(--surface-raised);
            box-shadow: 0 3px 12px var(--shadow);
        }}
        .portal-card {{ padding: .25rem .15rem; }}
        .profile-row, .assignment-copy, .submission-copy {{ display: flex; gap: .85rem; align-items: center; }}
        .avatar {{
            width: 4rem; height: 4rem; min-width: 4rem; border-radius: 50%;
            display: grid; place-items: center; background: var(--deep); color: #FFFFFF;
            font-size: 1.35rem; font-weight: 800;
        }}
        .subject-mark {{
            width: 3.15rem; height: 3.15rem; min-width: 3.15rem; border-radius: 6px;
            display: grid; place-items: center; background: var(--soft-green); color: var(--primary);
            font-size: .82rem; font-weight: 800; border: 1px solid var(--border);
        }}
        .profile-name, .assignment-subject {{ font-size: 1.05rem; font-weight: 750; line-height: 1.25; }}
        .profile-meta, .assignment-teacher, .submission-meta {{ color: var(--muted); font-size: .86rem; line-height: 1.4; }}
        .gold-rule {{ height: 2px; background: var(--gold); margin: .45rem 0 .55rem; width: 100%; }}
        .period-row {{ display: flex; align-items: center; justify-content: space-between; gap: 1rem; }}
        .period-label {{ color: var(--muted); font-size: .82rem; }}
        .period-value {{ color: var(--primary); font-size: 1.12rem; font-weight: 750; }}
        .progress-count {{ margin: .35rem 0; font-size: 1.08rem; }}
        .progress-count strong {{ color: var(--primary); font-size: 1.25rem; }}
        .status {{ font-size: .82rem; font-weight: 700; margin-top: .25rem; }}
        .status.pending {{ color: #B98200; }}
        .status.submitted {{ color: var(--primary); }}
        .status-dot {{ display: inline-block; width: .55rem; height: .55rem; border-radius: 50%; margin-right: .35rem; background: currentColor; }}
        .section-heading {{
            color: var(--primary); font-size: 1rem; font-weight: 800;
            padding-bottom: .45rem; border-bottom: 2px solid var(--gold); margin-bottom: .8rem;
        }}
        .rating-anchors {{ display: flex; justify-content: space-between; color: var(--muted); font-size: .68rem; margin-top: -.45rem; }}
        .success-mark {{
            width: 6rem; height: 6rem; margin: 2.25rem auto 1.25rem; border-radius: 50%;
            display: grid; place-items: center; background: var(--soft-green); color: var(--primary);
            font-size: 3.4rem; font-weight: 800;
        }}
        .success-title {{ text-align: center; color: var(--primary); font-size: 1.5rem; font-weight: 800; }}
        .success-copy {{ text-align: center; color: var(--muted); max-width: 21rem; margin: .45rem auto 1.5rem; }}
        .empty-state {{ text-align: center; padding: 3rem 1rem; color: var(--muted); }}
        .review-row {{ padding: .55rem 0; border-bottom: 1px solid var(--border); }}
        .review-question {{ color: var(--muted); font-size: .78rem; line-height: 1.35; }}
        .review-answer {{ color: var(--text); font-size: .9rem; font-weight: 700; margin-top: .16rem; }}
        .stButton button, .stFormSubmitButton button {{
            min-height: 2.85rem;
            border-radius: 6px;
            border: 1px solid var(--primary);
            background: var(--primary);
            color: #FFFFFF;
            font-size: .88rem;
            font-weight: 750;
            letter-spacing: 0;
            box-shadow: none;
        }}
        .stButton button:hover, .stFormSubmitButton button:hover {{
            border-color: var(--deep); background: var(--deep); color: #FFFFFF;
        }}
        button[data-testid="stBaseButton-primary"],
        button[data-testid="stBaseButton-primary"] p,
        button[data-testid="stBaseButton-primary"] span {{ color: #FFFFFF !important; }}
        .stButton button p, .stFormSubmitButton button p {{ color: inherit; }}
        .stButton button:focus-visible, .stFormSubmitButton button:focus-visible {{
            outline: 3px solid var(--gold); outline-offset: 2px;
        }}
        .stButton button:disabled {{ background: transparent; color: var(--muted); border-color: var(--border); }}
        .st-key-bottom_nav {{
            position: fixed;
            bottom: 0;
            left: 50%;
            transform: translateX(-50%);
            z-index: 45;
            width: min(480px, 100vw);
            padding: .48rem .55rem .42rem;
            background: var(--surface);
            border-top: 1px solid var(--border);
            box-shadow: 0 -4px 14px var(--shadow);
        }}
        .st-key-bottom_nav [data-testid="stHorizontalBlock"] {{ gap: .35rem; }}
        .st-key-bottom_nav .stButton button {{
            min-height: 3.35rem; padding: .2rem .15rem; border: 0;
            background: transparent; color: var(--muted); font-size: .68rem; line-height: 1.05;
        }}
        .st-key-bottom_nav .stButton button p {{
            color: inherit !important; font-size: .64rem; white-space: nowrap; letter-spacing: 0;
        }}
        .st-key-bottom_nav .stButton button:hover {{ background: var(--soft-green); color: var(--primary); }}
        .st-key-nav_active .stButton button {{ color: var(--primary); font-weight: 800; }}
        div[data-baseweb="progress-bar"] > div > div {{ background-color: var(--border) !important; }}
        div[data-baseweb="progress-bar"] > div > div > div {{ background-color: var(--primary) !important; }}
        [data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmented_controlActive"],
        [data-testid="stButtonGroup"] button[kind="segmented_controlActive"],
        [data-testid="stButtonGroup"] button[aria-pressed="true"],
        [role="radiogroup"] button[data-variant="segmented_control"][aria-checked="true"],
        [role="radiogroup"] button[data-variant="segmented_control"][data-selected="true"],
        [data-testid="stButtonGroup"] button[data-testid="stBaseButton-segmented_controlActive"] p,
        [data-testid="stButtonGroup"] button[kind="segmented_controlActive"] p,
        [data-testid="stButtonGroup"] button[aria-pressed="true"] p,
        [role="radiogroup"] button[data-variant="segmented_control"][aria-checked="true"] p,
        [role="radiogroup"] button[data-variant="segmented_control"][data-selected="true"] p {{
            background: var(--gold) !important; color: #142019 !important; border-color: var(--gold) !important;
        }}
        [data-testid="stButtonGroup"] button,
        [role="radiogroup"] button[data-variant="segmented_control"] {{
            min-height: 2.35rem; color: var(--text); background: var(--surface); border-color: var(--border);
        }}
        textarea, input {{ color: var(--text) !important; background: var(--surface) !important; }}
        [data-testid="stTextArea"] > div > div {{ border-color: var(--border); background: var(--surface); }}
        [data-testid="stAlert"] {{ border-radius: 6px; }}
        @media (max-width: 520px) {{
            [data-testid="stMainBlockContainer"] {{ box-shadow: none; }}
            .assignment-subject {{ font-size: .96rem; }}
            .subject-mark {{ width: 2.8rem; height: 2.8rem; min-width: 2.8rem; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header(back_page: str | None = None) -> None:
    with st.container(key="portal_header"):
        left, title, right = st.columns([0.14, 0.69, 0.17], vertical_alignment="center")
        with left:
            icon = ":material/arrow_back:" if back_page else ":material/menu:"
            if st.button("", icon=icon, key="header_left", help="Back" if back_page else "Menu"):
                if back_page:
                    navigate(back_page)
        with title:
            st.markdown(
                '<div class="header-title">FEU High School<span>Faculty Evaluation</span></div>',
                unsafe_allow_html=True,
            )
        with right:
            dark = st.session_state.portal_theme == "dark"
            icon = ":material/light_mode:" if dark else ":material/dark_mode:"
            if st.button("", icon=icon, key="theme_toggle", help="Switch color theme"):
                st.session_state.portal_theme = "light" if dark else "dark"
                st.rerun()


def render_bottom_nav(active: str) -> None:
    nav_items = (
        ("home", "Home", ":material/home:"),
        ("teachers", "My Teachers", ":material/groups:"),
        ("history", "My Evaluations", ":material/assignment_turned_in:"),
        ("help", "Help", ":material/help:"),
    )
    with st.container(key="bottom_nav"):
        columns = st.columns(4)
        for column, (page, label, icon) in zip(columns, nav_items):
            with column:
                wrapper_key = "nav_active" if page == active else f"nav_{page}"
                with st.container(key=wrapper_key):
                    if st.button(label, icon=icon, key=f"nav_button_{page}", use_container_width=True):
                        navigate(page)


def subject_mark(subject: str) -> str:
    words = [word for word in subject.replace("and", " ").split() if word]
    if not words:
        return "FE"
    if len(words) == 1:
        return words[0][:2].upper()
    return "".join(word[0] for word in words[:2]).upper()


def render_home(student, assignments, submitted: frozenset[str]) -> None:
    render_header()
    completed = len(submitted)
    total = len(assignments)

    with st.container(border=True, key="profile_card"):
        initials = "".join(part[0] for part in student.name.split()[:2]).upper()
        st.markdown(
            f"""
            <div class="portal-card">
              <div class="profile-row">
                <div class="avatar">{html.escape(initials)}</div>
                <div style="flex:1">
                  <div class="profile-name">{html.escape(student.name)}</div>
                  <div class="gold-rule"></div>
                  <div class="profile-meta">Grade {student.grade_level} · {html.escape(student.strand)} · {html.escape(student.section)}</div>
                </div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()
        st.markdown(
            f"""
            <div class="period-row">
              <div><div class="period-label">Evaluation Period</div><div class="period-value">{html.escape(student.evaluation_period)}</div></div>
              <div class="subject-mark">Q2</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with st.container(border=True, key="progress_card"):
        st.markdown('<div class="section-heading">Your Evaluation Progress</div>', unsafe_allow_html=True)
        st.markdown(
            f'<div class="progress-count"><strong>{completed} of {total}</strong> completed</div>',
            unsafe_allow_html=True,
        )
        progress = completed / total if total else 0
        st.progress(progress)
        st.caption(f"{progress:.0%} Complete")

    pending = pending_assignments(assignments, submitted)
    if pending:
        if st.button(
            "Start Evaluation",
            icon=":material/assignment:",
            use_container_width=True,
            type="primary",
        ):
            navigate("teachers")
    else:
        st.success("You have completed all available evaluations.")

    render_bottom_nav("home")


def render_assignment_card(assignment: TeacherAssignment, is_submitted: bool, index: int) -> None:
    with st.container(border=True, key=f"assignment_card_{index}"):
        copy, action = st.columns([0.69, 0.31], vertical_alignment="center")
        with copy:
            status_class = "submitted" if is_submitted else "pending"
            status_text = "Submitted" if is_submitted else "Pending"
            st.markdown(
                f"""
                <div class="assignment-copy">
                  <div class="subject-mark">{html.escape(subject_mark(assignment.subject))}</div>
                  <div>
                    <div class="assignment-subject">{html.escape(assignment.subject)}</div>
                    <div class="assignment-teacher">{html.escape(assignment.teacher_name)}</div>
                    <div class="status {status_class}"><span class="status-dot"></span>{status_text}</div>
                  </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        with action:
            if st.button(
                "Submitted" if is_submitted else "Evaluate",
                key=f"evaluate_{assignment.id}",
                disabled=is_submitted,
                use_container_width=True,
            ):
                select_assignment(assignment.id)


def render_teachers(assignments, submitted: frozenset[str]) -> None:
    render_header()
    st.caption("You can only evaluate teachers assigned to your section.")
    for index, assignment in enumerate(assignments):
        render_assignment_card(assignment, assignment.id in submitted, index)
    render_bottom_nav("teachers")


def evaluation_sections():
    block = DEFAULT_QUESTION_BLOCKS["shs"]
    return (
        ("Teacher Performance", block.faculty_items, "rating"),
        ("Student Experience", block.overall_experience_items, "rating"),
        ("Student Self-Evaluation", block.rci_items, "rating"),
        ("Additional Comments", block.open_ended_items, "comments"),
    )


def render_assignment_heading(assignment: TeacherAssignment) -> None:
    st.markdown(
        f"""
        <div class="assignment-copy" style="margin-bottom:.85rem">
          <div class="subject-mark">{html.escape(subject_mark(assignment.subject))}</div>
          <div>
            <div class="assignment-subject">{html.escape(assignment.teacher_name)}</div>
            <div class="assignment-teacher">{html.escape(assignment.subject)}</div>
          </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_evaluation(assignment: TeacherAssignment | None) -> None:
    if assignment is None:
        navigate("teachers")
        return

    render_header("teachers")
    render_assignment_heading(assignment)
    sections = evaluation_sections()
    section_index = min(st.session_state.evaluation_section, len(sections) - 1)
    title, items, section_type = sections[section_index]
    st.progress(section_index / len(sections))
    st.caption(f"Step {section_index + 1} of {len(sections)}")
    st.markdown(f'<div class="section-heading">{html.escape(title)}</div>', unsafe_allow_html=True)

    with st.form(f"evaluation_form_{assignment.id}_{section_index}", clear_on_submit=False):
        if section_type == "rating":
            for item in items:
                widget_key = f"rating_{assignment.id}_{item.id}"
                saved_value = st.session_state.answers.get(widget_key)
                st.segmented_control(
                    item.text,
                    options=[1, 2, 3, 4, 5],
                    default=saved_value,
                    key=widget_key,
                    selection_mode="single",
                    width="stretch",
                )
                st.markdown(
                    '<div class="rating-anchors"><span>Strongly Disagree</span><span>Strongly Agree</span></div>',
                    unsafe_allow_html=True,
                )
        else:
            for item in items:
                widget_key = f"comment_{assignment.id}_{item.id}"
                st.text_area(
                    item.text,
                    value=st.session_state.comments.get(widget_key, ""),
                    key=widget_key,
                    height=110,
                    max_chars=1000,
                    placeholder="Enter your comments here...",
                )

        back_col, next_col = st.columns(2)
        back_clicked = back_col.form_submit_button(
            "Back",
            icon=":material/arrow_back:",
            use_container_width=True,
        )
        next_label = "Review" if section_index == len(sections) - 1 else "Continue"
        next_icon = ":material/rate_review:" if next_label == "Review" else ":material/arrow_forward:"
        next_clicked = next_col.form_submit_button(
            next_label,
            icon=next_icon,
            use_container_width=True,
            type="primary",
        )

    if back_clicked:
        if section_index == 0:
            navigate("teachers")
        st.session_state.evaluation_section = section_index - 1
        st.rerun()

    if next_clicked:
        if section_type == "rating":
            missing = []
            for item in items:
                widget_key = f"rating_{assignment.id}_{item.id}"
                value = st.session_state.get(widget_key)
                if value is None:
                    missing.append(item.text)
                else:
                    st.session_state.answers[widget_key] = value
            if missing:
                st.error(f"Please answer all {len(items)} statements before continuing.")
                return
        else:
            for item in items:
                widget_key = f"comment_{assignment.id}_{item.id}"
                st.session_state.comments[widget_key] = st.session_state.get(widget_key, "").strip()

        if section_index == len(sections) - 1:
            navigate("review")
        st.session_state.evaluation_section = section_index + 1
        st.rerun()


def render_review(assignment: TeacherAssignment | None) -> None:
    if assignment is None:
        navigate("teachers")
        return

    render_header("evaluation")
    render_assignment_heading(assignment)
    st.markdown('<div class="section-heading">Review Your Responses</div>', unsafe_allow_html=True)

    for title, items, section_type in evaluation_sections():
        with st.expander(title, expanded=title == "Teacher Performance"):
            for item in items:
                prefix = "rating" if section_type == "rating" else "comment"
                key = f"{prefix}_{assignment.id}_{item.id}"
                value = st.session_state.answers.get(key) if section_type == "rating" else st.session_state.comments.get(key)
                display_value = RATING_LABELS.get(value, "Not answered") if section_type == "rating" else (value or "No comment")
                st.markdown(
                    f"""
                    <div class="review-row">
                      <div class="review-question">{html.escape(item.text)}</div>
                      <div class="review-answer">{html.escape(str(display_value))}</div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

    confirmed = st.checkbox("I confirm that these responses reflect my evaluation.")
    edit_col, submit_col = st.columns(2)
    if edit_col.button("Edit", icon=":material/edit:", use_container_width=True):
        st.session_state.evaluation_section = 0
        navigate("evaluation")
    if submit_col.button(
        "Submit",
        icon=":material/send:",
        use_container_width=True,
        type="primary",
        disabled=not confirmed,
    ):
        now = datetime.now()
        st.session_state.submissions = [
            submission
            for submission in st.session_state.submissions
            if not (
                submission.student_id == DEMO_STUDENT.id
                and submission.assignment_id == assignment.id
                and submission.evaluation_period == DEMO_STUDENT.evaluation_period
            )
        ]
        st.session_state.submissions.append(
            SubmissionRecord(
                student_id=DEMO_STUDENT.id,
                assignment_id=assignment.id,
                evaluation_period=DEMO_STUDENT.evaluation_period,
                submitted_at=now,
            )
        )
        st.session_state.last_submission = now
        navigate("submitted")


def render_submitted(assignment: TeacherAssignment | None, assignments, submitted: frozenset[str]) -> None:
    if assignment is None:
        navigate("history")
        return
    render_header()
    st.markdown('<div class="success-mark">✓</div>', unsafe_allow_html=True)
    st.markdown('<div class="success-title">Evaluation Submitted</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="success-copy">Thank you. Your feedback helps us improve teaching and learning.</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div class="gold-rule" style="margin:1.2rem 0"></div>', unsafe_allow_html=True)

    submitted_at = st.session_state.last_submission or datetime.now()
    with st.container(border=True, key="submitted_card"):
        st.markdown(
            f"""
            <div class="submission-copy">
              <div class="subject-mark">{html.escape(subject_mark(assignment.subject))}</div>
              <div>
                <div class="assignment-subject">{html.escape(assignment.teacher_name)}</div>
                <div class="assignment-teacher">{html.escape(assignment.subject)}</div>
                <div class="submission-meta">Submitted on {submitted_at:%B %d, %Y %I:%M %p}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    remaining = pending_assignments(assignments, submitted)
    if remaining:
        if st.button(
            "Evaluate Next Teacher",
            icon=":material/arrow_forward:",
            use_container_width=True,
            type="primary",
        ):
            select_assignment(remaining[0].id)
    if st.button(
        "View Remaining",
        icon=":material/list:",
        use_container_width=True,
    ):
        navigate("teachers")
    render_bottom_nav("history")


def render_history(assignments, submitted: frozenset[str]) -> None:
    render_header()
    st.markdown('<div class="section-heading">My Evaluations</div>', unsafe_allow_html=True)
    completed = [assignment for assignment in assignments if assignment.id in submitted]
    if not completed:
        st.markdown('<div class="empty-state">No evaluations submitted yet.</div>', unsafe_allow_html=True)
    for index, assignment in enumerate(completed):
        render_assignment_card(assignment, True, index + 100)
    render_bottom_nav("history")


def render_help(student) -> None:
    render_header()
    st.markdown('<div class="section-heading">Help</div>', unsafe_allow_html=True)
    st.markdown(
        f"""
        Your profile is currently assigned to **{html.escape(student.section)}**. The app only displays
        subjects and teachers attached to that roster record.

        Contact the evaluation administrator if your section or teacher assignments are incorrect.
        """
    )
    render_bottom_nav("help")


def main() -> None:
    initialize_state()
    inject_styles(st.session_state.portal_theme)
    student, assignments, submitted = portal_data()
    assignment = current_assignment(assignments)
    page = st.session_state.portal_page

    if page == "home":
        render_home(student, assignments, submitted)
    elif page == "teachers":
        render_teachers(assignments, submitted)
    elif page == "evaluation":
        render_evaluation(assignment)
    elif page == "review":
        render_review(assignment)
    elif page == "submitted":
        render_submitted(assignment, assignments, submitted)
    elif page == "history":
        render_history(assignments, submitted)
    elif page == "help":
        render_help(student)
    else:
        st.session_state.portal_page = "home"
        st.rerun()


if __name__ == "__main__":
    main()
