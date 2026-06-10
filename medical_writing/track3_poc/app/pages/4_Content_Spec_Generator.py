import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
from twins.registry import TwinRegistry
from generation.content_spec_generator import ContentSpecGenerator
from governance.permissions import PermissionEngine, Permission

st.set_page_config(page_title="Content Spec Generator", layout="wide")
role = st.session_state.get("session_role", config.SESSION_ROLE)
engine = PermissionEngine()

st.title("Content Specification Generator")
st.caption("Generate a structured content specification from a content twin + "
           "document structure twin.")

st.info(
    "**Document Archetype: Revision-Heavy** — EOP2 briefing documents require "
    "multiple rounds of stakeholder alignment. This tool generates the structured "
    "content specification that replaces document-level debate. Align on the spec "
    "first; generate prose after."
)

registry = TwinRegistry()
twin_pairs = registry.list_pairs()
labels = [f"{p.document_type} | {p.content_twin_id} + {p.structure_twin_id}" for p in twin_pairs]
idx = st.selectbox("Select document type + twin pair", range(len(labels)),
                   format_func=lambda i: labels[i])

use_real = st.sidebar.toggle("Use Real LLM (requires API key)", value=False)
sim_mode = st.sidebar.selectbox("Simulation Mode", ["high_quality", "low_quality"])
config.SIMULATION_MODE = sim_mode

can_edit = engine.can(role, "document_ra_sections", Permission.EDIT)
if not can_edit:
    st.warning(f"Your role ({role}) cannot generate/edit this document type.")

if st.button("Generate Content Specification", disabled=not can_edit):
    with st.spinner("Generating content specification from twins..."):
        pair = twin_pairs[idx]
        generator = ContentSpecGenerator(use_real_llm=use_real)
        spec = generator.generate(pair)
    st.session_state["current_spec"] = spec
    st.session_state["current_pair"] = pair
    st.session_state.pop("qc_findings", None)
    st.success(f"Specification generated: {len(spec.sections)} sections, "
               f"{len(spec.gaps_detected)} gaps detected.")

spec = st.session_state.get("current_spec")
if spec:
    if spec.gaps_detected:
        st.warning(f"**{len(spec.gaps_detected)} content gaps detected** — required "
                   f"elements missing from content twin.")
        st.caption("Navigate to **Gap Handler** to fill these just-in-time before running QC.")
        st.code(", ".join(spec.gaps_detected))

    for section in spec.sections:
        conf = section.overall_confidence
        conf_color = "green" if conf >= 0.8 else "orange" if conf >= 0.65 else "red"
        with st.expander(
            f"{'✅' if not section.needs_human_review else '⚠️'} {section.section_title} "
            f"— :{conf_color}[{conf:.0%} confidence]"
        ):
            st.caption(f"Primary reviewers: {', '.join(section.role_primary)}")
            for claim in section.claims:
                st.markdown(f"**Claim:** {claim.claim_text}")
                st.caption(f"Source: `{claim.supporting_element_id}` = `{claim.supporting_value}`")
                if claim.is_gap:
                    st.error(f"GAP: `{claim.supporting_element_id}` not in content twin — fill required")
                st.caption(f"Regulatory authority: {claim.regulatory_authority}")
