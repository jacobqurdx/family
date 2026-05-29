import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

st.set_page_config(page_title="Document Assembly", layout="wide")
st.title("Document Assembly")

if "workflow_session_id" not in st.session_state:
    st.warning("No active workflow session. Go to **4 Operator Setup** first.")
    st.stop()

session_id = st.session_state["workflow_session_id"]

try:
    from workflow.session import WorkflowSessionManager
    from workflow.assignment import AssignmentLoader

    mgr = WorkflowSessionManager()
    session = mgr.load(session_id)
    assignment = AssignmentLoader().load(session.assignment_id)
except Exception as e:
    st.error(f"Could not load session: {e}")
    st.stop()

if not session.adjudication_records:
    st.info("No adjudicated sections yet. Complete adjudication in **6 Adjudication** first.")
    st.stop()

st.info(f"Session: **{session_id}** | {len(session.adjudication_records)} sections assembled")

# Assemble document
doc_parts = [f"# {assignment.title}\n\n*Auto-assembled document*\n\n---\n"]
record_map = {r.section_id: r for r in session.adjudication_records}

for section in assignment.sections:
    record = record_map.get(section.section_id)
    if record:
        doc_parts.append(f"\n## {section.section_title}\n\n")
        doc_parts.append(record.final_prose)
        doc_parts.append(f"\n\n*[{record.decision.value.upper()}]*\n\n---\n")
    else:
        doc_parts.append(f"\n## {section.section_title}\n\n*[PENDING ADJUDICATION]*\n\n---\n")

full_doc = "".join(doc_parts)

# Display assembled document
st.markdown(full_doc)

st.divider()

# Download button
st.download_button(
    label="Download Document (.txt)",
    data=full_doc,
    file_name=f"{assignment.assignment_id}_assembled.txt",
    mime="text/plain",
)

# Section summary table
st.subheader("Section Summary")
import pandas as pd
rows = []
for section in assignment.sections:
    record = record_map.get(section.section_id)
    rows.append({
        "Section": section.section_title,
        "Decision": record.decision.value if record else "pending",
        "Time (sec)": f"{record.time_seconds:.1f}" if record else "-",
        "Has Revisions": "Yes" if record and record.revision_notes else "No",
    })
df = pd.DataFrame(rows)
st.dataframe(df, use_container_width=True)

# Complete session button
if session.status != "complete" and st.button("Mark Session Complete", type="primary"):
    mgr.complete(session)
    st.success("Session marked complete. Navigate to **8 Survey**.")
