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
Labeling extension of the RA AI system. Proves one focused hypothesis: a reviewer
given a pre-generated, **CI-grounded message map** reaches a locked map faster and
with greater confidence than synthesizing competitive intelligence from scratch.

**Navigation is wizard-first, hub-after.** First run walks the 8-step wizard in
order (each step gates on the prior). Return visits land on the **Hub**, which shows
status across all steps and lets you jump to any of them.
""")

session = st.session_state.get("labeling_session")
if session:
    st.success(f"Active session: `{session.session_id}` · reference `{session.reference_label}` "
               f"· mode `{session.simulation_mode}` · phase `{session.phase}`")
    st.page_link("pages/0_Hub.py", label="Open the Hub →", icon="🧭")
else:
    st.info("No active session yet.")
    st.page_link("pages/1_Operator_Setup.py", label="Start a new session →", icon="🚀")

st.markdown("""
| Step | Page |
|---|---|
| — | 0 · Hub (return-visit dashboard) |
| 1 | Operator Setup — program, reference label, mode |
| 2 | CI Review — achievability table + strategic insight |
| 3 | Message Map — synchronized reference/decision/proposed rows |
| 4 | QC Pipeline — labeling checklist |
| 5 | Message Map Lock |
| 6 | Draft Bridge — locked claims → generated prose |
| 7 | Claim Inspector — Precision Chain deep review |
| 8 | Survey |
| — | 9 · Results Dashboard (operator) |
""")