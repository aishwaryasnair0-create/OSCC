# utils/navigation.py

import streamlit as st

def require_module(required: str):
    """
    Enforce that this page is only usable in a given module.

    required: "Research", "Clinic", or "Lab"

    If the current module_mode (set on the 'Study and Mode' page)
    does not match, show a short info message and stop the page.
    """
    current = st.session_state.get("module_mode", "Research")

    if current != required:
        st.info(
            f"This page belongs to the **{required}** module.\n\n"
            "Please go to **Study and Mode** and switch the module to "
            f"`{required}` to use it."
        )
        st.stop()
