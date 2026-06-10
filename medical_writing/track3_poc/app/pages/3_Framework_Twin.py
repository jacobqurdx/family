import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
from regulatory.framework_twin import FrameworkTwinManager

st.set_page_config(page_title="Framework Twin", layout="wide")
role = st.session_state.get("session_role", config.SESSION_ROLE)

st.title("Regulatory Framework Twin")
st.caption("Per-agency store of ingested guidance requirements, known agency "
           "concerns, and prior company positions.")

mgr = FrameworkTwinManager()
ids = mgr.list_ids()
if not ids:
    st.warning("No framework twins found.")
    st.stop()

framework_id = st.selectbox("Framework twin", ids)
twin = mgr.load(framework_id)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Guidance docs", len(twin.guidance_documents))
c2.metric("Requirements", len(twin.requirements))
c3.metric("Agency concerns", len(twin.agency_concerns))
c4.metric("Prior positions", len(twin.prior_positions))

st.divider()
tabs = st.tabs(["Requirements", "Agency Concerns", "Prior Positions"])

with tabs[0]:
    doc_types = sorted({dt for r in twin.requirements for dt in r.applies_to_document_types})
    flt = st.multiselect("Filter by document type", doc_types, default=doc_types)
    for r in twin.requirements:
        if flt and not set(r.applies_to_document_types) & set(flt):
            continue
        with st.expander(f"{r.requirement_id} — {r.guidance_section} · {r.confidence:.0%}"):
            st.markdown(f"**{r.requirement_text}**")
            if r.source_quote:
                st.caption(f"📖 \"{r.source_quote}\"")
            st.caption(f"Type `{r.requirement_type}` · mandatory: {r.mandatory} · "
                       f"applies to: {', '.join(r.applies_to_document_types)}")

with tabs[1]:
    for c in twin.agency_concerns:
        with st.expander(f"{c.concern_id} — {c.source_type} · §{c.document_section}"):
            st.markdown(f"**Concern:** {c.concern_text}")
            st.caption(f"Source: {c.source_document}  ·  class: {c.indication_class}")
            st.success(f"Resolution expected: {c.resolution_guidance}")

with tabs[2]:
    for p in twin.prior_positions:
        with st.expander(f"{p.position_id} — {p.program_id} · {p.document_type} ({p.submission_date})"):
            st.markdown(f"**Position:** {p.position_text}")
            st.caption(f"§{p.section}  ·  outcome: {p.outcome or '—'}")
            if p.notes:
                st.caption(p.notes)
