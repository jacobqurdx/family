import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

st.set_page_config(page_title="Handoff to MW", layout="wide")
st.title("Handoff to Medical Writing")
st.caption("Locked content specification handed off for prose generation")

handoff = st.session_state.get("handoff")
if not handoff:
    st.warning("No handoff package created. Lock the spec first.")
    st.stop()

st.success(f"Handoff package ready: `{handoff.handoff_id}`")

st.subheader("Handoff Summary")
c1, c2 = st.columns(2)
with c1:
    st.write(f"**Document type:** {handoff.document_type}")
    st.write(f"**Locked version:** {handoff.locked_spec_version}")
    st.write(f"**Locked at:** {handoff.locked_at.strftime('%Y-%m-%d %H:%M')} by {handoff.locked_by}")
with c2:
    st.write(f"**Gaps filled JIT:** {len(handoff.gaps_filled)}")
    st.write(f"**Back-propagated:** {len(handoff.back_propagated)}")
    fs = handoff.qc_findings_summary
    st.write(f"**QC findings:** {fs.get('blocking', 0)} blocking / "
             f"{fs.get('major', 0)} major / {fs.get('minor', 0)} minor")

if handoff.review_decisions_summary:
    st.caption("Review decisions: " + ", ".join(
        f"{k}: {v}" for k, v in handoff.review_decisions_summary.items()))

if handoff.ra_notes:
    st.subheader("Notes from Regulatory Affairs")
    st.info(handoff.ra_notes)

if handoff.priority_sections:
    st.subheader("Priority Sections")
    for s in handoff.priority_sections:
        st.write(f"• `{s}`")

st.subheader("Locked Content Specification (for Medical Writing)")
st.caption("This structured outline is the input to prose generation. Medical writing "
           "generates from this — no interpretation required.")

for section_dict in handoff.sections:
    with st.expander(f"{section_dict['section_title']}", expanded=False):
        for claim in section_dict.get("claims", []):
            st.write(f"**Claim:** {claim['claim_text']}")
            st.caption(f"Source: `{claim['supporting_element_id']}` | "
                       f"Authority: {claim.get('regulatory_authority', '')}")

# Download handoff JSON for Track 2 integration
handoff_json = handoff.model_dump_json(indent=2)
st.download_button(
    "Download Handoff Package (JSON)",
    data=handoff_json,
    file_name=f"{handoff.handoff_id}.json",
    mime="application/json",
    help="This JSON is the formal input to the Track 2 prose generation workflow.",
)
