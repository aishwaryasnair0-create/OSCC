# pages/04_Research_Case_History.py
#
# Research Case History – core case history + medical history + attachments
# All sections are top-level expanders (no nested expanders).

import streamlit as st
import pandas as pd
import json
from datetime import datetime
from pathlib import Path

from data_io import load_table, save_table, DATA_DIR
from utils.navigation import require_module

# --------------------------------------------------------------------
# Restrict to Research module
# --------------------------------------------------------------------
require_module("Research")

st.title("Research Case History")

# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def iso_now():
    return datetime.now().isoformat(timespec="seconds")


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def adjust_nad(nad_flag: bool, has_data: bool, section_label: str):
    """If NAD is checked but the section has data, force NAD to False."""
    if nad_flag and has_data:
        st.warning(f"In **{section_label}**, you entered details, so 'NAD' will be ignored.")
        return False
    return nad_flag


# ----- drug database for AI-style medication helper -----------------
DRUG_DB_PATH = DATA_DIR / "drug_db.csv"


def load_drug_db() -> pd.DataFrame:
    if DRUG_DB_PATH.exists():
        df = pd.read_csv(DRUG_DB_PATH)
    else:
        df = pd.DataFrame(
            columns=[
                "brand_name",
                "generic_name",
                "strength",
                "form",
                "route",
                "standard_dose",
                "notes",
            ]
        )
    for col in ["brand_name", "generic_name"]:
        if col in df.columns:
            df[col + "_lower"] = df[col].astype(str).str.lower()
    return df


def medication_entry_widget(key_prefix: str, drug_db: pd.DataFrame, prev: dict | None = None) -> dict:
    """
    Renders a single medication row and returns a dict with values.
    key_prefix ensures unique keys. prev is a dict of previous values.
    """
    prev = prev or {}

    st.markdown(f"**Medication {key_prefix.split('_')[-1]}**")

    # 1. Input for brand / generic name
    name_input = st.text_input(
        "Drug name (brand or generic)",
        key=f"{key_prefix}_name",
        value=prev.get("DrugNameInput", ""),
        placeholder="Start typing, e.g. 'Ecosprin 75' or 'Metformin'",
    )

    suggested_generic = ""
    suggested_dose = ""
    suggestions = pd.DataFrame()

    # ---- SAFE suggestion logic ----
    if name_input and isinstance(drug_db, pd.DataFrame) and not drug_db.empty:
        try:
            q = name_input.strip().lower()

            # Build masks from whatever lower-cased columns exist
            masks = []

            if "brand_name_lower" in drug_db.columns:
                masks.append(
                    drug_db["brand_name_lower"]
                    .fillna("")
                    .str.contains(q, na=False)
                )
            if "generic_name_lower" in drug_db.columns:
                masks.append(
                    drug_db["generic_name_lower"]
                    .fillna("")
                    .str.contains(q, na=False)
                )

            if masks:
                # Combine all masks with OR, index is guaranteed to match drug_db
                mask = masks[0]
                for m in masks[1:]:
                    mask = mask | m

                suggestions = drug_db.loc[mask].copy()
            else:
                # No searchable columns – no suggestions, no crash
                suggestions = pd.DataFrame()
        except Exception as e:
            # If anything goes wrong, fall back to manual entry
            st.warning(
                "Drug suggestions temporarily unavailable – "
                "please fill generic name and dose manually."
            )
            suggestions = pd.DataFrame()

    # If you already have stored values for this med, they override suggestions
    if prev.get("GenericName"):
        suggested_generic = prev["GenericName"]
    if prev.get("Dose"):
        suggested_dose = prev["Dose"]

    # If we have suggestions and no previous override, populate from suggestion
    if not suggestions.empty and not prev.get("GenericName"):
        if len(suggestions) == 1:
            chosen = suggestions.iloc[0]
            suggested_generic = chosen.get("generic_name", "") or suggested_generic
            suggested_dose = chosen.get("standard_dose", "") or suggested_dose
            st.caption("✅ One matching drug found – generic name and usual dose pre-filled.")
        else:
            # Multiple matches – let you choose
            suggestion_labels = []
            for _, row in suggestions.iterrows():
                label = f"{row.get('brand_name', '')} – {row.get('generic_name', '')} {row.get('strength', '')} ({row.get('form', '')})"
                std = row.get("standard_dose", "")
                if isinstance(std, str) and std:
                    label += f" · usual: {std}"
                suggestion_labels.append(label)

            choice = st.selectbox(
                "Multiple matches found – choose the correct one:",
                suggestion_labels,
                key=f"{key_prefix}_choice",
            )
            idx = suggestion_labels.index(choice)
            chosen = suggestions.iloc[idx]
            suggested_generic = chosen.get("generic_name", "") or suggested_generic
            suggested_dose = chosen.get("standard_dose", "") or suggested_dose

    # 2. Rest of the fields
    generic_name = st.text_input(
        "Generic name",
        key=f"{key_prefix}_generic",
        value=suggested_generic,
    )

    strength = st.text_input(
        "Strength (e.g. 75 mg, 500 mg + 1 mg)",
        key=f"{key_prefix}_strength",
        value=prev.get("Strength", ""),
    )

    dose = st.text_input(
        "Dose & frequency",
        key=f"{key_prefix}_dose",
        value=suggested_dose,
        placeholder="e.g. 75 mg once daily after food",
    )

    indication = st.text_input(
        "Indication (why is the patient taking this?)",
        key=f"{key_prefix}_indication",
        value=prev.get("Indication", ""),
    )

    duration = st.text_input(
        "Duration / since when (approx)",
        key=f"{key_prefix}_duration",
        value=prev.get("Duration", ""),
        placeholder="e.g. 2 years, 6 months",
    )

    extra_notes = st.text_area(
        "Notes (side effects, prescribing doctor, etc.)",
        key=f"{key_prefix}_notes",
        value=prev.get("Notes", ""),
        height=80,
    )

    st.markdown("---")

    return {
        "DrugNameInput": name_input,
        "GenericName": generic_name,
        "Strength": strength,
        "Dose": dose,
        "Indication": indication,
        "Duration": duration,
        "Notes": extra_notes,
    }



# ----- documents (prescriptions, hospital records, reports) ----------
RESEARCH_DOCS_DIR = DATA_DIR / "research_documents"
ensure_dir(RESEARCH_DOCS_DIR)


def gen_document_id(existing_ids, research_id: str) -> str:
    """Generate DocumentID like <ResearchID>-DOC-001."""
    prefix = f"{research_id}-DOC-"
    nums = []
    for did in existing_ids:
        if isinstance(did, str) and did.startswith(prefix):
            tail = did.replace(prefix, "")
            try:
                nums.append(int(tail))
            except ValueError:
                continue
    next_num = max(nums) + 1 if nums else 1
    return f"{prefix}{next_num:03d}"


# --------------------------------------------------------------------
# Load research participants
# --------------------------------------------------------------------
participants = load_table("research_participants")

if participants.empty:
    st.error("No research participants found. Please register participants first.")
    st.stop()

if "CreatedAt" in participants.columns:
    participants = participants.sort_values(
        by=["CreatedAt", "ResearchID"], ascending=[False, False]
    )
elif "ResearchID" in participants.columns:
    participants = participants.sort_values(by="ResearchID", ascending=False)

# --------------------------------------------------------------------
# Select participant
# --------------------------------------------------------------------
st.subheader("Select research participant")

search_text = st.text_input(
    "Search by name or ResearchID",
    value="",
    help="Start typing participant name or ResearchID to filter.",
)

if search_text.strip():
    s = search_text.strip()
    mask = (
        participants["Name"].astype(str).str.contains(s, case=False, na=False)
        | participants["ResearchID"].astype(str).str.contains(s, case=False, na=False)
    )
    filtered = participants[mask]
else:
    filtered = participants

if filtered.empty:
    st.warning("No participants match the search text.")
    st.stop()

options = [
    f"{row.ResearchID} – {row.Name}"
    for _, row in filtered.iterrows()
]
sel_label = st.selectbox("Participant", options)
selected_id = sel_label.split(" – ")[0]

p_row = participants[participants["ResearchID"] == selected_id].iloc[0]
st.info(
    f"**{selected_id}** – {p_row['Name']} "
    f"(Age {p_row.get('Age', '')}, Sex {p_row.get('Sex', '')}) · "
    f"Group: {p_row.get('Group', '')}, Cohort: {p_row.get('Cohort', '')}"
)

st.markdown("---")

# --------------------------------------------------------------------
# Load existing medical history & meds & docs
# --------------------------------------------------------------------
mh_df = load_table("research_med_history")
mh_prev_dict = {}

if not mh_df.empty and "ResearchID" in mh_df.columns:
    row_match = mh_df[mh_df["ResearchID"] == selected_id]
    if not row_match.empty:
        record = row_match.iloc[0]
        try:
            mh_prev_dict = json.loads(record.get("MedicalHistoryJSON", "{}"))
        except Exception:
            mh_prev_dict = {}


def get_prev(name, default=None):
    return mh_prev_dict.get(name, default)


# medications table
meds_df = load_table("research_medications")
if meds_df.empty:
    meds_df = pd.DataFrame(
        columns=[
            "ResearchID",
            "MedIndex",
            "DrugNameInput",
            "GenericName",
            "Strength",
            "Dose",
            "Indication",
            "Duration",
            "Notes",
        ]
    )

prev_meds_for_pt = meds_df[meds_df["ResearchID"] == selected_id].sort_values("MedIndex")
prev_meds_list = []
if not prev_meds_for_pt.empty:
    for _, r in prev_meds_for_pt.iterrows():
        prev_meds_list.append(
            {
                "DrugNameInput": r.get("DrugNameInput", ""),
                "GenericName": r.get("GenericName", ""),
                "Strength": r.get("Strength", ""),
                "Dose": r.get("Dose", ""),
                "Indication": r.get("Indication", ""),
                "Duration": r.get("Duration", ""),
                "Notes": r.get("Notes", ""),
            }
        )

# documents table
doc_cols = [
    "DocumentID",
    "ResearchID",
    "DocType",
    "FileName",
    "FileExt",
    "Caption",
    "Notes",
    "CreatedAt",
]
docs_df = load_table("research_documents")
if docs_df.empty:
    docs_df = pd.DataFrame(columns=doc_cols)

# --------------------------------------------------------------------
# Case history & medical history
# --------------------------------------------------------------------
st.subheader("Detailed case & medical history (IEC case history level)")

mh_data: dict = {}

# 01. Chief complaint & HOPI
with st.expander("01. Chief complaint & history of presenting illness", expanded=False):
    ch_cc = st.text_area(
        "Chief complaint (as reported by patient, with duration)",
        value=get_prev("CH_ChiefComplaint", ""),
        key="CH_ChiefComplaint",
        height=120,
    )

    ch_hopi = st.text_area(
        "History of presenting illness (chronological, in your words)",
        value=get_prev("CH_HOPI", ""),
        key="CH_HOPI",
        height=160,
    )

    mh_data.update(
        dict(
            CH_ChiefComplaint=ch_cc,
            CH_HOPI=ch_hopi,
        )
    )

# 02. Symptom analysis – pain / swelling / ulcer
with st.expander("02. Symptom analysis – pain / swelling / ulcer", expanded=False):

    # Pain
    st.markdown("### Pain")
    pain_present = st.radio(
        "Is pain present?",
        options=["No", "Yes"],
        index=["No", "Yes"].index(get_prev("Pain_Present", "No")),
        key="Pain_Present",
        horizontal=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        pain_onset_date = st.text_input(
            "Date / approximate onset",
            value=get_prev("Pain_OnsetDate", ""),
            key="Pain_OnsetDate",
        )
        pain_type_onset = st.text_input(
            "Type of onset (acute / chronic / gradual / sudden)",
            value=get_prev("Pain_TypeOnset", ""),
            key="Pain_TypeOnset",
        )
        pain_character = st.text_input(
            "Character (dull / sharp / throbbing / burning / others)",
            value=get_prev("Pain_Character", ""),
            key="Pain_Character",
        )
        pain_location = st.text_input(
            "Location",
            value=get_prev("Pain_Location", ""),
            key="Pain_Location",
        )
    with col2:
        pain_radiation = st.text_input(
            "Radiation of pain (if any)",
            value=get_prev("Pain_Radiation", ""),
            key="Pain_Radiation",
        )
        pain_aggravating = st.text_input(
            "Aggravating factors",
            value=get_prev("Pain_AggravatingFactors", ""),
            key="Pain_AggravatingFactors",
        )
        pain_relieving = st.text_input(
            "Relieving factors",
            value=get_prev("Pain_RelievingFactors", ""),
            key="Pain_RelievingFactors",
        )
        pain_timing = st.text_input(
            "Timing & duration (continuous / intermittent, day/night)",
            value=get_prev("Pain_TimingDuration", ""),
            key="Pain_TimingDuration",
        )

    pain_relation_activities = st.text_input(
        "Relation to other activities (eating, talking, swallowing, etc.)",
        value=get_prev("Pain_RelationActivities", ""),
        key="Pain_RelationActivities",
    )

    pain_associated_comp = st.text_input(
        "Association with other complications / symptoms",
        value=get_prev("Pain_AssociatedComplications", ""),
        key="Pain_AssociatedComplications",
    )

    pain_notes = st.text_area(
        "Additional notes about pain (if any)",
        value=get_prev("Pain_Notes", ""),
        key="Pain_Notes",
        height=80,
    )

    mh_data.update(
        dict(
            Pain_Present=pain_present,
            Pain_OnsetDate=pain_onset_date,
            Pain_TypeOnset=pain_type_onset,
            Pain_Character=pain_character,
            Pain_Location=pain_location,
            Pain_Radiation=pain_radiation,
            Pain_AggravatingFactors=pain_aggravating,
            Pain_RelievingFactors=pain_relieving,
            Pain_TimingDuration=pain_timing,
            Pain_RelationActivities=pain_relation_activities,
            Pain_AssociatedComplications=pain_associated_comp,
            Pain_Notes=pain_notes,
        )
    )

    # Swelling
    st.markdown("---")
    st.markdown("### Swelling")
    swell_present = st.radio(
        "Is swelling present?",
        options=["No", "Yes"],
        index=["No", "Yes"].index(get_prev("Swelling_Present", "No")),
        key="Swelling_Present",
        horizontal=True,
    )

    swell_duration = st.text_input(
        "Duration of swelling (acute / chronic, in weeks/months/years)",
        value=get_prev("Swelling_Duration", ""),
        key="Swelling_Duration",
    )
    swell_mode = st.text_input(
        "Mode of onset (rapid / slow / associated with any action)",
        value=get_prev("Swelling_ModeOnset", ""),
        key="Swelling_ModeOnset",
    )
    swell_symptoms = st.text_area(
        "Symptoms associated with swelling (pain, difficulty in breathing/swallowing, fever, weight loss, etc.)",
        value=get_prev("Swelling_Symptoms", ""),
        key="Swelling_Symptoms",
        height=100,
    )
    swell_changes = st.text_area(
        "Secondary changes (ulceration, inflammation, colour change, discharge)",
        value=get_prev("Swelling_SecondaryChanges", ""),
        key="Swelling_SecondaryChanges",
        height=80,
    )
    swell_function = st.text_input(
        "Impairment of function (difficulty in eating or opening mouth, etc.)",
        value=get_prev("Swelling_FunctionImpairment", ""),
        key="Swelling_FunctionImpairment",
    )
    swell_recurrence = st.text_input(
        "Recurrence (if any)",
        value=get_prev("Swelling_Recurrence", ""),
        key="Swelling_Recurrence",
    )

    mh_data.update(
        dict(
            Swelling_Present=swell_present,
            Swelling_Duration=swell_duration,
            Swelling_ModeOnset=swell_mode,
            Swelling_Symptoms=swell_symptoms,
            Swelling_SecondaryChanges=swell_changes,
            Swelling_FunctionImpairment=swell_function,
            Swelling_Recurrence=swell_recurrence,
        )
    )

    # Ulcer
    st.markdown("---")
    st.markdown("### Ulcer")
    ulcer_present = st.radio(
        "Is ulcer present?",
        options=["No", "Yes"],
        index=["No", "Yes"].index(get_prev("Ulcer_Present", "No")),
        key="Ulcer_Present",
        horizontal=True,
    )

    ulcer_mode = st.text_input(
        "Mode of onset (sudden / gradual / associated with trauma, etc.)",
        value=get_prev("Ulcer_ModeOnset", ""),
        key="Ulcer_ModeOnset",
    )
    ulcer_duration = st.text_input(
        "Duration of ulcer",
        value=get_prev("Ulcer_Duration", ""),
        key="Ulcer_Duration",
    )
    ulcer_discharge = st.text_input(
        "Discharge (serum / blood / pus – amount, frequency)",
        value=get_prev("Ulcer_Discharge", ""),
        key="Ulcer_Discharge",
    )
    ulcer_assoc_disease = st.text_input(
        "Associated systemic diseases (if any)",
        value=get_prev("Ulcer_AssociatedDiseases", ""),
        key="Ulcer_AssociatedDiseases",
    )
    ulcer_notes = st.text_area(
        "Additional notes about ulcer",
        value=get_prev("Ulcer_Notes", ""),
        key="Ulcer_Notes",
        height=80,
    )

    mh_data.update(
        dict(
            Ulcer_Present=ulcer_present,
            Ulcer_ModeOnset=ulcer_mode,
            Ulcer_Duration=ulcer_duration,
            Ulcer_Discharge=ulcer_discharge,
            Ulcer_AssociatedDiseases=ulcer_assoc_disease,
            Ulcer_Notes=ulcer_notes,
        )
    )

# 03. Family history, past dental history & pregnancies
with st.expander("03. Family history, past dental history & pregnancies", expanded=False):

    fam_nad = st.checkbox(
        "Family history NAD / no significant family history",
        value=bool(get_prev("Family_NAD", False)),
        key="Family_NAD",
    )
    fam_hist = st.text_area(
        "Family history (systemic diseases, cancer, syndromes, habits)",
        value=get_prev("Family_History", ""),
        key="Family_History",
        height=120,
    )
    fam_nad = adjust_nad(fam_nad, bool(fam_hist.strip()), "Family history")

    pdh_nad = st.checkbox(
        "Past dental history NAD",
        value=bool(get_prev("PastDental_NAD", False)),
        key="PastDental_NAD",
    )
    pdh = st.text_area(
        "Past dental history of presenting illness (previous treatment, extractions, restorations, trauma, etc.)",
        value=get_prev("PastDental_History", ""),
        key="PastDental_History",
        height=120,
    )
    pdh_nad = adjust_nad(pdh_nad, bool(pdh.strip()), "Past dental history")

    obst_hist = st.text_area(
        "Obstetric history (G, P, L, A and any complications in pregnancies)",
        value=get_prev("Obstetric_History", ""),
        key="Obstetric_History",
        height=100,
    )

    mh_data.update(
        dict(
            Family_NAD=fam_nad,
            Family_History=fam_hist,
            PastDental_NAD=pdh_nad,
            PastDental_History=pdh,
            Obstetric_History=obst_hist,
        )
    )

# 04. Personal history – tobacco, alcohol, diet, habits
with st.expander("04. Personal history – tobacco, alcohol, diet, habits", expanded=False):

    # Tobacco usage
    st.markdown("### Tobacco usage")

    tob_nad = st.checkbox(
        "No history of tobacco use",
        value=bool(get_prev("Tobacco_NAD", False)),
        key="Tobacco_NAD",
    )

    tob_type_free = st.text_input(
        "Summary of tobacco types (cigarettes, bidis, gutkha, khaini, pan with tobacco, etc.)",
        value=get_prev("Tobacco_TypeSummary", ""),
        key="Tobacco_TypeSummary",
    )

    st.markdown("#### Smoked tobacco – pack years")
    col1, col2, col3 = st.columns(3)
    with col1:
        smoked_packs_per_day = st.number_input(
            "No. of packs per day",
            min_value=0.0,
            step=0.1,
            value=float(get_prev("Tob_Smoked_PacksPerDay", 0.0) or 0.0),
            key="Tob_Smoked_PacksPerDay",
        )
    with col2:
        smoked_years = st.number_input(
            "No. of years smoked",
            min_value=0.0,
            step=0.5,
            value=float(get_prev("Tob_Smoked_Years", 0.0) or 0.0),
            key="Tob_Smoked_Years",
        )
    with col3:
        smoked_pack_years = smoked_packs_per_day * smoked_years
        st.metric("Estimated pack-years (smoked)", f"{smoked_pack_years:.1f}")

    mh_data["Tob_Smoked_PacksPerDay"] = smoked_packs_per_day
    mh_data["Tob_Smoked_Years"] = smoked_years
    mh_data["Tob_Smoked_PackYears"] = smoked_pack_years

    st.markdown("#### Smokeless tobacco – packets per day")
    col1, col2, col3 = st.columns(3)
    with col1:
        smokeless_packets_per_day = st.number_input(
            "No. of packets per day",
            min_value=0.0,
            step=0.1,
            value=float(get_prev("Tob_Smokeless_PacketsPerDay", 0.0) or 0.0),
            key="Tob_Smokeless_PacketsPerDay",
        )
    with col2:
        smokeless_years = st.number_input(
            "No. of years used",
            min_value=0.0,
            step=0.5,
            value=float(get_prev("Tob_Smokeless_Years", 0.0) or 0.0),
            key="Tob_Smokeless_Years",
        )
    with col3:
        smokeless_packet_years = smokeless_packets_per_day * smokeless_years
        st.metric("Packets-years (smokeless)", f"{smokeless_packet_years:.1f}")

    mh_data["Tob_Smokeless_PacketsPerDay"] = smokeless_packets_per_day
    mh_data["Tob_Smokeless_Years"] = smokeless_years
    mh_data["Tob_Smokeless_PacketYears"] = smokeless_packet_years

    st.markdown("#### Pouches (gutkha, pan masala with tobacco, etc.)")
    col1, col2, col3 = st.columns(3)
    with col1:
        pouch_per_day = st.number_input(
            "No. of pouches per day",
            min_value=0.0,
            step=0.1,
            value=float(get_prev("Tob_Pouch_PerDay", 0.0) or 0.0),
            key="Tob_Pouch_PerDay",
        )
    with col2:
        pouch_years = st.number_input(
            "No. of years used",
            min_value=0.0,
            step=0.5,
            value=float(get_prev("Tob_Pouch_Years", 0.0) or 0.0),
            key="Tob_Pouch_Years",
        )
    with col3:
        pouch_year_index = pouch_per_day * pouch_years
        st.metric("Pouch-years", f"{pouch_year_index:.1f}")

    mh_data["Tob_Pouch_PerDay"] = pouch_per_day
    mh_data["Tob_Pouch_Years"] = pouch_years
    mh_data["Tob_Pouch_Index"] = pouch_year_index

    st.markdown("#### Other smokeless forms")
    tob_other_name = st.text_input(
        "Identify smokeless form used (others)",
        value=get_prev("Tob_Other_Name", ""),
        key="Tob_Other_Name",
    )
    col1, col2 = st.columns(2)
    with col1:
        tob_other_amount = st.text_input(
            "Amount used per day (approx)",
            value=get_prev("Tob_Other_AmountPerDay", ""),
            key="Tob_Other_AmountPerDay",
        )
    with col2:
        tob_other_years = st.text_input(
            "No. of years used",
            value=get_prev("Tob_Other_Years", ""),
            key="Tob_Other_Years",
        )

    tob_notes = st.text_area(
        "Additional notes on pattern, quitting attempts, counseling, etc.",
        value=get_prev("Tobacco_Notes", ""),
        key="Tobacco_Notes",
        height=100,
    )

    any_tob_data = (
        tob_type_free.strip()
        or smoked_packs_per_day
        or smoked_years
        or smokeless_packets_per_day
        or smokeless_years
        or pouch_per_day
        or pouch_years
        or tob_other_name.strip()
        or tob_other_amount.strip()
        or tob_other_years.strip()
        or tob_notes.strip()
    )
    tob_nad = adjust_nad(tob_nad, any_tob_data, "Tobacco usage")

    mh_data.update(
        dict(
            Tobacco_NAD=tob_nad,
            Tobacco_TypeSummary=tob_type_free,
            Tob_Other_Name=tob_other_name,
            Tob_Other_AmountPerDay=tob_other_amount,
            Tob_Other_Years=tob_other_years,
            Tobacco_Notes=tob_notes,
        )
    )

    st.caption(
        "Later we can add reference images of tobacco products here once you place "
        "them in a folder (e.g. data/tobacco_images)."
    )

    # Alcohol summary (AUDIT already on separate page)
    st.markdown("---")
    st.markdown("### Alcohol history (summary)")
    alc_nad = st.checkbox(
        "No alcohol use / lifetime abstainer",
        value=bool(get_prev("Alcohol_NAD", False)),
        key="Alcohol_NAD",
    )

    alc_pattern = st.text_area(
        "Alcohol history summary (pattern, quantity, duration – cross-check with AUDIT page)",
        value=get_prev("Alcohol_History", ""),
        key="Alcohol_History",
        height=100,
    )

    alc_nad = adjust_nad(alc_nad, bool(alc_pattern.strip()), "Alcohol history")

    mh_data.update(
        dict(
            Alcohol_NAD=alc_nad,
            Alcohol_History=alc_pattern,
        )
    )

    # Diet & other habits
    st.markdown("---")
    st.markdown("### Diet & other habits")

    diet_type = st.selectbox(
        "Diet type",
        options=["Mixed", "Vegetarian", "Non-vegetarian", "Eggetarian", "Other"],
        index=["Mixed", "Vegetarian", "Non-vegetarian", "Eggetarian", "Other"].index(
            get_prev("Diet_Type", "Mixed")
        ),
        key="Diet_Type",
    )
    diet_details = st.text_area(
        "Diet details (spicy / hot drinks / frequency of meals, etc.)",
        value=get_prev("Diet_Details", ""),
        key="Diet_Details",
        height=80,
    )

    other_habits = st.text_area(
        "Other habits (betel nut, pan, mouth breathing, bruxism, lip/cheek biting, etc.)",
        value=get_prev("Other_Habits", ""),
        key="Other_Habits",
        height=100,
    )

    mh_data.update(
        dict(
            Diet_Type=diet_type,
            Diet_Details=diet_details,
            Other_Habits=other_habits,
        )
    )

# 05. Medical history – overview summary
with st.expander("05. Medical history – overview (summary)", expanded=False):
    mh_overall_nad = st.checkbox(
        "No significant medical history (NKMI)",
        value=bool(get_prev("MH_Overall_NAD", False)),
        key="MH_Overall_NAD",
    )
    mh_overview_notes = st.text_area(
        "If NKMI not applicable, write a brief overall summary (optional)",
        value=get_prev("MH_Overview_Notes", ""),
        key="MH_Overview_Notes",
        height=80,
    )

    mh_data["MH_Overall_NAD"] = mh_overall_nad
    mh_data["MH_Overview_Notes"] = mh_overview_notes

# 06. Serious illnesses
with st.expander("06. Medical history – serious / significant illnesses", expanded=False):
    mh_serious_nad = st.checkbox(
        "No serious or significant illnesses reported",
        value=bool(get_prev("MH_Serious_NAD", False)),
        key="MH_Serious_NAD",
    )

    mh_serious_diagnosis = st.text_area(
        "Diagnoses (with year and current status)",
        value=get_prev("MH_Serious_DiagnosisList", ""),
        key="MH_Serious_DiagnosisList",
        height=80,
    )

    mh_serious_systems = st.multiselect(
        "Main systems involved",
        options=[
            "Heart disease",
            "Liver disease",
            "Kidney disease",
            "Lung disease",
            "Congenital disorder",
            "Infectious disease",
            "Immunologic / autoimmune",
            "Endocrine / diabetes",
            "Radiation/chemotherapy",
            "Bleeding disorder",
            "Psychiatric illness",
            "Other",
        ],
        default=get_prev("MH_Serious_Systems", []),
        key="MH_Serious_Systems",
    )

    mh_serious_notes = st.text_area(
        "Additional notes",
        value=get_prev("MH_Serious_Notes", ""),
        key="MH_Serious_Notes",
        height=80,
    )

    mh_serious_nad = adjust_nad(
        mh_serious_nad,
        bool(mh_serious_diagnosis.strip() or mh_serious_systems or mh_serious_notes.strip()),
        "Serious illnesses",
    )

    mh_data.update(
        dict(
            MH_Serious_NAD=mh_serious_nad,
            MH_Serious_DiagnosisList=mh_serious_diagnosis,
            MH_Serious_Systems=mh_serious_systems,
            MH_Serious_Notes=mh_serious_notes,
        )
    )

# 07. Hospitalisations / surgeries
with st.expander("07. Medical history – hospitalisations / surgeries", expanded=False):
    mh_hosp_nad = st.checkbox(
        "No prior hospitalisation or surgery",
        value=bool(get_prev("MH_Hosp_NAD", False)),
        key="MH_Hosp_NAD",
    )

    mh_hosp_ever = st.radio(
        "Any previous admission to hospital?",
        options=["No", "Yes"],
        index=["No", "Yes"].index(get_prev("MH_Hosp_EverAdmitted", "No")),
        key="MH_Hosp_EverAdmitted",
        horizontal=True,
    )

    mh_hosp_number = st.text_input(
        "Approximate number of admissions",
        value=get_prev("MH_Hosp_Number", ""),
        key="MH_Hosp_Number",
    )

    mh_hosp_last_year = st.text_input(
        "Year of last admission",
        value=get_prev("MH_Hosp_LastAdmission_Year", ""),
        key="MH_Hosp_LastAdmission_Year",
    )

    mh_hosp_last_reason = st.text_area(
        "Reason for last admission / surgery",
        value=get_prev("MH_Hosp_LastAdmission_Reason", ""),
        key="MH_Hosp_LastAdmission_Reason",
        height=80,
    )

    mh_hosp_surgeries = st.text_area(
        "Important surgeries (year, organ/system, hospital/city)",
        value=get_prev("MH_Hosp_Surgeries_List", ""),
        key="MH_Hosp_Surgeries_List",
        height=100,
    )

    mh_hosp_notes = st.text_area(
        "Additional notes",
        value=get_prev("MH_Hosp_Notes", ""),
        key="MH_Hosp_Notes",
        height=80,
    )

    mh_hosp_nad = adjust_nad(
        mh_hosp_nad,
        bool(
            mh_hosp_ever == "Yes"
            or mh_hosp_number.strip()
            or mh_hosp_last_year.strip()
            or mh_hosp_last_reason.strip()
            or mh_hosp_surgeries.strip()
            or mh_hosp_notes.strip()
        ),
        "Hospitalisations / surgeries",
    )

    mh_data.update(
        dict(
            MH_Hosp_NAD=mh_hosp_nad,
            MH_Hosp_EverAdmitted=mh_hosp_ever,
            MH_Hosp_Number=mh_hosp_number,
            MH_Hosp_LastAdmission_Year=mh_hosp_last_year,
            MH_Hosp_LastAdmission_Reason=mh_hosp_last_reason,
            MH_Hosp_Surgeries_List=mh_hosp_surgeries,
            MH_Hosp_Notes=mh_hosp_notes,
        )
    )

# 08. Transfusions
with st.expander("08. Medical history – transfusions", expanded=False):
    mh_tr_nad = st.checkbox(
        "No history of blood transfusion",
        value=bool(get_prev("MH_Transfusion_NAD", False)),
        key="MH_Transfusion_NAD",
    )

    mh_tr_hist = st.radio(
        "Any blood transfusion in the past?",
        options=["No", "Yes"],
        index=["No", "Yes"].index(get_prev("MH_Transfusion_History", "No")),
        key="MH_Transfusion_History",
        horizontal=True,
    )

    mh_tr_indication = st.text_input(
        "Indication (why transfused?)",
        value=get_prev("MH_Transfusion_Indication", ""),
        key="MH_Transfusion_Indication",
    )

    mh_tr_lastdate = st.text_input(
        "Last transfusion (approx date/year)",
        value=get_prev("MH_Transfusion_LastDate", ""),
        key="MH_Transfusion_LastDate",
    )

    mh_tr_units = st.text_input(
        "Approximate total number of units transfused",
        value=get_prev("MH_Transfusion_NumberUnits_Total", ""),
        key="MH_Transfusion_NumberUnits_Total",
    )

    mh_tr_notes = st.text_area(
        "Additional notes (screening for hepatitis/HIV, reactions, etc.)",
        value=get_prev("MH_Transfusion_Notes", ""),
        key="MH_Transfusion_Notes",
        height=80,
    )

    mh_tr_nad = adjust_nad(
        mh_tr_nad,
        bool(
            mh_tr_hist == "Yes"
            or mh_tr_indication.strip()
            or mh_tr_lastdate.strip()
            or mh_tr_units.strip()
            or mh_tr_notes.strip()
        ),
        "Transfusions",
    )

    mh_data.update(
        dict(
            MH_Transfusion_NAD=mh_tr_nad,
            MH_Transfusion_History=mh_tr_hist,
            MH_Transfusion_Indication=mh_tr_indication,
            MH_Transfusion_LastDate=mh_tr_lastdate,
            MH_Transfusion_NumberUnits_Total=mh_tr_units,
            MH_Transfusion_Notes=mh_tr_notes,
        )
    )

# 09. Allergies / adverse reactions
with st.expander("09. Medical history – allergies / adverse reactions", expanded=False):
    mh_all_nad = st.checkbox(
        "NKDA / no known allergies",
        value=bool(get_prev("MH_Allergy_NAD", False)),
        key="MH_Allergy_NAD",
    )

    mh_all_drug = st.text_area(
        "Drug allergies (drug – reaction – severity)",
        value=get_prev("MH_Allergy_Drug_List", ""),
        key="MH_Allergy_Drug_List",
        height=80,
    )

    mh_all_food = st.text_area(
        "Food allergies",
        value=get_prev("MH_Allergy_Food_List", ""),
        key="MH_Allergy_Food_List",
        height=80,
    )

    mh_all_latex = st.text_input(
        "Latex allergy details (if any)",
        value=get_prev("MH_Allergy_Latex_Details", ""),
        key="MH_Allergy_Latex_Details",
    )

    mh_all_other = st.text_area(
        "Other allergies (contrast dyes, LA, etc.)",
        value=get_prev("MH_Allergy_Other_Details", ""),
        key="MH_Allergy_Other_Details",
        height=80,
    )

    mh_all_severe = st.radio(
        "Any history of severe reaction / anaphylaxis?",
        options=["No", "Yes"],
        index=["No", "Yes"].index(get_prev("MH_Allergy_SevereReactionYN", "No")),
        key="MH_Allergy_SevereReactionYN",
        horizontal=True,
    )

    mh_all_notes = st.text_area(
        "Additional notes",
        value=get_prev("MH_Allergy_Notes", ""),
        key="MH_Allergy_Notes",
        height=80,
    )

    mh_all_nad = adjust_nad(
        mh_all_nad,
        bool(
            mh_all_drug.strip()
            or mh_all_food.strip()
            or mh_all_latex.strip()
            or mh_all_other.strip()
            or mh_all_severe == "Yes"
            or mh_all_notes.strip()
        ),
        "Allergies",
    )

    mh_data.update(
        dict(
            MH_Allergy_NAD=mh_all_nad,
            MH_Allergy_Drug_List=mh_all_drug,
            MH_Allergy_Food_List=mh_all_food,
            MH_Allergy_Latex_Details=mh_all_latex,
            MH_Allergy_Other_Details=mh_all_other,
            MH_Allergy_SevereReactionYN=mh_all_severe,
            MH_Allergy_Notes=mh_all_notes,
        )
    )

# 10. Medications (AI-assisted)
drug_db = load_drug_db()
meds_prev_data = prev_meds_list + [{}] * max(0, 3 - len(prev_meds_list))  # pad to 3

with st.expander("10. Medications (AI-assisted)", expanded=False):
    mh_meds_nad = st.checkbox(
        "Not on any regular medication",
        value=bool(get_prev("MH_Meds_NAD", False)),
        key="MH_Meds_NAD",
    )

    st.caption(
        "For each drug, type the brand or generic name. "
        "The app searches the local drug list and suggests generic name and usual dose."
    )

    meds_records = []
    for i in range(3):  # support 3 meds to start
        st.markdown("---")
        meds_records.append(
            medication_entry_widget(
                key_prefix=f"med_{i+1}",
                drug_db=drug_db,
                prev=meds_prev_data[i] if i < len(meds_prev_data) else {},
            )
        )

    otc_4_6w = st.text_area(
        "Over-the-counter medicines in last 4–6 weeks",
        value=get_prev("MH_Meds_OTC_4to6weeks", ""),
        key="MH_Meds_OTC_4to6weeks",
        height=80,
    )

    col_a, col_b = st.columns(2)
    with col_a:
        mh_anticoag = st.checkbox(
            "On anticoagulant / antiplatelet",
            value=bool(get_prev("MH_Meds_Anticoagulant", False)),
            key="MH_Meds_Anticoagulant",
        )
        mh_steroid = st.checkbox(
            "On systemic steroids",
            value=bool(get_prev("MH_Meds_Steroid", False)),
            key="MH_Meds_Steroid",
        )
        mh_immuno = st.checkbox(
            "On immunosuppressant / biologic",
            value=bool(get_prev("MH_Meds_Immuno", False)),
            key="MH_Meds_Immuno",
        )
    with col_b:
        mh_diab = st.checkbox(
            "On insulin / OHA",
            value=bool(get_prev("MH_Meds_DiabetesRx", False)),
            key="MH_Meds_DiabetesRx",
        )
        mh_antiep = st.checkbox(
            "On antiepileptic",
            value=bool(get_prev("MH_Meds_Antiepileptic", False)),
            key="MH_Meds_Antiepileptic",
        )
        mh_chemo = st.checkbox(
            "On chemo / targeted / hormonal therapy",
            value=bool(get_prev("MH_Meds_Chemo", False)),
            key="MH_Meds_Chemo",
        )

    mh_compliance = st.selectbox(
        "Compliance with medication",
        options=["Unknown", "Good", "Irregular", "Stopped"],
        index=["Unknown", "Good", "Irregular", "Stopped"].index(
            get_prev("MH_Meds_Compliance", "Unknown")
        ),
        key="MH_Meds_Compliance",
    )

    mh_meds_notes = st.text_area(
        "Any other important comments about medication",
        value=get_prev("MH_Meds_Notes", ""),
        key="MH_Meds_Notes",
        height=80,
    )

    any_meds_entered = any(
        rec["DrugNameInput"] or rec["GenericName"] or rec["Dose"] or rec["Strength"]
        for rec in meds_records
    ) or otc_4_6w.strip() or mh_meds_notes.strip()
    mh_meds_nad = adjust_nad(
        mh_meds_nad,
        any_meds_entered,
        "Medications",
    )

    mh_data.update(
        dict(
            MH_Meds_NAD=mh_meds_nad,
            MH_Meds_OTC_4to6weeks=otc_4_6w,
            MH_Meds_Anticoagulant=mh_anticoag,
            MH_Meds_Steroid=mh_steroid,
            MH_Meds_Immuno=mh_immuno,
            MH_Meds_DiabetesRx=mh_diab,
            MH_Meds_Antiepileptic=mh_antiep,
            MH_Meds_Chemo=mh_chemo,
            MH_Meds_Compliance=mh_compliance,
            MH_Meds_Notes=mh_meds_notes,
        )
    )

# 11. Pregnancy (current – females only)
with st.expander("11. Pregnancy (current – females only)", expanded=False):
    mh_preg_applicable = st.radio(
        "Is pregnancy relevant?",
        options=["Not applicable", "Applicable"],
        index=["Not applicable", "Applicable"].index(
            get_prev("MH_Pregnancy_Applicable", "Not applicable")
        ),
        key="MH_Pregnancy_Applicable",
        horizontal=True,
    )

    mh_preg_status = st.selectbox(
        "Current pregnancy status",
        options=[
            "Not pregnant",
            "Pregnant – 1st trimester",
            "Pregnant – 2nd trimester",
            "Pregnant – 3rd trimester",
        ],
        index=[
            "Not pregnant",
            "Pregnant – 1st trimester",
            "Pregnant – 2nd trimester",
            "Pregnant – 3rd trimester",
        ].index(get_prev("MH_Pregnancy_CurrentStatus", "Not pregnant")),
        key="MH_Pregnancy_CurrentStatus",
    )

    mh_preg_weeks = st.text_input(
        "Weeks of gestation (if pregnant)",
        value=get_prev("MH_Pregnancy_WeeksGestation", ""),
        key="MH_Pregnancy_WeeksGestation",
    )

    mh_preg_risk = st.multiselect(
        "High-risk flags (if any)",
        options=[
            "Hypertension",
            "Gestational diabetes",
            "Pre-eclampsia",
            "Bleeding",
            "Other",
        ],
        default=get_prev("MH_Pregnancy_HighRiskFlags", []),
        key="MH_Pregnancy_HighRiskFlags",
    )

    mh_preg_obg = st.text_input(
        "Obstetrician / treating doctor (if any)",
        value=get_prev("MH_Pregnancy_ObstetricianName", ""),
        key="MH_Pregnancy_ObstetricianName",
    )

    mh_preg_notes = st.text_area(
        "Additional pregnancy-related notes",
        value=get_prev("MH_Pregnancy_Notes", ""),
        key="MH_Pregnancy_Notes",
        height=80,
    )

    mh_data.update(
        dict(
            MH_Pregnancy_Applicable=mh_preg_applicable,
            MH_Pregnancy_CurrentStatus=mh_preg_status,
            MH_Pregnancy_WeeksGestation=mh_preg_weeks,
            MH_Pregnancy_HighRiskFlags=mh_preg_risk,
            MH_Pregnancy_ObstetricianName=mh_preg_obg,
            MH_Pregnancy_Notes=mh_preg_notes,
        )
    )

# 12. System-wise checklist – placeholder
with st.expander("12. System-wise disease checklist (placeholder)", expanded=False):
    st.write(
        "Endocrine, cardiovascular, haematological, respiratory, renal, "
        "GI, neuromuscular and other system-wise checklists will be added "
        "here with NAD checkboxes and free-text boxes, mirroring the IEC proforma."
    )
    sys_free_text = st.text_area(
        "Temporary notes for system-wise diseases",
        value=get_prev("MH_Systems_TempNotes", ""),
        key="MH_Systems_TempNotes",
        height=100,
    )
    mh_data["MH_Systems_TempNotes"] = sys_free_text

# --- General examination (IEC level) ---
with st.expander("General examination", expanded=False):
    st.markdown("**General appraisal**")
    mh_data["gen_appraisal"] = st.text_area(
        "Overall general appraisal / impression",
        value=mh_data.get("gen_appraisal", ""),
        help="Mental state & intelligence, build & nutrition, attitude, gait, stature, constitution…"
    )

    st.markdown("**Vital signs**")
    cols_v1 = st.columns(2)
    mh_data["gen_bp"] = cols_v1[0].text_input(
        "Blood pressure (mmHg)",
        value=mh_data.get("gen_bp", ""),
    )
    mh_data["gen_pulse"] = cols_v1[1].text_input(
        "Pulse rate (beats/min)",
        value=mh_data.get("gen_pulse", ""),
    )
    cols_v2 = st.columns(2)
    mh_data["gen_temp"] = cols_v2[0].text_input(
        "Temperature (°C)",
        value=mh_data.get("gen_temp", ""),
    )
    mh_data["gen_rr"] = cols_v2[1].text_input(
        "Respiratory rate (breaths/min)",
        value=mh_data.get("gen_rr", ""),
    )

    st.markdown("**Examination – skin / hair / extremities / face**")
    mh_data["gen_skin"] = st.text_area(
        "Skin",
        value=mh_data.get("gen_skin", ""),
    )
    mh_data["gen_hair"] = st.text_area(
        "Hair",
        value=mh_data.get("gen_hair", ""),
    )
    mh_data["gen_hands_feet"] = st.text_area(
        "Hands, fingers, feet, toes, nails",
        value=mh_data.get("gen_hands_feet", ""),
        help="Describe any clubbing, cyanosis, koilonychia, etc."
    )
    mh_data["gen_face_neck"] = st.text_area(
        "Face & neck (profile, swellings, scars, gland enlargement, tracheal deviation, developmental defects)",
        value=mh_data.get("gen_face_neck", ""),
    )

    st.markdown("**Constitutional features**")
    mh_data["gen_pain"] = st.text_area(
        "Generalised pain, tenderness",
        value=mh_data.get("gen_pain", ""),
    )
    mh_data["gen_oedema"] = st.text_area(
        "Oedema (site, pitting/non-pitting, extent)",
        value=mh_data.get("gen_oedema", ""),
    )

# --- Extra-oral examination (including lymph nodes & TMJ) ---
with st.expander("Extra-oral examination (face, neck, lymph nodes, TMJ)", expanded=False):
    st.markdown("**Face**")
    mh_data["eo_face_profile"] = st.text_input(
        "Facial profile (orthognathic / prognathic / retrognathic)",
        value=mh_data.get("eo_face_profile", ""),
    )
    mh_data["eo_face_positioning"] = st.text_area(
        "Face positioning & symmetry",
        value=mh_data.get("eo_face_positioning", ""),
    )
    mh_data["eo_face_swellings"] = st.text_area(
        "Facial swellings / scars / deformities",
        value=mh_data.get("eo_face_swellings", ""),
    )

    st.markdown("**Neck**")
    mh_data["eo_neck"] = st.text_area(
        "Neck (scars, deviation of trachea, gland enlargement, other findings)",
        value=mh_data.get("eo_neck", ""),
    )

    st.markdown("**Lymph node examination**")
    ln_nad_default = mh_data.get("eo_ln_nad", True)
    eo_ln_nad = st.checkbox("NAD – lymph nodes clinically normal", value=ln_nad_default)
    mh_data["eo_ln_nad"] = eo_ln_nad
    if not eo_ln_nad:
        cols_ln1 = st.columns(2)
        mh_data["eo_ln_site"] = cols_ln1[0].text_input(
            "Site(s)",
            value=mh_data.get("eo_ln_site", ""),
        )
        mh_data["eo_ln_number"] = cols_ln1[1].text_input(
            "Number (solitary / multiple)",
            value=mh_data.get("eo_ln_number", ""),
        )
        cols_ln2 = st.columns(2)
        mh_data["eo_ln_side"] = cols_ln2[0].text_input(
            "Side (unilateral / bilateral)",
            value=mh_data.get("eo_ln_side", ""),
        )
        mh_data["eo_ln_consistency"] = cols_ln2[1].text_input(
            "Consistency (soft / firm / hard / fluctuant)",
            value=mh_data.get("eo_ln_consistency", ""),
        )
        cols_ln3 = st.columns(2)
        mh_data["eo_ln_tender"] = cols_ln3[0].text_input(
            "Tenderness (tender / non-tender)",
            value=mh_data.get("eo_ln_tender", ""),
        )
        mh_data["eo_ln_mobility"] = cols_ln3[1].text_input(
            "Mobility (movable / fixed / matted)",
            value=mh_data.get("eo_ln_mobility", ""),
        )
        mh_data["eo_ln_skin"] = st.text_input(
            "Skin over lymph node",
            value=mh_data.get("eo_ln_skin", ""),
        )
        mh_data["eo_ln_notes"] = st.text_area(
            "Additional lymph node notes",
            value=mh_data.get("eo_ln_notes", ""),
        )

    st.markdown("**TMJ examination**")
    tmj_nad_default = mh_data.get("eo_tmj_nad", True)
    eo_tmj_nad = st.checkbox("NAD – TMJ clinically normal", value=tmj_nad_default)
    mh_data["eo_tmj_nad"] = eo_tmj_nad
    if not eo_tmj_nad:
        mh_data["eo_tmj_inspection"] = st.text_area(
            "Inspection (asymmetry, deviation/deflection, swelling)",
            value=mh_data.get("eo_tmj_inspection", ""),
        )
        mh_data["eo_tmj_palpation"] = st.text_area(
            "Palpation (tenderness, crepitus, intra-/extra-auricular findings, mobility)",
            value=mh_data.get("eo_tmj_palpation", ""),
        )
        mh_data["eo_tmj_auscultation"] = st.text_area(
            "Auscultation (clicks, crepitus – bell-end stethoscope)",
            value=mh_data.get("eo_tmj_auscultation", ""),
        )
        mh_data["eo_tmj_mo"] = st.text_input(
            "Mouth opening (mm)",
            value=mh_data.get("eo_tmj_mo", ""),
        )
        mh_data["eo_tmj_notes"] = st.text_area(
            "Additional TMJ notes",
            value=mh_data.get("eo_tmj_notes", ""),
        )

# --- Intra-oral examination (soft & hard tissues) ---
with st.expander("Intra-oral examination (soft & hard tissue findings)", expanded=False):
    st.markdown("**Soft tissue examination**")
    mh_data["io_lips"] = st.text_area(
        "1. Lips",
        value=mh_data.get("io_lips", ""),
    )
    mh_data["io_buccal_mucosa"] = st.text_area(
        "2. Buccal mucosa & vestibular sulcus",
        value=mh_data.get("io_buccal_mucosa", ""),
    )
    mh_data["io_hard_palate"] = st.text_area(
        "3. Hard palate",
        value=mh_data.get("io_hard_palate", ""),
    )
    mh_data["io_floor_mouth"] = st.text_area(
        "4. Floor of the mouth (inspection + bimanual palpation)",
        value=mh_data.get("io_floor_mouth", ""),
    )
    mh_data["io_soft_palate"] = st.text_area(
        "5. Soft palate & uvula",
        value=mh_data.get("io_soft_palate", ""),
    )
    mh_data["io_tongue"] = st.text_area(
        "6. Tongue (inspection + palpation)",
        value=mh_data.get("io_tongue", ""),
    )
    mh_data["io_gingiva"] = st.text_area(
        "7. Gingiva (colour, contour, consistency, bleeding, pockets, recession)",
        value=mh_data.get("io_gingiva", ""),
    )

    st.markdown("**Hard tissue / teeth**")
    mh_data["io_decay"] = st.text_area(
        "Decay (list teeth / surfaces, DMFT/DMFS if recorded)",
        value=mh_data.get("io_decay", ""),
    )
    mh_data["io_missing"] = st.text_area(
        "Missing teeth",
        value=mh_data.get("io_missing", ""),
    )
    mh_data["io_filled"] = st.text_area(
        "Filled teeth / restorations",
        value=mh_data.get("io_filled", ""),
    )
    mh_data["io_endo"] = st.text_area(
        "Endodontically treated teeth",
        value=mh_data.get("io_endo", ""),
    )
    mh_data["io_prosthesis"] = st.text_area(
        "Fixed / removable prosthesis",
        value=mh_data.get("io_prosthesis", ""),
    )
    mh_data["io_periodontal_status"] = st.text_area(
        "Periodontal status (generalised/localised, severity, indices if any)",
        value=mh_data.get("io_periodontal_status", ""),
    )
    mh_data["io_other_findings"] = st.text_area(
        "Other intra-oral findings (e.g., white/red lesions, pigmentation, tori, etc.)",
        value=mh_data.get("io_other_findings", ""),
    )

# --- Investigations & working diagnosis ---
with st.expander("Investigations & working diagnosis", expanded=False):
    # Investigations ordered / done
    mh_data["inv_investigations"] = st.text_area(
        "Investigations ordered / done (blood tests, imaging, cytology, histopathology, etc.)",
        value=mh_data.get("inv_investigations", ""),
        height=100,
    )

    # Key results
    mh_data["inv_results"] = st.text_area(
        "Key investigation results",
        value=mh_data.get("inv_results", ""),
        height=100,
    )

    st.markdown("**Working diagnosis (up to ~15 items)**")

    # Build a default multiline text from any previously stored 1–5 diagnoses
    prev_dx_lines = []
    for k in ["inv_working_dx1", "inv_working_dx2", "inv_working_dx3",
              "inv_working_dx4", "inv_working_dx5"]:
        val = mh_data.get(k, "")
        if isinstance(val, str) and val.strip():
            prev_dx_lines.append(val.strip())

    default_dx_text = mh_data.get(
        "inv_working_dx_multiline",
        "\n".join(prev_dx_lines) if prev_dx_lines else "",
    )

    inv_working_dx_multiline = st.text_area(
        "List working diagnoses here (one per line; you can easily enter up to 15).",
        value=default_dx_text,
        height=220,
        help="Example:\n"
             "1. Chronic hyperplastic candidiasis – right buccal mucosa\n"
             "2. OSMF – stage II\n"
             "3. Suspected OSCC – retromolar trigone, left\n"
             "...\n"
    )

    # Store the full multiline text
    mh_data["inv_working_dx_multiline"] = inv_working_dx_multiline

    # Also keep the first 15 lines split into individual keys if needed later
    lines = [ln.strip() for ln in inv_working_dx_multiline.splitlines() if ln.strip()]
    for i in range(15):
        key = f"inv_working_dx{i+1}"
        mh_data[key] = lines[i] if i < len(lines) else ""

    # Extra notes / staging
    mh_data["inv_notes"] = st.text_area(
        "Additional notes / differential diagnosis / TNM staging if known",
        value=mh_data.get("inv_notes", ""),
        height=100,
    )


# --------------------------------------------------------------------
# 13. Attachments – prescriptions, hospital records, reports
# --------------------------------------------------------------------
st.markdown("---")
st.subheader("Attachments – prescriptions, hospital records, reports")

docs_for_pt = docs_df[docs_df["ResearchID"] == selected_id]

with st.expander("Capture / upload new document", expanded=False):
    doc_type = st.selectbox(
        "Document type",
        options=[
            "Prescription",
            "Hospital case file / discharge summary",
            "Investigation / lab report",
            "Histopathology report",
            "Imaging report",
            "Other",
        ],
        key="DocType",
    )

    caption = st.text_input(
        "Short caption",
        key="DocCaption",
        placeholder="e.g. 'Oncology prescription – Jan 2025'",
    )

    notes = st.text_area(
        "Notes (optional)",
        key="DocNotes",
        height=80,
    )

    st.markdown("#### Capture image with camera (for prescriptions, records)")
    cam_img = st.camera_input(
        "Use device camera – optional",
        key=f"cam_doc_{selected_id}",
    )

    st.markdown("#### Or upload file (PDF / image)")
    uploaded_file = st.file_uploader(
        "Upload prescription / case sheet / report",
        type=["png", "jpg", "jpeg", "bmp", "gif", "pdf"],
        key="DocUpload",
    )

    if st.button("Save document for this participant"):
        file_obj = cam_img if cam_img is not None else uploaded_file

        if file_obj is None:
            st.error("Please capture an image or upload a file.")
        else:
            existing_ids = docs_for_pt["DocumentID"].tolist()
            new_doc_id = gen_document_id(existing_ids, selected_id)

            suffix = Path(file_obj.name).suffix.lower() or ".jpg"
            safe_fname = f"{selected_id}_{new_doc_id}{suffix}"
            file_path = RESEARCH_DOCS_DIR / safe_fname

            with open(file_path, "wb") as f:
                f.write(file_obj.read())

            now = iso_now()
            new_row = {
                "DocumentID": new_doc_id,
                "ResearchID": selected_id,
                "DocType": doc_type,
                "FileName": safe_fname,
                "FileExt": suffix.lstrip("."),
                "Caption": caption.strip(),
                "Notes": notes.strip(),
                "CreatedAt": now,
            }

            docs_df_new = pd.concat([docs_df, pd.DataFrame([new_row])], ignore_index=True)
            save_table(docs_df_new, "research_documents")

            st.success(f"Saved document as **{new_doc_id}**.")
            st.rerun()

with st.expander("Existing documents for this participant", expanded=True):
    docs_for_pt = load_table("research_documents")
    if not docs_for_pt.empty:
        docs_for_pt = docs_for_pt[docs_for_pt["ResearchID"] == selected_id]

    if docs_for_pt.empty:
        st.info("No documents recorded yet for this participant.")
    else:
        docs_for_pt = docs_for_pt.sort_values("CreatedAt", ascending=False)
        disp = docs_for_pt[["DocumentID", "DocType", "Caption", "FileName", "CreatedAt"]].copy()
        disp.insert(0, "No.", range(1, len(disp) + 1))
        st.dataframe(disp, use_container_width=True)

        st.markdown("#### Thumbnails (image documents)")
        img_exts = (".png", ".jpg", ".jpeg", ".bmp", ".gif")
        img_rows = docs_for_pt[
            docs_for_pt["FileName"].str.lower().str.endswith(img_exts)
        ]

        if img_rows.empty:
            st.caption("No image files to preview.")
        else:
            cols = st.columns(4)
            for idx, (_, row) in enumerate(img_rows.iterrows()):
                col = cols[idx % 4]
                with col:
                    img_path = RESEARCH_DOCS_DIR / row["FileName"]
                    st.image(
                        str(img_path),
                        caption=f"{row['DocumentID']}\n{row['Caption'] or ''}",
                        width=180,
                    )

# --------------------------------------------------------------------
# SAVE BUTTON – medical history + medications
# --------------------------------------------------------------------
st.markdown("---")
if st.button("Save case & medical history for this participant"):

    mh_df = load_table("research_case_history")

    # 🔧 Ensure there is a 'ResearchID' column even when the table is empty
    if mh_df is None or mh_df.empty:
        import pandas as pd  # usually already imported at top
        mh_df = pd.DataFrame(columns=["ResearchID"])
    elif "ResearchID" not in mh_df.columns:
        mh_df["ResearchID"] = pd.Series(dtype=str)

    match = mh_df[mh_df["ResearchID"] == selected_id]


    # Overview already in mh_data
    new_row = {
        "ResearchID": selected_id,
        "MedicalHistoryJSON": json.dumps(mh_data),
        "UpdatedAt": iso_now(),
    }

    if "CreatedAt" not in mh_df.columns:
        mh_df["CreatedAt"] = pd.NaT

    match = mh_df[mh_df["ResearchID"] == selected_id]
    if not match.empty:
        created_val = match.iloc[0].get("CreatedAt", iso_now())
    else:
        created_val = iso_now()
    new_row["CreatedAt"] = created_val

    mh_df = mh_df[mh_df["ResearchID"] != selected_id]
    mh_df = pd.concat([mh_df, pd.DataFrame([new_row])], ignore_index=True)
    save_table(mh_df, "research_med_history")

    # Medications table
    meds_df = meds_df[meds_df["ResearchID"] != selected_id]
    med_rows = []
    idx = 1
    for rec in meds_records:
        if not (
            rec["DrugNameInput"]
            or rec["GenericName"]
            or rec["Dose"]
            or rec["Strength"]
        ):
            continue
        med_rows.append(
            {
                "ResearchID": selected_id,
                "MedIndex": idx,
                **rec,
            }
        )
        idx += 1

    if med_rows:
        meds_df = pd.concat([meds_df, pd.DataFrame(med_rows)], ignore_index=True)

    save_table(meds_df, "research_medications")

    st.success("Case history + medical history (including medications) saved.")
    st.rerun()


