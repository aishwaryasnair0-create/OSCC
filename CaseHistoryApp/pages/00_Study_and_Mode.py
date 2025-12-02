import streamlit as st
import pandas as pd
from data_io import load_table, save_table

st.title("Study / Project setup and mode")

# ---------- Tables ----------
labs_cols = [
    "LabID",
    "LabName",
    "LabType",
    "ContactPerson",
    "Email",
    "Phone",
    "Address",
    "Notes",
]
inv_cols = [
    "InvestigatorID",
    "Name",
    "Role",
    "Affiliation",
    "Email",
    "Phone",
    "IsConsentTakerDefault",
]
studies_cols = [
    "StudyID",
    "StudyName",
    "Mode",
    "DefaultLabName",
    "DefaultConsentTaker",
    "LinkedStudies",
    "Notes",
]

labs_df = load_table("labs", columns=labs_cols)
inv_df = load_table("investigators", columns=inv_cols)
studies_df = load_table("studies", columns=studies_cols)

# ---------- Global module toggle (mode) ----------
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

# ---------- Choose active study ----------
study_ids = studies_df["StudyID"].tolist()
study_options = ["(none)"] + study_ids

current = st.sidebar.selectbox(
    "Active study / project",
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
    row = studies_df[studies_df["StudyID"] == current].iloc[0]
    st.sidebar.markdown(f"**Study:** {row['StudyName']}")
    st.sidebar.caption(
        f"Mode: {row.get('Mode','')} · "
        f"Lab: {row.get('DefaultLabName','')} · "
        f"Consent taker: {row.get('DefaultConsentTaker','')}"
    )

st.sidebar.markdown("---")
st.sidebar.caption("Set mode + active study here. All other pages can read these defaults.")

st.caption(f"Current module: **{module}**")
if st.session_state["active_study_id"]:
    st.caption(f"Active study: **{st.session_state['active_study_id']}**")
else:
    st.caption("Active study: **none**")

st.markdown("---")

col_left, col_right = st.columns(2)

# ======================================================================
# LEFT: Existing studies with 1-based numbering
# ======================================================================
with col_left:
    st.subheader("Existing studies / projects")

    if studies_df.empty:
        st.info("No studies created yet.")
    else:
        display_df = studies_df.copy()
        # Insert a 1-based numbering column "No."
        display_df.insert(0, "No.", range(1, len(display_df) + 1))
        st.dataframe(display_df, use_container_width=True)

# ======================================================================
# RIGHT: Register / edit / delete a study
# ======================================================================
with col_right:
    st.subheader("Register / edit a study or research project")

    # simple lists for dropdowns
    lab_names = [""] + labs_df["LabName"].tolist()
    consent_names = [""] + inv_df["Name"].tolist()

    # Select study to edit
    edit_options = ["(new study)"] + studies_df["StudyID"].tolist()
    selected_edit = st.selectbox(
        "Select an existing study to edit",
        edit_options,
    )

    # Determine default values depending on whether we edit or create new
    if selected_edit != "(new study)" and not studies_df.empty:
        row_edit = studies_df[studies_df["StudyID"] == selected_edit].iloc[0]
        def_id = row_edit["StudyID"]
        def_name = row_edit["StudyName"]
        def_mode = row_edit.get("Mode", "Research")
        def_lab = row_edit.get("DefaultLabName", "")
        def_consent = row_edit.get("DefaultConsentTaker", "")
        def_linked = row_edit.get("LinkedStudies", "")
        def_notes = row_edit.get("Notes", "")
    else:
        def_id = "OSCC_PILOT"
        def_name = "OSCC salivary miRNA pilot"
        def_mode = "Research"
        def_lab = labs_df["LabName"].iloc[0] if not labs_df.empty else ""
        def_consent = ""
        def_linked = ""
        def_notes = "Pilot: 15 cases + 15 controls, 3 matrices each (WS, WS+EC, EC)."

    # Helper to get index safely for selectboxes
    def get_index_safe(options, value):
        try:
            return options.index(value)
        except ValueError:
            return 0

    with st.form("study_form"):
        study_id = st.text_input("Study ID (short code)", value=def_id)
        study_name = st.text_input("Study name", value=def_name)
        mode_sel = st.selectbox(
            "Typical mode for this study",
            ["Research", "Clinic", "Hybrid"],
            index=get_index_safe(["Research", "Clinic", "Hybrid"], def_mode),
        )
        default_lab_name = st.selectbox(
            "Default lab name (for extraction / PCR / NGS pages)",
            lab_names,
            index=get_index_safe(lab_names, def_lab),
        )
        default_consent_taker = st.selectbox(
            "Default consent taker name (for consent page)",
            consent_names,
            index=get_index_safe(consent_names, def_consent),
        )
        linked_studies = st.text_input(
            "Linked study IDs (comma separated, optional)",
            value=def_linked,
        )
        notes = st.text_area(
            "Study notes (optional)",
            value=def_notes,
        )

        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            save_study = st.form_submit_button("Save / update study")
        with col_btn2:
            delete_study = st.form_submit_button(
                "Delete this study",
                help="Deletes the selected study from the list.",
            )

    # Handle delete first
    if delete_study:
        if selected_edit == "(new study)":
            st.error("Select an existing study above before deleting.")
        else:
            studies_df = studies_df[studies_df["StudyID"] != selected_edit]
            save_table(studies_df, "studies")
            # If this was the active study, clear it
            if st.session_state.get("active_study_id") == selected_edit:
                st.session_state["active_study_id"] = None
            st.success(f"Study '{selected_edit}' deleted.")
            st.rerun()

    # Handle save / update
    if save_study:
        if not study_id.strip() or not study_name.strip():
            st.error("Study ID and Study name are required.")
        else:
            new_row = {
                "StudyID": study_id.strip(),
                "StudyName": study_name.strip(),
                "Mode": mode_sel,
                "DefaultLabName": default_lab_name.strip(),
                "DefaultConsentTaker": default_consent_taker.strip(),
                "LinkedStudies": linked_studies.strip(),
                "Notes": notes.strip(),
            }
            # Remove any existing row with same StudyID, then append
            studies_df = studies_df[studies_df["StudyID"] != study_id.strip()]
            studies_df = pd.concat([studies_df, pd.DataFrame([new_row])], ignore_index=True)
            save_table(studies_df, "studies")
            st.success(f"Study '{study_id.strip()}' saved/updated.")
            # Optionally set it as active immediately
            st.session_state["active_study_id"] = study_id.strip()
            st.rerun()

st.markdown("---")
st.subheader("Quick add: lab and investigator (for defaults)")

c1, c2 = st.columns(2)

with c1:
    st.markdown("**Add lab (short form)**")
    with st.form("quick_lab"):
        lab_name_q = st.text_input("Lab name", "")
        lab_type_q = st.selectbox(
            "Type",
            ["Extraction", "PCR", "NGS", "Combined", "Other"],
        )
        save_lab_q = st.form_submit_button("Save lab")
    if save_lab_q:
        if not lab_name_q.strip():
            st.error("Lab name required.")
        else:
            next_id = f"LAB{len(labs_df) + 1}"
            new_lab = {
                "LabID": next_id,
                "LabName": lab_name_q.strip(),
                "LabType": lab_type_q,
                "ContactPerson": "",
                "Email": "",
                "Phone": "",
                "Address": "",
                "Notes": "",
            }
            labs_df = pd.concat([labs_df, pd.DataFrame([new_lab])], ignore_index=True)
            save_table(labs_df, "labs")
            st.success(f"Lab '{lab_name_q}' saved as {next_id}.")
            st.rerun()

with c2:
    st.markdown("**Add investigator / consent taker (short form)**")
    with st.form("quick_inv"):
        inv_name_q = st.text_input("Name", "")
        role_q = st.text_input("Role", "PI / Resident / Staff")
        save_inv_q = st.form_submit_button("Save investigator")
    if save_inv_q:
        if not inv_name_q.strip():
            st.error("Name required.")
        else:
            next_id = f"INV{len(inv_df) + 1}"
            new_inv = {
                "InvestigatorID": next_id,
                "Name": inv_name_q.strip(),
                "Role": role_q.strip(),
                "Affiliation": "",
                "Email": "",
                "Phone": "",
                "IsConsentTakerDefault": True,
            }
            inv_df = pd.concat([inv_df, pd.DataFrame([new_inv])], ignore_index=True)
            save_table(inv_df, "investigators")
            st.success(f"Investigator '{inv_name_q}' saved as {next_id}.")
            st.rerun()

st.markdown("---")
st.info(
    "Step 1: use this page to create your **study / project** and select it as active "
    "in the left sidebar. Then move through the Research pages (Participants, "
    "Consent, Samples, Lab, Risk). All those pages can read the active study and "
    "defaults (lab name, consent taker) from here."
)
