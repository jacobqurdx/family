import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
from workflow.evaluator import WorkflowEvaluator
from workflow.session import SessionManager

st.set_page_config(page_title="Results Dashboard", layout="wide")
st.title("Results Dashboard")
st.caption("Cross-session metrics — Track 4 hypothesis validation")

# Load all persisted sessions; overlay the live in-memory session if present
mgr = SessionManager()
sessions = {s.session_id: s for s in mgr.list_sessions()}
if "alignment_session" in st.session_state:
    live = st.session_state["alignment_session"]
    sessions[live.session_id] = live
sessions = list(sessions.values())

if not sessions:
    st.info("No completed sessions yet. Run alignment sessions to populate this dashboard.")
    st.stop()

evaluator = WorkflowEvaluator()
df = evaluator.to_dataframe(sessions)

# ── Hypothesis 1: EOP2 Alignment ─────────────────────────────────────────────
st.subheader("Hypothesis 1 — EOP2 Alignment")
st.caption("High quality spec → faster alignment, fewer content revision requests")

col1, col2, col3, col4 = st.columns(4)
col1.metric("Sessions", len(sessions))
col2.metric("Avg Content Revisions",
            f"{df['content_revision_requests'].mean():.1f}" if not df.empty else "—")
align_series = df["alignment_duration_minutes"].dropna()
col3.metric("Avg Alignment Duration",
            f"{align_series.mean():.0f} min" if not align_series.empty else "—",
            help="Baseline TBD — to be established with SME time-and-motion observation")
col4.metric("Avg Gaps Filled JIT",
            f"{df['gaps_filled_jit'].mean():.1f}" if not df.empty else "—")

# ── High vs Low quality comparison ───────────────────────────────────────────
hq = [s for s in sessions if s.simulation_mode == "high_quality"]
lq = [s for s in sessions if s.simulation_mode == "low_quality"]
if hq and lq:
    comparison = evaluator.compare_modes(hq, lq)
    st.subheader("High vs Low Quality Comparison")
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**High quality** ({comparison['high_quality']['sessions']} sessions)")
        st.metric("HQ Content Revisions", comparison["high_quality"]["avg_content_revisions"])
        st.metric("HQ Survey Preference", comparison["high_quality"]["avg_survey_preference"])
    with col2:
        st.markdown(f"**Low quality** ({comparison['low_quality']['sessions']} sessions)")
        st.metric("LQ Content Revisions", comparison["low_quality"]["avg_content_revisions"])
        st.metric("LQ Survey Preference", comparison["low_quality"]["avg_survey_preference"])

    val = comparison["validation"]
    (st.success if val["high_quality_fewer_revisions"] else st.error)(
        "✅ HQ produces fewer content revisions" if val["high_quality_fewer_revisions"]
        else "❌ HQ does not produce fewer revisions")
    (st.success if val["high_quality_higher_preference"] else st.error)(
        "✅ HQ produces higher preference rating" if val["high_quality_higher_preference"]
        else "❌ HQ does not produce higher preference rating")
else:
    st.caption(f"High-vs-low comparison needs both modes "
               f"(have {len(hq)} high_quality, {len(lq)} low_quality).")

# ── Hypothesis 2: Role-Based Review ─────────────────────────────────────────
st.subheader("Hypothesis 2 — Role-Based Review")
pref_s = df["avg_alignment_process_preference"].dropna()
clarity_s = df["avg_role_review_clarity"].dropna()
conf_s = df["avg_confidence_in_document"].dropna()
qc_util_s = df["avg_qc_findings_utility"].dropna()

col1, col2, col3 = st.columns(3)
col1.metric("Avg Process Preference",
            f"{pref_s.mean():.1f}/10" if not pref_s.empty else "—")
col2.metric("Avg Role Clarity",
            f"{clarity_s.mean():.1f}/10" if not clarity_s.empty else "—")
col3.metric("Avg Confidence in Doc",
            f"{conf_s.mean():.1f}/10" if not conf_s.empty else "—")

# Success criteria check
pref = pref_s.mean() if not pref_s.empty else 0
clarity = clarity_s.mean() if not clarity_s.empty else 0
qc_util = qc_util_s.mean() if not qc_util_s.empty else 0
(st.success if pref >= 7.0 else st.error)(
    "✅ Preference threshold met (≥7.0)" if pref >= 7.0
    else f"❌ Preference: {pref:.1f}/10 (target ≥7.0)")
(st.success if clarity >= 7.0 else st.error)(
    "✅ Role clarity threshold met (≥7.0)" if clarity >= 7.0
    else f"❌ Role clarity: {clarity:.1f}/10 (target ≥7.0)")
(st.success if qc_util >= 6.5 else st.error)(
    "✅ QC findings utility threshold met (≥6.5)" if qc_util >= 6.5
    else f"❌ QC findings utility: {qc_util:.1f}/10 (target ≥6.5)")

st.divider()
st.subheader("All Sessions")
st.dataframe(df[[
    "session_id", "simulation_mode", "participants", "gaps_detected",
    "qc_findings_total", "qc_findings_blocking", "content_revision_requests",
    "avg_alignment_process_preference", "avg_confidence_in_document",
]], use_container_width=True)
