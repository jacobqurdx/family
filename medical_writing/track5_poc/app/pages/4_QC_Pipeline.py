import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
from labeling.labeling_qc import LabelingQCValidator
from workflow.session import SessionManager
from workflow.ui import render_stepper

st.set_page_config(page_title="QC Pipeline", layout="wide")
render_stepper(active_step=4)
st.title("QC Pipeline — Labeling Checklist")
st.caption("Automated QC checks against standing labeling rules before locking")

if "labeling_session" not in st.session_state or "message_map" not in st.session_state:
    st.warning("No active session or message map.")
    st.stop()

session = st.session_state["labeling_session"]
message_map = st.session_state["message_map"]

st.subheader("Labeling-Specific QC Checks")
st.caption(
    "Five standing rules run automatically. These encode lessons from prior FDA label "
    "negotiations and class-specific requirements that must always be satisfied. Mandatory "
    "class claims (thyroid C-cell warning, BMI threshold) must be present AND grounded in "
    "competitive precedent."
)

if st.button("Run QC Checklist"):
    findings = LabelingQCValidator().validate(message_map)
    st.session_state["qc_findings"] = findings
    message_map.qc_passed = not any(f.severity == "blocking" for f in findings)
    st.session_state["message_map"] = message_map
    SessionManager().save(session)

findings = st.session_state.get("qc_findings")
if findings is not None:
    blocking = [f for f in findings if f.severity == "blocking"]
    major = [f for f in findings if f.severity == "major"]
    if not findings:
        st.success("All QC checks passed. Ready to lock.")
    else:
        if blocking:
            st.error(f"{len(blocking)} blocking finding(s) — must be resolved before locking.")
        if major:
            st.warning(f"{len(major)} major finding(s) — review recommended.")

    for finding in findings:
        sev_color = {"blocking": "red", "major": "orange", "minor": "blue"}.get(finding.severity, "gray")
        st.markdown(f":{sev_color}[**{finding.severity.upper()}**] `{finding.category}` "
                    f"— §{finding.section_id} ({finding.finding_id})")
        st.write(finding.description)
        if finding.suggested_resolution:
            st.caption(f"Resolution: {finding.suggested_resolution}")

    if not blocking:
        if st.button("QC Complete — Lock Message Map →", type="primary"):
            session.phase = "locked"
            SessionManager().save(session)
        st.page_link("pages/5_Message_Map_Lock.py", label="Next: Message Map Lock →", icon="➡️")
