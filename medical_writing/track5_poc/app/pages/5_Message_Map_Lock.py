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
blocking = [f for f in st.session_state.get("qc_findings", []) if f.severity == "blocking"]

col1, col2, col3, col4 = st.columns(4)
col1.metric("High Achievability", high)
col2.metric("Medium Achievability", med)
col3.metric("Low Achievability", low)
col4.metric("Gaps Remaining", gaps_remaining,
            delta="must resolve" if gaps_remaining else "all filled",
            delta_color="inverse")

if gaps_remaining:
    st.warning(f"{gaps_remaining} gap(s) still unresolved. Return to Message Map Review to fill.")
if blocking:
    st.error(f"{len(blocking)} blocking QC finding(s) outstanding — locking is disabled.")

st.divider()
ra_notes = st.text_area("Lock notes (optional)",
                        placeholder="Any open items, caveats, or next steps to note at lock time...")

can_lock = engine.can("regulatory_affairs", "document_ra_sections", Permission.LOCK)
if st.button("Lock Message Map",
             disabled=(gaps_remaining > 0 or bool(blocking) or not can_lock)):
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
