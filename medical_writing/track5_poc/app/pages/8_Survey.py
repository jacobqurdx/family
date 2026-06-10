import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from labeling.labeling_models import LabelingSurveyResponse
from workflow.survey import submit_survey, SURVEY_QUESTIONS
from workflow.session import SessionManager

st.set_page_config(page_title="Survey", layout="wide")
st.title("Post-Session Survey")
st.caption("Rate your experience with the message-map-first labeling workflow")

session = st.session_state.get("labeling_session")
if not session:
    st.warning("No active session.")
    st.stop()

participant_id = st.session_state.get("participant_id", "ra_reviewer_1")

if session.survey_response:
    st.success("Survey already submitted for this session.")

st.info(
    "Your feedback directly informs whether this approach should be adopted for label "
    "strategy and CCDS preparation. Please be candid — especially about what didn't work."
)

# Draft-review ratings captured on the Draft Review page (read-only summary here)
review = st.session_state.get("draft_review")
if review is not None:
    st.subheader("Label Draft Quality (from your Draft Review)")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Overall draft", f"{review.overall_draft_quality}/10")
    c2.metric("Reg language", f"{review.regulatory_language_quality}/10")
    c3.metric("Precedent align", f"{review.precedent_alignment}/10")
    c4.metric("Readiness", f"{review.ready_for_revision}/10")
    st.caption(f"Content revision requests logged: {review.content_revision_count} "
               f"(of {len(review.revision_requests)} total)")
    st.divider()

ratings = {}
for field, question, scale_desc in SURVEY_QUESTIONS:
    ratings[field] = st.slider(question, 1, 10, 7, help=scale_desc, key=f"q_{field}")

st.subheader("Open feedback")
most_valuable = st.text_area("What was the most valuable part of this workflow?")
biggest_gap = st.text_area("What was missing or needs improvement?")
production_use = st.selectbox("Would you use this in your real labeling workflow?",
                              ["yes", "yes, with changes", "no"])
changes = st.text_area("If yes with changes or no — what would need to change?")

if st.button("Submit Survey"):
    response = LabelingSurveyResponse(
        participant_id=participant_id, role="regulatory_affairs", **ratings,
        most_valuable_feature=most_valuable, biggest_gap=biggest_gap,
        would_use_in_production=production_use, changes_needed=changes,
    )
    submit_survey(session, response)
    SessionManager().save(session)
    st.success("Survey submitted. Thank you for your feedback.")
    st.info("Operator: see the **Results Dashboard** for cross-session metrics.")
