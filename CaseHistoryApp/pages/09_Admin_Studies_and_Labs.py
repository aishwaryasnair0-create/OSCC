import streamlit as st
import pandas as pd
from data_io import load_table, save_table

st.title("Admin – Labs, Investigators, Studies / Projects")

mode = st.session_state.get("module_mode", "Research")
st.caption(f"Current module: **{mode}**")
active_study_id = st.session_state.get("active_study_id")

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

tab_labs, tab_inv, tab_studies = st.tabs(["Labs", "Investigators", "Studies / projects"])

# ---------- Labs ----------
with tab_labs:
    st.subheader("Registered labs")

    if not labs_df.empty:
        st.dataframe(labs_df, use_container_width=True)
    else:
        st.info("No labs registered yet.")

    with st.form("lab_form"):
        st.markdown("### Add / update lab")
        lab_id = st.text_input("Lab ID (short code, e.g. LAB1)", "")
        lab_name = st.text_input("Lab name")
        lab_type = st.selectbox(
            "Lab type",
            ["Extraction", "PCR", "NGS", "Combined", "Other"],
        )
        contact = st.text_input("Contact person (optional)")
        email = st.text_input("Email (optional)")
        phone = st.text_input("Phone (optional)")
        address = st.text_area("Address (optional)")
        notes = st.text_area("Notes (optional)")

        save_lab = st.form_submit_button("Save lab")

    if save_lab:
        if not lab_id.strip() or not lab_name.strip():
            st.error("Lab ID and Lab name are required.")
        else:
            new_row = {
                "LabID": lab_id.strip(),
                "LabName": lab_name.strip(),
                "LabType": lab_type,
                "ContactPerson": contact.strip(),
                "Email": email.strip(),
                "Phone": phone.strip(),
                "Address": address.strip(),
                "Notes": notes.strip(),
            }
            labs_df = labs_df[labs_df["LabID"] != lab_id.strip()]
            labs_df = pd.concat([labs_df, pd.DataFrame([new_row])], ignore_index=True)
            save_table(labs_df, "labs")
            st.success("Lab saved.")
            st.rerun()

# ---------- Investigators ----------
with tab_inv:
    st.subheader("Investigators / clinicians")

    if not inv_df.empty:
        st.dataframe(inv_df, use_container_width=True)
    else:
        st.info("No investigators added yet.")

    with st.form("inv_form"):
        st.markdown("### Add / update investigator")
        inv_id = st.text_input("Investigator ID (short code)", "")
        name = st.text_input("Name")
        role = st.text_input("Role (PI, Co-PI, Resident, etc.)")
        aff = st.text_input("Affiliation / department")
        email = st.text_input("Email (optional)")
        phone = st.text_input("Phone (optional)")
        is_default_consent = st.checkbox(
            "Use as default consent taker for new studies?",
            value=False,
        )

        save_inv = st.form_submit_button("Save investigator")

    if save_inv:
        if not inv_id.strip() or not name.strip():
            st.error("Investigator ID and Name are required.")
        else:
            new_row = {
                "InvestigatorID": inv_id.strip(),
                "Name": name.strip(),
                "Role": role.strip(),
                "Affiliation": aff.strip(),
                "Email": email.strip(),
                "Phone": phone.strip(),
                "IsConsentTakerDefault": bool(is_default_consent),
            }
            inv_df = inv_df[inv_df["InvestigatorID"] != inv_id.strip()]
            inv_df = pd.concat([inv_df, pd.DataFrame([new_row])], ignore_index=True)
            save_table(inv_df, "investigators")
            st.success("Investigator saved.")
            st.rerun()

# ---------- Studies / projects ----------
with tab_studies:
    st.subheader("Studies / research projects")

    if not studies_df.empty:
        st.dataframe(studies_df, use_container_width=True)
    else:
        st.info("No studies created yet.")

    lab_names = [""] + labs_df["LabName"].tolist()
    consent_names = [""] + inv_df["Name"].tolist()

    with st.form("study_form"):
        st.markdown("### Add / update study / project")

        study_id = st.text_input("Study ID (short code, e.g. OSCC_PILOT)", "")
        study_name = st.text_input("Study name", "OSCC salivary miRNA pilot")
        mode = st.selectbox(
            "Mode",
            ["Research", "Clinic", "Hybrid"],
        )
        default_lab_name = st.selectbox(
            "Default lab name (for PCR / extraction pages)",
            lab_names,
        )
        default_consent_taker = st.selectbox(
            "Default consent taker (for consent page)",
            consent_names,
        )
        linked_studies = st.text_input(
            "Linked study IDs (comma separated, optional)",
        )
        notes = st.text_area("Study notes (optional)")

        save_study = st.form_submit_button("Save study")

    if save_study:
        if not study_id.strip() or not study_name.strip():
            st.error("Study ID and Study name are required.")
        else:
            new_row = {
                "StudyID": study_id.strip(),
                "StudyName": study_name.strip(),
                "Mode": mode,
                "DefaultLabName": default_lab_name.strip(),
                "DefaultConsentTaker": default_consent_taker.strip(),
                "LinkedStudies": linked_studies.strip(),
                "Notes": notes.strip(),
            }
            studies_df = studies_df[studies_df["StudyID"] != study_id.strip()]
            studies_df = pd.concat([studies_df, pd.DataFrame([new_row])], ignore_index=True)
            save_table(studies_df, "studies")
            st.success("Study saved.")
            st.rerun()

    if active_study_id:
        st.info(f"Current active study in sidebar: **{active_study_id}**")
    else:
        st.info("No active study selected in sidebar.")
