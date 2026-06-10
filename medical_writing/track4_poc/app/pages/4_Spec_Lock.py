import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import datetime
import config
from governance.permissions import PermissionEngine, Permission
from workflow.session import SessionPhase, SessionManager
from workflow.participant import review_duration_minutes
from workflow.handoff import HandoffManager

st.set_page_config(page_title="Spec Lock", layout="wide")
st.title("Content Specification Lock")
st.caption("Regulatory Affairs lead locks the content specification after all "
           "participants have reviewed")

session = st.session_state.get("alignment_session")
spec = st.session_state.get("current_spec")

if not session or not spec:
    st.warning("No active session or specification.")
    st.stop()

config.SESSION_ROLE = "regulatory_affairs"
engine = PermissionEngine()
mgr = SessionManager()

# Review completion status
st.subheader("Review Completion Status")
for participant in session.participants:
    status = "✅ Complete" if participant.review_completed_at else "⏳ Pending"
    duration = ""
    minutes = review_duration_minutes(participant)
    if minutes is not None:
        duration = f" ({minutes:.0f} min)"
    st.write(f"**{participant.role.replace('_', ' ').title()}:** {status}{duration} "
             f"| {participant.decisions_made} decisions")

all_complete = all(p.review_completed_at for p in session.participants)
if not all_complete:
    st.warning("Not all participants have completed their review. "
               "Locking is permitted but not recommended.")

blocking_open = session.qc_findings_blocking > 0
if blocking_open:
    st.error(f"{session.qc_findings_blocking} blocking QC finding(s) outstanding — "
             f"locking is disabled until resolved.")

st.divider()
ra_notes = st.text_area(
    "Notes for Medical Writing team",
    placeholder="Any context, priority sections, or open items the medical writing "
                "team should know before generating prose...",
    help="These notes accompany the locked spec in the handoff package.",
)

priority_sections = st.multiselect(
    "Priority sections for Medical Writing",
    options=[s.section_id for s in spec.sections],
    help="Sections where medical writing should pay particular attention during prose generation.",
)

can_lock = engine.can("regulatory_affairs", "document_ra_sections", Permission.LOCK)
if st.button("Lock Content Specification and Create Handoff Package",
             disabled=not can_lock or blocking_open):
    spec.locked = True
    spec.locked_at = datetime.datetime.utcnow()
    spec.locked_by = "regulatory_affairs"
    spec.version = f"v{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M')}"
    session.phase = SessionPhase.LOCKED
    session.complete_step("alignment_session")

    # Collect decision + back-propagation summaries for the handoff metadata
    decision_summary = {}
    back_propagated = []
    for p in session.participants:
        for d in st.session_state.get(f"decisions_{p.role}", []):
            decision_summary[d.decision] = decision_summary.get(d.decision, 0) + 1
            if d.back_propagate:
                back_propagated.append(d.section_id)

    handoff = HandoffManager().create(
        session.session_id, spec,
        ra_notes=ra_notes, priority_sections=priority_sections,
        qc_findings=st.session_state.get("qc_findings", []),
        review_decisions_summary=decision_summary,
        back_propagated=back_propagated,
    )
    session.handoff_id = handoff.handoff_id
    session.phase = SessionPhase.HANDOFF
    st.session_state["handoff"] = handoff
    st.session_state["current_spec"] = spec
    mgr.save(session)

    st.success(f"Spec locked: `{spec.version}`. Handoff package created: "
               f"`{handoff.handoff_id}`.")
    st.info("Navigate to **Handoff to MW** to pass the locked spec to Medical Writing.")
