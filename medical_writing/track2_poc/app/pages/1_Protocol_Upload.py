import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import tempfile
import os

st.set_page_config(page_title="Protocol Upload", layout="wide")
st.title("Protocol Upload")
st.markdown("Upload a .docx clinical trial protocol to begin ingestion.")

uploaded_file = st.file_uploader("Upload Protocol (.docx)", type=["docx"])

col1, col2 = st.columns(2)
with col1:
    twin_id = st.text_input("Twin ID", value="synth_phase2_trial")
    schema_id = st.selectbox("Schema", ["protocol"])
with col2:
    writer_id = st.text_input("Writer ID", value="writer_1")
    use_stub = st.checkbox("Use stub extraction (no API key needed)", value=True)

if uploaded_file and st.button("Start Ingestion Session"):
    # Save upload to temp location
    tmp_dir = Path(tempfile.mkdtemp())
    doc_path = tmp_dir / uploaded_file.name
    doc_path.write_bytes(uploaded_file.getvalue())

    try:
        from ingestion.ingestion_session import IngestionSessionManager
        mgr = IngestionSessionManager()
        session = mgr.create(str(doc_path), twin_id, schema_id, writer_id)
        mgr.save(session)

        st.session_state["ingestion_session_id"] = session.session_id
        st.session_state["use_stub"] = use_stub
        st.success(f"Session created: **{session.session_id}**")
        st.info("Navigate to **2 Layer Verification** to begin extraction.")
    except Exception as e:
        st.error(f"Error creating session: {e}")

# Show existing sessions
st.divider()
st.subheader("Existing Sessions")
try:
    from ingestion.ingestion_session import IngestionSessionManager
    mgr = IngestionSessionManager()
    sessions = mgr.list_sessions()
    if sessions:
        for s in sessions:
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.write(f"**{s.session_id}** — {s.document_filename} — Layer {s.current_layer}/{s.total_layers} — {s.status}")
            with col_b:
                if st.button("Use this session", key=f"use_{s.session_id}"):
                    st.session_state["ingestion_session_id"] = s.session_id
                    st.success(f"Active session set to {s.session_id}")
    else:
        st.info("No sessions yet.")
except Exception as e:
    st.error(f"Could not load sessions: {e}")
