# pages/13_Treatment_Notes.py

import streamlit as st
import pandas as pd
from datetime import datetime

from data_io import load_table, save_table, DATA_DIR  # DATA_DIR unused but harmless
from utils.navigation import require_module

# This page is strictly for the Clinic module
require_module("Clinic")

st.title("Treatment Notes")

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


def ensure_1based_id(existing_ids, clinical_id: str) -> str:
    """
    TreatmentID pattern: <ClinicalID>-TX-001, -TX-002, ...
    Always 1-based per patient.
    """
    prefix = f"{clinical_id}-TX-"
    nums = []
    for tid in existing_ids:
        if isinstance(tid, str) and tid.startswith(prefix):
            tail = tid.replace(prefix, "")
            try:
                nums.append(int(tail))
            except ValueError:
                continue
    next_num = max(nums) + 1 if nums else 1
    return f"{prefix}{next_num:03d}"


def get_index_safe(options, value):
    try:
        return options.index(value)
    except ValueError:
        return 0


# --------------------------------------------------------------------
# Load data: clinical patients, visits, treatments
# --------------------------------------------------------------------
patient_cols = [
    "ClinicalID",
    "Name",
    "Age",
    "Sex",
    "Phone",
    "MRN",
    "ClinicalCategory",
    "LinkedResearchID",
    "LinkedStudyID",
    "CreatedAt",
    "UpdatedAt",
]
clin_df = load_table("clinical_patients", columns=patient_cols)

visit_cols = [
    "ClinicalID",
    "VisitID",
    "VisitNumber",
    "VisitDateTime",
    "Mode",
    "ProvisionalDiagnosis",
    "CreatedAt",
    "UpdatedAt",
]
visits_df = load_table("clinical_visits", columns=visit_cols)

treat_cols = [
    "TreatmentID",
    "ClinicalID",
    "VisitID",
    "TreatmentDateTime",
    "ProcedureCategory",
    "ToothOrSite",
    "ProcedureDetails",
    "Provider",
    "Location",
    "Notes",
    "NoTreatmentToday",
    "CreatedAt",
    "UpdatedAt",
]
treat_df = load_table("clinical_treatments", columns=treat_cols)

if clin_df.empty:
    st.error("No clinical patients found. Please register patients first (page 10).")
    st.stop()

# Sort patients latest first
if "CreatedAt" in clin_df.columns:
    clin_df = clin_df.sort_values(by=["CreatedAt", "ClinicalID"], ascending=[False, False])
else:
    clin_df = clin_df.sort_values(by="ClinicalID", ascending=False)

# --------------------------------------------------------------------
# Select patient (with search)
# --------------------------------------------------------------------
st.subheader("Select clinical patient")

search_text = st.text_input(
    "Search by name or ClinicalID",
    value="",
    help="Start typing patient name or ClinicalID to filter.",
)

if search_text.strip():
    s = search_text.strip()
    mask = (
        clin_df["Name"].astype(str).str.contains(s, case=False, na=False)
        | clin_df["ClinicalID"].astype(str).str.contains(s, case=False, na=False)
    )
    filtered_patients = clin_df[mask]
else:
    filtered_patients = clin_df

if filtered_patients.empty:
    st.warning("No clinical patients match the search text.")
    st.stop()

patient_options = [
    f"{row.ClinicalID} – {row.Name}" for _, row in filtered_patients.iterrows()
]
selected_label = st.selectbox("Patient", patient_options)
selected_cid = selected_label.split(" – ")[0]

pt_row = clin_df[clin_df["ClinicalID"] == selected_cid].iloc[0]
st.info(
    f"**{selected_cid}** – {pt_row['Name']} "
    f"(Age {pt_row['Age']}, Sex {pt_row['Sex']})  \n"
    f"Category: {pt_row['ClinicalCategory']}"
)

# --------------------------------------------------------------------
# Link to visit (optional)
# --------------------------------------------------------------------
st.markdown("---")
st.subheader("Link treatments to a visit (optional)")

visits_for_pt = visits_df[visits_df["ClinicalID"] == selected_cid]

visit_choice_labels = ["(no specific visit)"]
visit_choice_ids = [""]

if not visits_for_pt.empty:
    if "VisitNumber" in visits_for_pt.columns:
        visits_for_pt = visits_for_pt.sort_values(
            by=["VisitNumber", "VisitDateTime"],
            ascending=[False, False],
        )
    else:
        visits_for_pt = visits_for_pt.sort_values("VisitDateTime", ascending=False)

    for _, r in visits_for_pt.iterrows():
        vid = r["VisitID"]
        vnum = r["VisitNumber"]
        vdt = r["VisitDateTime"]
        diag = r.get("ProvisionalDiagnosis", "") or ""
        label = f"{vid} (Visit {vnum}, {vdt}" + (f", Dx: {diag}" if diag else "") + ")"
        visit_choice_labels.append(label)
        visit_choice_ids.append(vid)

selected_visit_label = st.selectbox("Visit context", visit_choice_labels)
selected_visit_id = visit_choice_ids[visit_choice_labels.index(selected_visit_label)]

if selected_visit_id:
    st.caption(f"Treatments will be linked to **Visit {selected_visit_id}**.")
else:
    st.caption("Treatments will be stored without a specific visit link (general for this patient).")

# --------------------------------------------------------------------
# Existing treatments for this patient
# --------------------------------------------------------------------
st.markdown("---")
st.subheader("Treatment log for this patient")

treat_for_pt = treat_df[treat_df["ClinicalID"] == selected_cid]

if treat_for_pt.empty:
    st.info("No treatment notes recorded yet for this patient.")
else:
    # Latest first
    if "TreatmentDateTime" in treat_for_pt.columns:
        treat_for_pt = treat_for_pt.sort_values(
            by=["TreatmentDateTime", "TreatmentID"],
            ascending=[False, False],
        )
    else:
        treat_for_pt = treat_for_pt.sort_values("TreatmentID", ascending=False)

    display_cols = [
        "TreatmentID",
        "TreatmentDateTime",
        "VisitID",
        "ProcedureCategory",
        "ToothOrSite",
        "ProcedureDetails",
        "Provider",
    ]
    disp = treat_for_pt[display_cols].copy()
    disp.insert(0, "No.", range(1, len(disp) + 1))
    st.dataframe(disp, use_container_width=True)

# --------------------------------------------------------------------
# Add new treatment note
# --------------------------------------------------------------------
st.markdown("---")
st.subheader("Add new treatment entry")

existing_ids_for_pt = treat_df[treat_df["ClinicalID"] == selected_cid]["TreatmentID"].tolist()
suggested_tid = ensure_1based_id(existing_ids_for_pt, selected_cid)
st.caption(f"Next TreatmentID for this patient will be like **{suggested_tid}**.")

with st.form("treatment_form"):
    now_str = iso_now()
    st.caption(f"Treatment date & time (auto): **{now_str}**")

    proc_categories = [
        "Biopsy / lesion scraping",
        "Lesion excision / surgery",
        "Extraction",
        "Restorative procedure",
        "Scaling / periodontal therapy",
        "Medication prescribed",
        "Referral (oncology / radiotherapy / surgery)",
        "Review / no active treatment",
        "Other",
    ]
    proc_cat = st.selectbox(
        "Procedure category",
        proc_categories,
        index=get_index_safe(proc_categories, "Review / no active treatment"),
    )

    no_tx_today = st.checkbox(
        "No active treatment performed (review / counselling only)",
        value=(proc_cat == "Review / no active treatment"),
        help="Tick this if this visit was only review / counselling, no actual procedure.",
    )

    col_site, col_provider = st.columns(2)
    with col_site:
        tooth_or_site = st.text_input(
            "Tooth / site (e.g. 36, left buccal mucosa)",
            value="",
        )
    with col_provider:
        provider = st.text_input(
            "Procedure done by (name / initials)",
            value="",
        )

    location = st.text_input(
        "Location (OPD / OT / ward, etc.)",
        value="",
    )

    proc_details = st.text_area(
        "Procedure details (short description)",
        value="",
        height=120,
    )

    notes = st.text_area(
        "Additional notes (complications, instructions, etc.)",
        value="",
        height=80,
    )

    save_btn = st.form_submit_button("Save treatment entry")

# --------------------------------------------------------------------
# Handle save
# --------------------------------------------------------------------
if save_btn:
    # Decide new TreatmentID again at save time (in case others were added)
    existing_ids_for_pt = treat_df[treat_df["ClinicalID"] == selected_cid]["TreatmentID"].tolist()
    new_tid = ensure_1based_id(existing_ids_for_pt, selected_cid)

    now = iso_now()
    new_row = {
        "TreatmentID": new_tid,
        "ClinicalID": selected_cid,
        "VisitID": selected_visit_id,
        "TreatmentDateTime": now,
        "ProcedureCategory": proc_cat,
        "ToothOrSite": tooth_or_site.strip(),
        "ProcedureDetails": proc_details.strip(),
        "Provider": provider.strip(),
        "Location": location.strip(),
        "Notes": notes.strip(),
        "NoTreatmentToday": bool(no_tx_today),
        "CreatedAt": now,
        "UpdatedAt": now,
    }

    treat_df = treat_df[treat_df["TreatmentID"] != new_tid]
    treat_df = pd.concat([treat_df, pd.DataFrame([new_row])], ignore_index=True)
    save_table(treat_df, "clinical_treatments")

    st.success(f"Saved treatment entry **{new_tid}**.")
    st.rerun()

# --------------------------------------------------------------------
# Optional: delete a treatment record
# --------------------------------------------------------------------
st.markdown("---")
st.subheader("Delete a treatment entry (if needed)")

treat_for_pt = treat_df[treat_df["ClinicalID"] == selected_cid]

if treat_for_pt.empty:
    st.caption("Nothing to delete yet.")
else:
    delete_labels = ["(none)"] + [
        f"{row.TreatmentID} – {row.ProcedureCategory} – {row.ToothOrSite or ''}"
        for _, row in treat_for_pt.sort_values("TreatmentID").iterrows()
    ]
    del_choice = st.selectbox("Choose treatment to delete", delete_labels)
    if del_choice != "(none)":
        to_delete_id = del_choice.split(" – ")[0]
        if st.button("Delete selected treatment", type="secondary"):
            treat_df = treat_df[treat_df["TreatmentID"] != to_delete_id]
            save_table(treat_df, "clinical_treatments")
            st.success(f"Deleted treatment entry **{to_delete_id}**.")
            st.rerun()
