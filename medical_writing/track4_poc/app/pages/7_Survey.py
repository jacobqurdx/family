import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from workflow.session import SurveyResponse, SessionManager
from workflow.survey import submit_survey, SURVEY_QUESTIONS

st.set_page_config(page_title="Survey", layout="wide")
st.title("Post-Session Survey")
st.caption("Rate your experience with the structured content specification alignment workflow")

session = st.session_state.get("alignment_session")
if not session:
    st.warning("No active session.")
    st.stop()

mgr = SessionManager()
role = st.selectbox("Your role:", [p.role for p in session.participants])

participant = session.get_participant(role)
if participant and participant.survey_completed:
    st.success(f"Survey already submitted for {role}.")

st.info(
    "This survey captures your experience with the structured content specification "
    "approach. Your responses directly inform whether this approach should be adopted "
    "for EOP2 meeting preparation and other regulatory documents."
)

ratings = {}
for field, question, scale_desc in SURVEY_QUESTIONS:
    ratings[field] = st.slider(question, 1, 10, 7, help=scale_desc, key=f"q_{field}")

st.subheader("Open-ended feedback")
what_worked = st.text_area("What worked well in this workflow?")
what_didnt = st.text_area("What didn't work or created friction?")
biggest_saver = st.text_area("What was the biggest time saver vs. your current approach?")
biggest_friction = st.text_area("What was the biggest source of friction?")

if st.button("Submit Survey"):
    response = SurveyResponse(
        participant_id=participant.participant_id if participant else f"{role}_p1",
        role=role,
        **ratings,
        what_worked=what_worked,
        what_didnt_work=what_didnt,
        biggest_time_saver=biggest_saver,
        biggest_friction=biggest_friction,
    )
    submit_survey(session, response)
    mgr.save(session)
    st.success("Survey submitted. Thank you.")
    st.info("Operator: see the **Results Dashboard** for cross-session metrics.")
