import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

st.set_page_config(
    page_title="Track 4 — RA Workflow Integration",
    page_icon="🤝",
    layout="wide",
)

st.title("🤝 RA Workflow Integration")
st.caption("Track 4 POC — Workflow Value | Structure Therapeutics")

st.markdown("""
Workflow-integration sibling of Track 3 (RA analogue of Track 2). LLM components
are simulated; **real timing and survey data are collected from human participants**.

**Hypothesis 1 — EOP2 Alignment:** a pre-generated, QC-checked structured content
specification produces faster locked content agreement and fewer post-authoring
content revision requests than document-level debate.

**Hypothesis 2 — Role-Based Review:** role-specific review packages produce higher
reviewer confidence and fewer missed findings than unfiltered prose.

| Page | Session phase |
|---|---|
| 1 · Operator Setup | Configure roles, mode, participants |
| 2 · Spec Review (RA) | RA lead generates spec, fills gaps, runs QC |
| 3 · Alignment Session | All participants review spec by role |
| 4 · Spec Lock | RA lead locks spec after alignment |
| 5 · Handoff to MW | Locked spec → Track 2 prose generation |
| 6 · Post-Prose Review | Log content revision requests |
| 7 · Survey | Post-session experiential ratings |
| 8 · Results Dashboard | Cross-session hypothesis validation |
""")

session = st.session_state.get("alignment_session")
if session:
    st.success(f"Active session: `{session.session_id}` · mode `{session.simulation_mode}` "
               f"· phase `{session.phase.value}` · {len(session.participants)} participants")
else:
    st.info("No active session. Start at **Operator Setup**.")
