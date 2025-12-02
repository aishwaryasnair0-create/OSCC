# pages/10_Clinical_Patients.py

import streamlit as st
import pandas as pd
from datetime import datetime

from data_io import load_table, save_table

from utils.navigation import require_module

require_module("Clinic")

st.title("Clinical Patients – registration")

# --------------------------------------------------------------------
# Context: mode and active study
# --------------------------------------------------------------------
mode = st.session_state.get("module_mode", "Clinic")
active_study_id = st.session_state.get("active_study_id")

st.caption(f"Current module: **{mode}**")
if active_study_id:
    st.caption(f"Linked study / project (if any): **{active_study_id}**")
else:
    st.caption("Linked study / project: **none**")

st.markdown("---")

# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def iso_now():
    return datetime.now().isoformat(timespec="seconds")


def generate_clinical_id(existing_ids: list[str]) -> str:
    """
    ClinicalID pattern: CLIN-0001, CLIN-0002, ...
    Always 1-based (no CLIN-0000).
    """
    prefix = "CLIN-"
    nums = []
    for cid in existing_ids:
        if isinstance(cid, str) and cid.startswith(prefix):
            suffix = cid.split("-")[-1]
            try:
                nums.append(int(suffix))
            except ValueError:
                continue
    next_num = max(nums) + 1 if nums else 1
    return f"{prefix}{next_num:04d}"


def get_index_safe(options, value):
    try:
        return options.index(value)
    except ValueError:
        return 0


# --------------------------------------------------------------------
# Load / init clinical patients table
# --------------------------------------------------------------------
cols = [
    "ClinicalID",
    "Name",
    "Age",
    "Sex",
    "Phone",
    "MRN",
    "Address",
    "City",
    "State",
    "PIN",
    "Email",
    "ClinicalCategory",
    "LinkedResearchID",
    "LinkedStudyID",
    "CreatedAt",
    "UpdatedAt",
]
clin_df = load_table("clinical_patients", columns=cols)

# Sort so that latest patients are on top (descending by CreatedAt, then ClinicalID)
if not clin_df.empty:
    if "CreatedAt" in clin_df.columns:
        clin_df = clin_df.sort_values(
            by=["CreatedAt", "ClinicalID"],
            ascending=[False, False],
        )
    else:
        clin_df = clin_df.sort_values(by="ClinicalID", ascending=False)

# --------------------------------------------------------------------
# Patient selection – search + edit vs new
# --------------------------------------------------------------------
st.subheader("Select patient to edit (or choose new)")

# Search box to filter by name or ClinicalID
search_text = st.text_input(
    "Search by name or ClinicalID",
    value="",
    help="Start typing patient name or ClinicalID to filter the list below.",
)

if clin_df.empty:
    filtered_df = pd.DataFrame(columns=clin_df.columns)
else:
    if search_text.strip():
        s = search_text.strip()
        mask = (
            clin_df["Name"].astype(str).str.contains(s, case=False, na=False)
            | clin_df["ClinicalID"].astype(str).str.contains(s, case=False, na=False)
        )
        filtered_df = clin_df[mask]
    else:
        filtered_df = clin_df

if filtered_df.empty:
    edit_options = ["(new patient)"]
    existing_row = None
    st.info("No existing patients match your search. You can register a new patient below.")
else:
    edit_options = ["(new patient)"] + [
        f"{row.ClinicalID} – {row.Name}" for _, row in filtered_df.iterrows()
    ]
    selected_label = st.selectbox("Patient", edit_options)
    if selected_label == "(new patient)":
        existing_row = None
    else:
        selected_cid = selected_label.split(" – ")[0]
        existing_row = clin_df[clin_df["ClinicalID"] == selected_cid].iloc[0]

# --------------------------------------------------------------------
# Defaults for form fields
# --------------------------------------------------------------------
if existing_row is not None:
    def_cid = existing_row["ClinicalID"]
    def_name = existing_row["Name"]
    def_age = int(existing_row["Age"]) if pd.notna(existing_row["Age"]) else 40
    def_sex = existing_row["Sex"] or "Female"
    def_phone = existing_row["Phone"] or ""
    def_mrn = existing_row["MRN"] or ""
    def_addr = existing_row["Address"] or ""
    def_city = existing_row["City"] or ""
    def_state = existing_row["State"] or ""
    def_pin = existing_row["PIN"] or ""
    def_email = existing_row["Email"] or ""
    def_cat = existing_row["ClinicalCategory"] or "New OSCC / lesion case"
    def_linked_res = existing_row["LinkedResearchID"] or ""
    def_linked_study = existing_row["LinkedStudyID"] or (active_study_id or "")
else:
    def_cid = ""  # will be generated
    def_name = ""
    def_age = 40
    def_sex = "Female"
    def_phone = ""
    def_mrn = ""
    def_addr = ""
    def_city = ""
    def_state = ""
    def_pin = ""
    def_email = ""
    def_cat = "New OSCC / lesion case"
    def_linked_res = ""
    def_linked_study = active_study_id or ""

# --------------------------------------------------------------------
# Patient registration / edit form
# --------------------------------------------------------------------
st.subheader("Register / edit clinical patient")

with st.form("clinical_patient_form"):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Name", value=def_name)
        age = st.number_input(
            "Age",
            min_value=0,
            max_value=120,
            step=1,
            value=int(def_age),
        )
        sex = st.selectbox(
            "Sex",
            ["Female", "Male", "Other"],
            index=get_index_safe(["Female", "Male", "Other"], def_sex),
        )
        phone = st.text_input("Phone", value=def_phone)
        email = st.text_input("Email (optional)", value=def_email)

    with col2:
        mrn = st.text_input(
            "Hospital MRN / registration number (optional)",
            value=def_mrn,
        )
        address = st.text_input("Address (optional)", value=def_addr)
        city = st.text_input("City / town (optional)", value=def_city)
        state = st.text_input("State (optional)", value=def_state)
        pin = st.text_input("PIN code (optional)", value=def_pin)

    clinical_cat = st.selectbox(
        "Clinical category",
        [
            "New OSCC / lesion case",
            "Potentially malignant disorder (PMD)",
            "Non-OSCC oral lesion",
            "Routine / non-lesion dental patient",
            "Follow-up visit for known case",
        ],
        index=get_index_safe(
            [
                "New OSCC / lesion case",
                "Potentially malignant disorder (PMD)",
                "Non-OSCC oral lesion",
                "Routine / non-lesion dental patient",
                "Follow-up visit for known case",
            ],
            def_cat,
        ),
        help="Broad clinical category – detailed diagnosis will be entered in case history.",
    )

    col3, col4 = st.columns(2)
    with col3:
        linked_res_id = st.text_input(
            "Linked ResearchID (if this patient is also in research module)",
            value=def_linked_res,
            help="Example: PILOT-CA-001. Leave blank if not applicable.",
        )
    with col4:
        linked_study_id = st.text_input(
            "Linked study ID (optional)",
            value=def_linked_study,
            help="Eg. OSCC_THESIS / OSCC_PILOT if this clinical patient is part of a study.",
        )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        save_btn = st.form_submit_button("Save / update patient")
    with col_btn2:
        delete_btn = st.form_submit_button(
            "Delete this patient",
            help="Deletes the selected clinical patient (cannot be undone).",
        )

# --------------------------------------------------------------------
# Handle delete
# --------------------------------------------------------------------
if delete_btn:
    if existing_row is None:
        st.error("Select an existing patient above before deleting.")
    else:
        cid = existing_row["ClinicalID"]
        clin_df = clin_df[clin_df["ClinicalID"] != cid]
        save_table(clin_df, "clinical_patients")
        st.success(f"Clinical patient '{cid}' deleted.")
        st.rerun()

# --------------------------------------------------------------------
# Handle save
# --------------------------------------------------------------------
if save_btn:
    if not name.strip():
        st.error("Name is required.")
    else:
        # Generate ClinicalID if new
        existing_ids = clin_df["ClinicalID"].tolist()
        if existing_row is None or not def_cid:
            new_cid = generate_clinical_id(existing_ids)
        else:
            new_cid = def_cid

        now = iso_now()
        created_at = (
            existing_row["CreatedAt"]
            if existing_row is not None and "CreatedAt" in existing_row.index
            else now
        )

        new_row = {
            "ClinicalID": new_cid,
            "Name": name.strip(),
            "Age": int(age),
            "Sex": sex,
            "Phone": phone.strip(),
            "MRN": mrn.strip(),
            "Address": address.strip(),
            "City": city.strip(),
            "State": state.strip(),
            "PIN": pin.strip(),
            "Email": email.strip(),
            "ClinicalCategory": clinical_cat,
            "LinkedResearchID": linked_res_id.strip(),
            "LinkedStudyID": linked_study_id.strip(),
            "CreatedAt": created_at,
            "UpdatedAt": now,
        }

        # Upsert
        clin_df = clin_df[clin_df["ClinicalID"] != new_cid]
        clin_df = pd.concat([clin_df, pd.DataFrame([new_row])], ignore_index=True)
        # Resort after adding new row so latest stays on top
        if "CreatedAt" in clin_df.columns:
            clin_df = clin_df.sort_values(
                by=["CreatedAt", "ClinicalID"],
                ascending=[False, False],
            )
        else:
            clin_df = clin_df.sort_values(by="ClinicalID", ascending=False)

        save_table(clin_df, "clinical_patients")

        st.success(f"Clinical patient saved as **{new_cid}**.")
        st.rerun()

# --------------------------------------------------------------------
# Overview table with numbering (latest first)
# --------------------------------------------------------------------
st.markdown("---")
st.subheader("All clinical patients (latest first)")

if clin_df.empty:
    st.info("No clinical patients registered yet.")
else:
    display_df = clin_df.copy()
    display_df.insert(0, "No.", range(1, len(display_df) + 1))  # 1-based numbering
    st.dataframe(display_df, use_container_width=True)
