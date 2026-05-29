import streamlit as st

st.set_page_config(
    page_title="Track 1 — Clinical Document Intelligence",
    page_icon="🧬",
    layout="wide"
)

st.title("🧬 Clinical Document Intelligence System")
st.caption("Track 1 POC — Technical Feasibility | Structure Therapeutics")

st.markdown("""
This application demonstrates the core technical components of the Clinical Document
Intelligence System. Use the sidebar to navigate between modules.

| Module | What it proves |
|---|---|
| Schema Explorer | Generic schema engine with dependency graph visualization |
| Twin Editor | Guided authoring with dependency propagation |
| Dependency Graph | Visual graph of element relationships and propagation |
| Prose Generator | AI section generation from structured twin data |
| QC Agent | Automated validation of generated prose against source data |
| LLM Testbed | Accuracy and calibration evaluation against ground truth |
""")
