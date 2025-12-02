# pages/01_Research_Participants.py

import streamlit as st
import pandas as pd
from datetime import datetime

from data_io import load_table, save_table
from utils.navigation import require_module

require_module("Research")

st.title("01 – Research Participants")

# --------------------------------------------------------------------
# Context: mode and active study
# --------------------------------------------------------------------
mode = st.session_state.get("module_mode", "Research")
active_study_id = st.session_state.get("active_study_id")

st.caption(f"Current module: **{mode}**")
if active_study_id:
    st.caption(f"Active study / project: **{active_study_id}**")
else:
    st.caption("Active study / project: **none**")

st.markdown("---")

# --------------------------------------------------------------------
# Load base tables
# --------------------------------------------------------------------
participants = load_table(
    "research_participants",
    columns=[
        "ResearchID",
        "Name",
        "Age",
        "Sex",
        "Phone",
        "Group",
        "Cohort",
        "CreatedAt",
    ],
)

samples = load_table("research_samples")
lab_df = load_table("lab_pcr_ngs")
# if your case history table has another name, change it here
case_hist = load_table("research_case_history")

# --------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------
def iso_now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def generate_research_id(group: str, cohort: str, existing_ids: list[str]) -> str:
    """
    OSCC study naming convention.

    Cases:
      OSCC_PilotCA-001 .. OSCC_PilotCA-015
      then OSCC_MainCA-016 .. OSCC_MainCA-071

    Controls:
      OSCC_PilotCO-001 .. OSCC_PilotCO-015
      then OSCC_MainCO-016 .. OSCC_MainCO-071

    Logic:
      - Study code is taken from active_study_id (e.g. 'OSCC_THESIS' -> 'OSCC').
      - 'Pilot' vs 'Main' comes from the Cohort field.
      - Counters are separate for CA and CO, and run sequentially across
        both Pilot + Main within that group.
    """
    # Group code
    grp_code = "CA" if group == "Case" else "CO"

    # Derive base study code: 'OSCC_THESIS' -> 'OSCC'
    if active_study_id:
        study_code = str(active_study_id).split("_")[0]
    else:
        study_code = "STUDY"

    # Cohort tag
    if isinstance(cohort, str) and cohort.upper().startswith("PILOT"):
        cohort_tag = "Pilot"
    else:
        cohort_tag = "Main"

    # Find existing numbers for this study + group (CA or CO)
    nums: list[int] = []
    study_prefix = f"{study_code}_"
    group_fragment = f"{grp_code}-"

    for rid in existing_ids:
        if not isinstance(rid, str):
            continue
        # only consider IDs for this study and group
        if not rid.startswith(study_prefix):
            continue
        if group_fragment not in rid:
            continue
        try:
            n = int(rid.split("-")[-1])
            nums.append(n)
        except ValueError:
            continue

    next_num = max(nums) + 1 if nums else 1

    # Build final ID
    return f"{study_code}_{cohort_tag}{grp_code}-{next_num:03d}"



def compute_status(research_id: str):
    """
    Compute a simple pipeline status for a participant.

    Stages (we pick the furthest):
      - Registered only
      - History taken
      - Samples collected
      - In deep freezer
      - In lab / analysis
    """

    has_history = False
    if not case_hist.empty and "ResearchID" in case_hist.columns:
        has_history = research_id in case_hist["ResearchID"].astype(str).values

    has_samples = False
    in_deep_freezer = False
    sample_ids = []

    if not samples.empty and "ResearchID" in samples.columns:
        sm = samples[samples["ResearchID"] == research_id]
        if not sm.empty:
            has_samples = True
            sample_ids = sm["SampleID"].astype(str).tolist()
            if "Lab_ReceivedYN" in sm.columns:
                in_deep_freezer = bool(sm["Lab_ReceivedYN"].fillna(False).any())

    in_lab = False
    if sample_ids and not lab_df.empty and "SampleID" in lab_df.columns:
        in_lab = lab_df["SampleID"].astype(str).isin(sample_ids).any()

    # Decide main status label
    if in_lab:
        main = "In lab / analysis"
    elif in_deep_freezer:
        main = "In deep freezer"
    elif has_history:
        main = "History taken"
    elif has_samples:
        main = "Samples collected"
    else:
        main = "Registered only"

    # Detail string for display
    flags = []
    flags.append("History ✓" if has_history else "History –")
    flags.append("Samples ✓" if has_samples else "Samples –")
    flags.append("Deep freezer ✓" if in_deep_freezer else "Deep freezer –")
    flags.append("Lab ✓" if in_lab else "Lab –")

    detail = " | ".join(flags)
    return main, detail


def render_participant_card(row):
    """One row with EDIT / DELETE buttons + status."""
    rid = row["ResearchID"]
    name = row.get("Name", "")
    age = row.get("Age", "")
    cohort = row.get("Cohort", "")
    created = row.get("CreatedAt", "")

    main_status, detail_status = compute_status(rid)

    st.markdown(f"**{rid}** – {name} (Age {age}, Cohort {cohort})")
    st.caption(f"Status: **{main_status}**  \n{detail_status}")

    c1, c2 = st.columns(2)
    with c1:
        if st.button("Edit", key=f"edit_{rid}"):
            st.session_state["active_research_id"] = rid
            st.success(
                f"Now working on **{rid}**. "
                "Use the sidebar to go to Eligibility, Consent, Case History, Samples, Lab, etc."
            )
    with c2:
        if st.button("Delete", key=f"delete_{rid}"):
            # mark this ID for deletion confirmation
            st.session_state["delete_candidate"] = rid

    if created:
        st.caption(f"Created at: {created}")

    st.markdown("---")


# --------------------------------------------------------------------
# Add new participant – plus button + compact form
# --------------------------------------------------------------------
if "show_add_participant" not in st.session_state:
    st.session_state["show_add_participant"] = False

top_c1, top_c2 = st.columns([4, 1])
with top_c1:
    st.subheader("Add new research participant")
with top_c2:
    if st.button("➕ New", key="btn_toggle_add_participant"):
        st.session_state["show_add_participant"] = not st.session_state[
            "show_add_participant"
        ]

if st.session_state["show_add_participant"]:
    with st.form("add_participant_form"):
        name = st.text_input("Name / code", "")

        c1, c2 = st.columns(2)
        with c1:
            age = st.number_input(
                "Age", min_value=0, max_value=120, value=40, step=1
            )
        with c2:
            sex = st.selectbox("Sex", ["Female", "Male", "Other"])

        c3, c4 = st.columns(2)
        with c3:
            group = st.selectbox("Group", ["Case", "Control"])
        with c4:
            cohort = st.selectbox(
                "Cohort",
                ["PILOT", "MAIN", "OTHER"],
                help="PILOT = initial pilot; MAIN = later cohorts.",
            )

        phone = st.text_input("Phone (optional)", "")

        create_btn = st.form_submit_button("Create ResearchID")

    if create_btn:
        if not name.strip():
            st.error("Name is required.")
        else:
            existing_ids = (
                participants["ResearchID"].tolist()
                if not participants.empty
                else []
            )

            new_id = generate_research_id(group, cohort, existing_ids)

            new_row = {
                "ResearchID": new_id,
                "Name": name.strip(),
                "Age": int(age),
                "Sex": sex,
                "Phone": phone.strip(),
                "Group": group,
                "Cohort": cohort,
                "CreatedAt": iso_now(),
            }

            # Append or create table
            if participants.empty:
                participants = pd.DataFrame([new_row])
            else:
                participants = pd.concat(
                    [participants, pd.DataFrame([new_row])],
                    ignore_index=True,
                )

            # Save to disk
            save_table(participants, "research_participants")

            # Set new participant as active and hide form
            st.session_state["active_research_id"] = new_id
            st.session_state["show_add_participant"] = False

            # Auto-go to Eligibility / AUDIT if supported
            if hasattr(st, "switch_page"):
                st.switch_page("pages/02_Eligibility_AUDIT.py")
            else:
                st.success(f"Created research participant: **{new_id}**")
                st.rerun()

st.markdown("---")

# --------------------------------------------------------------------
# Registered participants – Cases and Controls side-by-side
# --------------------------------------------------------------------
st.subheader("Registered participants")

if participants.empty:
    st.info("No research participants added yet.")
else:
    df = participants.copy()

    # Sort by CreatedAt (newest first)
    if "CreatedAt" in df.columns:
        df["_CreatedAt_dt"] = pd.to_datetime(df["CreatedAt"], errors="coerce")
        df = df.sort_values("_CreatedAt_dt", ascending=False)
    else:
        df = df.sort_values("ResearchID", ascending=False)

    # Global search across ID + name
    search_text = st.text_input(
        "Search by ResearchID or name",
        key="participants_search",
        placeholder="Type part of ID or name (works even with 100+ participants).",
    )

    if search_text.strip():
        s = search_text.strip()
        df = df[
            df["ResearchID"].astype(str).str.contains(s, case=False, na=False)
            | df["Name"].astype(str).str.contains(s, case=False, na=False)
        ]

    cases = df[df["Group"] == "Case"]
    controls = df[df["Group"] == "Control"]

    col_cases, col_controls = st.columns(2)

    with col_cases:
        st.markdown(f"### Cases ({len(cases)})")
        if cases.empty:
            st.caption("No cases.")
        else:
            for _, row in cases.iterrows():
                render_participant_card(row)

    with col_controls:
        st.markdown(f"### Controls ({len(controls)})")
        if controls.empty:
            st.caption("No controls.")
        else:
            for _, row in controls.iterrows():
                render_participant_card(row)

# --------------------------------------------------------------------
# Deletion confirmation (centralised, to avoid accidents)
# --------------------------------------------------------------------
delete_candidate = st.session_state.get("delete_candidate")

if delete_candidate:
    st.error(f"Delete participant **{delete_candidate}**? This cannot be undone.")
    c1, c2, c3 = st.columns(3)

    with c1:
        if st.button("✅ Confirm delete", key="btn_confirm_delete"):
            rid = delete_candidate

            # 1) Delete from main participants table
            if participants is not None and not participants.empty and "ResearchID" in participants.columns:
                participants = participants[participants["ResearchID"] != rid]
                save_table(participants, "research_participants")

            # 2) Cascade delete in all other research tables that store ResearchID
            related_tables = [
                "research_eligibility",
                "research_consent",
                "research_samples",
                "research_case_history",
                "research_lab_pcr_ngs",
                "research_panel_risk",
            ]

            for tbl in related_tables:
                try:
                    df = load_table(tbl)
                except Exception:
                    df = None

                if df is not None and not df.empty and "ResearchID" in df.columns:
                    df = df[df["ResearchID"] != rid]
                    save_table(df, tbl)

            # Clear session state for this participant
            if st.session_state.get("active_research_id") == rid:
                st.session_state["active_research_id"] = None
            st.session_state["delete_candidate"] = None

            st.success(f"Participant {rid} and all related records deleted.")
            st.rerun()

    with c2:
        if st.button("❌ Cancel", key="btn_cancel_delete"):
            st.session_state["delete_candidate"] = None
            st.info("Deletion cancelled.")
            st.rerun()

    with c3:
        st.write("")  # spacer


# --------------------------------------------------------------------
# Next button – go to Eligibility / AUDIT
# --------------------------------------------------------------------
st.markdown("---")
active_id = st.session_state.get("active_research_id")

if not active_id:
    st.info(
        "Select or create a participant above; then the **Next** button to Eligibility/AUDIT will be enabled."
    )
else:
    if st.button("Next: Eligibility / AUDIT ➜", key="btn_next_to_eligibility"):
        if hasattr(st, "switch_page"):
            st.switch_page("pages/02_Eligibility_AUDIT.py")
        else:
            st.warning(
                "Please open **02 – Eligibility AUDIT** from the sidebar – "
                "the current participant is already selected."
            )
