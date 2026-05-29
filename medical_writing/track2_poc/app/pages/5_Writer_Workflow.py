import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import datetime

st.set_page_config(page_title="Writer Workflow", layout="wide")
st.title("Writer Workflow")

if "workflow_session_id" not in st.session_state:
    st.warning("No active workflow session. Go to **4 Operator Setup** first.")
    st.stop()

session_id = st.session_state["workflow_session_id"]

try:
    from workflow.session import WorkflowSessionManager
    from workflow.assignment import AssignmentLoader
    from workflow.simulator import OutputSimulator
    from core.twin import DigitalTwin

    mgr = WorkflowSessionManager()
    session = mgr.load(session_id)
    assignment = AssignmentLoader().load(session.assignment_id)
    sim = OutputSimulator(mode=session.simulation_mode)
    twin = DigitalTwin.load(session.twin_id)
except Exception as e:
    st.error(f"Could not load session data: {e}")
    st.stop()

st.info(f"Session: **{session_id}** | Mode: **{session.simulation_mode}** | Assignment: {session.assignment_id}")

# Section navigation
section_titles = [s.section_title for s in assignment.sections]
section_ids = [s.section_id for s in assignment.sections]
current_idx = st.session_state.get("current_section_idx", 0)
current_idx = min(current_idx, len(section_ids) - 1)

col_prev, col_sel, col_next = st.columns([1, 4, 1])
with col_prev:
    if st.button("Previous") and current_idx > 0:
        st.session_state["current_section_idx"] = current_idx - 1
        st.rerun()
with col_sel:
    selected_title = st.selectbox("Section", section_titles, index=current_idx)
    current_idx = section_titles.index(selected_title)
    st.session_state["current_section_idx"] = current_idx
with col_next:
    if st.button("Next") and current_idx < len(section_ids) - 1:
        st.session_state["current_section_idx"] = current_idx + 1
        st.rerun()

section = assignment.sections[current_idx]
st.subheader(f"{section.section_title}")

# Twin source data
st.markdown("#### Source Data from Twin")
source_data = twin.get_section_data(section.source_elements)
cols = st.columns(min(len(source_data), 3))
for i, (eid, val) in enumerate(source_data.items()):
    with cols[i % len(cols)]:
        st.markdown(f"**{eid}**")
        if isinstance(val, list):
            for item in val:
                st.write(f"  - {item}")
        else:
            st.write(str(val) if val is not None else "*Not populated*")

st.divider()

# Simulated output
st.markdown("#### AI-Generated Prose")
try:
    output = sim.load_section(section.section_id)
    st.info(f"Confidence: {output.simulated_confidence:.0%} | Quality tier: {output.quality_tier}")
    st.markdown(output.prose)
except Exception as e:
    st.warning(f"Could not load simulated output: {e}")

st.divider()

# Timer
timer_key = f"timer_start_{section.section_id}"
if st.button("Start Timer"):
    st.session_state[timer_key] = datetime.datetime.utcnow().isoformat()
    st.success("Timer started.")

if timer_key in st.session_state:
    start = datetime.datetime.fromisoformat(st.session_state[timer_key])
    elapsed = (datetime.datetime.utcnow() - start).total_seconds()
    st.write(f"Elapsed: {elapsed:.0f} seconds")

st.divider()
if st.button("Go to Adjudication", type="primary"):
    st.switch_page("pages/6_Adjudication.py")
