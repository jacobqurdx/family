"""
Survey capture for the labeling workflow.

LabelingSurveyResponse (the model) lives in labeling.labeling_models; this module
owns the question definitions (single source of truth for UI + CLI) and the
submission transition (response serialized onto the session).
"""
from labeling.labeling_models import LabelingSession, LabelingSurveyResponse  # noqa: F401

# (field, question, scale description)
SURVEY_QUESTIONS = [
    ("process_preference",
     "Is the message-map-first approach preferable to your current manual CI synthesis and label strategy process?",
     "1 = strongly prefer current approach, 10 = strongly prefer message-map-first"),
    ("ci_summary_quality",
     "How useful was the structured competitive intelligence summary?",
     "1 = not useful, 10 = extremely useful — saved significant time"),
    ("achievability_accuracy",
     "How accurate were the achievability ratings (high / medium / low) on the claims?",
     "1 = mostly wrong, 10 = mostly correct"),
    ("risk_note_quality",
     "How useful were the risk notes on each claim?",
     "1 = not useful, 10 = very useful — highlighted risks I would have missed"),
    ("overall_confidence",
     "How confident are you in the locked message map as a foundation for CCDS authoring?",
     "1 = not confident, 10 = very confident"),
    ("time_saved_rating",
     "Compared to your current approach, how much time do you feel this saved?",
     "1 = took more time, 5 = about the same, 10 = saved significant time"),
]


def submit_survey(session: LabelingSession, response: LabelingSurveyResponse) -> LabelingSurveyResponse:
    """Store the survey response on the session as a serialized dict."""
    session.survey_response = response.model_dump()
    return response
