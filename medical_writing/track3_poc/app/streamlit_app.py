import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st
import config

st.set_page_config(
    page_title="Track 3 — Regulatory Intelligence",
    page_icon="⚖️",
    layout="wide",
)

# ── Session role selector (simulated permissions) ────────────────────────────
ROLES = [
    "regulatory_affairs", "medical_writing", "clinical_science",
    "clinical_operations", "biostatistician", "qc_compliance", "admin",
]
if "session_role" not in st.session_state:
    st.session_state["session_role"] = config.SESSION_ROLE

st.sidebar.subheader("Session Role")
st.session_state["session_role"] = st.sidebar.selectbox(
    "Acting as (simulated)",
    ROLES,
    index=ROLES.index(st.session_state["session_role"])
    if st.session_state["session_role"] in ROLES else 0,
)
st.sidebar.caption("Permissions are simulated — set by the operator at session start.")

st.title("⚖️ AI Regulatory Intelligence System")
st.caption("Track 3 POC — Technical Feasibility | Structure Therapeutics")

st.markdown(f"""
Regulatory-affairs sibling of Track 1. Document generation is always
**f(Content Twin, Document Structure Twin) → Document**.

**Acting as:** `{st.session_state["session_role"]}`

| Page | What it proves |
|---|---|
| 1 · Twin Registry | Content + structure twin pair resolution |
| 2 · Guidance Ingestor | FDA/EMA guidance → structured requirements |
| 3 · Framework Twin | Browse regulatory requirements + agency concerns |
| 4 · Content Spec Generator | Generate a content spec from a twin pair |
| 5 · Gap Handler | Fill content gaps just-in-time + back-propagate |
| 6 · QC Pipeline | Five-pass automated QC before human review |
| 7 · Review Package | Role-based from→to review interface |
| 8 · Governance | Permissions, locking, versioning (simulated) |
""")

st.info(
    "All LLM components are **stubbed**. Toggle **Simulation Mode** "
    "(`high_quality` / `low_quality`) in the sidebar of the generator and QC "
    "pages to exercise the QC pipeline with deliberately degraded output."
)
