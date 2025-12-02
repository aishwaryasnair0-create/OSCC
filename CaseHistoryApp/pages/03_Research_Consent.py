# pages/03_Research_Consent.py

import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path
import base64
import numpy as np
from PIL import Image
from streamlit_drawable_canvas import st_canvas

from data_io import load_table, save_table, DATA_DIR

from utils.navigation import require_module

require_module("Research")

st.title("03 – Research Consent (IEC PDF + pilot addendum)")
# -------------------------------------------------------------
# Load participants
# -------------------------------------------------------------
participants = load_table(
    "research_participants",
    columns=["ResearchID", "Name", "Age", "Sex", "Group", "Cohort", "CreatedAt"],
)

if participants.empty:
    st.error("No research participants found. Please create one first.")
    st.stop()

# Build list of labels + IDs
options = []
for _, row in participants.iterrows():
    rid = row["ResearchID"]
    label = f"{rid} – {row['Name']} (Group: {row['Group']}, Cohort: {row['Cohort']})"
    options.append((label, rid))

labels = [o[0] for o in options]
ids = [o[1] for o in options]

# Default index based on active_research_id from previous page
active_id = st.session_state.get("active_research_id")
default_idx = 0
if active_id in ids:
    default_idx = ids.index(active_id)

selected_idx = st.selectbox(
    "Choose participant",
    options=list(range(len(options))),
    index=default_idx,
    format_func=lambda i: labels[i],
    key="consent_participant_select",
)

selected_id = ids[selected_idx]
# Keep session_state in sync
st.session_state["active_research_id"] = selected_id

# Convenience header
pt_row = participants[participants["ResearchID"] == selected_id].iloc[0]
group = pt_row["Group"]
cohort = pt_row["Cohort"]

st.caption(
    f"{pt_row['ResearchID']} – {pt_row['Name']} "
    f"(Age {pt_row['Age']}, Sex {pt_row['Sex']}, "
    f"Group: {pt_row['Group']}, Cohort: {pt_row['Cohort']})"
)

st.markdown("---")

# --------------------------------------------------------------------
# Context: mode, active study, and current user
# --------------------------------------------------------------------
mode = st.session_state.get("module_mode", "Research")
active_study_id = st.session_state.get("active_study_id")

st.caption(f"Current module: **{mode}**")
if active_study_id:
    st.caption(f"Active study / project: **{active_study_id}**")
else:
    st.caption("Active study / project: **none**")

st.markdown("---")

# Logged-in user / clinician (used as consent taker fallback)
if "current_user" not in st.session_state:
    st.session_state["current_user"] = ""

st.session_state["current_user"] = st.text_input(
    "Logged-in user / clinician name",
    value=st.session_state["current_user"],
    help="This name will be used as a fallback default for 'Consent taken by'.",
)
current_user = st.session_state["current_user"]

# --------------------------------------------------------------------
# Load core tables
# --------------------------------------------------------------------
participants = load_table(
    "research_participants",
    columns=["ResearchID", "Name", "Age", "Sex", "Phone", "Group", "Cohort", "CreatedAt"],
)
elig_df = load_table("eligibility")
studies_df = load_table("studies")

# Consent table structure
consent_cols = [
    "ResearchID",
    "ConsentDateTime",
    "Language",
    "CohortAtConsent",
    "PlannedSampleTypes",
    "IncludesScraping",
    "ConsentTakenBy",
    "ConsentLocation",
    "PilotExtraExplained",
    "PilotParticipantSignatureFile",
    "PilotClinicianSignatureFile",
    "SignedPdfFile",
    "ExtraFiles",
]
consents = load_table("research_consents", columns=consent_cols)

if participants.empty:
    st.error("No research participants found. Please add participants first.")
    st.stop()

# Study default: consent taker
default_consent_from_study = ""
if active_study_id and not studies_df.empty:
    row_st = studies_df[studies_df["StudyID"] == active_study_id]
    if not row_st.empty:
        default_consent_from_study = row_st.iloc[0].get("DefaultConsentTaker", "")

# Paths for consent PDFs & pilot extra text
PDF_DIR = DATA_DIR / "consent_pdfs"
PDF_DIR.mkdir(exist_ok=True)

PILOT_INFO_PATH = DATA_DIR / "pilot_extra_info.txt"

CONSENTS_DIR = DATA_DIR / "consents"
CONSENTS_DIR.mkdir(exist_ok=True)


def pdf_path_for_language(lang: str) -> Path:
    """
    Expected IEC-approved consent PDF for this language.
    Example filenames:
        consent_EN.pdf, consent_HI.pdf, consent_KN.pdf, consent_ML.pdf
    in the folder data/consent_pdfs
    """
    return PDF_DIR / f"consent_{lang}.pdf"


def load_pilot_extra_info() -> str:
    if PILOT_INFO_PATH.exists():
        return PILOT_INFO_PATH.read_text(encoding="utf-8")
    # Default placeholder text until you paste in the IEC-approved pilot addendum
    return (
        "Pilot study – additional information:\n\n"
        "- Three sample types will be collected (e.g., whole saliva, saliva with "
        "epithelial cells, and epithelial cells alone).\n"
        "- The lesion may be scraped / brush biopsied twice to collect sufficient "
        "cells.\n"
        "- Approximately 5 mL of saliva will be collected.\n\n"
        "Please replace this text with the exact IEC-approved pilot addendum "
        "wording using the Admin editor below."
    )


def save_pilot_extra_info(text: str):
    PILOT_INFO_PATH.write_text(text, encoding="utf-8")


# --------------------------------------------------------------------
# Participant selection
# --------------------------------------------------------------------
st.subheader("Existing consent record (if any)")

existing = consents[consents["ResearchID"] == selected_id]
if not existing.empty:
    disp = existing.copy()
    disp.insert(0, "No.", range(1, len(disp) + 1))
    st.dataframe(disp, use_container_width=True)
else:
    st.write("No consent record saved yet for this participant.")

existing_row = existing.iloc[0] if not existing.empty else None
existing_part_sig = (
    existing_row["PilotParticipantSignatureFile"]
    if existing_row is not None and isinstance(existing_row["PilotParticipantSignatureFile"], str)
    else ""
)
existing_clin_sig = (
    existing_row["PilotClinicianSignatureFile"]
    if existing_row is not None and isinstance(existing_row["PilotClinicianSignatureFile"], str)
    else ""
)

# --------------------------------------------------------------------
# IEC consent PDF viewer (in browser)
# --------------------------------------------------------------------
st.markdown("---")
st.subheader("IEC consent form (opens in this browser)")

language = st.selectbox(
    "Consent language (IEC-approved version)",
    ["EN", "HI", "KN", "ML"],
    help="Choose the language in which the IEC consent is read and signed.",
    key="consent_lang",
)

pdf_path = pdf_path_for_language(language)

if pdf_path.exists():
    st.success(f"IEC-approved consent PDF found: `{pdf_path.name}`")

    pdf_bytes = pdf_path.read_bytes()
    b64_pdf = base64.b64encode(pdf_bytes).decode("utf-8")

    # Show PDF inline
    st.markdown(
        f"""
        <iframe src="data:application/pdf;base64,{b64_pdf}"
                width="100%" height="700"
                type="application/pdf">
        </iframe>
        """,
        unsafe_allow_html=True,
    )

    # Button/link to open PDF in a new browser tab
    st.markdown(
        f"""
        <a href="data:application/pdf;base64,{b64_pdf}" target="_blank">
        👉 Open IEC consent PDF in a new browser tab (for ticking checkboxes & signing with pen)
        </a>
        """,
        unsafe_allow_html=True,
    )

else:
    st.error(
        f"No IEC consent PDF found for language {language}. "
        f"Place the IEC-approved file at: `{pdf_path}`"
    )
    st.caption(
        "Example: save your English IEC consent as `consent_EN.pdf` inside the "
        "`data/consent_pdfs` folder."
    )

st.info(
    "Use the inline viewer or open the PDF in a new tab to tick checkboxes and sign "
    "directly inside the PDF using your pen (e.g., PDFgear in the browser). "
    "After saving/exporting the signed PDF, you can upload it back on this page."
)

# --------------------------------------------------------------------
# Pilot study extra information + addendum
# --------------------------------------------------------------------
pilot_extra_explained_default = False
pilot_text = load_pilot_extra_info()

if cohort == "PILOT":
    st.markdown("---")
    st.subheader("Pilot study – additional information (three matrices addendum)")

    st.text_area(
        "Pilot extra information as read to the participant",
        value=pilot_text,
        height=180,
        disabled=True,
    )

    with st.expander("Admin: edit pilot extra information text"):
        editable_pilot_text = st.text_area(
            "Paste the exact IEC-approved pilot study additional information here.",
            value=pilot_text,
            height=200,
        )
        if st.button("Save pilot extra information text"):
            save_pilot_extra_info(editable_pilot_text)
            st.success("Pilot extra information saved.")
            st.rerun()

    if existing_row is not None and "PilotExtraExplained" in existing_row.index:
        pilot_extra_explained_default = bool(existing_row.get("PilotExtraExplained", False))

# --------------------------------------------------------------------
# Create / update consent record
# --------------------------------------------------------------------
st.markdown("---")
st.subheader("Create / update consent record for this participant")

with st.form("consent_form"):

    # Planned sample types depend on cohort (pilot vs main)
    if cohort == "PILOT":
        default_samples = ["WS", "WS+EC", "EC"]
    else:
        default_samples = ["SalivaMain"]

    planned_sample_types = st.multiselect(
        "Planned sample types",
        ["WS", "WS+EC", "EC", "SalivaMain"],
        default=default_samples,
        help="Select the sample types that will be collected according to your protocol.",
    )

    includes_scraping = st.checkbox(
        "Includes lesion scraping / brush biopsy",
        value=True,
    )

    # default for "Consent taken by" = existing value OR study default OR current user
    if existing_row is not None and isinstance(existing_row.get("ConsentTakenBy", ""), str):
        default_taken_by = existing_row["ConsentTakenBy"]
    elif default_consent_from_study:
        default_taken_by = default_consent_from_study
    elif current_user:
        default_taken_by = current_user
    else:
        default_taken_by = ""

    consent_taken_by = st.text_input(
        "Consent taken by (name)",
        value=default_taken_by,
    )

    consent_location = st.text_input(
        "Consent location",
        value=(
            existing_row["ConsentLocation"]
            if existing_row is not None
            and isinstance(existing_row.get("ConsentLocation", ""), str)
            else "Hospital OPD"
        ),
    )

    # Pilot addendum check + digital signatures
    pilot_extra_explained = False
    if cohort == "PILOT":
        pilot_extra_explained = st.checkbox(
            "I have explained the additional pilot study details "
            "(three sample types, two scrapings, 5 mL saliva).",
            value=pilot_extra_explained_default,
        )

        st.markdown("#### Digital signatures for pilot addendum")

        col_sig1, col_sig2 = st.columns(2)

        with col_sig1:
            st.caption("Participant / giver – pilot addendum")
            if existing_part_sig:
                st.image(str(CONSENTS_DIR / existing_part_sig), width=250)
            part_canvas = st_canvas(
                fill_color="rgba(0,0,0,0)",
                stroke_width=2,
                stroke_color="#000000",
                background_color="#FFFFFF",
                height=180,
                width=500,
                drawing_mode="freedraw",
                key=f"participant_signature_canvas_{selected_id}",
            )

        with col_sig2:
            st.caption("Clinician / receiver – pilot addendum")
            if existing_clin_sig:
                st.image(str(CONSENTS_DIR / existing_clin_sig), width=250)
            clin_canvas = st_canvas(
                fill_color="rgba(0,0,0,0)",
                stroke_width=2,
                stroke_color="#000000",
                background_color="#FFFFFF",
                height=180,
                width=500,
                drawing_mode="freedraw",
                key=f"clinician_signature_canvas_{selected_id}",
            )
    else:
        part_canvas = None
        clin_canvas = None

    signed_pdf_file = st.file_uploader(
        "Upload final signed IEC consent PDF from browser (optional)",
        type=["pdf"],
        key="signed_pdf_file",
        help="After signing in the PDF viewer/new tab, save/export and upload the "
             "signed version here for record-keeping.",
    )

    extra_files = st.file_uploader(
        "Upload additional files/images related to consent (optional, multiple)",
        type=["pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="extra_files",
    )

    submitted = st.form_submit_button("Save consent record")

# --------------------------------------------------------------------
# Handle form submission
# --------------------------------------------------------------------
if submitted:
    if not consent_taken_by.strip():
        st.error("Please enter who took the consent.")
    else:
        # Use existing filenames unless we save new ones
        part_sig_name = existing_part_sig
        clin_sig_name = existing_clin_sig

        # Save pilot addendum signatures
        if cohort == "PILOT":
            # Participant signature
            if part_canvas is not None and part_canvas.image_data is not None:
                img_data = part_canvas.image_data.astype("uint8")
                # Check if canvas is not blank (all white)
                if not np.all(img_data[:, :, :3] == 255):
                    img = Image.fromarray(img_data, "RGBA").convert("RGB")
                    part_sig_name = f"{selected_id}_pilot_participant_signature.png"
                    img.save(CONSENTS_DIR / part_sig_name)

            # Clinician signature
            if clin_canvas is not None and clin_canvas.image_data is not None:
                img_data = clin_canvas.image_data.astype("uint8")
                if not np.all(img_data[:, :, :3] == 255):
                    img = Image.fromarray(img_data, "RGBA").convert("RGB")
                    clin_sig_name = f"{selected_id}_pilot_clinician_signature.png"
                    img.save(CONSENTS_DIR / clin_sig_name)

        # Save final signed IEC PDF (if uploaded)
        signed_pdf_name = ""
        if signed_pdf_file is not None:
            signed_pdf_name = f"{selected_id}_signed_consent.pdf"
            with open(CONSENTS_DIR / signed_pdf_name, "wb") as out:
                out.write(signed_pdf_file.read())

        # Save any extra files
        extra_names = []
        for f in extra_files or []:
            fname = f"{selected_id}_extra_{f.name}"
            with open(CONSENTS_DIR / fname, "wb") as out:
                out.write(f.read())
            extra_names.append(fname)

        new_row = {
            "ResearchID": selected_id,
            "ConsentDateTime": datetime.now().isoformat(timespec="seconds"),
            "Language": language,
            "CohortAtConsent": cohort,
            "PlannedSampleTypes": ";".join(planned_sample_types),
            "IncludesScraping": includes_scraping,
            "ConsentTakenBy": consent_taken_by.strip(),
            "ConsentLocation": consent_location.strip(),
            "PilotExtraExplained": bool(pilot_extra_explained) if cohort == "PILOT" else False,
            "PilotParticipantSignatureFile": part_sig_name,
            "PilotClinicianSignatureFile": clin_sig_name,
            "SignedPdfFile": signed_pdf_name,
            "ExtraFiles": ";".join(extra_names),
        }

        # Upsert into consents table
        consents = consents[consents["ResearchID"] != selected_id]
        consents = pd.concat([consents, pd.DataFrame([new_row])], ignore_index=True)
        save_table(consents, "research_consents")

        st.success("Consent record saved/updated for this participant.")
        st.rerun()

