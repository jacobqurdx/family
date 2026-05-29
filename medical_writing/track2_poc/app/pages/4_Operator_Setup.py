import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

st.set_page_config(page_title="Operator Setup", layout="wide")
st.title("Operator Setup")
st.markdown("Configure and launch a writer workflow session.")

col1, col2 = st.columns(2)

with col1:
    twin_id = st.text_input("Twin ID", value="synth_phase2_trial")
    writer_id = st.text_input("Writer ID", value="writer_1")

with col2:
    simulation_mode = st.selectbox(
        "Simulation Mode",
        options=["high_quality", "low_quality"],
        help="high_quality = realistic regulatory prose; low_quality = vague placeholder text",
    )

    try:
        from workflow.assignment import AssignmentLoader
        loader = AssignmentLoader()
        available = loader.list_assignments()
        assignment_id = st.selectbox("Assignment", options=available if available else ["csr_efficacy_assignment"])
    except Exception:
        assignment_id = st.text_input("Assignment ID", value="csr_efficacy_assignment")

if st.button("Launch Session", type="primary"):
    try:
        from workflow.session import WorkflowSessionManager
        mgr = WorkflowSessionManager()
        session = mgr.create(writer_id, assignment_id, twin_id, simulation_mode)
        st.session_state["workflow_session_id"] = session.session_id
        st.session_state["twin_id"] = twin_id
        st.session_state["simulation_mode"] = simulation_mode
        st.success(f"Session created: **{session.session_id}**")
        st.info("Navigate to **5 Writer Workflow** to begin.")
    except Exception as e:
        st.error(f"Error creating session: {e}")

st.divider()
st.subheader("Existing Workflow Sessions")
try:
    from workflow.session import WorkflowSessionManager
    mgr = WorkflowSessionManager()
    sessions = mgr.list_sessions()
    if sessions:
        for s in sessions:
            col_a, col_b = st.columns([4, 1])
            with col_a:
                st.write(f"**{s.session_id}** | {s.writer_id} | {s.assignment_id} | {s.simulation_mode} | {s.status} | {len(s.adjudication_records)} sections")
            with col_b:
                if st.button("Resume", key=f"resume_{s.session_id}"):
                    st.session_state["workflow_session_id"] = s.session_id
                    st.session_state["twin_id"] = s.twin_id
                    st.session_state["simulation_mode"] = s.simulation_mode
                    st.success(f"Resumed session {s.session_id}")
    else:
        st.info("No workflow sessions yet.")
except Exception as e:
    st.error(f"Could not load sessions: {e}")
