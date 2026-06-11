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

st.caption(
    "**Blocking** findings must be resolved (regenerate / edit the claim) before locking. "
    "**Major** findings do not block the lock but must be **acknowledged** — e.g. \"values "
    "pending Phase 3, accepted for now.\" **Minor** findings are informational."
)

if st.button("Run QC Checklist"):
    findings = LabelingQCValidator().validate(message_map)
    st.session_state["qc_findings"] = findings
    st.session_state["qc_acknowledged"] = set()   # reset on a fresh run
    st.session_state["qc_flagged"] = set()
    message_map.qc_passed = not any(f.severity == "blocking" for f in findings)
    st.session_state["message_map"] = message_map
    SessionManager().save(session)

findings = st.session_state.get("qc_findings")
ack = st.session_state.setdefault("qc_acknowledged", set())
flagged = st.session_state.setdefault("qc_flagged", set())

if findings is not None:
    blocking = [f for f in findings if f.severity == "blocking"]
    major = [f for f in findings if f.severity == "major"]
    if not findings:
        st.success("All QC checks passed. Ready to lock.")
    else:
        if blocking:
            st.error(f"{len(blocking)} blocking finding(s) — must be resolved before locking.")
        if major:
            unack = [f for f in major if f.finding_id not in ack]
            st.warning(f"{len(major)} major finding(s) — {len(unack)} still to acknowledge.")

    for finding in findings:
        sev_color = {"blocking": "red", "major": "orange", "minor": "blue"}.get(finding.severity, "gray")
        is_ack = finding.finding_id in ack
        is_flag = finding.finding_id in flagged
        badge = "  ✅ acknowledged" if is_ack else ("  🚩 flagged for team" if is_flag else "")
        st.markdown(f":{sev_color}[**{finding.severity.upper()}**] `{finding.category}` "
                    f"— §{finding.section_id} ({finding.finding_id}){badge}")
        st.write(finding.description)
        if finding.suggested_resolution:
            st.caption(f"Resolution: {finding.suggested_resolution}")

        # Inline actions
        if finding.severity == "major":
            b1, b2, _ = st.columns([1, 1, 4])
            if b1.button("Acknowledge & proceed", key=f"ack_{finding.finding_id}"):
                ack.add(finding.finding_id); flagged.discard(finding.finding_id); st.rerun()
            if b2.button("Flag for team", key=f"flag_{finding.finding_id}"):
                flagged.add(finding.finding_id); ack.discard(finding.finding_id); st.rerun()
        elif finding.severity == "blocking":
            b1, _ = st.columns([1, 5])
            if b1.button("Flag for team", key=f"flag_{finding.finding_id}"):
                flagged.add(finding.finding_id); st.rerun()
            st.caption("Blocking findings cannot be acknowledged away — resolve by regenerating "
                       "the map (high-quality mode) or editing the claim, then re-run QC.")
        st.divider()

    unack_major = [f for f in major if f.finding_id not in ack]
    if blocking:
        st.error("Resolve the blocking finding(s) and re-run QC before locking.")
    elif unack_major:
        st.info(f"Acknowledge the {len(unack_major)} remaining major finding(s) above to proceed.")
    else:
        if st.button("QC Complete — Lock Message Map →", type="primary"):
            session.phase = "locked"
            SessionManager().save(session)
        st.page_link("pages/5_Message_Map_Lock.py", label="Next: Message Map Lock →", icon="➡️")
