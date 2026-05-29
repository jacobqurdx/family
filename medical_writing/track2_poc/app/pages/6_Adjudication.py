import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import datetime

st.set_page_config(page_title="Adjudication", layout="wide")
st.title("Section Adjudication")

if "workflow_session_id" not in st.session_state:
    st.warning("No active workflow session. Go to **4 Operator Setup** first.")
    st.stop()

session_id = st.session_state["workflow_session_id"]

try:
    from workflow.session import WorkflowSessionManager
    from workflow.assignment import AssignmentLoader
    from workflow.simulator import OutputSimulator
    from workflow.adjudication import AdjudicationManager
    from workflow.models import AdjudicationDecision
    from core.twin import DigitalTwin

    mgr = WorkflowSessionManager()
    session = mgr.load(session_id)
    assignment = AssignmentLoader().load(session.assignment_id)
    sim = OutputSimulator(mode=session.simulation_mode)
    twin = DigitalTwin.load(session.twin_id)
    adj_mgr = AdjudicationManager()
except Exception as e:
    st.error(f"Could not load session data: {e}")
    st.stop()

# Progress
adjudicated_ids = {r.section_id for r in session.adjudication_records}
total = len(assignment.sections)
done = len(adjudicated_ids)
st.progress(done / total if total else 0, text=f"Adjudicated: {done}/{total} sections")

# Section selector
remaining = [s for s in assignment.sections if s.section_id not in adjudicated_ids]
all_sections = assignment.sections

section_titles_all = [s.section_title + (" [done]" if s.section_id in adjudicated_ids else "") for s in all_sections]
sel_idx = st.selectbox("Select section", range(len(all_sections)), format_func=lambda i: section_titles_all[i])
section = all_sections[sel_idx]

st.subheader(section.section_title)

# Side-by-side: twin data vs prose
col_left, col_right = st.columns(2)

with col_left:
    st.markdown("#### Source Data (Twin)")
    source_data = twin.get_section_data(section.source_elements)
    for eid, val in source_data.items():
        st.markdown(f"**{eid}**")
        if isinstance(val, list):
            for item in val:
                st.write(f"  - {item}")
        else:
            st.write(str(val) if val is not None else "*Not populated*")

with col_right:
    st.markdown("#### AI-Generated Prose")
    try:
        output = sim.load_section(section.section_id)
        st.caption(f"Confidence: {output.simulated_confidence:.0%}")
        prose_display = output.prose
    except Exception as e:
        prose_display = f"Error loading prose: {e}"
        output = None
    st.text_area("Prose", value=prose_display, height=300, key=f"prose_view_{section.section_id}", disabled=True)

st.divider()

# Already adjudicated?
existing = adj_mgr.get_record(session, section.section_id)
if existing:
    st.success(f"Already adjudicated: **{existing.decision.value}**")
    if existing.revision_notes:
        st.write(f"Notes: {existing.revision_notes}")

# Decision buttons
st.markdown("#### Your Decision")
decision_col, notes_col = st.columns([1, 2])

with decision_col:
    decision = st.radio(
        "Decision",
        options=["approved", "revised", "escalated"],
        index=0,
        key=f"adj_decision_{section.section_id}",
    )

with notes_col:
    revision_notes = st.text_area(
        "Revision notes (required for 'revised' and 'escalated')",
        key=f"adj_notes_{section.section_id}",
        height=80,
    )
    if decision == "revised":
        final_prose = st.text_area(
            "Revised prose",
            value=prose_display if output else "",
            height=200,
            key=f"adj_prose_{section.section_id}",
        )
    else:
        final_prose = prose_display if output else ""

start_time_key = f"adj_start_{section.section_id}"
if start_time_key not in st.session_state:
    st.session_state[start_time_key] = datetime.datetime.utcnow().isoformat()

if st.button("Submit Decision", type="primary"):
    start = datetime.datetime.fromisoformat(st.session_state[start_time_key])
    elapsed = (datetime.datetime.utcnow() - start).total_seconds()

    decision_enum = {
        "approved": AdjudicationDecision.APPROVED,
        "revised": AdjudicationDecision.REVISED,
        "escalated": AdjudicationDecision.ESCALATED,
    }[decision]

    adj_mgr.record_decision(
        session=session,
        section_id=section.section_id,
        section_title=section.section_title,
        decision=decision_enum,
        simulated_prose=output.prose if output else "",
        final_prose=final_prose,
        revision_notes=revision_notes or None,
        time_seconds=elapsed,
    )
    mgr.save(session)

    del st.session_state[start_time_key]
    st.success(f"Recorded **{decision}** for '{section.section_title}'")

    if done + 1 >= total:
        st.balloons()
        st.info("All sections adjudicated! Go to **7 Document Assembly**.")
    st.rerun()
