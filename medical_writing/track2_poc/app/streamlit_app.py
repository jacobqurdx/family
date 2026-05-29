import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import streamlit as st

st.set_page_config(
    page_title="AI Clinical Document Intelligence — Track 2",
    page_icon="",
    layout="wide",
)

st.title("AI Clinical Document Intelligence System")
st.subheader("Track 2: Downstream Writer Workflow")

st.markdown("""
## Navigation Guide

| Page | Purpose |
|------|---------|
| **1 Protocol Upload** | Upload a .docx protocol and start an ingestion session |
| **2 Layer Verification** | Step through USDM extraction layers, verify node values |
| **3 Twin Inspector** | Inspect the populated digital twin |
| **4 Operator Setup** | Configure a writer workflow session |
| **5 Writer Workflow** | Review simulated AI-generated section prose |
| **6 Adjudication** | Approve / Revise / Escalate each section |
| **7 Document Assembly** | View assembled document and download |
| **8 Survey** | Post-session satisfaction survey |
| **9 Results Dashboard** | Operator metrics across all sessions |

---

Use the **sidebar** to navigate between pages.
""")

st.info("Start with **1 Protocol Upload** to begin a new ingestion session, or **4 Operator Setup** to use the pre-populated twin.")
