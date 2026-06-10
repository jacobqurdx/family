"""
Survey capture: post-session experiential ratings.

SurveyResponse (the model) lives in workflow/session.py; this module owns the
question definitions and the submission transition (response stored on the
session, participant flagged complete).
"""
from typing import Optional

from workflow.session import AlignmentSession, SurveyResponse

# (field, question, scale description) — single source of truth for UI + CLI
SURVEY_QUESTIONS = [
    ("alignment_process_preference",
     "Was the spec-first alignment approach preferable to debating content in the document itself?",
     "1 = strongly prefer document debate, 10 = strongly prefer spec-first"),
    ("spec_quality_rating",
     "How useful was the pre-generated content specification as a starting point?",
     "1 = not useful at all, 10 = extremely useful"),
    ("qc_findings_utility",
     "How useful were the pre-generated QC findings in your review?",
     "1 = not useful, 10 = very useful"),
    ("role_review_clarity",
     "How clear was the role-specific review interface (primary sections highlighted, findings surfaced)?",
     "1 = very confusing, 10 = very clear"),
    ("confidence_in_document",
     "How confident are you in the final document quality based on the alignment process?",
     "1 = not confident, 10 = very confident"),
    ("likelihood_of_content_revisions",
     "How likely are you to need content revisions after prose is generated from the locked spec?",
     "1 = very likely to need many revisions, 10 = unlikely to need any content revisions"),
]


def submit_survey(session: AlignmentSession, response: SurveyResponse) -> SurveyResponse:
    """Store the response and mark the participant's survey complete."""
    session.survey_responses.append(response)
    participant = session.get_participant(response.role)
    if participant:
        participant.survey_completed = True
    return response
