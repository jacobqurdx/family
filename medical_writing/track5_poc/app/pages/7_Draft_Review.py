import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import uuid
from labeling.draft_models import DraftReviewResult, DraftRevisionRequest
from workflow.session import SessionManager
from workflow.timer import StepTimer

st.set_page_config(page_title="Draft Review", layout="wide")
st.title("Label Draft Review")
st.caption("Rate the quality of each section and log any revision requests")

if "labeling_session" not in st.session_state or "label_draft" not in st.session_state:
    st.warning("No active session or label draft.")
    st.stop()

session = st.session_state["labeling_session"]
draft = st.session_state["label_draft"]

st.info(
    "**Your task:** Read each generated section and:\n"
    "1. Rate the quality (1-10)\n"
    "2. Log any revision requests — but only log **content changes** (wrong claims, missing "
    "required elements, incorrect regulatory language). Do not log formatting preferences or "
    "minor wording changes.\n\n"
    "Content revisions are the key outcome metric — fewer content revisions = the "
    "message-map-first approach is working."
)

section_ratings = {}
all_revision_requests = []

for section in draft.sections:
    st.subheader(section.section_title)
    st.text_area("Generated prose:", value=section.prose, height=180,
                 key=f"view_{section.section_id}", disabled=True)

    col1, col2 = st.columns([1, 2])
    with col1:
        rating = st.slider("Section quality (1-10):", 1, 10, 7,
                           key=f"rating_{section.section_id}",
                           help="1 = unusable, 5 = needs significant revision, 10 = ready to send")
        section_ratings[section.section_id] = rating
    with col2:
        st.caption("Log content revision requests for this section:")
        num_revisions = st.number_input("Number of revision requests:", min_value=0, max_value=5,
                                        value=0, key=f"num_rev_{section.section_id}")
        for i in range(int(num_revisions)):
            with st.expander(f"Revision {i + 1}", expanded=True):
                change_type = st.selectbox("Type:", ["content_change", "formatting", "language"],
                                           key=f"type_{section.section_id}_{i}",
                                           help="Only content_change counts against the POC hypothesis.")
                description = st.text_input("Describe the required change:",
                                            key=f"desc_{section.section_id}_{i}")
                from_text = st.text_input("Offending text (optional):",
                                          key=f"from_{section.section_id}_{i}")
                if description:
                    all_revision_requests.append(DraftRevisionRequest(
                        request_id=f"rev_{uuid.uuid4().hex[:6]}",
                        section_id=section.section_id, change_type=change_type,
                        description=description, from_text=from_text or None,
                    ))
    st.divider()

st.subheader("Overall Draft Assessment")
col1, col2 = st.columns(2)
with col1:
    overall_quality = st.slider("Overall draft quality (1-10):", 1, 10, 7,
                                help="How good is this draft as a starting point for CCDS authoring?")
    reg_language = st.slider("Regulatory language quality (1-10):", 1, 10, 7,
                             help="Is the language appropriate and standard for a product label?")
with col2:
    precedent_align = st.slider("Competitive precedent alignment (1-10):", 1, 10, 7,
                                help="Does the draft reflect the approved label landscape?")
    ready_for_revision = st.slider("Readiness for revision round (1-10):", 1, 10, 7,
                                   help="How close is this to something you'd send to an external reviewer?")

most_accurate = st.text_input("Which section was most accurately generated?")
most_problematic = st.text_input("Which section had the biggest problems?")
notes = st.text_area("Any other notes on the draft quality?")

if st.button("Submit Draft Review"):
    content_revisions = [r for r in all_revision_requests if r.change_type == "content_change"]
    review = DraftReviewResult(
        draft_id=draft.draft_id, reviewer_role="regulatory_affairs",
        section_ratings=section_ratings, overall_draft_quality=overall_quality,
        regulatory_language_quality=reg_language, precedent_alignment=precedent_align,
        ready_for_revision=ready_for_revision, revision_requests=all_revision_requests,
        most_accurate_section=most_accurate, most_problematic_section=most_problematic, notes=notes,
    )
    st.session_state["draft_review"] = review

    # Persist outcomes onto the session for the evaluator / dashboard
    session.draft_total_revision_requests = len(all_revision_requests)
    session.draft_content_revision_requests = len(content_revisions)
    session.draft_overall_quality_rating = overall_quality
    session.draft_regulatory_language_rating = reg_language
    session.draft_precedent_alignment_rating = precedent_align
    session.draft_ready_for_revision_rating = ready_for_revision
    StepTimer(session).mark("draft_review_complete")
    SessionManager().save(session)

    st.success(
        f"Draft review submitted.\n\n"
        f"**{len(all_revision_requests)} total revision requests** logged "
        f"({len(content_revisions)} content changes, "
        f"{len(all_revision_requests) - len(content_revisions)} formatting/language).\n\n"
        f"Content changes are the key metric — fewer = the message map did its job."
    )
    st.info("Navigate to **Survey** to complete your post-session ratings.")
