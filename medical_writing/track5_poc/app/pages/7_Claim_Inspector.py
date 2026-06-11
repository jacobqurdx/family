import sys
import re
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
from labeling.ci_twin import CITwinManager
from labeling.draft_models import DraftReviewResult, DraftRevisionRequest
from labeling.labeling_models import Achievability
from workflow.session import SessionManager
from workflow.timer import StepTimer
from workflow.ui import render_stepper

st.set_page_config(page_title="Claim Inspector", layout="wide")
render_stepper(active_step=7)

st.title("Claim Inspector — Precision Chain")
st.caption("Trace each section from CI precedent → locked claim → generated prose, and assess it")

if "labeling_session" not in st.session_state or "label_draft" not in st.session_state:
    st.warning("No active session or label draft. Generate the draft on the Draft Bridge first.")
    st.page_link("pages/6_Draft_Bridge.py", label="← Draft Bridge")
    st.stop()

session = st.session_state["labeling_session"]
draft = st.session_state["label_draft"]
message_map = st.session_state["message_map"]
ci_twin = CITwinManager().load(session.ci_twin_id)

SECTION_LABEL = {
    "indications_usage": "Indications and Usage",
    "clinical_studies": "Clinical Studies",
    "warnings_precautions": "Warnings and Precautions",
    "adverse_reactions": "Adverse Reactions",
}
ci_by_id = {c.claim_id: c for c in ci_twin.approved_claims}
claims_by_section = {}
for c in message_map.claims:
    claims_by_section.setdefault(c.label_section, []).append(c)

if "inspector_idx" not in st.session_state:
    st.session_state["inspector_idx"] = 0
if "inspector_assess" not in st.session_state:
    st.session_state["inspector_assess"] = {}
idx = st.session_state["inspector_idx"] % len(draft.sections)

colL, colC, colR = st.columns([1.1, 1.5, 2.2])

# ── Left: claims list ────────────────────────────────────────────────────────
with colL:
    st.subheader("Sections")
    for i, sec in enumerate(draft.sections):
        label = SECTION_LABEL.get(sec.section_id, sec.section_title)
        claims = claims_by_section.get(label, [])
        achiev = claims[0].achievability.value.upper() if claims else "—"
        gap = " · GAP" if any(c.is_gap for c in claims) else ""
        marker = "▶ " if i == idx else ""
        if st.button(f"{marker}{label}", key=f"pick_{i}", use_container_width=True):
            st.session_state["inspector_idx"] = i
            st.rerun()
        st.caption(f"{achiev}{gap} · conf {sec.confidence:.0%}")

section = draft.sections[idx]
label = SECTION_LABEL.get(section.section_id, section.section_title)
claims = claims_by_section.get(label, [])

# ── Centre: evidence chain ───────────────────────────────────────────────────
with colC:
    st.subheader("Evidence chain")
    precedent_ids = []
    for cl in claims:
        precedent_ids.extend(cl.regulatory_precedent_ids)
    if precedent_ids:
        st.caption("CI precedent that fed this claim:")
        for pid in precedent_ids:
            ap = ci_by_id.get(pid)
            if ap:
                st.markdown(
                    f"<div style='border-left:3px solid #6f42c1;padding:6px 10px;margin:6px 0;"
                    f"background:#faf8ff;font-size:0.85rem;'>"
                    f"<strong>{ap.drug_name}</strong> · {ap.label_section}<br>"
                    f"<span style='font-family:Georgia,serif;'>{ap.claim_text}</span></div>",
                    unsafe_allow_html=True,
                )
    else:
        st.info("No CI precedent linked — claim requires manual grounding.")

    st.markdown("**Locked message map claim:**")
    for cl in claims:
        st.markdown(
            f"<div style='border-left:3px solid #0969da;padding:6px 10px;background:#eef4fc;"
            f"font-family:Georgia,serif;font-size:0.9rem;'>{cl.proposed_claim_text}</div>",
            unsafe_allow_html=True,
        )
    st.markdown("<div style='text-align:center;color:#57606a;margin:6px 0;'>↓ generated ↓</div>",
                unsafe_allow_html=True)

# ── Right: generated draft + assessment ──────────────────────────────────────
with colR:
    st.subheader(label)
    cc = "#1a7f37" if section.confidence >= 0.80 else ("#bf8700" if section.confidence >= 0.60 else "#cf222e")
    prose = re.sub(
        r"\[MISSING:[^\]]*\]",
        lambda m: f"<span style='background:#fdf0c8;color:#8a6d00;padding:1px 6px;border-radius:4px;'>{m.group(0)}</span>",
        section.prose,
    )
    lines = prose.split("\n")
    if section.source_claim_ids and section.confidence >= 0.60:
        for i, ln in enumerate(lines):
            s = ln.strip()
            if s and not s[0].isdigit():
                lines[i] = f"<span style='border-bottom:2px dotted #0969da;'>{ln}</span>"
                break
    st.markdown(
        f"<div style='border:1px solid #eaeef2;border-radius:6px;padding:12px;"
        f"font-family:Georgia,serif;line-height:1.55;'>"
        f"<div style='font-size:0.78rem;color:{cc};font-family:sans-serif;'>{section.confidence:.0%} confidence</div>"
        + "<br>".join(lines) + "</div>",
        unsafe_allow_html=True,
    )

    assessment = st.radio(
        "Assessment",
        ["Approve", "Minor revision", "Content revision needed"],
        key=f"assess_{section.section_id}",
        horizontal=True,
    )
    st.session_state["inspector_assess"][section.section_id] = assessment
    st.text_area("Notes", key=f"notes_{section.section_id}", height=80)

    nav1, nav2, nav3 = st.columns(3)
    if nav1.button("← Prev"):
        st.session_state["inspector_idx"] = (idx - 1) % len(draft.sections)
        st.rerun()
    if nav2.button("Next →"):
        st.session_state["inspector_idx"] = (idx + 1) % len(draft.sections)
        st.rerun()

st.divider()
st.subheader("Overall draft assessment")
o1, o2 = st.columns(2)
with o1:
    overall_quality = st.slider("Overall draft quality", 1, 10, 7)
    reg_language = st.slider("Regulatory language quality", 1, 10, 7)
with o2:
    precedent_align = st.slider("Competitive precedent alignment", 1, 10, 7)
    ready = st.slider("Readiness for revision round", 1, 10, 7)

if st.button("Submit Draft Review", type="primary"):
    rating_map = {"Approve": 9, "Minor revision": 7, "Content revision needed": 4}
    section_ratings, revisions = {}, []
    for sec in draft.sections:
        a = st.session_state["inspector_assess"].get(sec.section_id, "Approve")
        section_ratings[sec.section_id] = rating_map[a]
        if a == "Content revision needed":
            revisions.append(DraftRevisionRequest(
                request_id=f"rev_{uuid.uuid4().hex[:6]}",
                section_id=sec.section_id, change_type="content_change",
                description=st.session_state.get(f"notes_{sec.section_id}") or "Content revision flagged in inspector",
            ))
    review = DraftReviewResult(
        draft_id=draft.draft_id, reviewer_role="regulatory_affairs",
        section_ratings=section_ratings, overall_draft_quality=overall_quality,
        regulatory_language_quality=reg_language, precedent_alignment=precedent_align,
        ready_for_revision=ready, revision_requests=revisions,
    )
    st.session_state["draft_review"] = review
    session.draft_total_revision_requests = len(revisions)
    session.draft_content_revision_requests = review.content_revision_count
    session.draft_overall_quality_rating = overall_quality
    session.draft_regulatory_language_rating = reg_language
    session.draft_precedent_alignment_rating = precedent_align
    session.draft_ready_for_revision_rating = ready
    StepTimer(session).mark("draft_review_complete")
    SessionManager().save(session)
    st.success(f"Draft review submitted — {review.content_revision_count} content revision(s) logged.")
    st.page_link("pages/8_Survey.py", label="Next: Survey →", icon="➡️")
