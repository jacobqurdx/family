import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import datetime
import config
from labeling.labeling_models import Achievability
from labeling.message_map import MessageMapManager
from governance.permissions import PermissionEngine, Permission
from workflow.session import SessionManager
from workflow.timer import StepTimer
from workflow.ui import render_stepper

st.set_page_config(page_title="Message Map Lock", layout="wide")
render_stepper(active_step=5)
st.title("Lock Message Map")
st.caption("Regulatory affairs lead locks the message map — this is the alignment milestone")

session = st.session_state.get("labeling_session")
message_map = st.session_state.get("message_map")
if not session or not message_map:
    st.warning("No active session or message map.")
    st.stop()

config.SESSION_ROLE = "regulatory_affairs"
engine = PermissionEngine()

high = sum(1 for c in message_map.claims if c.achievability == Achievability.HIGH)
med = sum(1 for c in message_map.claims if c.achievability == Achievability.MEDIUM)
low = sum(1 for c in message_map.claims if c.achievability == Achievability.LOW)
gaps_remaining = sum(1 for c in message_map.claims if c.is_gap)
findings = st.session_state.get("qc_findings", [])
ack = st.session_state.get("qc_acknowledged", set())
blocking = [f for f in findings if f.severity == "blocking"]
unack_major = [f for f in findings if f.severity == "major" and f.finding_id not in ack]

col1, col2, col3, col4 = st.columns(4)
col1.metric("High Achievability", high)
col2.metric("Medium Achievability", med)
col3.metric("Low Achievability", low)
col4.metric("Gaps Remaining", gaps_remaining,
            help="Gaps surface as QC findings; acknowledge them on the QC page rather than "
                 "forcing a placeholder value. They do not hard-block the lock.")

# Lock gate (v2): blocking findings must be resolved; major findings must be acknowledged.
if blocking:
    st.error(f"{len(blocking)} blocking QC finding(s) outstanding — resolve on the QC page. "
             f"Locking is disabled.")
if unack_major:
    st.warning(f"{len(unack_major)} major QC finding(s) not yet acknowledged — acknowledge "
               f"them on the QC page before locking.")
if gaps_remaining:
    st.caption(f"ℹ️ {gaps_remaining} claim(s) still flagged as gaps (data pending). These are "
               f"captured as QC findings; acknowledging them is sufficient to lock.")
if not findings:
    st.info("Run the QC checklist before locking.")

st.divider()
ra_notes = st.text_area("Lock notes (optional)",
                        placeholder="Any open items, caveats, or next steps to note at lock time...")

lock_blocked = bool(blocking) or bool(unack_major) or not findings
can_lock = engine.can("regulatory_affairs", "document_ra_sections", Permission.LOCK)
if st.button("Lock Message Map", type="primary",
             disabled=(lock_blocked or not can_lock)):
    message_map.locked = True
    message_map.locked_at = datetime.datetime.utcnow()
    message_map.locked_by = "regulatory_affairs"
    message_map.version = f"v{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M')}"
    message_map.qc_passed = True
    message_map.recount()

    StepTimer(session).mark("map_locked")
    session.phase = "locked"
    st.session_state["message_map"] = message_map
    MessageMapManager().save(message_map)
    SessionManager().save(session)

    st.success(
        f"Message map locked: `{message_map.version}`.\n\n"
        f"**{high}** high achievability claims | **{med}** medium | **{low}** low.\n\n"
        f"This locked message map is now the input to CCDS authoring."
    )
    st.page_link("pages/6_Draft_Bridge.py", label="Next: Draft Bridge →", icon="➡️")
