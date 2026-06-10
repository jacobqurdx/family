import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import uuid
import config
from labeling.labeling_models import LabelingSession
from workflow.session import SessionManager

st.set_page_config(page_title="Operator Setup", layout="wide")
st.title("Operator Setup — Labeling Workflow Session")
st.caption("Configure the message map generation session before the reviewer begins")

st.info(
    "**What this session proves:** Does providing a pre-generated, CI-grounded message map "
    "enable a regulatory affairs reviewer to reach a locked label strategy faster and with "
    "greater confidence than the current manual approach?\n\n"
    "**Document focus:** Company Core Data Sheet (CCDS) — narrow, high-stakes label document. "
    "The bottleneck is not writing the CCDS. The bottleneck is synthesizing competitive "
    "intelligence and mapping our claims to the evidence."
)

col1, col2 = st.columns(2)
with col1:
    sim_mode = st.selectbox(
        "Simulation Mode", ["high_quality", "low_quality"],
        help=("High quality: strong CI precedent citations and accurate achievability "
              "ratings. Low quality: poor precedent, degraded ratings — tests whether the "
              "reviewer notices and corrects."),
    )
with col2:
    program = st.selectbox("Program", ["Aleniglipron"])

participant_id = st.text_input("Reviewer ID", value="ra_reviewer_1")

if st.button("Start Session"):
    session = LabelingSession(
        session_id=f"t5_{uuid.uuid4().hex[:8]}",
        simulation_mode=sim_mode,
        program_name=program,
        indication="obesity",
        ci_twin_id="ci_glp1_obesity_fda",
        content_twin_id="molecule_aleniglipron",
    )
    config.SIMULATION_MODE = sim_mode
    st.session_state["labeling_session"] = session
    st.session_state["participant_id"] = participant_id
    for key in ["message_map", "qc_findings"]:
        st.session_state.pop(key, None)
    SessionManager().save(session)
    st.success(f"Session created: `{session.session_id}` | Mode: `{sim_mode}`")
    st.info("Navigate to **CI Review** to begin.")
