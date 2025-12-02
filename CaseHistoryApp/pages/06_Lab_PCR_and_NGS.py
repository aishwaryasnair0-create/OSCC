# pages/06_Lab_PCR_and_NGS.py

import streamlit as st
import pandas as pd
from datetime import datetime, date

from data_io import load_table, save_table

# --------------------------------------------------------------------
# Allow this page in both Research and Lab modules (not Clinic)
# --------------------------------------------------------------------
mode = st.session_state.get("module_mode", "Research")
if mode not in ("Research", "Lab"):
    st.info(
        "This page is available only in the **Research** or **Lab** module.\n\n"
        "Please go to **Study and Mode** and switch the module to Research or Lab."
    )
    st.stop()

st.title("06 – Lab: Chain of custody, RNA QC, 16S and miRNA/NGS")

active_study = st.session_state.get("active_study_id", None)
st.info(
    f"Current study: **{active_study or 'None'}** – "
    "lab data entry applies to samples recorded via the research module."
)

# --------------------------------------------------------------------
# Helper for dates: auto-today, but keeps existing value if present
# --------------------------------------------------------------------
def get_default_date(value) -> date:
    """Return a sensible default date for date_input."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return datetime.today().date()
    try:
        # stored as ISO string usually
        return datetime.fromisoformat(str(value)).date()
    except Exception:
        return datetime.today().date()

# --------------------------------------------------------------------
# Load participants and samples
# --------------------------------------------------------------------
participants = load_table(
    "research_participants",
    columns=["ResearchID", "Name", "Age", "Sex", "Group", "Cohort"],
)

samples_all = st.session_state.get("research_samples_cache")
if samples_all is None:
    samples_all = load_table("research_samples")

if samples_all is None or len(samples_all) == 0:
    st.error(
        "No research samples found. Complete sample collection "
        "& chain-of-custody first (page 05)."
    )
    st.stop()

samples = samples_all.copy()
if participants is not None and not participants.empty:
    valid_ids = set(participants["ResearchID"])
    samples = samples[samples["ResearchID"].isin(valid_ids)].copy()

if samples.empty:
    st.error(
        "Samples exist, but none match current research participants.\n\n"
        "Please check that ResearchID values are consistent between pages."
    )
    st.stop()

# --------------------------------------------------------------------
# Sample selector
# --------------------------------------------------------------------
def make_sample_label(row: pd.Series) -> str:
    rid = row.get("ResearchID", "")
    sid = row.get("SampleID", "")
    stype = row.get("SampleType", "")
    cohort = row.get("Cohort", "")
    t = row.get("CollectionStart", "")
    t_str = str(t)[:19] if pd.notna(t) else ""
    return f"{sid} – {rid} – {stype} ({cohort}) {t_str}"


if "CollectionStart" in samples.columns:
    samples = samples.sort_values("CollectionStart", ascending=False)

samples = samples.reset_index(drop=True)
samples["Label"] = samples.apply(make_sample_label, axis=1)

sample_labels = samples["Label"].tolist()
sample_ids = samples["SampleID"].tolist()

st.subheader("Select sample")

selected_idx = st.selectbox(
    "Sample (SampleID – ResearchID – SampleType (Cohort) – Collection time)",
    options=list(range(len(sample_labels))),
    format_func=lambda i: sample_labels[i],
    key="lab_sample_select",
)

selected_sample_id = sample_ids[selected_idx]
sample_row = samples.loc[selected_idx]
selected_research_id = sample_row["ResearchID"]
selected_sample_type = sample_row.get("SampleType", "")
selected_cohort = sample_row.get("Cohort", "")

is_pilot_sample = (
    isinstance(selected_cohort, str)
    and selected_cohort.upper().startswith("PILOT")
)

st.success(
    f"Selected sample **{selected_sample_id}** "
    f"for participant **{selected_research_id}** "
    f"(Sample type: {selected_sample_type}, Cohort: {selected_cohort})."
)

with st.expander(
    "📋 Sample details (from collection / chain-of-custody page)", expanded=False
):
    st.write(sample_row)

# --------------------------------------------------------------------
# Load / prepare lab results table
# --------------------------------------------------------------------
lab_cols = [
    "ResearchID",
    "SampleID",
    "SampleType",
    "Cohort",
    # Lab chain of custody (lab side)
    "ReceivedAtMicroLab",
    "PlacedInMinus80_Micro",
    "RemovedFromMinus80_ForExternal",
    "LoadedIntoCryocan_ForExternal",
    "ArrivedExternalLab",
    "PlacedInMinus80_External",
    "RemovedFromMinus80_ForProcessing",
    # RNA extraction & QC
    "RNA_ExtractionDate",
    "RNA_ExtractionKit",
    "RNA_InputVolume_uL",
    "RNA_ElutionVolume_uL",
    "RNA_SpikeIn_Used_YN",
    "RNA_SpikeIn_Details",
    "RNA_TotalConc_ng_per_uL",
    "RNA_A260_280",
    "RNA_A260_230",
    "RNA_SmallRNA_Conc",
    "RNA_SmallRNA_Percent",
    "RNA_Bioanalyzer_Report",
    "RNA_QC_Notes",
    # Total bacterial load (16S qPCR)
    "DNA_ExtractionDate",
    "DNA_ExtractionKit",
    "DNA_InputVolume_uL",
    "DNA_ElutionVolume_uL",
    "Bact16S_qPCR_MeanCq",
    "Bact16S_StdCurve_ID",
    "Bact16S_Copies_per_mL",
    "Bact16S_RunDate",
    "Bact16S_Notes",
    # miRNA / NGS generic
    "AssayType",
    "AssayName",
    "LabName",
    "RunDate",
    "ResultSummary",
    "CtValuesOrMetrics",
    "ReportFileName",
    # Flags / metadata
    "IsPilotSample",
    "UpdatedAt",
]

lab_df = load_table("research_lab_pcr_ngs", columns=lab_cols)
if lab_df is None:
    lab_df = pd.DataFrame(columns=lab_cols)

for col in lab_cols:
    if col not in lab_df.columns:
        lab_df[col] = pd.Series(dtype="object")

existing_rows = lab_df[lab_df["SampleID"] == selected_sample_id]
if not existing_rows.empty:
    st.info("Existing lab record found – saving will **overwrite** that record.")
    existing = existing_rows.iloc[0]
else:
    existing = pd.Series({col: None for col in lab_cols})

# --------------------------------------------------------------------
# Helper: small timestamp display + “Record time” button
# --------------------------------------------------------------------
def render_ts_field(field: str, label: str, help_text: str = "") -> str:
    """
    One line with:
      - a small read-only time box
      - 'Record time' button: fill with current date+time

    Returns the current value as a string.
    """
    widget_key = f"lab_ts_{selected_sample_id}_{field}"

    # Initialise from existing saved value only once
    if widget_key not in st.session_state:
        st.session_state[widget_key] = existing.get(field) or ""

    st.markdown(f"**{label}**")
    if help_text:
        st.caption(help_text)

    col_ts, col_btn = st.columns([3, 1])

    with col_ts:
        st.text_input("", key=widget_key, disabled=True)

    def _record_now(k=widget_key):
        st.session_state[k] = datetime.now().strftime("%Y-%m-%d %H:%M")

    with col_btn:
        st.button(
            "Record time",
            key=f"{widget_key}_record",
            on_click=_record_now,
        )

    return st.session_state[widget_key]

# --------------------------------------------------------------------
# A. Lab chain of custody (lab side) – COLLAPSIBLE
# --------------------------------------------------------------------
st.markdown("---")
with st.expander("🧊 A. Lab chain of custody (lab side)", expanded=True):

    recv_micro = render_ts_field(
        "ReceivedAtMicroLab",
        "Received at microbiology / molecular lab (date & time)",
    )

    placed_m80_micro = render_ts_field(
        "PlacedInMinus80_Micro",
        "Placed in −80 °C freezer (first lab) – date & time",
    )

    removed_m80_external = render_ts_field(
        "RemovedFromMinus80_ForExternal",
        "Removed from −80 °C for external transport – date & time",
    )

    loaded_cryocan = render_ts_field(
        "LoadedIntoCryocan_ForExternal",
        "Loaded into Cryocan / dry ice container – date & time",
    )

    arrived_ext = render_ts_field(
        "ArrivedExternalLab",
        "Arrived at external molecular lab – date & time",
    )

    placed_m80_ext = render_ts_field(
        "PlacedInMinus80_External",
        "Placed in −80 °C freezer (external lab) – date & time",
    )

    removed_m80_proc = render_ts_field(
        "RemovedFromMinus80_ForProcessing",
        "Removed from −80 °C for processing – date & time",
    )

    st.caption(
        "Tap **Record time** when each step happens. "
        "Time will be filled automatically."
    )

# --------------------------------------------------------------------
# B–D: RNA QC, 16S, miRNA/NGS – inside one form, each section collapsible
# --------------------------------------------------------------------
with st.form("lab_result_form"):

    # ===========================
    # B. RNA extraction & QC
    # ===========================
    with st.expander("🧬 B. RNA extraction and QC", expanded=False):

        c1, c2 = st.columns(2)
        with c1:
            rna_extr_date = st.date_input(
                "RNA extraction date",
                value=get_default_date(existing.get("RNA_ExtractionDate")),
                key="rna_extraction_date",
            )
            rna_extr_kit = st.text_input(
                "RNA extraction kit / method",
                value=existing.get("RNA_ExtractionKit") or "",
            )
            spike_options = ["", "Yes", "No"]
            spike_raw = existing.get("RNA_SpikeIn_Used_YN")
            if pd.isna(spike_raw) or spike_raw not in spike_options:
                spike_raw = ""
            spike_index = spike_options.index(spike_raw)
            rna_spike_used = st.selectbox(
                "Spike-in miRNA added before extraction?",
                spike_options,
                index=spike_index,
            )
            rna_spike_details = st.text_input(
                "Spike-in details (e.g. cel-miR-39-3p, lot, amount)",
                value=existing.get("RNA_SpikeIn_Details") or "",
            )

        with c2:
            rna_input_vol = st.number_input(
                "Input volume (µL)",
                min_value=0.0,
                value=float(existing.get("RNA_InputVolume_uL") or 0.0),
                step=10.0,
            )
            rna_elution_vol = st.number_input(
                "Elution volume (µL)",
                min_value=0.0,
                value=float(existing.get("RNA_ElutionVolume_uL") or 0.0),
                step=10.0,
            )
            rna_total_conc = st.number_input(
                "Total RNA conc. (ng/µL, Qubit)",
                min_value=0.0,
                value=float(existing.get("RNA_TotalConc_ng_per_uL") or 0.0),
                step=0.1,
            )

        c3, c4 = st.columns(2)
        with c3:
            rna_a260_280 = st.number_input(
                "A260/280 ratio",
                min_value=0.0,
                value=float(existing.get("RNA_A260_280") or 0.0),
                step=0.01,
            )
            rna_small_conc = st.number_input(
                "Small-RNA conc. (ng/µL)",
                min_value=0.0,
                value=float(existing.get("RNA_SmallRNA_Conc") or 0.0),
                step=0.1,
            )
        with c4:
            rna_a260_230 = st.number_input(
                "A260/230 ratio",
                min_value=0.0,
                value=float(existing.get("RNA_A260_230") or 0.0),
                step=0.01,
            )
            rna_small_pct = st.number_input(
                "Percent in miRNA size range (%)",
                min_value=0.0,
                max_value=100.0,
                value=float(existing.get("RNA_SmallRNA_Percent") or 0.0),
                step=1.0,
            )

        rna_bio_report = st.text_input(
            "Bioanalyzer/TapeStation report ID / filename",
            value=existing.get("RNA_Bioanalyzer_Report") or "",
        )
        rna_qc_notes = st.text_area(
            "RNA QC notes",
            value=existing.get("RNA_QC_Notes") or "",
            height=80,
        )

    # ===========================
    # C. Total bacterial load (16S qPCR)
    # ===========================
    with st.expander("🦠 C. Total bacterial load (16S qPCR)", expanded=False):

        c5, c6 = st.columns(2)
        with c5:
            dna_extr_date = st.date_input(
                "DNA extraction date",
                value=get_default_date(existing.get("DNA_ExtractionDate")),
                key="dna_extraction_date",
            )
            dna_extr_kit = st.text_input(
                "DNA extraction kit / method",
                value=existing.get("DNA_ExtractionKit") or "",
            )
            bact_run_date = st.date_input(
                "16S qPCR run date",
                value=get_default_date(existing.get("Bact16S_RunDate")),
                key="bact_run_date",
            )
        with c6:
            dna_input_vol = st.number_input(
                "DNA extraction input volume (µL)",
                min_value=0.0,
                value=float(existing.get("DNA_InputVolume_uL") or 0.0),
                step=10.0,
            )
            dna_elution_vol = st.number_input(
                "DNA elution volume (µL)",
                min_value=0.0,
                value=float(existing.get("DNA_ElutionVolume_uL") or 0.0),
                step=10.0,
            )
            bact_mean_cq = st.number_input(
                "16S qPCR mean Cq",
                min_value=0.0,
                value=float(existing.get("Bact16S_qPCR_MeanCq") or 0.0),
                step=0.1,
            )

        c7, c8 = st.columns(2)
        with c7:
            bact_stdcurve_id = st.text_input(
                "16S standard curve ID / reference",
                value=existing.get("Bact16S_StdCurve_ID") or "",
            )
        with c8:
            bact_copies_ml = st.number_input(
                "Total bacterial load (16S copies/mL)",
                min_value=0.0,
                value=float(existing.get("Bact16S_Copies_per_mL") or 0.0),
                step=1.0,
            )

        bact_notes = st.text_area(
            "Bacterial load notes",
            value=existing.get("Bact16S_Notes") or "",
            height=80,
        )

    # ===========================
    # D. miRNA / NGS result
    # ===========================
    with st.expander("🧪 D. miRNA / NGS result", expanded=False):

        assay_type_options = ["PCR", "qPCR", "RT-qPCR", "NGS", "Panel", "Other"]
        existing_assay_type = existing.get("AssayType")
        if existing_assay_type in assay_type_options:
            default_assay_type = existing_assay_type
        else:
            default_assay_type = "PCR"

        c9, c10 = st.columns(2)
        with c9:
            assay_type = st.selectbox(
                "Assay type",
                assay_type_options,
                index=assay_type_options.index(default_assay_type),
            )
            assay_name = st.text_input(
                "Assay / panel name",
                value=existing.get("AssayName") or "",
                help=(
                    "e.g. 'OSCC miRNA panel v1', 'Pilot RT-qPCR panel', "
                    "'Targeted NGS of 16 miRNAs'."
                ),
            )
        with c10:
            default_lab = st.session_state.get("active_lab_name", "")
            lab_name = st.text_input(
                "Performing lab name",
                value=existing.get("LabName") or default_lab,
            )
            run_date = st.date_input(
                "Run date (miRNA / NGS)",
                value=get_default_date(existing.get("RunDate")),
                key="mirna_run_date",
            )

        result_summary = st.text_area(
            "Result summary / interpretation",
            value=existing.get("ResultSummary") or "",
            height=120,
        )

        ct_values = st.text_area(
            "Ct values / key metrics (free text, paste if needed)",
            value=existing.get("CtValuesOrMetrics") or "",
            height=120,
        )

        report_file = st.file_uploader(
            "Attach lab report (PDF / image, optional – only filename is stored)",
            type=["pdf", "png", "jpg", "jpeg"],
        )

    # This is the submit button the earlier warning complained about
    submitted = st.form_submit_button("Save / update lab data for this sample")

# --------------------------------------------------------------------
# Save lab result when form is submitted
# --------------------------------------------------------------------
if submitted:
    report_name = report_file.name if report_file is not None else existing.get(
        "ReportFileName"
    )

    new_row = {
        "ResearchID": selected_research_id,
        "SampleID": selected_sample_id,
        "SampleType": selected_sample_type,
        "Cohort": selected_cohort,
        # Chain of custody (lab side)
        "ReceivedAtMicroLab": recv_micro,
        "PlacedInMinus80_Micro": placed_m80_micro,
        "RemovedFromMinus80_ForExternal": removed_m80_external,
        "LoadedIntoCryocan_ForExternal": loaded_cryocan,
        "ArrivedExternalLab": arrived_ext,
        "PlacedInMinus80_External": placed_m80_ext,
        "RemovedFromMinus80_ForProcessing": removed_m80_proc,
        # RNA QC
        "RNA_ExtractionDate": rna_extr_date.isoformat(),
        "RNA_ExtractionKit": rna_extr_kit,
        "RNA_InputVolume_uL": rna_input_vol,
        "RNA_ElutionVolume_uL": rna_elution_vol,
        "RNA_SpikeIn_Used_YN": rna_spike_used,
        "RNA_SpikeIn_Details": rna_spike_details,
        "RNA_TotalConc_ng_per_uL": rna_total_conc,
        "RNA_A260_280": rna_a260_280,
        "RNA_A260_230": rna_a260_230,
        "RNA_SmallRNA_Conc": rna_small_conc,
        "RNA_SmallRNA_Percent": rna_small_pct,
        "RNA_Bioanalyzer_Report": rna_bio_report,
        "RNA_QC_Notes": rna_qc_notes,
        # 16S qPCR
        "DNA_ExtractionDate": dna_extr_date.isoformat(),
        "DNA_ExtractionKit": dna_extr_kit,
        "DNA_InputVolume_uL": dna_input_vol,
        "DNA_ElutionVolume_uL": dna_elution_vol,
        "Bact16S_qPCR_MeanCq": bact_mean_cq,
        "Bact16S_StdCurve_ID": bact_stdcurve_id,
        "Bact16S_Copies_per_mL": bact_copies_ml,
        "Bact16S_RunDate": bact_run_date.isoformat(),
        "Bact16S_Notes": bact_notes,
        # miRNA / NGS
        "AssayType": assay_type,
        "AssayName": assay_name,
        "LabName": lab_name,
        "RunDate": run_date.isoformat(),
        "ResultSummary": result_summary,
        "CtValuesOrMetrics": ct_values,
        "ReportFileName": report_name,
        # Metadata
        "IsPilotSample": "Yes" if is_pilot_sample else "No",
        "UpdatedAt": datetime.now().isoformat(timespec="seconds"),
    }

    lab_df = lab_df[lab_df["SampleID"] != selected_sample_id]
    lab_df = pd.concat([lab_df, pd.DataFrame([new_row])], ignore_index=True)
    save_table(lab_df, "research_lab_pcr_ngs")

    st.success("Lab data saved / updated for this sample.")
    st.rerun()

# --------------------------------------------------------------------
# Overview of lab results
# --------------------------------------------------------------------
st.markdown("---")
st.subheader("Overview of lab results (all samples)")

lab_df = load_table("research_lab_pcr_ngs", columns=lab_cols)
if lab_df is None or lab_df.empty:
    st.info("No lab results saved yet.")
else:
    display_df = lab_df.copy()
    display_df.insert(0, "No.", range(1, len(display_df) + 1))
    st.dataframe(display_df, use_container_width=True)
