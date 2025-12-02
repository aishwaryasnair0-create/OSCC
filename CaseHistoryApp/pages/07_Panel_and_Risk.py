import streamlit as st
import pandas as pd
from datetime import datetime
from pathlib import Path

from data_io import load_table, save_table, DATA_DIR

from utils.navigation import require_module

require_module("Research")

st.title("07 – Panel and OSCC Risk Assessment")

# ---------- Load core tables ----------
participants = load_table(
    "research_participants",
    columns=["ResearchID", "Name", "Age", "Sex", "Phone", "Group", "Cohort", "CreatedAt"],
)
samples = load_table(
    "samples",
    columns=[
        "SampleID",
        "ResearchID",
        "SampleType",
        "Cohort",
        "CollectionStart",
        "CollectionEnd",
        "PlacedInCryocan",
        "VolumeML",
        "VisibleBlood",
        "Discomfort",
        "Notes",
    ],
)
rtqpcr_df = load_table("rtqpcr_results")  # from lab page (miRNA RT-qPCR)

# Risk assessment table
risk_cols = [
    "ResearchID",
    "SampleID",
    "Cohort",
    "PanelName",
    "RiskToolName",
    "RiskToolVersion",
    "RiskDateTime",
    "RiskScore",
    "RiskCategory",
    "RiskThreshold",
    "RiskNotes",
    "RiskReportFile",
    "PanelInputFile",
]
risk_df = load_table("risk_results", columns=risk_cols)

risk_dir = DATA_DIR / "risk_reports"
risk_dir.mkdir(exist_ok=True)

if participants.empty:
    st.error("No research participants yet. Add some in page 01.")
    st.stop()

# ---------- Select participant ----------
research_ids = participants["ResearchID"].tolist()
selected_id = st.selectbox("Select ResearchID", research_ids)

p = participants.loc[participants["ResearchID"] == selected_id].iloc[0]
st.write(
    f"**{selected_id}** – {p['Name']} (Age {p['Age']}, {p['Sex']}) – "
    f"Group: {p['Group']}, Cohort: {p['Cohort']}"
)

# Available samples for this participant
samp_for_pt = samples[samples["ResearchID"] == selected_id]
if samp_for_pt.empty:
    st.warning("No samples recorded yet for this participant (see Samples Chain of Custody page).")
else:
    st.markdown("**Samples for this participant:**")
    st.dataframe(
        samp_for_pt[
            ["SampleID", "SampleType", "CollectionStart", "CollectionEnd", "PlacedInCryocan"]
        ],
        use_container_width=True,
    )

# Shared sample selector
sample_options = ["(not linked)"]
sample_map = {"(not linked)": ""}
for _, r in samp_for_pt.iterrows():
    label = f"{r['SampleID']} [{r['SampleType']}]"
    sample_options.append(label)
    sample_map[label] = r["SampleID"]

st.markdown("---")

# ---------- Quick link to risk tool ----------
st.subheader("Open OSCC miRNA risk tool")

st.markdown(
    """
Use the link below to open the **OSCC risk calculator** (your existing Streamlit app)
in a new tab. Enter the panel miRNA values there, obtain the risk score/category, and
then come back to this page to record the result for audit/logbook.

**Risk tool link:**

👉 [Open OSCC risk tool in new tab](https://oralcancerrisk.streamlit.app/)
""",
    unsafe_allow_html=True,
)

st.markdown("---")
st.subheader("Record risk result for this participant")

# Pre-fill panel name from RT-qPCR if available
default_panel = ""

if ("ResearchID" in rtqpcr_df.columns) and ("PanelName" in rtqpcr_df.columns):
    rt_for_pt = rtqpcr_df[rtqpcr_df["ResearchID"] == selected_id]
    if not rt_for_pt.empty:
        # If there is exactly one RT-qPCR record, use its panel name as default
        unique_panels = rt_for_pt["PanelName"].dropna().unique()
        if len(unique_panels) == 1:
            default_panel = unique_panels[0]
        # else: leave default_panel as empty string so you can type it yourself
else:
    # rtqpcr_results file exists but has old/other structure; ignore for defaults
    rt_for_pt = pd.DataFrame()


# Existing risk records for this participant
existing_risk = risk_df[risk_df["ResearchID"] == selected_id]
if not existing_risk.empty:
    st.caption("Existing risk assessments for this participant:")
    st.dataframe(existing_risk, use_container_width=True)

# ---------- Risk entry form ----------
with st.form("risk_form"):
    sel_sample_label = st.selectbox(
        "Sample used for risk assessment (matrix that panel is based on)",
        sample_options,
    )
    sel_sample_id = sample_map[sel_sample_label]

    panel_name = st.text_input(
        "Panel name / signature used",
        value=default_panel,
        help="e.g., 'GSE45238 miRNA panel', 'Pilot 13-miRNA diagnostic panel'.",
    )

    risk_tool_name = st.text_input(
        "Risk tool name",
        value="OSCC miRNA risk tool (Streamlit)",
    )

    risk_tool_version = st.text_input(
        "Risk tool version / alias",
        value="v1",
        help="Use this if you update the model later (e.g. v1, v2, calibrated-2026, etc.).",
    )

    # numeric risk score (probability, log-odds, etc. – you decide)
    risk_score = st.number_input(
        "Risk score / probability from tool",
        value=0.0,
        step=0.01,
        help="Enter the main numeric output from the tool (e.g. predicted probability of OSCC).",
    )

    risk_category = st.selectbox(
        "Risk category from tool",
        ["Not set", "Low", "Intermediate", "High", "Very high", "Other"],
    )

    risk_threshold = st.text_input(
        "Threshold(s) or cut-off(s) used (optional)",
        value="",
        help="Example: 'High risk if score ≥ 0.75, intermediate 0.4–0.75, low < 0.4'.",
    )

    risk_notes = st.text_area(
        "Notes / interpretation (optional)",
        help="Any comments on how you interpreted this result, or anything special about the sample.",
    )

    risk_report_file = st.file_uploader(
        "Upload risk report or screenshot (PDF / image, optional)",
        type=["pdf", "png", "jpg", "jpeg"],
        key="risk_report",
    )

    panel_input_file = st.file_uploader(
        "Upload panel input file used in tool (optional, CSV/TSV/Excel)",
        type=["csv", "tsv", "xls", "xlsx"],
        key="panel_input",
        help="Optional: a small file with the exact miRNA values you fed into the tool.",
    )

    submitted = st.form_submit_button("Save risk result")

if submitted:
    # Save files
    risk_report_name = ""
    if risk_report_file is not None:
        risk_report_name = f"{selected_id}_{sel_sample_id or 'NOSAMPLE'}_risk_report_{risk_report_file.name}"
        with open(risk_dir / risk_report_name, "wb") as out:
            out.write(risk_report_file.read())

    panel_input_name = ""
    if panel_input_file is not None:
        panel_input_name = f"{selected_id}_{sel_sample_id or 'NOSAMPLE'}_panel_input_{panel_input_file.name}"
        with open(risk_dir / panel_input_name, "wb") as out:
            out.write(panel_input_file.read())

    new_row = {
        "ResearchID": selected_id,
        "SampleID": sel_sample_id,
        "Cohort": p["Cohort"],
        "PanelName": panel_name.strip(),
        "RiskToolName": risk_tool_name.strip(),
        "RiskToolVersion": risk_tool_version.strip(),
        "RiskDateTime": datetime.now().isoformat(timespec="seconds"),
        "RiskScore": float(risk_score),
        "RiskCategory": risk_category,
        "RiskThreshold": risk_threshold.strip(),
        "RiskNotes": risk_notes.strip(),
        "RiskReportFile": risk_report_name,
        "PanelInputFile": panel_input_name,
    }

    # We allow multiple risk assessments per participant; just append
    risk_df = pd.concat([risk_df, pd.DataFrame([new_row])], ignore_index=True)
    save_table(risk_df, "risk_results")

    st.success("Risk result saved for this participant.")
    st.experimental_rerun()
