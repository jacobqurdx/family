import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
import uuid
import datetime
from review.review_package import ReviewPackageBuilder
from review.finding_models import ReviewDecision
from governance.permissions import PermissionEngine, Permission

st.set_page_config(page_title="Review Package", layout="wide")
role = st.session_state.get("session_role", config.SESSION_ROLE)
engine = PermissionEngine()

st.title("Document Review")
st.caption("Role-specific review interface — from → to")

if "current_spec" not in st.session_state:
    st.warning("No content specification loaded. Generate a spec first (page 4).")
    st.stop()

spec = st.session_state["current_spec"]
findings = st.session_state.get("qc_findings", [])

builder = ReviewPackageBuilder()
package = builder.build(spec, findings, role)

st.subheader(f"Review Package — {role.replace('_', ' ').title()}")
st.caption(f"Primary sections for your role: {', '.join(package.primary_sections) or '—'}")

col1, col2, col3 = st.columns(3)
col1.metric("Total Findings", len(package.all_findings))
blocking = [f for f in package.all_findings if f.severity == "blocking"]
major = [f for f in package.all_findings if f.severity == "major"]
col2.metric("Blocking", len(blocking), delta="must resolve before lock" if blocking else None)
col3.metric("Major", len(major))

st.divider()
st.subheader("Section-by-Section Review")
st.caption("For each finding: review the from → to change, then Accept, Correct, or Flag.")

decisions = []
can_edit = engine.can(role, "document_ra_sections", Permission.EDIT)
for section in spec.sections:
    section_findings = [f for f in package.all_findings if f.section_id == section.section_id]
    is_primary = section.section_id in package.primary_sections
    header = (f"{'★ ' if is_primary else ''}{section.section_title}"
              + (f" — ⚠️ {len(section_findings)} finding(s)" if section_findings
                 else " — ✅ No findings"))
    with st.expander(header, expanded=is_primary and bool(section_findings)):
        for claim in section.claims:
            st.markdown("**Current claim:**")
            st.info(claim.claim_text)
            if can_edit:
                new_text = st.text_area(
                    "Proposed revision (leave unchanged to accept):",
                    value=claim.claim_text, key=f"edit_{claim.claim_id}",
                )
                back_prop = st.checkbox(
                    "Back-propagate this correction to the content twin",
                    key=f"bp_{claim.claim_id}",
                    help="If checked, this value is saved to the content twin for future documents.",
                )
                if new_text != claim.claim_text:
                    decisions.append(ReviewDecision(
                        decision_id=f"dec_{uuid.uuid4().hex[:6]}",
                        section_id=section.section_id, reviewer_role=role,
                        decision="correct", from_value=claim.claim_text,
                        to_value=new_text, back_propagate=back_prop,
                        decided_at=datetime.datetime.utcnow(),
                    ))
            else:
                st.caption(f"Your role ({role}) can suggest but not edit this section.")
                suggestion = st.text_area("Suggest revision:", key=f"sug_{claim.claim_id}")
                if suggestion:
                    decisions.append(ReviewDecision(
                        decision_id=f"dec_{uuid.uuid4().hex[:6]}",
                        section_id=section.section_id, reviewer_role=role,
                        decision="suggest", from_value=claim.claim_text,
                        to_value=suggestion, decided_at=datetime.datetime.utcnow(),
                    ))

        for finding in section_findings:
            sev_color = {"blocking": "red", "major": "orange", "minor": "blue"}.get(finding.severity, "gray")
            st.markdown(f":{sev_color}[**{finding.severity.upper()} — Pass {finding.pass_number}**] "
                        f"`{finding.category}`")
            st.markdown(f"**Finding:** {finding.description}")
            if finding.suggested_resolution:
                st.caption(f"Suggested resolution: {finding.suggested_resolution}")

if decisions and st.button("Submit Review Decisions"):
    st.session_state["review_decisions"] = decisions
    st.success(f"{len(decisions)} decisions recorded.")
    back_prop_count = sum(1 for d in decisions if d.back_propagate)
    if back_prop_count:
        st.info(f"{back_prop_count} correction(s) will be back-propagated to the content twin.")
