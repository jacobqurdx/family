import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st

st.set_page_config(page_title="Survey", layout="wide")
st.title("Post-Session Survey")

if "workflow_session_id" not in st.session_state:
    st.warning("No active workflow session. Go to **4 Operator Setup** first.")
    st.stop()

session_id = st.session_state["workflow_session_id"]

try:
    from workflow.session import WorkflowSessionManager
    mgr = WorkflowSessionManager()
    session = mgr.load(session_id)
except Exception as e:
    st.error(f"Could not load session: {e}")
    st.stop()

if session.survey:
    st.success("Survey already submitted for this session.")
    st.write(f"Overall experience: {session.survey.overall_experience}/10")
    st.write(f"Time savings perceived: {session.survey.time_savings_perceived}/10")
    st.write(f"Document quality: {session.survey.document_quality}/10")
    st.write(f"Would use again: {session.survey.would_use_again}")
    if session.survey.free_text:
        st.write(f"Comments: {session.survey.free_text}")
    st.stop()

st.markdown("Please rate your experience with the AI-assisted document authoring workflow.")
st.info(f"Session: **{session_id}** | Mode: {session.simulation_mode}")

overall = st.slider("Overall experience (1 = very poor, 10 = excellent)", 1, 10, 7)
time_savings = st.slider("Perceived time savings compared to manual authoring (1 = no savings, 10 = extreme savings)", 1, 10, 7)
quality = st.slider("Quality of the AI-generated prose (1 = very poor, 10 = excellent)", 1, 10, 7)
would_use = st.radio("Would you use this system again in your workflow?", ["Yes", "No"]) == "Yes"
free_text = st.text_area("Additional comments (optional)", height=100)

if st.button("Submit Survey", type="primary"):
    from workflow.models import SurveyRating
    survey = SurveyRating(
        overall_experience=overall,
        time_savings_perceived=time_savings,
        document_quality=quality,
        would_use_again=would_use,
        free_text=free_text or None,
    )
    session.survey = survey
    mgr.save(session)
    st.success("Survey submitted! Navigate to **9 Results Dashboard** to see your metrics.")
    st.balloons()
