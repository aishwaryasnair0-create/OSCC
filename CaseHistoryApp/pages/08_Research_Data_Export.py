# pages/08_Research_Data_Export.py

import streamlit as st
import pandas as pd
from io import BytesIO
import zipfile

from data_io import load_table, DATA_DIR

from utils.navigation import require_module

require_module("Research")

st.title("08 – Research data export")

# -------------------------------------------------------------------
# Context: mode and active study
# -------------------------------------------------------------------
mode = st.session_state.get("module_mode", "Research")
active_study_id = st.session_state.get("active_study_id")

st.caption(f"Current module: **{mode}**")
if active_study_id:
    st.caption(f"Active study / project: **{active_study_id}**")
else:
    st.caption("Active study / project: **none** (exporting all studies together)")

st.markdown(
    "Use this page to export **all research, sample, and lab data** as CSV files or as a "
    "single ZIP archive that you can analyse in R / Python or share with your data analyst."
)
st.markdown("---")

# -------------------------------------------------------------------
# Load all relevant tables
# -------------------------------------------------------------------
tables = {
    "studies": load_table("studies"),
    "labs": load_table("labs"),
    "investigators": load_table("investigators"),
    "research_participants": load_table("research_participants"),
    "eligibility": load_table("eligibility"),
    "research_consents": load_table("research_consents"),
    "samples": load_table("samples"),
    "rna_extraction_qc": load_table("rna_extraction_qc"),
    "rtqpcr_results": load_table("rtqpcr_results"),
    "bacterial_qpcr": load_table("bacterial_qpcr"),
    "ngs_results": load_table("ngs_results"),
    "risk_results": load_table("risk_results"),
}

# NOTE:
# Right now we are exporting ALL rows. Once every table has a StudyID column,
# you can optionally filter each df by active_study_id here before exporting.


# -------------------------------------------------------------------
# Overview table – which tables exist, row/column counts
# -------------------------------------------------------------------
st.subheader("Table overview")

info_rows = []
for name, df in tables.items():
    info_rows.append(
        {
            "Table": name,
            "n_rows": len(df),
            "n_cols": len(df.columns),
            "Some columns": ", ".join(df.columns[:7]) + (" ..." if len(df.columns) > 7 else ""),
        }
    )

overview_df = pd.DataFrame(info_rows)
overview_df.insert(0, "No.", range(1, len(overview_df) + 1))  # 1-based numbering
st.dataframe(overview_df, use_container_width=True)

st.markdown("---")

# -------------------------------------------------------------------
# Download each table separately as CSV
# -------------------------------------------------------------------
st.subheader("Download individual tables as CSV")

for name, df in tables.items():
    st.markdown(f"**{name}** – {len(df)} rows")

    if len(df) == 0:
        st.caption("No rows in this table yet.")
        continue

    csv_bytes = df.to_csv(index=False).encode("utf-8")
    st.download_button(
        label=f"Download {name}.csv",
        data=csv_bytes,
        file_name=f"{name}.csv",
        mime="text/csv",
        key=f"dl_{name}",
    )

    st.markdown("---")

# -------------------------------------------------------------------
# Download everything together as one ZIP
# -------------------------------------------------------------------
st.subheader("Download all tables together as a ZIP archive")

zip_buffer = BytesIO()
with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
    for name, df in tables.items():
        csv_data = df.to_csv(index=False).encode("utf-8")
        zf.writestr(f"{name}.csv", csv_data)

zip_buffer.seek(0)

st.download_button(
    label="Download all research tables as research_data.zip",
    data=zip_buffer,
    file_name="research_data.zip",
    mime="application/zip",
)
