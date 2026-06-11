import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
from workflow.ui import compute_status

st.set_page_config(page_title="Hub", layout="wide")
st.title("Labeling Workflow Hub")
st.caption("Session status across all steps — jump to any step, or start a new engagement")

session = st.session_state.get("labeling_session")

if session is None:
    st.info("No active session. Start a new labeling engagement to begin.")
    st.page_link("pages/1_Operator_Setup.py", label="➕ New session — Operator Setup", icon="🚀")
    st.stop()

# ── Session metadata ─────────────────────────────────────────────────────────
mm = st.session_state.get("message_map")
last_activity = session.step_timings[-1]["timestamp"][:19].replace("T", " ") if session.step_timings else "—"
st.markdown(
    f"**Program:** {session.program_name}  ·  **Indication:** {session.indication}  ·  "
    f"**Document:** CCDS  ·  **Reference label:** {session.reference_label}  ·  "
    f"**Mode:** `{session.simulation_mode}`  ·  **Last activity:** {last_activity}"
)

# ── Four key metrics ─────────────────────────────────────────────────────────
findings = st.session_state.get("qc_findings") or []
open_findings = [f for f in findings if getattr(f, "severity", "") in ("blocking", "major")]
draft = st.session_state.get("label_draft")
review = st.session_state.get("draft_review")
sections_defined = len(mm.claims) if mm else 0
approved_sections = 0
if review is not None:
    approved_sections = sum(1 for v in review.section_ratings.values() if v >= 7)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Claims Defined", sections_defined)
c2.metric("Message Map", "🔒 Locked" if (mm and mm.locked) else ("Draft" if mm else "Not started"))
c3.metric("Open QC Findings", len(open_findings))
c4.metric("Draft Sections Rated ≥7", approved_sections if review else "—")

st.divider()

# ── Step status rows ─────────────────────────────────────────────────────────
st.subheader("Workflow Steps")
rows = compute_status(session, active_step=None)
badge = {
    "done": "🟢 Complete", "locked": "🔒 Locked", "active": "🔵 In progress",
    "attention": "🟠 Needs attention", "todo": "⚪ Not started",
}
for r in rows:
    col1, col2, col3 = st.columns([0.5, 3, 2.2])
    col1.markdown(f"**{r['num']}**")
    with col2:
        st.page_link(r["page"], label=r["title"])
        st.caption(r["detail"])
    col3.markdown(badge[r["status"]])

st.divider()
colA, colB = st.columns(2)
colA.page_link("pages/9_Results_Dashboard.py", label="📊 Results Dashboard", icon="📊")
colB.page_link("pages/1_Operator_Setup.py", label="➕ Start a new session", icon="🚀")
