import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import uuid
import config
from review.review_package import ReviewPackageBuilder
from review.finding_models import ReviewDecision
from governance.permissions import PermissionEngine, Permission
from workflow.session import SessionManager
from workflow.participant import start_review, complete_review

st.set_page_config(page_title="Alignment Session", layout="wide")
st.title("Alignment Session — Multi-Role Content Specification Review")
st.caption("Each participant reviews the content specification from their role's perspective")

if "alignment_session" not in st.session_state:
    st.warning("No alignment session configured.")
    st.stop()

session = st.session_state["alignment_session"]
spec = st.session_state.get("current_spec")
findings = st.session_state.get("qc_findings", [])
mgr = SessionManager()

if not spec:
    st.warning("No content specification generated. Complete RA Review first.")
    st.stop()

# Participant selector
participant_roles = [p.role for p in session.participants]
current_role = st.selectbox(
    "Reviewing as:",
    options=participant_roles,
    help="Each participant selects their role and completes their review independently.",
)
config.SESSION_ROLE = current_role
engine = PermissionEngine()

st.info(
    f"**Your role:** {current_role.replace('_', ' ').title()}\n\n"
    f"You are reviewing a pre-generated structured content specification for the "
    f"**EOP2 Briefing Document** (aleniglipron, obesity). Your primary sections are "
    f"highlighted. QC findings relevant to your role are flagged. "
    f"Review each section and record your decisions below."
)

# Mark review start time
start_review(session, current_role)

# Build role-specific review package
package = ReviewPackageBuilder().build(spec, findings, current_role)

primary_sections = [s for s in spec.sections if s.section_id in package.primary_sections]
secondary_sections = [s for s in spec.sections if s.section_id not in package.primary_sections]

decisions = []
can_edit = engine.can(current_role, "document_ra_sections", Permission.EDIT)

st.subheader("Your Primary Sections")
if not primary_sections:
    st.caption("No primary sections mapped for this role — review the awareness sections below.")
for section in primary_sections:
    section_findings = [f for f in findings if f.section_id == section.section_id]
    with st.expander(f"★ {section.section_title} — {len(section_findings)} finding(s)",
                     expanded=True):
        for claim in section.claims:
            st.markdown("**Current claim:**")
            st.info(claim.claim_text)
            st.caption(f"Source: `{claim.supporting_element_id}` | Confidence: {claim.confidence:.0%}")
            st.caption(f"Regulatory authority: {claim.regulatory_authority}")

            if claim.gap_filled_by:
                st.warning(f"GAP filled just-in-time by {claim.gap_filled_by}: "
                           f"`{claim.supporting_element_id}` was missing from the content twin.")
            elif claim.is_gap:
                st.error(f"GAP: `{claim.supporting_element_id}` missing from content twin.")

            if can_edit:
                new_text = st.text_area("Propose revision:", value=claim.claim_text,
                                        key=f"rev_{current_role}_{section.section_id}_{claim.claim_id}")
                back_prop = st.checkbox("Back-propagate to content twin",
                                        key=f"bp_{current_role}_{section.section_id}_{claim.claim_id}")
                if new_text != claim.claim_text:
                    decisions.append(ReviewDecision(
                        decision_id=f"dec_{uuid.uuid4().hex[:6]}",
                        section_id=section.section_id, reviewer_role=current_role,
                        decision="correct", from_value=claim.claim_text,
                        to_value=new_text, back_propagate=back_prop,
                    ))
            else:
                suggestion = st.text_area(
                    "Suggest revision (your role can suggest but not edit):",
                    key=f"sug_{current_role}_{section.section_id}_{claim.claim_id}")
                if suggestion:
                    decisions.append(ReviewDecision(
                        decision_id=f"dec_{uuid.uuid4().hex[:6]}",
                        section_id=section.section_id, reviewer_role=current_role,
                        decision="suggest", from_value=claim.claim_text,
                        to_value=suggestion,
                    ))

        for finding in section_findings:
            sev_color = {"blocking": "red", "major": "orange", "minor": "blue"}.get(finding.severity, "gray")
            st.markdown(f":{sev_color}[**{finding.severity.upper()}**] {finding.description}")

st.subheader("Other Sections (for awareness)")
for section in secondary_sections:
    with st.expander(f"{section.section_title}", expanded=False):
        for claim in section.claims:
            st.write(claim.claim_text)
            st.caption(f"Primary reviewers: {', '.join(section.role_primary)}")

if st.button("Submit Review"):
    complete_review(session, current_role, len(decisions))
    st.session_state[f"decisions_{current_role}"] = decisions
    mgr.save(session)
    st.success(f"Review submitted. {len(decisions)} decisions recorded.")
    st.info("Navigate to **Survey** to complete your post-session survey.")
