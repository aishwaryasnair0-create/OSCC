# app.py
import streamlit as st
import pandas as pd
from data_io import load_table, DATA_DIR

st.set_page_config(
    page_title="OSCC Hospital Case & Research App",
    layout="wide",
)

# ---------- Global module toggle ----------
if "module_mode" not in st.session_state:
    st.session_state["module_mode"] = "Research"
if "active_study_id" not in st.session_state:
    st.session_state["active_study_id"] = None

st.sidebar.title("Mode & Study")

module = st.sidebar.radio(
    "Module / role",
    ["Research", "Clinic", "Lab"],
    index=["Research", "Clinic", "Lab"].index(st.session_state["module_mode"]),
)
st.session_state["module_mode"] = module

# ---------- Study selector ----------
studies = load_table(
    "studies",
    columns=[
        "StudyID",
        "StudyName",
        "Mode",                 # e.g. Research / Clinic / Hybrid
        "DefaultLabName",       # default lab name
        "DefaultConsentTaker",  # default consent taker
        "LinkedStudies",        # comma-separated StudyIDs for interlinking
        "Notes",
    ],
)

study_options = ["(none)"] + studies["StudyID"].tolist()
current = st.sidebar.selectbox(
    "Active study",
    study_options,
    index=study_options.index(st.session_state["active_study_id"])
    if st.session_state["active_study_id"] in study_options
    else 0,
)

if current == "(none)":
    st.session_state["active_study_id"] = None
    st.sidebar.info("No active study selected.")
else:
    st.session_state["active_study_id"] = current
    row = studies[studies["StudyID"] == current].iloc[0]
    st.sidebar.markdown(f"**Study:** {row['StudyName']}")
    st.sidebar.caption(
        f"Mode: {row.get('Mode','')} · Lab: {row.get('DefaultLabName','')} · "
        f"Consent taker: {row.get('DefaultConsentTaker','')}"
    )

st.sidebar.markdown("---")
st.sidebar.markdown(
    "Use the sidebar to choose **Research / Clinic / Lab** mode and set the "
    "current **Study / project**."
)

st.title("OSCC Hospital Case & Research App")

st.write(
    "Use the pages on the left for research participants, consent, lab work, "
    "clinical patients, and admin. The current module and active study are set "
    "in the sidebar."
)
