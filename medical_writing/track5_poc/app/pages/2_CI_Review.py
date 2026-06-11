import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import datetime
import config
from labeling.ci_twin import CITwinManager
from labeling.ci_analysis import (
    achievability_table, strategic_insight, comparator_detail,
    list_comparators, SIGNAL_COLOR,
)
from workflow.session import SessionManager
from workflow.timer import StepTimer
from workflow.ui import render_stepper

st.set_page_config(page_title="CI Review", layout="wide")
render_stepper(active_step=2)

st.title("Competitive Intelligence Review")
st.caption("Strategic read of the approved-label landscape before message map generation")

if "labeling_session" not in st.session_state:
    st.warning("No active session. Return to Operator Setup.")
    st.page_link("pages/1_Operator_Setup.py", label="← Operator Setup")
    st.stop()

session = st.session_state["labeling_session"]
ci_twin = CITwinManager().load(session.ci_twin_id)

# ── Strategic insight bar (full width) ───────────────────────────────────────
insight = strategic_insight(ci_twin, session.program_name.lower(), session.reference_label)
st.markdown(
    f"<div style='background:#0b3d91;color:#fff;padding:14px 18px;border-radius:8px;"
    f"margin-bottom:14px;line-height:1.5;'>"
    f"<strong>Strategic read — {session.program_name} / {session.indication}:</strong><br>{insight}</div>",
    unsafe_allow_html=True,
)

left, right = st.columns([1, 1.4])

# ── Left: comparator selector + achievability table ──────────────────────────
with left:
    st.subheader("Comparators")
    comparators = list_comparators(ci_twin)
    selected = st.radio(
        "Select a comparator to inspect",
        comparators,
        index=comparators.index(session.reference_label) if session.reference_label in comparators else 0,
    )
    st.session_state["selected_comparator"] = selected

    st.subheader("Achievability ceiling")
    st.caption("Strategic pre-read: where do we have precedent and data?")
    table = achievability_table(ci_twin)
    header = ("<table style='width:100%;border-collapse:collapse;font-size:0.85rem;'>"
              "<tr style='text-align:left;border-bottom:1px solid #d0d7de;'>"
              "<th>CCDS Section</th><th>Precedents</th><th>Our data</th><th>Signal</th></tr>")
    body = ""
    for r in table:
        sc = SIGNAL_COLOR.get(r["signal"], "gray")
        body += (
            f"<tr style='border-bottom:1px solid #eaeef2;'>"
            f"<td style='padding:6px 4px;'>{r['section']}</td>"
            f"<td>{r['precedents']}</td>"
            f"<td>{r['our_data']}</td>"
            f"<td><span style='background:{sc};color:#fff;padding:1px 8px;border-radius:10px;"
            f"font-size:0.75rem;'>{r['signal']}</span></td></tr>"
        )
    st.markdown(header + body + "</table>", unsafe_allow_html=True)

# ── Right: selected comparator detail ────────────────────────────────────────
with right:
    detail = comparator_detail(ci_twin, selected)
    header_claim = next((c for c in ci_twin.approved_claims if c.drug_name == selected), None)
    st.subheader(selected)
    if header_claim:
        st.caption(f"Approved {header_claim.approval_date} · {ci_twin.drug_class}")

    ACTION_LABEL = {"adopt": "🟣 ADOPT", "adapt": "🟡 ADAPT", "new": "🔵 NEW", "skip": "🔴 SKIP"}
    ACTION_HEX = {"purple": "#6f42c1", "amber": "#bf8700", "blue": "#0969da", "red": "#cf222e"}
    for d in detail:
        chip = ACTION_LABEL.get(d["action"], d["action"].upper())
        border = ACTION_HEX.get(d["color"], "#d0d7de")
        st.markdown(
            f"<div style='border-left:4px solid {border};padding:8px 12px;margin:8px 0;"
            f"background:#fbfbfd;border-radius:4px;'>"
            f"<div style='font-size:0.8rem;color:#57606a;'>{d['section']} &nbsp; "
            f"<span style='float:right;'>{chip}</span></div>"
            f"<div style='font-family:Georgia,serif;margin-top:4px;'>{d['claim_text']}</div>"
            + (f"<div style='font-size:0.8rem;color:#bf8700;margin-top:6px;'>Δ {d['delta']}</div>"
               if d['delta'] else "")
            + "</div>",
            unsafe_allow_html=True,
        )

st.divider()
if st.button("CI Reviewed — Generate Message Map →", type="primary"):
    session.phase = "map_review"
    StepTimer(session).mark("ci_review_complete")
    SessionManager().save(session)
    st.page_link("pages/3_Message_Map_Review.py", label="Next: Message Map →", icon="➡️")
