import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import uuid
import config
from labeling.labeling_models import LabelingSession
from workflow.session import SessionManager
from workflow.ui import render_stepper

st.set_page_config(page_title="Operator Setup", layout="wide")
render_stepper(active_step=1)

st.title("Operator Setup — Labeling Workflow Session")
st.caption("Configure the message map generation session before the reviewer begins")

st.info(
    "**What this session proves:** Does providing a pre-generated, CI-grounded message map "
    "enable a regulatory affairs reviewer to reach a locked label strategy faster and with "
    "greater confidence than the current manual approach?\n\n"
    "**Document focus:** Company Core Data Sheet (CCDS). The bottleneck is not writing the "
    "CCDS — it is synthesizing competitive intelligence and mapping our claims to the evidence."
)

REFERENCE_OPTIONS = {
    "orforglipron (Foundayo)": "Most recent obesity approval · closest mechanism precedent (default)",
    "semaglutide (Wegovy)": "First-in-class injectable · established indication standard",
    "tirzepatide (Zepbound)": "Dual GIP/GLP-1 · highest reported weight loss",
    "liraglutide (Saxenda)": "Original class indication standard (2014)",
}

left, right = st.columns(2)

with left:
    st.subheader("Program details")
    program = st.selectbox("Program", ["Aleniglipron"])
    indication = st.text_input("Indication", value="obesity", disabled=True)
    document_type = st.selectbox("Document type", ["Company Core Data Sheet (CCDS)"])
    regulatory_body = st.selectbox("Regulatory body", ["FDA"])
    participant_id = st.text_input("Reviewer ID", value="ra_reviewer_1")

with right:
    st.subheader("Reference label")
    st.caption("The comparator the CI review and message map are built against — "
               "pre-selected before you see the claims.")
    reference_label = st.radio(
        "Primary reference",
        list(REFERENCE_OPTIONS.keys()),
        captions=list(REFERENCE_OPTIONS.values()),
        index=0,
    )
    st.subheader("Simulation mode")
    sim_mode = st.radio(
        "Mode",
        ["high_quality", "low_quality"],
        captions=[
            "Strong CI precedent citations and accurate achievability ratings",
            "Poor precedent, degraded ratings — tests whether the reviewer notices and corrects",
        ],
        index=0,
    )

if st.button("Start Session", type="primary"):
    session = LabelingSession(
        session_id=f"t5_{uuid.uuid4().hex[:8]}",
        simulation_mode=sim_mode,
        program_name=program,
        indication="obesity",
        ci_twin_id="ci_glp1_obesity_fda",
        content_twin_id="molecule_aleniglipron",
        reference_label=reference_label,
    )
    config.SIMULATION_MODE = sim_mode
    st.session_state["labeling_session"] = session
    st.session_state["participant_id"] = participant_id
    st.session_state["selected_comparator"] = reference_label
    for key in ["message_map", "qc_findings", "label_draft", "draft_review"]:
        st.session_state.pop(key, None)
    SessionManager().save(session)
    st.success(f"Session created: `{session.session_id}` | Reference: {reference_label} | Mode: `{sim_mode}`")
    st.page_link("pages/2_CI_Review.py", label="Next: CI Review →", icon="➡️")
