import sys
import re
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
from labeling.label_draft_generator import LabelDraftGenerator
from labeling.labeling_models import Achievability
from workflow.session import SessionManager
from workflow.timer import StepTimer
from workflow.ui import render_stepper

st.set_page_config(page_title="Draft Bridge", layout="wide")
render_stepper(active_step=6)

st.title("Draft Bridge")
st.caption("Locked message map claims → generated CCDS prose, side by side")

if "labeling_session" not in st.session_state or "message_map" not in st.session_state:
    st.warning("No active session or message map. Complete QC and Lock first.")
    st.stop()

session = st.session_state["labeling_session"]
message_map = st.session_state["message_map"]
config.SIMULATION_MODE = session.simulation_mode

if not message_map.locked:
    st.warning("Message map must be locked before generating the draft. Complete Step 5.")
    st.page_link("pages/5_Message_Map_Lock.py", label="← Message Map Lock")
    st.stop()

# Generate the draft once
if "label_draft" not in st.session_state:
    with st.spinner("Generating CCDS prose from the locked message map..."):
        timer = StepTimer(session)
        timer.mark("draft_generation_start")
        draft = LabelDraftGenerator().generate(message_map)
        timer.mark("draft_generation_complete")
    session.draft_id = draft.draft_id
    session.phase = "draft_review"
    st.session_state["label_draft"] = draft
    SessionManager().save(session)

draft = st.session_state["label_draft"]
claims_by_section = {}
for c in message_map.claims:
    claims_by_section.setdefault(c.label_section, []).append(c)

SECTION_LABEL = {
    "indications_usage": "Indications and Usage",
    "clinical_studies": "Clinical Studies",
    "warnings_precautions": "Warnings and Precautions",
    "adverse_reactions": "Adverse Reactions",
}

# Info bar
st.markdown(
    f"<div style='display:flex;justify-content:space-between;align-items:center;"
    f"background:#eef4fc;border:1px solid #cfe0fb;border-radius:8px;padding:10px 16px;margin-bottom:12px;'>"
    f"<span><span style='border-bottom:2px dotted #0969da;'>blue underline</span> = CI-traceable text"
    f" &nbsp;·&nbsp; <span style='background:#fdf0c8;padding:1px 6px;border-radius:4px;'>amber badge</span>"
    f" = gap placeholder</span>"
    f"<span style='font-weight:600;'>Overall confidence: {draft.overall_confidence:.0%}</span></div>",
    unsafe_allow_html=True,
)

# Column headers
hL, _, hR = st.columns([46, 8, 46])
hL.markdown(f"**Locked Message Map Claims** &nbsp;`{message_map.version}`")
hR.markdown(f"**Generated CCDS Draft** &nbsp;· avg {draft.overall_confidence:.0%}")


def render_prose(section):
    """Render prose HTML: amber badges for [MISSING:...], blue underline on CI-traceable lead."""
    prose = section.prose
    # amber badges for gap placeholders
    prose = re.sub(
        r"\[MISSING:[^\]]*\]",
        lambda m: f"<span style='background:#fdf0c8;color:#8a6d00;padding:1px 6px;"
                  f"border-radius:4px;font-size:0.85rem;'>{m.group(0)}</span>",
        prose,
    )
    lines = prose.split("\n")
    # underline the first substantive (non-heading) line for traceable sections
    if section.source_claim_ids and section.confidence >= 0.60:
        for i, ln in enumerate(lines):
            stripped = ln.strip()
            if stripped and not stripped[0].isdigit():
                lines[i] = (f"<span style='border-bottom:2px dotted #0969da;' "
                            f"title='Traceable to approved label precedent'>{ln}</span>")
                break
    return "<br>".join(lines)


CONF_COLOR = lambda c: "#1a7f37" if c >= 0.80 else ("#bf8700" if c >= 0.60 else "#cf222e")

if "bridge_decisions" not in st.session_state:
    st.session_state["bridge_decisions"] = {}

for section in draft.sections:
    label = SECTION_LABEL.get(section.section_id, section.section_title)
    claims = claims_by_section.get(label, [])
    cL, cMid, cR = st.columns([46, 8, 46])

    # Left — locked claims
    with cL:
        inner = (f"<div style='background:#faf8ff;border:1px solid #e6e0f5;border-radius:6px;"
                 f"padding:10px 14px;min-height:120px;'>"
                 f"<div style='font-size:0.78rem;color:#57606a;'>{label}</div>")
        if claims:
            for cl in claims:
                achiev = cl.achievability.value.upper()
                gapchip = " · <span style='color:#cf222e;'>GAP</span>" if cl.is_gap else ""
                inner += (f"<div style='font-family:Georgia,serif;margin-top:6px;'>{cl.proposed_claim_text}</div>"
                          f"<div style='font-size:0.74rem;color:#6f42c1;margin-top:3px;'>{achiev}{gapchip}</div>")
        else:
            inner += "<div style='color:#57606a;margin-top:6px;'>(no locked claim for this section)</div>"
        inner += "</div>"
        st.markdown(inner, unsafe_allow_html=True)

    # Middle — flow arrow
    arrow_color = "#bf8700" if section.has_gaps else "#0969da"
    cMid.markdown(
        f"<div style='text-align:center;font-size:1.6rem;color:{arrow_color};padding-top:40px;'>→</div>",
        unsafe_allow_html=True,
    )

    # Right — generated prose
    with cR:
        cc = CONF_COLOR(section.confidence)
        sec_bg = "#fffaf0" if section.confidence < 0.60 else "#ffffff"
        st.markdown(
            f"<div style='background:{sec_bg};border:1px solid #eaeef2;border-radius:6px;padding:10px 14px;'>"
            f"<div style='height:6px;background:#eaeef2;border-radius:3px;overflow:hidden;'>"
            f"<div style='width:{section.confidence*100:.0f}%;height:100%;background:{cc};'></div></div>"
            f"<div style='font-size:0.78rem;color:{cc};margin-top:3px;'>{section.confidence:.0%} confidence</div>"
            f"<div style='font-family:Georgia,serif;margin-top:8px;line-height:1.5;'>{render_prose(section)}</div>"
            f"</div>",
            unsafe_allow_html=True,
        )
        b1, b2 = st.columns(2)
        if b1.button("✅ Approve", key=f"approve_{section.section_id}"):
            st.session_state["bridge_decisions"][section.section_id] = "approve"
        if b2.button("🚩 Flag revision", key=f"flag_{section.section_id}"):
            st.session_state["bridge_decisions"][section.section_id] = "flag"
        dec = st.session_state["bridge_decisions"].get(section.section_id)
        if dec:
            st.caption(f"Decision: **{dec}**")
    st.divider()

st.page_link("pages/7_Claim_Inspector.py", label="Next: Claim Inspector (deep review) →", icon="➡️")
