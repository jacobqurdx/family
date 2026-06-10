import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from labeling.ci_twin import CITwinManager
from workflow.session import SessionManager
from workflow.timer import StepTimer

st.set_page_config(page_title="CI Review", layout="wide")
st.title("Competitive Intelligence Review")
st.caption("Review the structured CI summary before message map generation")

if "labeling_session" not in st.session_state:
    st.warning("No active session. Return to Operator Setup.")
    st.stop()

session = st.session_state["labeling_session"]
ci_twin = CITwinManager().load(session.ci_twin_id)

st.subheader(f"CI Twin: {ci_twin.indication_class.title()} | {ci_twin.drug_class} | {ci_twin.regulatory_body}")
st.caption(f"Last updated: {ci_twin.last_updated.strftime('%Y-%m-%d')} | "
           f"{len(ci_twin.approved_claims)} approved claims indexed")

st.info(
    "This is a structured summary of what FDA has approved for comparable programs in obesity. "
    "Review this before the system generates the message map — it is the competitive "
    "intelligence foundation that drives the achievability ratings and precedent citations."
)

sections = {}
for claim in ci_twin.approved_claims:
    sections.setdefault(claim.label_section, []).append(claim)

for section_name, claims in sections.items():
    with st.expander(f"**{section_name}** — {len(claims)} approved claims", expanded=True):
        for claim in claims:
            col1, col2 = st.columns([1, 3])
            with col1:
                st.markdown(f"**{claim.drug_name}**")
                st.caption(f"Approved: {claim.approval_date}")
                if claim.quantitative_threshold:
                    st.caption(f"Threshold: {claim.quantitative_threshold}")
            with col2:
                st.write(claim.claim_text)
                if claim.regulatory_notes:
                    st.caption(f"📋 {claim.regulatory_notes}")

st.divider()
st.caption("Confirm you have reviewed the CI summary before proceeding.")
if st.button("CI Reviewed — Generate Message Map →"):
    session.phase = "map_review"
    StepTimer(session).mark("ci_review_complete")
    SessionManager().save(session)
    st.info("Navigate to **Message Map Review** to see the generated message map.")
