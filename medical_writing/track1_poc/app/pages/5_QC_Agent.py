import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from core.twin import DigitalTwin
from core.schema import SchemaRegistry
from generation.generator import ProseGenerator
from generation.qc_agent import QCAgent
import config

st.title("QC Agent")
st.caption("Validate generated prose against structured twin data")

use_real = st.sidebar.toggle("Use Real LLM (requires API key)", value=False)

twin_files = list(Path(config.TWINS_DIR).glob("*.json"))
twin_id = st.selectbox("Select Twin", [f.stem for f in twin_files])
twin = DigitalTwin.load(twin_id)
registry = SchemaRegistry()
schema = registry.get(twin.schema_id)

st.subheader("Batch QC — All Sections")
if st.button("Run QC on All Sections"):
    generator = ProseGenerator(use_real_llm=use_real)
    qc = QCAgent(use_real_llm=use_real)

    for section in schema.sections:
        source_data = twin.get_section_data(section.source_elements)
        result = generator.generate(section.id, section.title, source_data)
        qc_result = qc.check(result, source_data)

        rec_color = {"approve": "green", "revise": "orange", "escalate": "red"}.get(
            qc_result.recommendation, "gray"
        )
        with st.expander(
            f"{section.title} — :{rec_color}[{qc_result.recommendation.upper()}]  "
            f"(confidence: {qc_result.overall_confidence:.2f})"
        ):
            st.write("**Generated prose:**")
            st.write(result.prose)
            if qc_result.findings:
                st.write("**Findings:**")
                for f in qc_result.findings:
                    sev_color = {"blocking": "red", "major": "orange", "minor": "blue"}.get(
                        f.severity, "gray"
                    )
                    st.markdown(
                        f":{sev_color}[**{f.severity.upper()}**] "
                        f"`{f.category}` — {f.description}"
                    )
            else:
                st.success("No findings.")
