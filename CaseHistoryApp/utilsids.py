import re
from typing import Iterable


def generate_research_id(group: str, cohort: str, existing_ids: Iterable[str]) -> str:
    """
    Generate a new ResearchID like:
    - PILOT-CA-001 for Pilot Case
    - PILOT-CO-001 for Pilot Control
    - MAIN-CA-001 for Main Case
    - MAIN-CO-001 for Main Control
    """
    group = group.strip().lower()
    cohort = cohort.strip().lower()

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
    pattern = re.compile(rf"^{prefix}(\d+)$")
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
    return f"{research_id}_{sample_type}"
