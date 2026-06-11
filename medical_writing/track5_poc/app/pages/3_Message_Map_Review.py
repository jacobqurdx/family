import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import datetime
import config
from labeling.message_map_generator import MessageMapGenerator
from labeling.ci_twin import CITwinManager
from labeling.ci_analysis import reference_sections
from labeling.labeling_models import Achievability
from core.twin import DigitalTwin
from workflow.session import SessionManager
from workflow.timer import StepTimer
from workflow.ui import render_stepper

st.set_page_config(page_title="Message Map", layout="wide")
render_stepper(active_step=3)

st.title("Message Map Definition")
st.caption("Reference label vs proposed claim — review and decide, section by section")

if "labeling_session" not in st.session_state:
    st.warning("No active session.")
    st.stop()

session = st.session_state["labeling_session"]
config.SIMULATION_MODE = session.simulation_mode
ci_twin = CITwinManager().load(session.ci_twin_id)

# Generate the message map once
if "message_map" not in st.session_state:
    with st.spinner("Generating message map from CI twin and content twin..."):
        timer = StepTimer(session)
        timer.mark("map_generation_start")
        message_map = MessageMapGenerator().generate(ci_twin, DigitalTwin.load(session.content_twin_id))
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
claims_by_id = {c.claim_id: c for c in message_map.claims}
rows = reference_sections(ci_twin, session.reference_label, message_map)

# Colour system for reference highlights
TINT = {"purple": ("#f3effc", "#6f42c1"), "amber": ("#fdf6e3", "#bf8700"),
        "red": ("#fcebec", "#cf222e"), "blue": ("#eef4fc", "#0969da")}
ACTION_OPTIONS = ["Adopt", "Adapt", "New", "Skip"]
DEFAULT_ACTION = {"adopt": "Adopt", "adapt": "Adapt", "new": "New", "skip": "Skip"}

st.info(
    "Each row shows the **reference label** (left, colour-coded: 🟣 adopt · 🟡 adapt · 🔴 diverge), "
    "your **decision** (centre), and the **proposed aleniglipron claim** (right). The page scrolls "
    "as one unit so the three columns stay aligned."
)

# Sticky column-header bar
st.markdown(
    "<div style='position:sticky;top:0;z-index:5;background:#fff;border-bottom:2px solid #d0d7de;"
    "padding:6px 0;display:flex;font-weight:600;font-size:0.85rem;'>"
    "<div style='flex:0 0 42%;'>Reference Label</div>"
    "<div style='flex:0 0 14%;text-align:center;'>Decision</div>"
    "<div style='flex:0 0 44%;'>Aleniglipron</div></div>",
    unsafe_allow_html=True,
)

# Drug anchor row
anchor_l, _, anchor_r = st.columns([42, 14, 44])
anchor_l.markdown(f"**{session.reference_label}** · approved precedent")
anchor_r.markdown(f"**{session.program_name}** · proposed label")

for row in rows:
    sid = row["section"].lower().replace(" ", "_")
    bg, border = TINT.get(row["color"], ("#f6f8fa", "#d0d7de"))
    cL, cM, cR = st.columns([42, 14, 44])

    with cL:
        st.markdown(
            f"<div style='background:{bg};border-left:4px solid {border};padding:8px 12px;"
            f"border-radius:4px;min-height:90px;'>"
            f"<div style='font-size:0.78rem;color:#57606a;'>{row['section']}</div>"
            f"<div style='font-family:Georgia,serif;margin-top:4px;'>{row['reference_text']}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )

    with cM:
        st.radio("decision", ACTION_OPTIONS,
                 index=ACTION_OPTIONS.index(DEFAULT_ACTION.get(row["action"], "Adapt")),
                 key=f"decision_{sid}", label_visibility="collapsed")

    with cR:
        claim = claims_by_id.get(row["claim_id"]) if row["claim_id"] else None
        if claim is not None:
            st.text_area("proposed claim", value=claim.proposed_claim_text,
                         key=f"text_{claim.claim_id}", height=90, label_visibility="collapsed")
            if claim.is_gap:
                gv = st.text_input(f"Fill gap `{claim.supporting_element_id}`",
                                   key=f"gap_{claim.claim_id}")
                bp = st.checkbox("Save to content twin", key=f"bp_{claim.claim_id}")
                if gv:
                    claim.supporting_value = gv
                    claim.is_gap = False
                    claim.back_propagate = bp
            if row["delta"]:
                st.markdown(
                    f"<div style='font-size:0.78rem;color:#bf8700;border-left:3px solid #bf8700;"
                    f"padding-left:8px;margin-top:4px;'>Δ {row['delta']}</div>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                f"<div style='color:#cf222e;font-size:0.85rem;padding:8px 0;'>"
                f"No proposed claim — section marked <strong>Skip</strong>.</div>",
                unsafe_allow_html=True,
            )
            if row["delta"]:
                st.markdown(
                    f"<div style='font-size:0.78rem;color:#cf222e;border-left:3px solid #cf222e;"
                    f"padding-left:8px;'>Δ {row['delta']}</div>",
                    unsafe_allow_html=True,
                )
    st.divider()

if st.button("All Claims Reviewed — Run QC →", type="primary"):
    # persist edited text + recompute counters idempotently
    for claim in message_map.claims:
        edited = st.session_state.get(f"text_{claim.claim_id}")
        if edited is not None:
            claim.proposed_claim_text = edited
    remaining_gaps = sum(1 for c in message_map.claims if c.is_gap)
    message_map.recount()
    session.reviewer_decisions = len(message_map.claims)
    session.gaps_filled_jit = max(session.gaps_detected - remaining_gaps, 0)
    session.back_propagations = sum(1 for c in message_map.claims if c.back_propagate)
    session.phase = "qc"
    st.session_state["message_map"] = message_map
    SessionManager().save(session)
    st.page_link("pages/4_QC_Pipeline.py", label="Next: QC Pipeline →", icon="➡️")
