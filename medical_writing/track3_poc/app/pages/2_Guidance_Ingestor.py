import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
from regulatory.guidance_ingestor import GuidanceIngestor

st.set_page_config(page_title="Guidance Ingestor", layout="wide")
role = st.session_state.get("session_role", config.SESSION_ROLE)

st.title("Guidance Ingestor")
st.caption("Ingest an FDA/EMA guidance document into structured, citation-backed "
           "regulatory requirements.")

sim_mode = st.sidebar.selectbox("Simulation Mode", ["high_quality", "low_quality"])
config.SIMULATION_MODE = sim_mode

default_path = f"{config.GUIDANCE_DOCS_DIR}/fda_obesity_guidance.txt"
doc_path = st.text_input("Guidance document path", value=default_path)
doc_type = st.selectbox("Target document type", ["eop2_briefing", "ind", "protocol", "csr"])

uploaded = st.file_uploader("…or upload a guidance document (.txt / .pdf / .docx)",
                            type=["txt", "pdf", "docx"])
if uploaded is not None:
    save_path = Path(config.GUIDANCE_DOCS_DIR) / uploaded.name
    save_path.write_bytes(uploaded.getbuffer())
    doc_path = str(save_path)
    st.success(f"Uploaded to {doc_path}")

if st.button("Run Extraction"):
    reqs = GuidanceIngestor().ingest(doc_path, doc_type)
    st.session_state["extracted_requirements"] = [r.model_dump() for r in reqs]
    st.success(f"Extracted {len(reqs)} requirements (mode: {sim_mode}).")

reqs = st.session_state.get("extracted_requirements", [])
if reqs:
    st.subheader(f"Extracted Requirements ({len(reqs)})")
    for r in reqs:
        conf = r["confidence"]
        color = "green" if conf >= 0.80 else "orange" if conf >= 0.6 else "red"
        with st.expander(
            f"{r['requirement_id']} — {r['guidance_section']} "
            f"· :{color}[{conf:.0%}]"
        ):
            st.markdown(f"**Requirement:** {r['requirement_text']}")
            if r["source_quote"]:
                st.caption(f"📖 Source quote: \"{r['source_quote']}\"")
            else:
                st.error("⚠️ No source citation — verification required before use.")
            st.caption(
                f"Type: `{r['requirement_type']}` · "
                f"Mandatory: {'yes' if r['mandatory'] else 'no'} · "
                f"Applies to: {', '.join(r['applies_to_document_types'])}"
            )
