# pages/11_Clinical_Visits_CaseHistory.py

import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path

from data_io import load_table, save_table, DATA_DIR

from utils.navigation import require_module

require_module("Clinic")

st.title("Clinical Visits & Case History")

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


def get_index_safe(options, value):
    try:
        return options.index(value)
    except ValueError:
        return 0


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


# Directory for clinical attachments (voice notes etc.)
CLIN_ATTACH_DIR = DATA_DIR / "clinical_attachments"
ensure_dir(CLIN_ATTACH_DIR)

# --------------------------------------------------------------------
# Load clinical patients and visits
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
    "Mode",  # Simple / Detailed
    "ChiefComplaint",
    "HOPI",
    "MedicalHistory",
    "MedicalHistory_NAD",
    "DentalHistory",
    "DentalHistory_NAD",
    "PersonalHistory",
    "PersonalHistory_NAD",
    "FamilyHistory",
    "FamilyHistory_NAD",
    "ExtraoralExam",
    "ExtraoralExam_NAD",
    "IntraoralExam",
    "IntraoralExam_NAD",
    # Detailed sections
    "TMJExam",
    "TMJExam_NAD",
    "LymphNodesExam",
    "LymphNodesExam_NAD",
    "OralMucosaExam",
    "OralMucosaExam_NAD",
    "TeethExam",
    "TeethExam_NAD",
    "OtherFindings",
    "OtherFindings_NAD",
    # Common
    "ProvisionalDiagnosis",
    "AdditionalNotes",
    "VoiceNoteFile",
    "CreatedAt",
    "UpdatedAt",
]
visits_df = load_table("clinical_visits", columns=visit_cols)

if clin_df.empty:
    st.error("No clinical patients found. Please register patients first (page 10).")
    st.stop()

# Sort patients latest first (same as page 10)
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
    f"Category: {pt_row['ClinicalCategory']} · "
    f"Linked ResearchID: {pt_row.get('LinkedResearchID', '') or '—'}"
)

# --------------------------------------------------------------------
# Visits for this patient
# --------------------------------------------------------------------
st.markdown("---")
st.subheader("Visits for this patient")

visits_for_pt = visits_df[visits_df["ClinicalID"] == selected_cid]

if not visits_for_pt.empty:
    if "VisitNumber" in visits_for_pt.columns:
        visits_for_pt = visits_for_pt.sort_values(
            by=["VisitNumber", "VisitDateTime"],
            ascending=[False, False],
        )
    else:
        visits_for_pt = visits_for_pt.sort_values("VisitDateTime", ascending=False)

    disp = visits_for_pt[[
        "VisitID", "VisitNumber", "VisitDateTime", "Mode",
        "ProvisionalDiagnosis"
    ]].copy()
    disp.insert(0, "No.", range(1, len(disp) + 1))
    st.dataframe(disp, use_container_width=True)
else:
    st.info("No visits recorded yet for this patient.")

# --------------------------------------------------------------------
# Choose visit to edit or create new
# --------------------------------------------------------------------
st.markdown("---")
st.subheader("Create / edit a visit")

visit_options = ["(new visit)"]
visit_id_list = []

for _, row in visits_for_pt.iterrows():
    vid = row["VisitID"]
    vnum = row["VisitNumber"]
    vdt = row["VisitDateTime"]
    label = f"{vid} (Visit {vnum}, {vdt})"
    visit_options.append(label)
    visit_id_list.append(vid)

selected_visit_label = st.selectbox("Visit", visit_options)
if selected_visit_label == "(new visit)" or not visit_id_list:
    existing_visit = None
else:
    sel_vid = selected_visit_label.split(" (")[0]
    existing_visit = visits_for_pt[visits_for_pt["VisitID"] == sel_vid].iloc[0]

# Determine next visit number for new visits
if visits_for_pt.empty:
    next_visit_number = 1
else:
    max_num = visits_for_pt["VisitNumber"].max()
    try:
        next_visit_number = int(max_num) + 1
    except Exception:
        next_visit_number = 1

# --------------------------------------------------------------------
# Defaults for form fields
# --------------------------------------------------------------------
if existing_visit is not None:
    def_mode = existing_visit["Mode"] or "Simple"
    def_cc = existing_visit["ChiefComplaint"] or ""
    def_hopi = existing_visit["HOPI"] or ""
    def_med_hist = existing_visit["MedicalHistory"] or ""
    def_med_nad = bool(existing_visit.get("MedicalHistory_NAD", True))
    def_dent_hist = existing_visit["DentalHistory"] or ""
    def_dent_nad = bool(existing_visit.get("DentalHistory_NAD", True))
    def_pers_hist = existing_visit["PersonalHistory"] or ""
    def_pers_nad = bool(existing_visit.get("PersonalHistory_NAD", False))
    def_fam_hist = existing_visit["FamilyHistory"] or ""
    def_fam_nad = bool(existing_visit.get("FamilyHistory_NAD", True))
    def_extra = existing_visit["ExtraoralExam"] or ""
    def_extra_nad = bool(existing_visit.get("ExtraoralExam_NAD", True))
    def_intra = existing_visit["IntraoralExam"] or ""
    def_intra_nad = bool(existing_visit.get("IntraoralExam_NAD", False))

    def_tmj = existing_visit["TMJExam"] or ""
    def_tmj_nad = bool(existing_visit.get("TMJExam_NAD", True))
    def_lymph = existing_visit["LymphNodesExam"] or ""
    def_lymph_nad = bool(existing_visit.get("LymphNodesExam_NAD", True))
    def_oral = existing_visit["OralMucosaExam"] or ""
    def_oral_nad = bool(existing_visit.get("OralMucosaExam_NAD", False))
    def_teeth = existing_visit["TeethExam"] or ""
    def_teeth_nad = bool(existing_visit.get("TeethExam_NAD", False))
    def_other = existing_visit["OtherFindings"] or ""
    def_other_nad = bool(existing_visit.get("OtherFindings_NAD", True))

    def_diag = existing_visit["ProvisionalDiagnosis"] or ""
    def_notes = existing_visit["AdditionalNotes"] or ""
    def_voice = existing_visit["VoiceNoteFile"] or ""

    def_visit_id = existing_visit["VisitID"]
    def_visit_num = int(existing_visit["VisitNumber"])
    def_visit_dt = existing_visit["VisitDateTime"]
else:
    def_mode = "Simple"
    def_cc = ""
    def_hopi = ""
    def_med_hist = ""
    def_med_nad = True
    def_dent_hist = ""
    def_dent_nad = True
    def_pers_hist = ""
    def_pers_nad = False
    def_fam_hist = ""
    def_fam_nad = True
    def_extra = ""
    def_extra_nad = True
    def_intra = ""
    def_intra_nad = False

    def_tmj = ""
    def_tmj_nad = True
    def_lymph = ""
    def_lymph_nad = True
    def_oral = ""
    def_oral_nad = False
    def_teeth = ""
    def_teeth_nad = False
    def_other = ""
    def_other_nad = True

    def_diag = ""
    def_notes = ""
    def_voice = ""

    def_visit_num = next_visit_number
    def_visit_id = f"{selected_cid}-V{def_visit_num}"
    def_visit_dt = iso_now()

st.caption(
    f"This visit will be stored as **{def_visit_id}** "
    f"(Visit {def_visit_num})"
    + (f" – original timestamp: {def_visit_dt}" if existing_visit is not None else "")
)

# --------------------------------------------------------------------
# Visit mode: Simple vs Detailed
# --------------------------------------------------------------------
mode_choice = st.radio(
    "Case history mode for this visit",
    ["Simple", "Detailed"],
    index=get_index_safe(["Simple", "Detailed"], def_mode),
    horizontal=True,
)

# --------------------------------------------------------------------
# Visit form (with unique keys to avoid duplication)
# --------------------------------------------------------------------
st.markdown("---")

with st.form("visit_form"):
    st.markdown("### Basic history")

    cc = st.text_input(
        "Chief complaint",
        value=def_cc,
        key=f"cc_{selected_cid}_{def_visit_num}",
    )
    hopi = st.text_area(
        "History of present illness (HOPI)",
        value=def_hopi,
        height=100,
        key=f"hopi_{selected_cid}_{def_visit_num}",
    )

    # Medical history
    st.markdown("#### Medical history")
    col_med1, col_med2 = st.columns([1, 4])
    with col_med1:
        med_nad = st.checkbox(
            "NAD / No significant medical history",
            value=def_med_nad,
            key=f"med_nad_{selected_cid}_{def_visit_num}",
        )
    with col_med2:
        med_hist = st.text_area(
            "Medical history details",
            value=def_med_hist,
            height=80,
            key=f"med_hist_{selected_cid}_{def_visit_num}",
        )

    # Dental history
    st.markdown("#### Dental history")
    col_dent1, col_dent2 = st.columns([1, 4])
    with col_dent1:
        dent_nad = st.checkbox(
            "NAD / No significant dental history",
            value=def_dent_nad,
            key=f"dent_nad_{selected_cid}_{def_visit_num}",
        )
    with col_dent2:
        dent_hist = st.text_area(
            "Dental history details",
            value=def_dent_hist,
            height=80,
            key=f"dent_hist_{selected_cid}_{def_visit_num}",
        )

    # Personal history (habits – tobacco, alcohol, etc.)
    st.markdown("#### Personal history (habits)")
    col_pers1, col_pers2 = st.columns([1, 4])
    with col_pers1:
        pers_nad = st.checkbox(
            "NAD / no significant habits",
            value=def_pers_nad,
            key=f"pers_nad_{selected_cid}_{def_visit_num}",
        )
    with col_pers2:
        pers_hist = st.text_area(
            "Personal habits (tobacco smoking/chewing, alcohol, betel quid, etc.)",
            value=def_pers_hist,
            height=100,
            key=f"pers_hist_{selected_cid}_{def_visit_num}",
        )

    # Family history
    st.markdown("#### Family history")
    col_fam1, col_fam2 = st.columns([1, 4])
    with col_fam1:
        fam_nad = st.checkbox(
            "NAD / No relevant family history",
            value=def_fam_nad,
            key=f"fam_nad_{selected_cid}_{def_visit_num}",
        )
    with col_fam2:
        fam_hist = st.text_area(
            "Family history details",
            value=def_fam_hist,
            height=80,
            key=f"fam_hist_{selected_cid}_{def_visit_num}",
        )

    st.markdown("### Examination – Simple mode sections")

    # Extraoral
    st.markdown("#### Extraoral examination")
    col_ext1, col_ext2 = st.columns([1, 4])
    with col_ext1:
        extra_nad = st.checkbox(
            "NAD",
            value=def_extra_nad,
            key=f"extra_nad_{selected_cid}_{def_visit_num}",
        )
    with col_ext2:
        extra = st.text_area(
            "Extraoral findings (facial symmetry, TMJ region, swelling, etc.)",
            value=def_extra,
            height=80,
            key=f"extra_{selected_cid}_{def_visit_num}",
        )

    # Intraoral
    st.markdown("#### Intraoral examination")
    col_int1, col_int2 = st.columns([1, 4])
    with col_int1:
        intra_nad = st.checkbox(
            "NAD",
            value=def_intra_nad,
            key=f"intra_nad_{selected_cid}_{def_visit_num}",
        )
    with col_int2:
        intra = st.text_area(
            "Lesion description / intraoral findings",
            value=def_intra,
            height=120,
            key=f"intra_{selected_cid}_{def_visit_num}",
        )

    # Detailed sections (only if Detailed mode chosen)
    if mode_choice == "Detailed":
        st.markdown("---")
        st.markdown("### Detailed examination")

        st.markdown("#### TMJ examination")
        col_tmj1, col_tmj2 = st.columns([1, 4])
        with col_tmj1:
            tmj_nad = st.checkbox(
                "TMJ NAD",
                value=def_tmj_nad,
                key=f"tmj_nad_{selected_cid}_{def_visit_num}",
            )
        with col_tmj2:
            tmj_exam = st.text_area(
                "TMJ findings",
                value=def_tmj,
                height=80,
                key=f"tmj_{selected_cid}_{def_visit_num}",
            )

        st.markdown("#### Lymph nodes")
        col_lym1, col_lym2 = st.columns([1, 4])
        with col_lym1:
            lymph_nad = st.checkbox(
                "Lymph nodes NAD",
                value=def_lymph_nad,
                key=f"lymph_nad_{selected_cid}_{def_visit_num}",
            )
        with col_lym2:
            lymph_exam = st.text_area(
                "Lymph node findings",
                value=def_lymph,
                height=80,
                key=f"lymph_{selected_cid}_{def_visit_num}",
            )

        st.markdown("#### Oral mucosa / soft tissues")
        col_oral1, col_oral2 = st.columns([1, 4])
        with col_oral1:
            oral_nad = st.checkbox(
                "Oral mucosa NAD",
                value=def_oral_nad,
                key=f"oral_nad_{selected_cid}_{def_visit_num}",
            )
        with col_oral2:
            oral_exam = st.text_area(
                "Oral mucosa findings",
                value=def_oral,
                height=100,
                key=f"oral_{selected_cid}_{def_visit_num}",
            )

        st.markdown("#### Teeth & periodontal status")
        col_teeth1, col_teeth2 = st.columns([1, 4])
        with col_teeth1:
            teeth_nad = st.checkbox(
                "Teeth / periodontal NAD",
                value=def_teeth_nad,
                key=f"teeth_nad_{selected_cid}_{def_visit_num}",
            )
        with col_teeth2:
            teeth_exam = st.text_area(
                "Teeth / periodontal findings",
                value=def_teeth,
                height=100,
                key=f"teeth_{selected_cid}_{def_visit_num}",
            )

        st.markdown("#### Other findings")
        col_other1, col_other2 = st.columns([1, 4])
        with col_other1:
            other_nad = st.checkbox(
                "Other NAD",
                value=def_other_nad,
                key=f"other_nad_{selected_cid}_{def_visit_num}",
            )
        with col_other2:
            other_exam = st.text_area(
                "Other relevant findings",
                value=def_other,
                height=80,
                key=f"other_{selected_cid}_{def_visit_num}",
            )
    else:
        tmj_exam = def_tmj
        tmj_nad = def_tmj_nad
        lymph_exam = def_lymph
        lymph_nad = def_lymph_nad
        oral_exam = def_oral
        oral_nad = def_oral_nad
        teeth_exam = def_teeth
        teeth_nad = def_teeth_nad
        other_exam = def_other
        other_nad = def_other_nad

    st.markdown("---")
    st.markdown("### Diagnosis & notes")

    diag = st.text_input(
        "Provisional diagnosis",
        value=def_diag,
        key=f"diag_{selected_cid}_{def_visit_num}",
    )
    notes = st.text_area(
        "Additional notes",
        value=def_notes,
        height=100,
        key=f"notes_{selected_cid}_{def_visit_num}",
    )

    st.markdown("### Voice note attachment (optional)")
    if def_voice:
        st.caption(f"Existing voice note file: `{def_voice}`")

    voice_file = st.file_uploader(
        "Attach voice note (audio from phone / recorder)",
        type=["mp3", "m4a", "wav", "aac", "3gp", "amr"],
        key=f"voice_{selected_cid}_{def_visit_num}",
        help="Optional – you can quickly record on phone and attach here for this visit.",
    )

    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        save_visit = st.form_submit_button("Save visit")
    with col_btn2:
        delete_visit = st.form_submit_button(
            "Delete this visit",
            help="Delete this visit record (cannot be undone).",
        )

# --------------------------------------------------------------------
# Handle delete visit
# --------------------------------------------------------------------
if delete_visit:
    if existing_visit is None:
        st.error("Select an existing visit above before deleting.")
    else:
        vid = existing_visit["VisitID"]
        visits_df = visits_df[
            ~((visits_df["ClinicalID"] == selected_cid) & (visits_df["VisitID"] == vid))
        ]
        save_table(visits_df, "clinical_visits")
        st.success(f"Visit '{vid}' deleted.")
        st.rerun()

# --------------------------------------------------------------------
# NAD vs text helper
# --------------------------------------------------------------------
nad_warnings = []


def adjust_nad(nad_flag: bool, text: str, section_name: str) -> bool:
    if nad_flag and text.strip():
        nad_warnings.append(
            f"For **{section_name}**, NAD was ticked but details were entered – "
            f"saving NAD as **False**."
        )
        return False
    return nad_flag


# --------------------------------------------------------------------
# Handle save visit
# --------------------------------------------------------------------
if save_visit:
    if not cc.strip():
        st.error("Chief complaint is required.")
    else:
        if existing_visit is None:
            visit_number = next_visit_number
            visit_id = f"{selected_cid}-V{visit_number}"
            created_at = iso_now()
        else:
            visit_number = int(existing_visit["VisitNumber"])
            visit_id = existing_visit["VisitID"]
            created_at = existing_visit["CreatedAt"]

        now = iso_now()

        voice_fname = def_voice
        if voice_file is not None:
            voice_fname = f"{selected_cid}_{visit_id}_voice_{voice_file.name}"
            with open(CLIN_ATTACH_DIR / voice_fname, "wb") as out:
                out.write(voice_file.read())

        # Adjust NAD flags by text
        med_nad_adj = adjust_nad(med_nad, med_hist, "Medical history")
        dent_nad_adj = adjust_nad(dent_nad, dent_hist, "Dental history")
        pers_nad_adj = adjust_nad(pers_nad, pers_hist, "Personal history")
        fam_nad_adj = adjust_nad(fam_nad, fam_hist, "Family history")
        extra_nad_adj = adjust_nad(extra_nad, extra, "Extraoral exam")
        intra_nad_adj = adjust_nad(intra_nad, intra, "Intraoral exam")
        tmj_nad_adj = adjust_nad(tmj_nad, tmj_exam, "TMJ exam")
        lymph_nad_adj = adjust_nad(lymph_nad, lymph_exam, "Lymph nodes exam")
        oral_nad_adj = adjust_nad(oral_nad, oral_exam, "Oral mucosa exam")
        teeth_nad_adj = adjust_nad(teeth_nad, teeth_exam, "Teeth/periodontal exam")
        other_nad_adj = adjust_nad(other_nad, other_exam, "Other findings")

        new_row = {
            "ClinicalID": selected_cid,
            "VisitID": visit_id,
            "VisitNumber": visit_number,
            "VisitDateTime": def_visit_dt if existing_visit is not None else now,
            "Mode": mode_choice,
            "ChiefComplaint": cc.strip(),
            "HOPI": hopi.strip(),
            "MedicalHistory": med_hist.strip(),
            "MedicalHistory_NAD": bool(med_nad_adj),
            "DentalHistory": dent_hist.strip(),
            "DentalHistory_NAD": bool(dent_nad_adj),
            "PersonalHistory": pers_hist.strip(),
            "PersonalHistory_NAD": bool(pers_nad_adj),
            "FamilyHistory": fam_hist.strip(),
            "FamilyHistory_NAD": bool(fam_nad_adj),
            "ExtraoralExam": extra.strip(),
            "ExtraoralExam_NAD": bool(extra_nad_adj),
            "IntraoralExam": intra.strip(),
            "IntraoralExam_NAD": bool(intra_nad_adj),
            "TMJExam": tmj_exam.strip(),
            "TMJExam_NAD": bool(tmj_nad_adj),
            "LymphNodesExam": lymph_exam.strip(),
            "LymphNodesExam_NAD": bool(lymph_nad_adj),
            "OralMucosaExam": oral_exam.strip(),
            "OralMucosaExam_NAD": bool(oral_nad_adj),
            "TeethExam": teeth_exam.strip(),
            "TeethExam_NAD": bool(teeth_nad_adj),
            "OtherFindings": other_exam.strip(),
            "OtherFindings_NAD": bool(other_nad_adj),
            "ProvisionalDiagnosis": diag.strip(),
            "AdditionalNotes": notes.strip(),
            "VoiceNoteFile": voice_fname,
            "CreatedAt": created_at,
            "UpdatedAt": now,
        }

        if not visits_df.empty:
            visits_df = visits_df[
                ~((visits_df["ClinicalID"] == selected_cid) & (visits_df["VisitID"] == visit_id))
            ]
        visits_df = pd.concat([visits_df, pd.DataFrame([new_row])], ignore_index=True)
        save_table(visits_df, "clinical_visits")

        st.success(f"Visit **{visit_id}** saved.")
        for msg in nad_warnings:
            st.warning(msg)
        st.rerun()
