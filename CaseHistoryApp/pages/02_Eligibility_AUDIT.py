# pages/02_Eligibility_AUDIT.py

import streamlit as st
import pandas as pd
from datetime import datetime

from data_io import load_table, save_table
from utils.navigation import require_module

require_module("Research")

st.title("02 – Eligibility / AUDIT")

# -------------------------------------------------------------------
# Load participants
# -------------------------------------------------------------------
participants = load_table(
    "research_participants",
    columns=["ResearchID", "Name", "Age", "Sex", "Group", "Cohort", "CreatedAt"],
)

if participants.empty:
    st.error("No research participants found. Please create one first.")
    st.stop()

# -------------------------------------------------------------------
# Eligibility table (filtered to existing participants only)
# -------------------------------------------------------------------
elig_cols = [
    "ResearchID",
    "Group",
    "Cohort",
    "AUDIT_Q1",
    "AUDIT_Q2",
    "AUDIT_Q3",
    "AUDIT_Q4",
    "AUDIT_Q5",
    "AUDIT_Q6",
    "AUDIT_Q7",
    "AUDIT_Q8",
    "AUDIT_Q9",
    "AUDIT_Q10",
    "AUDIT_Total",
    "AUDIT_Risk",
    "AUDIT_AlcoholAbuseFlag",
    "Inc_Case_OSCCConfirmed",
    "Inc_Case_Age18Plus",
    "Inc_Case_AnyStage",
    "Inc_Case_Consent",
    "Inc_Case_SalivaAdequate",
    "Exc_Case_OtherMalignancy",
    "Exc_Case_PriorMalignancyTreatment",
    "Exc_Case_MetastaticOralLesion",
    "Exc_Case_Pregnancy",
    "Exc_Case_SubstanceAbuseNonAlcohol",
    "Inc_Ctrl_NoMalignancy",
    "Inc_Ctrl_Age18Plus",
    "Inc_Ctrl_Consent",
    "Inc_Ctrl_SalivaAdequate",
    "Exc_Ctrl_HistoryMalignancy",
    "Exc_Ctrl_Pregnancy",
    "Exc_Ctrl_SubstanceAbuseNonAlcohol",
    "OverallEligible",
    "IneligibilityReason",
    "UpdatedAt",
]

elig_df = load_table("eligibility", columns=elig_cols)
if elig_df is None:
    elig_df = pd.DataFrame(columns=elig_cols)

# Keep only rows for participants that still exist
if not elig_df.empty and "ResearchID" in elig_df.columns:
    valid_ids = set(participants["ResearchID"])
    elig_df = elig_df[elig_df["ResearchID"].isin(valid_ids)]


def get_existing_row(df: pd.DataFrame, research_id: str):
    sub = df[df["ResearchID"] == research_id]
    if sub.empty:
        return None
    return sub.iloc[0]


def get_bool(existing, col, default=False):
    if existing is None:
        return default
    if col not in existing.index:
        return default
    val = existing[col]
    if pd.isna(val):
        return default
    return bool(val)


def get_int(existing, col, default=0):
    if existing is None or col not in existing.index:
        return default
    val = existing[col]
    if pd.isna(val):
        return default
    try:
        return int(val)
    except Exception:
        return default


# -------------------------------------------------------------------
# AUDIT constants
# -------------------------------------------------------------------
AUDIT_EXCLUSION_THRESHOLD = 15  # > 15 => alcohol abuse flag

AUDIT_QUESTIONS = [
    {
        "id": "Q1",
        "text": "Q1. How often do you have a drink containing alcohol?",
        "options": [
            ("Never", 0),
            ("Monthly or less", 1),
            ("2–4 times a month", 2),
            ("2–3 times a week", 3),
            ("4 or more times a week", 4),
        ],
    },
    {
        "id": "Q2",
        "text": "Q2. How many drinks containing alcohol do you have on a typical day when you are drinking?",
        "options": [
            ("1–2", 0),
            ("3–4", 1),
            ("5–6", 2),
            ("7–9", 3),
            ("10 or more", 4),
        ],
    },
    {
        "id": "Q3",
        "text": "Q3. How often do you have six or more drinks on one occasion?",
        "options": [
            ("Never", 0),
            ("Less than monthly", 1),
            ("Monthly", 2),
            ("Weekly", 3),
            ("Daily or almost daily", 4),
        ],
    },
    {
        "id": "Q4",
        "text": "Q4. How often during the last year have you found that you were not able to stop drinking once you had started?",
        "options": [
            ("Never", 0),
            ("Less than monthly", 1),
            ("Monthly", 2),
            ("Weekly", 3),
            ("Daily or almost daily", 4),
        ],
    },
    {
        "id": "Q5",
        "text": "Q5. How often during the last year have you failed to do what was normally expected of you because of drinking?",
        "options": [
            ("Never", 0),
            ("Less than monthly", 1),
            ("Monthly", 2),
            ("Weekly", 3),
            ("Daily or almost daily", 4),
        ],
    },
    {
        "id": "Q6",
        "text": "Q6. How often during the last year have you needed a first drink in the morning to get yourself going after a heavy drinking session?",
        "options": [
            ("Never", 0),
            ("Less than monthly", 1),
            ("Monthly", 2),
            ("Weekly", 3),
            ("Daily or almost daily", 4),
        ],
    },
    {
        "id": "Q7",
        "text": "Q7. How often during the last year have you had a feeling of guilt or remorse after drinking?",
        "options": [
            ("Never", 0),
            ("Less than monthly", 1),
            ("Monthly", 2),
            ("Weekly", 3),
            ("Daily or almost daily", 4),
        ],
    },
    {
        "id": "Q8",
        "text": "Q8. How often during the last year have you been unable to remember what happened the night before because of your drinking?",
        "options": [
            ("Never", 0),
            ("Less than monthly", 1),
            ("Monthly", 2),
            ("Weekly", 3),
            ("Daily or almost daily", 4),
        ],
    },
    {
        "id": "Q9",
        "text": "Q9. Have you or someone else been injured because of your drinking?",
        "options": [
            ("No", 0),
            ("Yes, but not in the last year", 2),
            ("Yes, during the last year", 4),
        ],
    },
    {
        "id": "Q10",
        "text": "Q10. Has a relative, friend, doctor or other health worker been concerned about your drinking or suggested you cut down?",
        "options": [
            ("No", 0),
            ("Yes, but not in the last year", 2),
            ("Yes, during the last year", 4),
        ],
    },
]

# -------------------------------------------------------------------
# Participant selector (single, clean version)
# -------------------------------------------------------------------
st.subheader("Select participant")

options = []
for _, row in participants.iterrows():
    rid = row["ResearchID"]
    label = f"{rid} – {row['Name']} (Group: {row['Group']}, Cohort: {row['Cohort']})"
    options.append((label, rid))

labels = [o[0] for o in options]
ids = [o[1] for o in options]

# Default index from session_state["active_research_id"], if present
active_id = st.session_state.get("active_research_id")
default_idx = 0
if active_id in ids:
    default_idx = ids.index(active_id)

selected_idx = st.selectbox(
    "Choose participant",
    options=list(range(len(options))),
    index=default_idx,
    format_func=lambda i: labels[i],
    key="eligibility_participant_select",
)

selected_id = ids[selected_idx]
st.session_state["active_research_id"] = selected_id  # keep in sync

pt_row = participants[participants["ResearchID"] == selected_id].iloc[0]
group = pt_row["Group"]
cohort = pt_row["Cohort"]

st.info(
    f"**{selected_id}** – {pt_row['Name']} "
    f"(Age {pt_row['Age']}, Sex {pt_row['Sex']}, Group: {group}, Cohort: {cohort})"
)

existing = get_existing_row(elig_df, selected_id)

st.markdown("---")
st.subheader("Eligibility and AUDIT for this participant")

col_left, col_right = st.columns(2)

# -------------------------------------------------------------------
# LEFT: Inclusion / Exclusion checklists (protocol-based)
# -------------------------------------------------------------------
with col_left:
    if group == "Case":
        st.markdown("### Inclusion criteria – Cases (IEC protocol)")

        inc_case_oscc = st.checkbox(
            "Confirmed OSCC on histopathology and **no prior anticancer therapy**",
            value=get_bool(existing, "Inc_Case_OSCCConfirmed", True),
        )
        inc_case_age = st.checkbox(
            "Age ≥ 18 years",
            value=get_bool(existing, "Inc_Case_Age18Plus", True),
        )
        inc_case_any_stage = st.checkbox(
            "Any stage of OSCC (Stage I–IV) is acceptable",
            value=get_bool(existing, "Inc_Case_AnyStage", True),
        )
        inc_case_consent = st.checkbox(
            "Understands the study and **provides informed consent**",
            value=get_bool(existing, "Inc_Case_Consent", True),
        )
        inc_case_saliva = st.checkbox(
            "Able to provide adequate saliva sample for analysis",
            value=get_bool(existing, "Inc_Case_SalivaAdequate", True),
        )

        st.markdown("### Exclusion criteria – Cases")

        exc_case_other_malig = st.checkbox(
            "Diagnosis of malignancy other than OSCC / prior malignancy",
            value=get_bool(existing, "Exc_Case_OtherMalignancy", False),
        )
        exc_case_prior_treatment = st.checkbox(
            "Previously diagnosed with / treated for any malignancy",
            value=get_bool(existing, "Exc_Case_PriorMalignancyTreatment", False),
        )
        exc_case_metastatic = st.checkbox(
            "Metastatic lesions in the oral cavity",
            value=get_bool(existing, "Exc_Case_MetastaticOralLesion", False),
        )
        exc_case_preg = st.checkbox(
            "Pregnant (pregnancy may influence salivary miRNA levels)",
            value=get_bool(existing, "Exc_Case_Pregnancy", False),
        )
        exc_case_substance = st.checkbox(
            "History of substance abuse (illegal drugs / OTC misuse) – **excluding alcohol, which is based on AUDIT**",
            value=get_bool(existing, "Exc_Case_SubstanceAbuseNonAlcohol", False),
        )

        # For Controls, set placeholders
        inc_ctrl_no_malig = False
        inc_ctrl_age = False
        inc_ctrl_consent = False
        inc_ctrl_saliva = False
        exc_ctrl_hist_malig = False
        exc_ctrl_preg = False
        exc_ctrl_subst = False

    else:  # Control
        st.markdown("### Inclusion criteria – Controls (IEC protocol)")

        inc_ctrl_no_malig = st.checkbox(
            "No history of OSCC or any other malignancy",
            value=get_bool(existing, "Inc_Ctrl_NoMalignancy", True),
        )
        inc_ctrl_age = st.checkbox(
            "Age ≥ 18 years",
            value=get_bool(existing, "Inc_Ctrl_Age18Plus", True),
        )
        inc_ctrl_consent = st.checkbox(
            "Understands the study and **provides informed consent**",
            value=get_bool(existing, "Inc_Ctrl_Consent", True),
        )
        inc_ctrl_saliva = st.checkbox(
            "Able to provide adequate saliva sample for analysis",
            value=get_bool(existing, "Inc_Ctrl_SalivaAdequate", True),
        )

        st.markdown("### Exclusion criteria – Controls")

        exc_ctrl_hist_malig = st.checkbox(
            "Any history of malignancy",
            value=get_bool(existing, "Exc_Ctrl_HistoryMalignancy", False),
        )
        exc_ctrl_preg = st.checkbox(
            "Pregnant (pregnancy may influence salivary miRNA levels)",
            value=get_bool(existing, "Exc_Ctrl_Pregnancy", False),
        )
        exc_ctrl_subst = st.checkbox(
            "History of substance abuse (illegal drugs / OTC misuse) – **excluding alcohol, which is based on AUDIT**",
            value=get_bool(existing, "Exc_Ctrl_SubstanceAbuseNonAlcohol", False),
        )

        # For Cases, set placeholders
        inc_case_oscc = False
        inc_case_age = False
        inc_case_any_stage = False
        inc_case_consent = False
        inc_case_saliva = False
        exc_case_other_malig = False
        exc_case_prior_treatment = False
        exc_case_metastatic = False
        exc_case_preg = False
        exc_case_substance = False

# -------------------------------------------------------------------
# RIGHT: AUDIT questionnaire
# -------------------------------------------------------------------
with col_right:
    st.markdown("### AUDIT alcohol questionnaire")

    st.caption(
        "Each question is scored 0–4 (except Q9–Q10 which are 0/2/4). "
        "The app will calculate the total and decide eligibility based on the IEC rule."
    )

    audit_scores = {}
    for q in AUDIT_QUESTIONS:
        qid = q["id"]
        colname = f"AUDIT_{qid}"
        existing_score = get_int(existing, colname, 0)

        # default option index by matching score
        default_index = 0
        for i, (_label, score) in enumerate(q["options"]):
            if score == existing_score:
                default_index = i
                break

        opt_indices = list(range(len(q["options"])))

        selected_index = st.selectbox(
            q["text"],
            options=opt_indices,
            index=default_index,
            format_func=lambda i, q=q: f"{q['options'][i][1]} – {q['options'][i][0]}",
            key=f"audit_{qid}_{selected_id}",
        )

        audit_scores[qid] = q["options"][selected_index][1]

    audit_total = sum(audit_scores.values())

    # Risk category (typical AUDIT zones)
    if audit_total <= 7:
        audit_risk = "Zone I – Low risk"
    elif audit_total <= 15:
        audit_risk = "Zone II – Hazardous use"
    elif audit_total <= 19:
        audit_risk = "Zone III – Harmful use"
    else:
        audit_risk = "Zone IV – Possible dependence"

    alcohol_abuse_flag = audit_total > AUDIT_EXCLUSION_THRESHOLD

    st.markdown(
        f"**AUDIT total score: {audit_total}**  \n"
        f"Risk category: **{audit_risk}**"
    )
    st.caption(
        f"Current IEC rule implemented here: if **AUDIT total > {AUDIT_EXCLUSION_THRESHOLD}**, "
        "participant is flagged as having alcohol abuse and is **ineligible**."
    )

# -------------------------------------------------------------------
# Compute overall eligibility
# -------------------------------------------------------------------
reason_parts = []

if group == "Case":
    inc_ok = all(
        [
            inc_case_oscc,
            inc_case_age,
            inc_case_any_stage,
            inc_case_consent,
            inc_case_saliva,
        ]
    )
    if not inc_case_oscc:
        reason_parts.append("Inclusion (cases): OSCC not confirmed / prior therapy present.")
    if not inc_case_age:
        reason_parts.append("Inclusion: age < 18.")
    if not inc_case_any_stage:
        reason_parts.append("Inclusion: OSCC stage not acceptable.")
    if not inc_case_consent:
        reason_parts.append("Inclusion: consent not obtained.")
    if not inc_case_saliva:
        reason_parts.append("Inclusion: inadequate saliva sample.")

    exc_any = any(
        [
            exc_case_other_malig,
            exc_case_prior_treatment,
            exc_case_metastatic,
            exc_case_preg,
            exc_case_substance,
            alcohol_abuse_flag,
        ]
    )
    if exc_case_other_malig:
        reason_parts.append("Exclusion: malignancy other than OSCC / prior malignancy.")
    if exc_case_prior_treatment:
        reason_parts.append("Exclusion: previously treated for malignancy.")
    if exc_case_metastatic:
        reason_parts.append("Exclusion: metastatic oral lesion.")
    if exc_case_preg:
        reason_parts.append("Exclusion: pregnancy.")
    if exc_case_substance:
        reason_parts.append("Exclusion: substance abuse (non-alcohol).")
else:  # Control
    inc_ok = all(
        [
            inc_ctrl_no_malig,
            inc_ctrl_age,
            inc_ctrl_consent,
            inc_ctrl_saliva,
        ]
    )
    if not inc_ctrl_no_malig:
        reason_parts.append("Inclusion (controls): history of malignancy present.")
    if not inc_ctrl_age:
        reason_parts.append("Inclusion: age < 18.")
    if not inc_ctrl_consent:
        reason_parts.append("Inclusion: consent not obtained.")
    if not inc_ctrl_saliva:
        reason_parts.append("Inclusion: inadequate saliva sample.")

    exc_any = any(
        [
            exc_ctrl_hist_malig,
            exc_ctrl_preg,
            exc_ctrl_subst,
            alcohol_abuse_flag,
        ]
    )
    if exc_ctrl_hist_malig:
        reason_parts.append("Exclusion: any history of malignancy.")
    if exc_ctrl_preg:
        reason_parts.append("Exclusion: pregnancy.")
    if exc_ctrl_subst:
        reason_parts.append("Exclusion: substance abuse (non-alcohol).")

if alcohol_abuse_flag:
    reason_parts.append(
        f"Exclusion: alcohol abuse – AUDIT total {audit_total} > {AUDIT_EXCLUSION_THRESHOLD}."
    )

overall_eligible = bool(inc_ok and not exc_any)
if not reason_parts and overall_eligible:
    reason_text = ""
else:
    reason_text = "; ".join(reason_parts)

st.markdown("---")
if overall_eligible:
    st.success("Eligibility result: **ELIGIBLE** for this study.")
else:
    st.error("Eligibility result: **INELIGIBLE** for this study.")
    if reason_text:
        st.write("Reason(s):")
        st.markdown(f"- {reason_text.replace('; ', '\\n- ')}")

# -------------------------------------------------------------------
# Save button
# -------------------------------------------------------------------
if st.button("Save eligibility and AUDIT for this participant"):
    new_row = {
        "ResearchID": selected_id,
        "Group": group,
        "Cohort": cohort,
        "AUDIT_Q1": audit_scores["Q1"],
        "AUDIT_Q2": audit_scores["Q2"],
        "AUDIT_Q3": audit_scores["Q3"],
        "AUDIT_Q4": audit_scores["Q4"],
        "AUDIT_Q5": audit_scores["Q5"],
        "AUDIT_Q6": audit_scores["Q6"],
        "AUDIT_Q7": audit_scores["Q7"],
        "AUDIT_Q8": audit_scores["Q8"],
        "AUDIT_Q9": audit_scores["Q9"],
        "AUDIT_Q10": audit_scores["Q10"],
        "AUDIT_Total": audit_total,
        "AUDIT_Risk": audit_risk,
        "AUDIT_AlcoholAbuseFlag": alcohol_abuse_flag,
        "Inc_Case_OSCCConfirmed": inc_case_oscc,
        "Inc_Case_Age18Plus": inc_case_age,
        "Inc_Case_AnyStage": inc_case_any_stage,
        "Inc_Case_Consent": inc_case_consent,
        "Inc_Case_SalivaAdequate": inc_case_saliva,
        "Exc_Case_OtherMalignancy": exc_case_other_malig,
        "Exc_Case_PriorMalignancyTreatment": exc_case_prior_treatment,
        "Exc_Case_MetastaticOralLesion": exc_case_metastatic,
        "Exc_Case_Pregnancy": exc_case_preg,
        "Exc_Case_SubstanceAbuseNonAlcohol": exc_case_substance,
        "Inc_Ctrl_NoMalignancy": inc_ctrl_no_malig,
        "Inc_Ctrl_Age18Plus": inc_ctrl_age,
        "Inc_Ctrl_Consent": inc_ctrl_consent,
        "Inc_Ctrl_SalivaAdequate": inc_ctrl_saliva,
        "Exc_Ctrl_HistoryMalignancy": exc_ctrl_hist_malig,
        "Exc_Ctrl_Pregnancy": exc_ctrl_preg,
        "Exc_Ctrl_SubstanceAbuseNonAlcohol": exc_ctrl_subst,
        "OverallEligible": overall_eligible,
        "IneligibilityReason": reason_text,
        "UpdatedAt": datetime.now().isoformat(timespec="seconds"),
    }

    # Upsert into eligibility table
    elig_df = elig_df[elig_df["ResearchID"] != selected_id]
    elig_df = pd.concat([elig_df, pd.DataFrame([new_row])], ignore_index=True)
    save_table(elig_df, "eligibility")

    st.success("Eligibility and AUDIT details saved.")
    st.rerun()

# -------------------------------------------------------------------
# Overview table with numbering
# -------------------------------------------------------------------
st.markdown("---")
st.subheader("Eligibility overview (all participants)")

elig_df = load_table("eligibility", columns=elig_cols)  # reload after save

if elig_df.empty:
    st.info("No eligibility records saved yet.")
else:
    display_df = elig_df.copy()
    display_df.insert(0, "No.", range(1, len(display_df) + 1))  # 1-based numbering
    st.dataframe(display_df, use_container_width=True)
