import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import uuid
import config
from workflow.session import AlignmentSession, ParticipantRecord, SessionManager

st.set_page_config(page_title="Operator Setup", layout="wide")
st.title("Operator Setup — EOP2 Alignment Session")
st.caption("Configure the alignment session before participants join")

st.info(
    "**What this session proves:** Does providing a pre-generated, QC-checked structured "
    "content specification before the EOP2 alignment meeting produce faster alignment "
    "with fewer post-authoring content revision requests?\n\n"
    "**Document archetype:** EOP2 briefing document — **revision-heavy**. Most effort "
    "in current state is in iterative content alignment, not initial drafting. "
    "This session tests whether structured spec-first alignment changes that."
)

col1, col2 = st.columns(2)
with col1:
    sim_mode = st.selectbox(
        "Simulation Mode",
        ["high_quality", "low_quality"],
        help="High quality: content spec is well-formed and QC findings are actionable. "
             "Low quality: spec has issues, many blocking findings, to test whether workflow "
             "still functions and whether participants notice quality difference.",
    )
with col2:
    document_type = st.selectbox("Document Type", ["eop2_briefing"])

st.subheader("Participant Configuration")
st.caption("Add all participants before starting. Each participant reviews the spec in their own session.")

participants = []
roles = ["regulatory_affairs", "medical_writing", "clinical_science", "clinical_operations"]
for role in roles:
    include = st.checkbox(f"Include {role.replace('_', ' ').title()}", value=True, key=f"inc_{role}")
    if include:
        pid = st.text_input(f"Participant ID ({role})", value=f"{role}_p1", key=f"pid_{role}")
        participants.append(ParticipantRecord(participant_id=pid, role=role))

if st.button("Create Session", disabled=not participants):
    session = AlignmentSession(
        session_id=f"t4_{uuid.uuid4().hex[:8]}",
        simulation_mode=sim_mode,
        document_type=document_type,
        content_twin_id="molecule_aleniglipron",
        structure_twin_id="structure_eop2_fda",
        participants=participants,
    )
    config.SIMULATION_MODE = sim_mode
    st.session_state["alignment_session"] = session
    # Clear any prior session artifacts
    for key in ["current_spec", "qc_findings", "qc_complete", "handoff"]:
        st.session_state.pop(key, None)
    SessionManager().save(session)
    st.success(f"Session created: `{session.session_id}` | Mode: {sim_mode} | "
               f"{len(participants)} participants")
    st.info("Navigate to **Spec Review (RA)** to generate and review the content specification.")
