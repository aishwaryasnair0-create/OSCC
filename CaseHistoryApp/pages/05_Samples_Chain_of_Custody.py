# pages/05_Samples_Chain_of_Custody.py

import streamlit as st
import pandas as pd
from datetime import datetime
from data_io import load_table, save_table

from utils.navigation import require_module

require_module("Research")

st.title("05 – Samples Chain of Custody")

# -------------------------------------------------------------------
# Context: mode, active study
# -------------------------------------------------------------------
mode = st.session_state.get("module_mode", "Research")
active_study_id = st.session_state.get("active_study_id")

st.caption(f"Current module: **{mode}**")
if active_study_id:
    st.caption(f"Active study / project: **{active_study_id}**")
else:
    st.caption("Active study / project: **none**")

st.markdown("---")

# -------------------------------------------------------------------
# Constants and helpers
# -------------------------------------------------------------------
SAMPLE_LABELS = {
    "WS": "WS – Whole saliva (unstimulated)",
    "WS+EC": "WS+EC – Saliva with epithelial cells (scraping / brush)",
    "EC": "EC – Epithelial cells only (lesion scraping / brush)",
    "SalivaMain": "Main saliva sample (non-pilot cohort)",
}

DEFAULT_VOLUME_TYPES = {"WS", "WS+EC", "EC"}  # 5 mL default

SAMPLES_COLS = [
    "SampleID",
    "ResearchID",
    "Cohort",
    "SampleType",
    "StudyID",
    "CollectionStart",
    "CollectionEnd",
    "PlacedInCryocan",
    "VolumeML",
    "VisibleBlood",
    "Discomfort",
    "Notes",
    "UpdatedAt",
]


def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def get_index_safe(options, value):
    try:
        return options.index(value)
    except ValueError:
        return 0


def default_sample_id(research_id: str, sample_type: str, existing_ids: list[str]) -> str:
    """
    Simple pattern: <ResearchID>-<SampleType>.
    If already used, add -02, -03, etc.
    """
    base = f"{research_id}-{sample_type}"
    if base not in existing_ids:
        return base

    i = 2
    while True:
        cand = f"{base}-{i:02d}"
        if cand not in existing_ids:
            return cand
        i += 1


def get_existing_sample(samples_df: pd.DataFrame, research_id: str, sample_type: str):
    sub = samples_df[(samples_df["ResearchID"] == research_id) & (samples_df["SampleType"] == sample_type)]
    if sub.empty:
        return None
    return sub.iloc[0]


def upsert_sample(row: dict) -> pd.DataFrame:
    """
    Insert or update one sample row in the research_samples table,
    then return the updated DataFrame and cache it in session_state
    so the Lab page can see it immediately.
    """
    samples_df = load_table("research_samples")

    # If no table yet, create an empty one with the same columns as this row
    if samples_df is None or samples_df.empty:
        samples_df = pd.DataFrame(columns=list(row.keys()))
    else:
        # Make sure all keys in 'row' exist as columns
        for col in row.keys():
            if col not in samples_df.columns:
                samples_df[col] = pd.Series(dtype=type(row[col]))

    # Update existing sample with same SampleID, or append new
    mask = samples_df["SampleID"] == row["SampleID"]
    if mask.any():
        samples_df.loc[mask, list(row.keys())] = list(row.values())
    else:
        samples_df = pd.concat(
            [samples_df, pd.DataFrame([row])],
            ignore_index=True,
        )

    # Save to disk
    save_table(samples_df, "research_samples")

    # Cache in session_state so 06_Lab_PCR_and_NGS can use it
    st.session_state["research_samples_cache"] = samples_df.copy()

    return samples_df



# -------------------------------------------------------------------
# Load tables
# -------------------------------------------------------------------
participants = load_table(
    "research_participants",
    columns=["ResearchID", "Name", "Age", "Sex", "Phone", "Group", "Cohort", "CreatedAt"],
)

samples = load_table("samples", columns=SAMPLES_COLS)

if samples is None:
    samples = pd.DataFrame(columns=SAMPLES_COLS)

st.session_state["research_samples_cache"] = samples.copy()


consents = load_table(
    "research_consents",
    columns=["ResearchID", "PlannedSampleTypes", "CohortAtConsent"],
)

if participants.empty:
    st.error("No research participants found. Please add participants first.")
    st.stop()

# -------------------------------------------------------------------
# Select participant
# -------------------------------------------------------------------
st.subheader("Select participant")

options = []
for _, row in participants.iterrows():
    rid = row["ResearchID"]
    label = f"{rid} – {row['Name']} (Group: {row['Group']}, Cohort: {row['Cohort']})"
    options.append((label, rid))

labels = [o[0] for o in options]
ids = [o[1] for o in options]

selected_idx = st.selectbox(
    "Choose ResearchID",
    options=list(range(len(options))),
    format_func=lambda i: labels[i],
)
selected_id = ids[selected_idx]

p_row = participants[participants["ResearchID"] == selected_id].iloc[0]
group = p_row["Group"]
cohort = p_row["Cohort"]

st.info(
    f"**{selected_id}** – {p_row['Name']} "
    f"(Age {p_row['Age']}, Sex {p_row['Sex']}, Group: {group}, Cohort: {cohort})"
)

# -------------------------------------------------------------------
# Determine which sample types to show
# -------------------------------------------------------------------
pt_consent = consents[consents["ResearchID"] == selected_id]
if not pt_consent.empty:
    planned_str = pt_consent.iloc[0].get("PlannedSampleTypes", "")
    if isinstance(planned_str, str) and planned_str.strip():
        planned_types = [s for s in planned_str.split(";") if s]
    else:
        planned_types = []
else:
    planned_types = []

if planned_types:
    sample_types_to_show = planned_types
else:
    # Fallback based on cohort if consent not set
    if cohort == "PILOT":
        sample_types_to_show = ["WS", "WS+EC", "EC"]
    else:
        sample_types_to_show = ["SalivaMain"]

st.markdown("---")
st.subheader("Record sample collection and chain of custody")

st.caption(
    "For each planned sample type below, use the **Start / End / Cryocan** buttons "
    "to timestamp collection events, and fill in volume and notes as needed."
)

# -------------------------------------------------------------------
# Per-sample-type UI
# -------------------------------------------------------------------
existing_ids = samples["SampleID"].tolist()

for stype in sample_types_to_show:
    label = SAMPLE_LABELS.get(stype, stype)

    st.markdown(f"### Sample type: {label}")

    existing_sample = get_existing_sample(samples, selected_id, stype)

    if existing_sample is not None and isinstance(existing_sample.get("SampleID", ""), str):
        sample_id = existing_sample["SampleID"]
        st.caption(f"SampleID: **{sample_id}**")
    else:
        sample_id = default_sample_id(selected_id, stype, existing_ids)
        st.caption(f"SampleID (will be created): **{sample_id}**")

    # Current times
    cur_start = existing_sample["CollectionStart"] if existing_sample is not None else ""
    cur_end = existing_sample["CollectionEnd"] if existing_sample is not None else ""
    cur_cryo = existing_sample["PlacedInCryocan"] if existing_sample is not None else ""

    c_times = st.columns(3)
    c_times[0].markdown(f"**Start collection:**  {cur_start or 'Not set'}")
    c_times[1].markdown(f"**End collection:**  {cur_end or 'Not set'}")
    c_times[2].markdown(f"**Placed in cryocan:**  {cur_cryo or 'Not set'}")

    c_btn = st.columns(3)
    start_clicked = c_btn[0].button("Start collection", key=f"start_{stype}_{selected_id}")
    end_clicked = c_btn[1].button("End collection", key=f"end_{stype}_{selected_id}")
    cryo_clicked = c_btn[2].button("Mark placed in cryocan", key=f"cryo_{stype}_{selected_id}")

    # Defaults for details
    if existing_sample is not None and pd.notna(existing_sample.get("VolumeML", None)):
        default_vol = float(existing_sample["VolumeML"])
    else:
        default_vol = 5.0 if stype in DEFAULT_VOLUME_TYPES else 0.0

    default_blood = (
        existing_sample.get("VisibleBlood", "No")
        if existing_sample is not None
        else "No"
    )
    blood_opts = ["No", "Mild", "Moderate", "Severe"]

    default_disc = (
        existing_sample.get("Discomfort", "None")
        if existing_sample is not None
        else "None"
    )
    disc_opts = ["None", "Mild", "Moderate", "Severe"]

    default_notes = (
        existing_sample.get("Notes", "")
        if existing_sample is not None
        else ""
    )

    with st.expander("Volume, blood, discomfort & notes", expanded=True):
        col1, col2 = st.columns(2)
        with col1:
            volume = st.number_input(
                "Collected volume (mL)",
                min_value=0.0,
                value=float(default_vol),
                step=0.5,
                key=f"vol_{stype}_{selected_id}",
            )
        with col2:
            vis_blood = st.selectbox(
                "Visible blood in sample?",
                blood_opts,
                index=get_index_safe(blood_opts, default_blood),
                key=f"blood_{stype}_{selected_id}",
            )

        col3, col4 = st.columns([1, 2])
        with col3:
            discomfort = st.selectbox(
                "Patient discomfort",
                disc_opts,
                index=get_index_safe(disc_opts, default_disc),
                key=f"disc_{stype}_{selected_id}",
            )
        with col4:
            notes = st.text_area(
                "Notes for this sample (optional)",
                value=default_notes,
                key=f"notes_{stype}_{selected_id}",
            )

        save_clicked = st.button(
            "Save / update this sample",
            key=f"save_{stype}_{selected_id}",
        )

    # Handle actions
    if start_clicked or end_clicked or cryo_clicked or save_clicked:
        # Re-use existing values unless updated
        collection_start = cur_start
        collection_end = cur_end
        cryo_time = cur_cryo

        if start_clicked:
            collection_start = iso_now()

        if end_clicked:
            collection_end = iso_now()
            if volume <= 0 and stype in DEFAULT_VOLUME_TYPES:
                volume = 5.0  # default 5 mL if user didn't enter

        if cryo_clicked:
            cryo_time = iso_now()

        # Save row (for save_clicked we just keep times as they are)
        new_row = {
            "SampleID": sample_id,
            "ResearchID": selected_id,
            "Cohort": cohort,
            "SampleType": stype,
            "StudyID": active_study_id or "",
            "CollectionStart": collection_start,
            "CollectionEnd": collection_end,
            "PlacedInCryocan": cryo_time,
            "VolumeML": float(volume),
            "VisibleBlood": vis_blood,
            "Discomfort": discomfort,
            "Notes": notes.strip(),
            "UpdatedAt": iso_now(),
        }

        samples = upsert_sample(samples, new_row)
        existing_ids = samples["SampleID"].tolist()  # refresh
        st.success(f"Sample '{sample_id}' updated.")
        st.rerun()

    st.markdown("---")

# -------------------------------------------------------------------
# Overview for this participant
# -------------------------------------------------------------------
st.subheader("Samples for this participant")

sub = samples[samples["ResearchID"] == selected_id]
if sub.empty:
    st.info("No samples recorded yet for this participant.")
else:
    display_df = sub.copy()
    display_df.insert(0, "No.", range(1, len(display_df) + 1))
    st.dataframe(display_df, use_container_width=True)
