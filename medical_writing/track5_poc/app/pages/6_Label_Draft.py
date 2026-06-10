import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
from labeling.label_draft_generator import LabelDraftGenerator
from labeling.labeling_models import Achievability
from workflow.session import SessionManager
from workflow.timer import StepTimer

st.set_page_config(page_title="Label Draft", layout="wide")
st.title("Label Draft Generation")
st.caption("Generate CCDS section prose from the locked message map")

if "labeling_session" not in st.session_state or "message_map" not in st.session_state:
    st.warning("No active session or message map. Complete the QC and Lock steps first.")
    st.stop()

session = st.session_state["labeling_session"]
message_map = st.session_state.get("message_map")
config.SIMULATION_MODE = session.simulation_mode

if not message_map or not message_map.locked:
    st.warning("Message map must be locked before generating the label draft. Complete Step 5 first.")
    st.stop()

st.success(f"Locked message map: `{message_map.version}` | {len(message_map.claims)} claims")

st.info(
    "The system will now generate CCDS section prose directly from the locked message map. "
    "Each section is generated from the claims you reviewed and approved. Gaps that were not "
    "filled will appear as [MISSING: ...] placeholders.\n\n"
    "This draft is a **starting point**, not a finished document. The next step is to rate "
    "section quality and log any revision requests."
)

col1, col2, col3 = st.columns(3)
high = sum(1 for c in message_map.claims if c.achievability == Achievability.HIGH)
med = sum(1 for c in message_map.claims if c.achievability == Achievability.MEDIUM)
col1.metric("High Achievability Claims", high)
col2.metric("Medium Achievability Claims", med)
col3.metric("Remaining Gaps", len([c for c in message_map.claims if c.is_gap]))

if "label_draft" not in st.session_state:
    if st.button("Generate Label Draft"):
        timer = StepTimer(session)
        with st.spinner("Generating CCDS sections from locked message map..."):
            timer.mark("draft_generation_start")
            draft = LabelDraftGenerator(use_real_llm=False).generate(message_map)
            timer.mark("draft_generation_complete")
        session.draft_id = draft.draft_id
        session.phase = "draft_review"
        st.session_state["label_draft"] = draft
        SessionManager().save(session)
        st.rerun()
else:
    draft = st.session_state["label_draft"]
    st.success(f"Draft loaded: `{draft.draft_id}` | Overall confidence: {draft.overall_confidence:.0%}")

if "label_draft" in st.session_state:
    draft = st.session_state["label_draft"]
    st.divider()
    st.subheader("Generated CCDS Draft")
    for section in draft.sections:
        conf_color = ("green" if section.confidence >= 0.80
                      else "orange" if section.confidence >= 0.60 else "red")
        with st.expander(
            f"{section.section_title} — :{conf_color}[{section.confidence:.0%} confidence]"
            f"{'  ⚠️ gaps present' if section.has_gaps else ''}",
            expanded=True,
        ):
            st.text_area("Generated prose:", value=section.prose, height=200,
                         key=f"prose_{section.section_id}", disabled=True,
                         help="Read-only in the POC. Editing happens in the revision workflow.")
            st.caption(f"Confidence rationale: {section.confidence_rationale}")
            st.caption(f"Source claims: {', '.join(section.source_claim_ids)}")
            if section.has_gaps:
                st.warning("This section contains placeholder text for gap items. These will "
                           "need to be completed before the draft can be used.")

    st.divider()
    if st.button("Proceed to Draft Review →"):
        session.phase = "draft_review"
        SessionManager().save(session)
        st.info("Navigate to **Draft Review** to rate section quality and log revision requests.")
