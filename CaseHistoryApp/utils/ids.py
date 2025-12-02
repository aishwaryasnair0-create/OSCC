# utils/ids.py
from typing import Iterable
import re


def generate_research_id(group: str, cohort: str, existing_ids: Iterable[str]) -> str:
    """
    Generate new ResearchID like:
    - PILOT-CA-001 for Pilot Case
    - PILOT-CO-001 for Pilot Control
    - MAIN-CA-001 for Main Case
    - MAIN-CO-001 for Main Control
    """
    group = (group or "").strip().lower()
    cohort = (cohort or "").strip().lower()

    if "case" in group:
        gcode = "CA"
    else:
        gcode = "CO"

    if "pilot" in cohort:
        ccode = "PILOT"
    else:
        ccode = "MAIN"

    prefix = f"{ccode}-{gcode}-"

    nums = []
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    for rid in existing_ids:
        if isinstance(rid, str):
            m = pattern.match(rid)
            if m:
                try:
                    nums.append(int(m.group(1)))
                except ValueError:
                    pass

    next_num = max(nums) + 1 if nums else 1
    return f"{prefix}{next_num:03d}"


def generate_sample_id(research_id: str, sample_type: str) -> str:
    """
    Build SampleID by appending sample type.
    Example: research_id = 'PILOT-CA-001', sample_type = 'WS' -> 'PILOT-CA-001_WS'
    """
    research_id = (research_id or "").strip()
    sample_type = (sample_type or "").strip().upper()
    return f"{research_id}_{sample_type}"


def generate_incremental_id(existing_ids: Iterable[str], prefix: str = "ID") -> str:
    """
    Simple incremental numeric ID with prefix, e.g. CLIN-001.
    """
    nums = []
    pattern = re.compile(rf"^{re.escape(prefix)}-(\d+)$")
    for vid in existing_ids:
        if isinstance(vid, str):
            m = pattern.match(vid)
            if m:
                try:
                    nums.append(int(m.group(1)))
                except ValueError:
                    pass
    next_num = max(nums) + 1 if nums else 1
    return f"{prefix}-{next_num:03d}"
