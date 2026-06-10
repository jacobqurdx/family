import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
from labeling.message_map_generator import MessageMapGenerator
from labeling.ci_twin import CITwinManager
from labeling.labeling_models import Achievability
from core.twin import DigitalTwin
from workflow.session import SessionManager
from workflow.timer import StepTimer

st.set_page_config(page_title="Message Map Review", layout="wide")
st.title("Message Map Review")
st.caption("Review the generated message map claim by claim — this is the alignment before authoring")

if "labeling_session" not in st.session_state:
    st.warning("No active session.")
    st.stop()

session = st.session_state["labeling_session"]
config.SESSION_ROLE = "regulatory_affairs"
config.SIMULATION_MODE = session.simulation_mode

# Generate message map once per session
if "message_map" not in st.session_state:
    ci_twin = CITwinManager().load(session.ci_twin_id)
    content_twin = DigitalTwin.load(session.content_twin_id)
    timer = StepTimer(session)
    with st.spinner("Generating message map from CI twin and content twin..."):
        timer.mark("map_generation_start")
        message_map = MessageMapGenerator(use_real_llm=False).generate(ci_twin, content_twin)
        timer.mark("map_generation_complete")
    session.map_id = message_map.map_id
    session.claims_total = len(message_map.claims)
    session.claims_high = message_map.high_achievability_count
    session.claims_medium = message_map.medium_achievability_count
    session.claims_low = message_map.low_achievability_count
    session.gaps_detected = len(message_map.gaps_detected)
    st.session_state["message_map"] = message_map
    SessionManager().save(session)

message_map = st.session_state["message_map"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("Total Claims", session.claims_total)
col2.metric("High Achievability", message_map.high_achievability_count,
            help="Strong precedent; likely FDA approval")
col3.metric("Medium Achievability", message_map.medium_achievability_count,
            help="Precedent exists; some risk")
col4.metric("Low / Gaps", message_map.low_achievability_count + len(message_map.gaps_detected),
            help="Novel claims or missing data — need attention")

st.info(
    "**How to use this:** Each claim shows the proposed label language, the competitive "
    "precedent that supports it, the achievability rating, and a risk note. Review each "
    "claim — edit the language, change the achievability rating, or fill a gap. Lock the "
    "message map when all claims are decided."
)

sections = {}
for claim in message_map.claims:
    sections.setdefault(claim.label_section, []).append(claim)

for section_name, claims in sections.items():
    st.subheader(section_name)
    for claim in claims:
        color = {Achievability.HIGH: "green", Achievability.MEDIUM: "orange",
                 Achievability.LOW: "red"}.get(claim.achievability, "gray")
        icon = {"high": "🟢", "medium": "🟡", "low": "🔴"}[claim.achievability.value]
        with st.expander(
            f":{color}[{icon} {claim.achievability.value.upper()}] — {claim.label_section} "
            f"| Confidence: {claim.confidence:.0%}",
            expanded=(claim.achievability != Achievability.HIGH or claim.is_gap),
        ):
            st.markdown("**Proposed label language:**")
            new_text = st.text_area("Edit claim text:", value=claim.proposed_claim_text,
                                    key=f"text_{claim.claim_id}", height=100)

            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Competitive precedent:**")
                st.caption(claim.precedent_summary)
                if claim.regulatory_precedent_ids:
                    st.caption(f"Based on: {', '.join(claim.regulatory_precedent_ids)}")
                else:
                    st.warning("No precedent citations — manual review required.")
            with col2:
                st.markdown("**Risk assessment:**")
                st.caption(claim.risk_note or "No specific risk noted.")
                new_achiev = st.selectbox(
                    "Achievability:", options=[a.value for a in Achievability],
                    index=[a.value for a in Achievability].index(claim.achievability.value),
                    key=f"achiev_{claim.claim_id}")

            if claim.is_gap:
                st.warning(f"GAP: `{claim.supporting_element_id}` not yet in content twin.")
                gap_value = st.text_input(f"Provide value for `{claim.supporting_element_id}`:",
                                          key=f"gap_{claim.claim_id}")
                back_prop = st.checkbox("Save to aleniglipron content twin",
                                        key=f"bp_{claim.claim_id}",
                                        help="Back-propagate this value for future documents.")
                if gap_value:
                    claim.supporting_value = gap_value
                    claim.is_gap = False
                    claim.back_propagate = back_prop

            claim.proposed_claim_text = new_text
            claim.achievability = Achievability(new_achiev)

if st.button("All Claims Reviewed — Run QC →"):
    # Derive outcome counters from current claim state (idempotent across reruns).
    # gaps_detected was set at generation; remaining gaps are those still flagged.
    remaining_gaps = sum(1 for c in message_map.claims if c.is_gap)
    message_map.recount()
    session.reviewer_decisions = len(message_map.claims)
    session.gaps_filled_jit = max(session.gaps_detected - remaining_gaps, 0)
    session.back_propagations = sum(1 for c in message_map.claims if c.back_propagate)
    session.claims_high = message_map.high_achievability_count
    session.claims_medium = message_map.medium_achievability_count
    session.claims_low = message_map.low_achievability_count
    session.phase = "qc"
    st.session_state["message_map"] = message_map
    SessionManager().save(session)
    st.info("Navigate to **QC Pipeline** to run the labeling checklist.")
