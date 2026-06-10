import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
from twins.registry import TwinRegistry
from generation.content_spec_generator import ContentSpecGenerator
from generation.gap_handler import GapHandler
from regulatory.framework_twin import FrameworkTwinManager
from qc.pipeline import QCPipeline
from workflow.session import SessionPhase, SessionManager

st.set_page_config(page_title="Spec Review (RA)", layout="wide")
st.title("Regulatory Affairs — Content Specification Review")
st.caption("Generate content spec, run QC pipeline, resolve gaps and findings "
           "before the alignment session")

if "alignment_session" not in st.session_state:
    st.warning("No alignment session configured. Return to Operator Setup.")
    st.stop()

session = st.session_state["alignment_session"]
config.SESSION_ROLE = "regulatory_affairs"
config.SIMULATION_MODE = session.simulation_mode
mgr = SessionManager()

st.subheader(f"Session: `{session.session_id}` | Mode: `{session.simulation_mode}`")

# ── Step 1: Generate content spec ────────────────────────────────────────────
if "current_spec" not in st.session_state:
    if st.button("Generate Content Specification"):
        timing = session.start_step("spec_generation")
        session.phase = SessionPhase.RA_REVIEW
        session.start_step("ra_review")
        pair = TwinRegistry().resolve(session.structure_twin_id, session.content_twin_id)
        with st.spinner("Generating content specification from twins..."):
            spec = ContentSpecGenerator(use_real_llm=False).generate(pair)
        session.complete_step("spec_generation")
        session.spec_id = spec.spec_id
        session.gaps_detected = len(spec.gaps_detected)
        st.session_state["current_spec"] = spec
        mgr.save(session)
        st.rerun()
else:
    spec = st.session_state["current_spec"]
    st.success(f"Spec loaded: `{spec.spec_id}` — {len(spec.sections)} sections")

# ── Step 2: Gap filling ──────────────────────────────────────────────────────
if "current_spec" in st.session_state:
    spec = st.session_state["current_spec"]
    if spec.gaps_detected:
        st.subheader("Step 2: Fill Content Gaps (Just-in-Time)")
        st.caption("The following required elements are missing from the content twin. Provide them now.")

        filled_gaps = []
        for gap_element_id in spec.gaps_detected:
            col1, col2 = st.columns([2, 3])
            with col1:
                st.markdown(f"**Missing:** `{gap_element_id}`")
            with col2:
                value = st.text_input(f"Value for {gap_element_id}", key=f"gap_{gap_element_id}")
                back_prop = st.checkbox(
                    "Save to content twin", key=f"bp_{gap_element_id}",
                    help="Back-propagate to the aleniglipron content twin for future documents.",
                )
                if value:
                    filled_gaps.append((gap_element_id, value, back_prop))

        if filled_gaps and st.button("Commit Gap Fills"):
            handler = GapHandler()
            for eid, val, bp in filled_gaps:
                handler.fill_gap(spec, eid, val, filled_by="regulatory_affairs",
                                 back_propagate=bp)
            session.gaps_filled_jit += len(filled_gaps)
            st.session_state["current_spec"] = spec
            mgr.save(session)
            bp_count = sum(1 for g in filled_gaps if g[2])
            st.success(f"{len(filled_gaps)} gaps filled. {bp_count} back-propagated to content twin.")
            st.rerun()
    else:
        st.success("✅ No outstanding content gaps.")

    # ── Step 3: Run QC pipeline ──────────────────────────────────────────────
    if not st.session_state.get("qc_complete"):
        if st.button("Run QC Pipeline"):
            timing = session.start_step("qc_pipeline")
            framework = FrameworkTwinManager().load("framework_fda_obesity")
            pipeline = QCPipeline(framework, f"{config.CHECKLISTS_DIR}/eop2_checklist.json")
            with st.spinner("Running all 5 QC passes..."):
                spec, findings = pipeline.run(spec)
            session.complete_step("qc_pipeline")
            session.qc_findings_total = len(findings)
            session.qc_findings_blocking = len([f for f in findings if f.severity == "blocking"])
            st.session_state["current_spec"] = spec
            st.session_state["qc_findings"] = findings
            st.session_state["qc_complete"] = True
            mgr.save(session)
            st.rerun()

    if st.session_state.get("qc_complete"):
        findings = st.session_state.get("qc_findings", [])
        if findings:
            st.warning(f"**{len(findings)} QC findings** — "
                       f"{session.qc_findings_blocking} blocking.")
        else:
            st.success("QC pipeline passed. No findings.")
        for finding in findings:
            sev_color = {"blocking": "red", "major": "orange", "minor": "blue"}.get(finding.severity, "gray")
            st.markdown(f":{sev_color}[**{finding.severity.upper()} — Pass {finding.pass_number}**] "
                        f"`{finding.category}` (section: `{finding.section_id}`)")
            st.caption(finding.description)
            if finding.suggested_resolution:
                st.caption(f"Resolution: {finding.suggested_resolution}")

        if session.qc_findings_blocking == 0:
            st.success("No blocking findings. Ready to open alignment session.")
            if st.button("Open Alignment Session →"):
                session.phase = SessionPhase.ALIGNMENT
                session.complete_step("ra_review")
                session.start_step("alignment_session")
                mgr.save(session)
                st.info("Navigate to **Alignment Session** to begin multi-role review.")
        else:
            st.error(f"{session.qc_findings_blocking} blocking finding(s) must be "
                     f"resolved before alignment.")
            st.caption("POC: re-run spec generation in high_quality mode, or resolve "
                       "findings via the review interface.")
