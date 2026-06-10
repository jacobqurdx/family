import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

st.set_page_config(
    page_title="Track 5 — Labeling Workflow",
    page_icon="🏷️",
    layout="wide",
)

st.title("🏷️ Labeling Workflow Integration")
st.caption("Track 5 POC — Labeling Extension | Structure Therapeutics")

st.markdown("""
Labeling extension of the RA AI system. Proves one focused hypothesis:

> A regulatory affairs reviewer who receives a pre-generated, **CI-grounded message
> map** — claim by claim, with competitive precedent citations and achievability
> ratings — reaches a locked message map faster and with greater confidence than
> synthesizing competitive intelligence and constructing a map from scratch.

The CI twin is pre-populated from public approved labels (Wegovy, Zepbound,
Saxenda). The message map generator (**LLM-14**) is stubbed with high/low quality modes.

| Page | Session phase |
|---|---|
| 1 · Operator Setup | Configure role, mode, program |
| 2 · CI Review | Review the approved-label landscape |
| 3 · Message Map Review | Review the generated map claim by claim |
| 4 · QC Pipeline | Run the labeling checklist |
| 5 · Message Map Lock | Lock the map (gaps filled, no blocking findings) |
| 6 · Label Draft | Generate CCDS section prose from the locked map |
| 7 · Draft Review | Rate draft quality, log content revision requests |
| 8 · Survey | Post-session experiential ratings |
| 9 · Results Dashboard | Cross-session metrics incl. draft quality |
""")

session = st.session_state.get("labeling_session")
if session:
    st.success(f"Active session: `{session.session_id}` · mode `{session.simulation_mode}` "
               f"· phase `{session.phase}`")
else:
    st.info("No active session. Start at **Operator Setup**.")
