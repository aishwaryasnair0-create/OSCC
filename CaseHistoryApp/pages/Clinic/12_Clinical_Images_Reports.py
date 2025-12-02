# pages/12_Clinical_Images_Reports.py

import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path

from data_io import load_table, save_table, DATA_DIR
from utils.navigation import require_module

# This page is strictly for the Clinic module
require_module("Clinic")

st.title("Clinical Images & Reports")

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


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def generate_image_id(existing_ids, clinical_id: str) -> str:
    """
    ImageID pattern: <ClinicalID>-IMG-001, -IMG-002, ...
    Always 1-based per patient.
    """
    prefix = f"{clinical_id}-IMG-"
    nums = []
    for iid in existing_ids:
        if isinstance(iid, str) and iid.startswith(prefix):
            tail = iid.replace(prefix, "")
            try:
                nums.append(int(tail))
            except ValueError:
                continue
    next_num = max(nums) + 1 if nums else 1
    return f"{prefix}{next_num:03d}"


# Where actual files are stored
CLIN_IMG_DIR = DATA_DIR / "clinical_images_reports"
ensure_dir(CLIN_IMG_DIR)

# --------------------------------------------------------------------
# Load clinical patients, visits, and existing images/reports
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

image_cols = [
    "ImageID",
    "ClinicalID",
    "VisitID",
    "Category",          # lesion photo / prescription / test report / histopath / other
    "FileName",
    "FileType",
    "Caption",
    "Notes",
    "TakenBy",
    "Location",
    "IsPrimaryLesion",
    "CreatedAt",
    "UpdatedAt",
]
images_df = load_table("clinical_images_reports", columns=image_cols)

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
# Visits for this patient (for linking images)
# --------------------------------------------------------------------
st.markdown("---")
st.subheader("Link images/reports to a visit (optional)")

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
        lab = f"{vid} (Visit {vnum}, {vdt}" + (f", Dx: {diag}" if diag else "") + ")"
        visit_choice_labels.append(lab)
        visit_choice_ids.append(vid)

selected_visit_label = st.selectbox("Visit context", visit_choice_labels)
selected_visit_id = visit_choice_ids[visit_choice_labels.index(selected_visit_label)]

if selected_visit_id:
    st.caption(f"Images will be linked to **Visit {selected_visit_id}**.")
else:
    st.caption("Images will be stored without a specific visit link (general for this patient).")

# --------------------------------------------------------------------
# Upload / capture new image / report
# --------------------------------------------------------------------
st.markdown("---")
st.subheader("Capture or upload new clinical image / report")

existing_ids_for_pt = images_df[images_df["ClinicalID"] == selected_cid]["ImageID"].tolist()
suggested_image_id = generate_image_id(existing_ids_for_pt, selected_cid)
st.caption(f"Next ImageID for this patient will be like **{suggested_image_id}**.")

with st.form("upload_image_form"):
    category_options = [
        "Lesion photo (intraoral / extraoral)",
        "Prescription",
        "Pathology / histopathology report",
        "Imaging report (X-ray / CT / MRI / CBCT)",
        "Laboratory test report",
        "Other document",
    ]
    category = st.selectbox(
        "Type of file",
        options=category_options,
        index=0,
    )

    col1, col2 = st.columns(2)
    with col1:
        taken_by = st.text_input(
            "Captured / uploaded by (clinician / PG / intern)",
            value="",
        )
    with col2:
        location = st.text_input(
            "Location (OPD / ward / OT, etc.)",
            value="",
        )

    is_primary = st.checkbox(
        "Primary lesion / key image for this patient",
        value=False,
        help="Tick if this is the main representative image of the lesion.",
    )

    caption = st.text_input(
        "Short caption (e.g. 'Left buccal mucosa ulcer, pre-treatment')",
        value="",
    )
    notes = st.text_area(
        "Notes (optional)",
        value="",
        height=80,
    )

    st.markdown("#### Capture from camera (for lesion photos)")
    camera_image = st.camera_input(
        "Use device camera (tablet/phone/PC) – optional",
        key=f"cam_{selected_cid}",
    )

    st.markdown("#### Or upload a file (reports, existing photos)")
    uploaded_file = st.file_uploader(
        "Upload image or report file",
        type=[
            "png", "jpg", "jpeg",  # photos
            "pdf", "doc", "docx", "txt",  # documents
            "dcm", "dicom",  # imaging (if available)
        ],
        help="You can upload lesion photographs, prescriptions, reports, etc.",
    )

    save_btn = st.form_submit_button("Save image / report record")

# Handle upload / capture
if save_btn:
    # Prefer camera capture if available; otherwise use uploaded file
    file_obj = camera_image if camera_image is not None else uploaded_file

    if file_obj is None:
        st.error("Please capture an image with the camera or choose a file to upload.")
    else:
        # Decide new ImageID after re-reading existing IDs in case others were added
        existing_ids_for_pt = images_df[images_df["ClinicalID"] == selected_cid]["ImageID"].tolist()
        new_image_id = generate_image_id(existing_ids_for_pt, selected_cid)

        # Determine file extension
        suffix = Path(file_obj.name).suffix.lower()
        if not suffix:  # camera_input sometimes has no real filename
            # Assume JPEG for camera if missing
            suffix = ".jpg"

        safe_fname = f"{selected_cid}_{new_image_id}{suffix}"
        filepath = CLIN_IMG_DIR / safe_fname

        with open(filepath, "wb") as out:
            out.write(file_obj.read())

        now = iso_now()
        new_row = {
            "ImageID": new_image_id,
            "ClinicalID": selected_cid,
            "VisitID": selected_visit_id,
            "Category": category,
            "FileName": safe_fname,
            "FileType": suffix.lstrip("."),
            "Caption": caption.strip(),
            "Notes": notes.strip(),
            "TakenBy": taken_by.strip(),
            "Location": location.strip(),
            "IsPrimaryLesion": bool(is_primary),
            "CreatedAt": now,
            "UpdatedAt": now,
        }

        images_df = images_df[images_df["ImageID"] != new_image_id]
        images_df = pd.concat([images_df, pd.DataFrame([new_row])], ignore_index=True)
        save_table(images_df, "clinical_images_reports")

        st.success(f"Saved image/report as **{new_image_id}**.")
        st.rerun()

# --------------------------------------------------------------------
# Existing images/reports for this patient
# --------------------------------------------------------------------
st.markdown("---")
st.subheader("Images & reports for this patient")

images_for_pt = images_df[images_df["ClinicalID"] == selected_cid]

if images_for_pt.empty:
    st.info("No images or reports recorded yet for this patient.")
else:
    if "CreatedAt" in images_for_pt.columns:
        images_for_pt = images_for_pt.sort_values(
            by=["CreatedAt", "ImageID"],
            ascending=[False, False],
        )
    else:
        images_for_pt = images_for_pt.sort_values("ImageID", ascending=False)

    display_cols = [
        "ImageID",
        "VisitID",
        "Category",
        "Caption",
        "FileName",
        "CreatedAt",
    ]
    disp = images_for_pt[display_cols].copy()
    disp.insert(0, "No.", range(1, len(disp) + 1))
    st.dataframe(disp, use_container_width=True)

    # ----------------------------------------------------------------
    # Thumbnails for all image files
    # ----------------------------------------------------------------
    st.markdown("#### Thumbnail view of all lesion photos / images")

    image_exts = (".png", ".jpg", ".jpeg", ".bmp", ".gif")
    photo_rows = images_for_pt[
        images_for_pt["FileName"].str.lower().str.endswith(image_exts)
    ]

    if photo_rows.empty:
        st.caption("No image files to preview (only documents/reports).")
    else:
        cols_per_row = 4
        cols = st.columns(cols_per_row)
        for idx, (_, row) in enumerate(photo_rows.iterrows()):
            col = cols[idx % cols_per_row]
            with col:
                img_path = CLIN_IMG_DIR / row["FileName"]
                st.image(
                    str(img_path),
                    caption=f"{row['ImageID']}\n{row['Caption'] or ''}",
                    width=180,   # small thumbnail
                )


    # Simple viewer for the most recent image / report
    st.markdown("#### Quick view of the most recent file")
    latest = images_for_pt.iloc[0]
    file_path = CLIN_IMG_DIR / latest["FileName"]
    st.caption(
        f"Latest: **{latest['ImageID']}** – {latest['Category']} – "
        f"{latest['Caption'] or '(no caption)'}"
    )

    if file_path.suffix.lower() in [".png", ".jpg", ".jpeg"]:
        st.image(str(file_path), use_column_width=True)
    elif file_path.suffix.lower() == ".pdf":
        st.download_button(
            "Download latest PDF",
            data=open(file_path, "rb").read(),
            file_name=file_path.name,
            mime="application/pdf",
        )
    else:
        st.download_button(
            "Download latest file",
            data=open(file_path, "rb").read(),
            file_name=file_path.name,
        )

# --------------------------------------------------------------------
# Optional: delete a record
# --------------------------------------------------------------------
st.markdown("---")
st.subheader("Delete an image/report (if needed)")

if images_for_pt.empty:
    st.caption("Nothing to delete yet.")
else:
    delete_labels = ["(none)"] + [
        f"{row.ImageID} – {row.Category} – {row.Caption or ''}"
        for _, row in images_for_pt.iterrows()
    ]
    del_choice = st.selectbox("Choose record to delete", delete_labels)
    if del_choice != "(none)":
        to_delete_id = del_choice.split(" – ")[0]
        if st.button("Delete selected image/report", type="secondary"):
            images_df = images_df[images_df["ImageID"] != to_delete_id]
            save_table(images_df, "clinical_images_reports")

            row = images_for_pt[images_for_pt["ImageID"] == to_delete_id]
            if not row.empty:
                fname = row.iloc[0]["FileName"]
                try:
                    (CLIN_IMG_DIR / fname).unlink(missing_ok=True)
                except TypeError:
                    fpath = CLIN_IMG_DIR / fname
                    if fpath.exists():
                        fpath.unlink()

            st.success(f"Deleted image/report **{to_delete_id}**.")
            st.rerun()
