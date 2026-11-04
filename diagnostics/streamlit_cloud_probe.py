"""Temporary Streamlit Cloud probe for separating frontend/runtime issues."""

import platform

import streamlit as st


st.set_page_config(
    page_title="Temporary Streamlit Cloud Probe",
    page_icon="🩺",
    layout="centered",
)

st.title("Streamlit Cloud connection probe")
st.write(
    "This temporary page checks whether Streamlit can render its built-in "
    "widgets and maintain an interactive app connection."
)

st.caption(f"Streamlit: {st.__version__} · Python: {platform.python_version()}")

st.text_input("Text input check", placeholder="Type TEST")
if st.button("Check app interaction"):
    st.success("The app received the interaction and reran successfully.")

st.caption(
    "Do not enter real credentials or student information. "
    "This probe does not connect to Supabase or read app secrets."
)
