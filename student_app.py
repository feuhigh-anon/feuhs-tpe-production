"""Student-facing Streamlit prototype for faculty evaluations."""

from __future__ import annotations

import base64
import html
import os
from datetime import datetime
from pathlib import Path

import streamlit as st

from feval.models import QuestionBlock
from feval.questions import DEFAULT_QUESTION_BLOCKS
from feval.student_demo_data import DEMO_ASSIGNMENTS, DEMO_STUDENT, DEMO_SUBMISSIONS
from feval.student_portal import (
    SubmissionRecord,
    TeacherAssignment,
    assignments_for_student,
    pending_assignments,
    submitted_assignment_ids,
)
from feval.supabase_portal import (
    AuthSession,
    PortalAuthenticationError,
    PortalConfigurationError,
    PortalDataError,
    PortalSubmissionError,
    PortalSnapshot,
    SupabaseSettings,
    load_portal_snapshot,
    response_payload,
    restore_session,
    sign_in_with_password,
    sign_out,
    submit_evaluation,
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
CLIENT_VERSION = "streamlit-alpha-1"
AUTH_STATE_KEYS = (
    "supabase_session",
    "supabase_snapshot",
    "supabase_client",
)
ASSET_DIRECTORY = Path(__file__).resolve().parent / "assets"


@st.cache_data(show_spinner=False)
def asset_data_uri(filename: str) -> str:
    path = ASSET_DIRECTORY / filename
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def configured_supabase_settings() -> SupabaseSettings | None:
    try:
        secrets = st.secrets
        url = str(secrets.get("SUPABASE_URL", "") or "").strip()
        publishable_key = str(secrets.get("SUPABASE_PUBLISHABLE_KEY", "") or "").strip()
    except (FileNotFoundError, RuntimeError):
        url = ""
        publishable_key = ""

    url = str(os.getenv("SUPABASE_URL", url)).strip()
    publishable_key = str(os.getenv("SUPABASE_PUBLISHABLE_KEY", publishable_key)).strip()
    if not url and not publishable_key:
        return None
    if not url or not publishable_key:
        raise PortalConfigurationError(
            "SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be configured together."
        )
    settings = SupabaseSettings(url=url, publishable_key=publishable_key)
    settings.validate()
    return settings


def initialize_state(mode: str) -> None:
    if st.session_state.get("portal_mode") not in (None, mode):
        clear_portal_state(clear_theme=False)
    defaults = {
        "portal_mode": mode,
        "portal_page": "home",
        "portal_theme": "light",
        "selected_assignment_id": None,
        "evaluation_section": 0,
        "answers": {},
        "comments": {},
        "submissions": list(DEMO_SUBMISSIONS) if mode == "demo" else [],
        "last_submission": None,
        "supabase_session": None,
        "supabase_snapshot": None,
        "supabase_client": None,
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def clear_portal_state(*, clear_theme: bool) -> None:
    theme = st.session_state.get("portal_theme", "light")
    for key in list(st.session_state):
        del st.session_state[key]
    if not clear_theme:
        st.session_state.portal_theme = theme


def clear_authentication() -> None:
    client = st.session_state.get("supabase_client")
    if client is not None:
        sign_out(client)
    for key in AUTH_STATE_KEYS:
        st.session_state.pop(key, None)
    st.session_state.portal_page = "home"
    st.session_state.selected_assignment_id = None
    st.session_state.answers = {}
    st.session_state.comments = {}
    st.rerun()


def navigate(page: str) -> None:
    st.session_state.portal_page = page
    st.rerun()


def select_assignment(assignment_id: str) -> None:
    st.session_state.selected_assignment_id = assignment_id
    st.session_state.evaluation_section = 0
    navigate("evaluation")


def demo_portal_data():
    student = DEMO_STUDENT
    assignments = assignments_for_student(student, DEMO_ASSIGNMENTS)
    submitted = submitted_assignment_ids(student, st.session_state.submissions)
    block = DEFAULT_QUESTION_BLOCKS[student.school_level.lower()]
    return student, assignments, submitted, block


def authenticated_portal_data(settings: SupabaseSettings):
    saved_session = st.session_state.get("supabase_session")
    if not isinstance(saved_session, AuthSession):
        return None
    client, refreshed_session = restore_session(settings, saved_session)
    st.session_state.supabase_session = refreshed_session
    st.session_state.supabase_client = client
    snapshot = st.session_state.get("supabase_snapshot")
    if not isinstance(snapshot, PortalSnapshot):
        snapshot = load_portal_snapshot(client, refreshed_session)
        st.session_state.supabase_snapshot = snapshot
    submitted = submitted_assignment_ids(snapshot.student, snapshot.submissions)
    return snapshot.student, snapshot.assignments, submitted, snapshot.question_block


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
        .st-key-login_page {{ position: relative; min-height: calc(100vh - 5.75rem); }}
        .st-key-login_theme {{
            position: absolute; top: 1rem; right: .1rem; z-index: 20; width: 2.7rem;
        }}
        .st-key-login_theme .stButton button {{
            width: 2.55rem; min-height: 2.55rem; padding: 0; border: 1px solid rgba(255,255,255,.48);
            border-radius: 6px; background: rgba(0,0,0,.12); color: #FFFFFF; box-shadow: none;
        }}
        .st-key-login_theme .stButton button:hover {{
            background: var(--gold); border-color: var(--gold); color: #142019;
        }}
        .login-hero {{
            position: relative; overflow: hidden; width: calc(100% + 2rem); min-height: 13.5rem;
            margin: 0 -1rem 1.65rem; padding: 2.1rem 1.45rem 1.45rem;
            background: var(--deep); border-bottom: 5px solid var(--gold); color: #FFFFFF;
        }}
        .login-architecture {{
            position: absolute; inset: 0; z-index: 0; width: 100%; height: 100%;
            object-fit: cover; object-position: center bottom; opacity: .2; pointer-events: none;
        }}
        .login-brand-row {{
            position: relative; z-index: 2; display: flex; align-items: center;
            gap: 1rem; max-width: 20rem;
        }}
        .login-logo {{
            width: 4.6rem; height: 4.6rem; min-width: 4.6rem; object-fit: contain;
            filter: drop-shadow(0 .2rem .25rem rgba(0,0,0,.22));
        }}
        .login-brand-copy {{ min-width: 0; }}
        .login-kicker {{
            display: block; color: var(--gold); font-size: .67rem; font-weight: 800;
            line-height: 1.2; margin-bottom: .4rem; letter-spacing: 0;
        }}
        .login-brand-copy strong {{
            display: block; color: #FFFFFF; font-size: 1.55rem; line-height: 1.08; font-weight: 800;
        }}
        .login-brand-copy em {{
            display: block; color: rgba(255,255,255,.82); font-size: .82rem;
            font-style: normal; margin-top: .42rem;
        }}
        .login-hero-rule {{
            position: relative; z-index: 2; width: 3.5rem; height: 3px;
            background: var(--gold); margin: 1.35rem 0 .7rem;
        }}
        .login-portal-label {{
            position: relative; z-index: 2; color: rgba(255,255,255,.92);
            font-size: .76rem; font-weight: 650;
        }}
        .login-intro {{ margin: 0 .1rem 1rem; }}
        .login-eyebrow {{ color: var(--primary); font-size: .68rem; font-weight: 850; margin-bottom: .35rem; }}
        .login-heading {{ color: var(--text); font-size: 1.35rem; font-weight: 820; line-height: 1.2; }}
        .login-copy {{ color: var(--muted); font-size: .84rem; line-height: 1.45; margin-top: .35rem; }}
        .st-key-login_page [data-testid="stForm"] {{
            padding: 1.05rem 1rem 1rem; border: 1px solid var(--border);
            border-top: 3px solid var(--gold); border-radius: 6px;
            background: var(--surface-raised); box-shadow: 0 5px 18px var(--shadow);
        }}
        .st-key-login_page [data-testid="stForm"] [data-testid="stWidgetLabel"] p {{
            color: var(--text); font-size: .78rem; font-weight: 750;
        }}
        .st-key-login_page [data-testid="stTextInput"] input {{
            min-height: 2.75rem; border-color: var(--border); border-radius: 5px;
        }}
        .st-key-login_page [data-testid="stTextInput"] input:focus {{
            border-color: var(--primary); box-shadow: 0 0 0 1px var(--primary);
        }}
        .st-key-login_page .stFormSubmitButton {{ margin-top: .15rem; }}
        .login-assurance {{
            display: flex; align-items: center; gap: .75rem; margin: 1rem .1rem 0;
            padding: .8rem 0; border-top: 1px solid var(--border);
        }}
        .login-assurance-mark {{
            width: 2.15rem; height: 2.15rem; min-width: 2.15rem; display: grid; place-items: center;
            border: 1px solid var(--border); border-radius: 50%; background: var(--soft-green);
            color: var(--primary); font-size: .63rem; font-weight: 850;
        }}
        .login-assurance strong {{ display: block; color: var(--text); font-size: .76rem; }}
        .login-assurance span {{ display: block; color: var(--muted); font-size: .7rem; margin-top: .08rem; }}
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
        [data-testid="stExpander"] details {{
            overflow: hidden;
            border: 1px solid var(--border) !important;
            border-radius: 6px;
            background: var(--surface) !important;
        }}
        [data-testid="stExpander"] summary {{
            background: var(--surface) !important;
            color: var(--text) !important;
        }}
        [data-testid="stExpander"] details[open] > summary,
        [data-testid="stExpander"] summary:hover {{ background: var(--soft-green) !important; }}
        [data-testid="stExpander"] summary p,
        [data-testid="stExpander"] summary span {{ color: var(--text) !important; }}
        [data-testid="stExpanderDetails"] {{
            background: var(--surface) !important;
            color: var(--text) !important;
            border-top: 1px solid var(--border) !important;
        }}
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
        button[data-testid="stBaseButton-primary"] span,
        button[data-testid="stBaseButton-primaryFormSubmit"],
        button[data-testid="stBaseButton-primaryFormSubmit"] p,
        button[data-testid="stBaseButton-primaryFormSubmit"] span {{ color: #FFFFFF !important; }}
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
            .login-hero {{ min-height: 12.8rem; padding-top: 1.85rem; }}
            .login-brand-copy strong {{ font-size: 1.42rem; }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_login(settings: SupabaseSettings) -> None:
    logo_uri = asset_data_uri("feu-high-school-logo.png")
    architecture_uri = asset_data_uri("feu-architecture-line-art.png")
    with st.container(key="login_page"):
        with st.container(key="login_theme"):
            dark = st.session_state.portal_theme == "dark"
            icon = ":material/light_mode:" if dark else ":material/dark_mode:"
            if st.button("", icon=icon, key="login_theme_toggle", help="Switch color theme"):
                st.session_state.portal_theme = "light" if dark else "dark"
                st.rerun()

        st.markdown(
            f"""
            <div class="login-hero">
              <img class="login-architecture" src="{architecture_uri}" alt="">
              <div class="login-brand-row">
                <img class="login-logo" src="{logo_uri}" alt="FEU High School logo">
                <div class="login-brand-copy">
                  <span class="login-kicker">FEU HIGH SCHOOL</span>
                  <strong>Faculty Evaluation</strong>
                  <em>Student Portal</em>
                </div>
              </div>
              <div class="login-hero-rule"></div>
              <div class="login-portal-label">Confidential evaluation access</div>
            </div>
            <div class="login-intro">
              <div class="login-eyebrow">STUDENT ACCESS</div>
              <div class="login-heading">Welcome back</div>
              <div class="login-copy">Sign in with the evaluation account issued by your school.</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        with st.form("student_login", clear_on_submit=False):
            email = st.text_input(
                "Email",
                placeholder="Enter your evaluation email",
                autocomplete="email",
            )
            password = st.text_input(
                "Password",
                type="password",
                placeholder="Enter your password",
                autocomplete="current-password",
            )
            submitted = st.form_submit_button(
                "Sign In",
                icon=":material/login:",
                type="primary",
                use_container_width=True,
            )
        st.markdown(
            """
            <div class="login-assurance">
              <div class="login-assurance-mark">ID</div>
              <div><strong>Authorized access</strong><span>Only school-issued evaluation accounts can sign in.</span></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    if submitted:
        if not email.strip() or not password:
            st.error("Enter both your email and password.")
            return
        try:
            client, session = sign_in_with_password(settings, email, password)
        except PortalAuthenticationError:
            st.error("Sign-in failed. Check your account details and try again.")
            return
        st.session_state.supabase_client = client
        st.session_state.supabase_session = session
        st.session_state.supabase_snapshot = None
        st.session_state.portal_page = "home"
        st.rerun()


def render_header(back_page: str | None = None) -> None:
    with st.container(key="portal_header"):
        authenticated = st.session_state.get("portal_mode") == "supabase"
        if authenticated:
            left, title, theme_column, logout_column = st.columns(
                [0.13, 0.59, 0.14, 0.14], vertical_alignment="center"
            )
        else:
            left, title, theme_column = st.columns(
                [0.14, 0.69, 0.17], vertical_alignment="center"
            )
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
        with theme_column:
            dark = st.session_state.portal_theme == "dark"
            icon = ":material/light_mode:" if dark else ":material/dark_mode:"
            if st.button("", icon=icon, key="theme_toggle", help="Switch color theme"):
                st.session_state.portal_theme = "light" if dark else "dark"
                st.rerun()
        if authenticated:
            with logout_column:
                if st.button("", icon=":material/logout:", key="logout", help="Sign out"):
                    clear_authentication()


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
    profile_parts = [f"Grade {student.grade_level}"]
    if student.strand:
        profile_parts.append(student.strand)
    profile_parts.append(student.section)
    profile_meta = " · ".join(profile_parts)

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
                  <div class="profile-meta">{html.escape(profile_meta)}</div>
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
              <div class="subject-mark">{html.escape(subject_mark(student.evaluation_period))}</div>
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


def evaluation_sections(block: QuestionBlock):
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


def render_evaluation(assignment: TeacherAssignment | None, block: QuestionBlock) -> None:
    if assignment is None:
        navigate("teachers")
        return

    render_header("teachers")
    render_assignment_heading(assignment)
    sections = evaluation_sections(block)
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
            required_count = sum(item.required for item in items)
            st.caption(
                f"All {required_count} required qualitative responses must be completed. Enter N/A or Not "
                "applicable when you have no additional feedback."
            )
            for item in items:
                widget_key = f"comment_{assignment.id}_{item.id}"
                st.text_area(
                    item.text,
                    value=st.session_state.comments.get(widget_key, ""),
                    key=widget_key,
                    height=110,
                    max_chars=1000,
                    placeholder="Enter feedback or N/A...",
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
                if value is None and item.required:
                    missing.append(item.text)
                elif value is not None:
                    st.session_state.answers[widget_key] = value
            if missing:
                st.error(f"Please answer the {len(missing)} remaining required statements before continuing.")
                return
        else:
            comment_values = {}
            missing = []
            for item in items:
                widget_key = f"comment_{assignment.id}_{item.id}"
                value = st.session_state.get(widget_key, "").strip()
                comment_values[widget_key] = value
                if not value and item.required:
                    missing.append(item.text)
            if missing:
                st.error(
                    f"Please complete the {len(missing)} remaining required qualitative responses before reviewing. "
                    "Enter N/A or Not applicable when you have no additional feedback."
                )
                return
            st.session_state.comments.update(comment_values)

        if section_index == len(sections) - 1:
            navigate("review")
        st.session_state.evaluation_section = section_index + 1
        st.rerun()


def render_review(
    assignment: TeacherAssignment | None,
    block: QuestionBlock,
    student,
) -> None:
    if assignment is None:
        navigate("teachers")
        return

    render_header("evaluation")
    render_assignment_heading(assignment)
    st.markdown('<div class="section-heading">Review Your Responses</div>', unsafe_allow_html=True)

    for title, items, section_type in evaluation_sections(block):
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
        if st.session_state.portal_mode == "supabase":
            client = st.session_state.get("supabase_client")
            if client is None:
                st.error("Your session is unavailable. Sign in again before submitting.")
                return
            try:
                responses = response_payload(
                    block,
                    assignment.id,
                    st.session_state.answers,
                    st.session_state.comments,
                )
                submit_evaluation(
                    client,
                    assignment.id,
                    responses,
                    client_version=CLIENT_VERSION,
                )
            except PortalSubmissionError as exc:
                st.error(str(exc))
                return
            st.session_state.supabase_snapshot = None
        else:
            st.session_state.submissions = [
                submission
                for submission in st.session_state.submissions
                if not (
                    submission.student_id == student.id
                    and submission.assignment_id == assignment.id
                    and submission.evaluation_period == student.evaluation_period
                )
            ]
            st.session_state.submissions.append(
                SubmissionRecord(
                    student_id=student.id,
                    assignment_id=assignment.id,
                    evaluation_period=student.evaluation_period,
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


def render_portal_error(message: str) -> None:
    render_header()
    st.error(message)
    st.caption("Contact the evaluation administrator if this account should have access.")


def main() -> None:
    try:
        settings = configured_supabase_settings()
    except PortalConfigurationError as exc:
        initialize_state("supabase")
        inject_styles(st.session_state.portal_theme)
        st.error(f"Supabase configuration error: {exc}")
        return

    mode = "supabase" if settings is not None else "demo"
    initialize_state(mode)
    inject_styles(st.session_state.portal_theme)
    if settings is None:
        student, assignments, submitted, block = demo_portal_data()
    else:
        if not isinstance(st.session_state.get("supabase_session"), AuthSession):
            render_login(settings)
            return
        try:
            portal = authenticated_portal_data(settings)
        except PortalAuthenticationError:
            for key in AUTH_STATE_KEYS:
                st.session_state.pop(key, None)
            st.error("Your session has expired. Sign in again.")
            render_login(settings)
            return
        except PortalDataError as exc:
            render_portal_error(str(exc))
            return
        if portal is None:
            render_login(settings)
            return
        student, assignments, submitted, block = portal

    assignment = current_assignment(assignments)
    page = st.session_state.portal_page

    if page == "home":
        render_home(student, assignments, submitted)
    elif page == "teachers":
        render_teachers(assignments, submitted)
    elif page == "evaluation":
        render_evaluation(assignment, block)
    elif page == "review":
        render_review(assignment, block, student)
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
