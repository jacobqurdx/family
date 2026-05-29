import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from core.twin import DigitalTwin
from core.schema import SchemaRegistry
from generation.generator import ProseGenerator
from generation.qc_agent import QCAgent
import config

st.title("Prose Generator")
st.caption("AI-generated regulatory prose from twin data")

use_real = st.sidebar.toggle("Use Real LLM (requires API key)", value=False)

twin_files = list(Path(config.TWINS_DIR).glob("*.json"))
twin_id = st.selectbox("Select Twin", [f.stem for f in twin_files])
twin = DigitalTwin.load(twin_id)
registry = SchemaRegistry()
schema = registry.get(twin.schema_id)

section_options = {s.title: s for s in schema.sections}
section_title_sel = st.selectbox("Select Section", list(section_options.keys()))
section = section_options[section_title_sel]

source_data = twin.get_section_data(section.source_elements)

st.subheader("Source Data (from Twin)")
for k, v in source_data.items():
    if v is not None:
        st.write(f"**{k}:** {v}")
    else:
        st.write(f"**{k}:** :red[MISSING]")

if st.button("Generate Prose"):
    with st.spinner("Generating..."):
        generator = ProseGenerator(use_real_llm=use_real)
        result = generator.generate(section.id, section.title, source_data)

    st.subheader("Generated Prose")
    confidence_color = "green" if result.confidence >= 0.7 else "orange"
    st.markdown(f"**Confidence:** :{confidence_color}[{result.confidence:.2f}] — {result.confidence_rationale}")
    st.text_area("Prose", result.prose, height=200)

    st.subheader("QC Agent Results")
    with st.spinner("Running QC..."):
        qc = QCAgent(use_real_llm=use_real)
        qc_result = qc.check(result, source_data)

    rec_color = {"approve": "green", "revise": "orange", "escalate": "red"}.get(qc_result.recommendation, "gray")
    st.markdown(f"**Recommendation:** :{rec_color}[{qc_result.recommendation.upper()}]")

    if qc_result.findings:
        for f in qc_result.findings:
            sev_color = {"blocking": "red", "major": "orange", "minor": "blue"}.get(f.severity, "gray")
            st.markdown(f":{sev_color}[**{f.severity.upper()}**] `{f.category}` — {f.description}")
    else:
        st.success("No QC findings.")
