import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from workflow.evaluator import LabelingEvaluator
from workflow.session import SessionManager

st.set_page_config(page_title="Results Dashboard", layout="wide")
st.title("Results Dashboard — Track 5")
st.caption("Labeling workflow POC outcomes")

# Load persisted sessions; overlay the live in-memory session if present
mgr = SessionManager()
sessions = {s.session_id: s for s in mgr.list_sessions()}
if "labeling_session" in st.session_state:
    live = st.session_state["labeling_session"]
    sessions[live.session_id] = live
sessions = list(sessions.values())

if not sessions:
    st.info("No completed sessions yet.")
    st.stop()

evaluator = LabelingEvaluator()
df = evaluator.to_dataframe(sessions)

st.subheader("Hypothesis Validation")
st.caption("Does the message-map-first workflow produce faster alignment with greater confidence?")

pref_s = df["process_preference"].dropna() if "process_preference" in df.columns else df.get("process_preference")
conf_s = df["overall_confidence"].dropna() if "overall_confidence" in df.columns else None

col1, col2, col3 = st.columns(3)
col1.metric("Sessions", len(sessions))
avg_pref = pref_s.mean() if pref_s is not None and not pref_s.empty else None
avg_conf = conf_s.mean() if conf_s is not None and not conf_s.empty else None
col2.metric("Avg Process Preference", f"{avg_pref:.1f}/10" if avg_pref else "—")
col3.metric("Avg Confidence in Map", f"{avg_conf:.1f}/10" if avg_conf else "—")

if avg_pref:
    (st.success if avg_pref >= 7.0 else st.error)(
        "✅ Preference threshold met (≥7.0)" if avg_pref >= 7.0
        else f"❌ Preference: {avg_pref:.1f}/10 (target ≥7.0)")
if avg_conf:
    (st.success if avg_conf >= 7.0 else st.error)(
        "✅ Confidence threshold met (≥7.0)" if avg_conf >= 7.0
        else f"❌ Confidence: {avg_conf:.1f}/10 (target ≥7.0)")

st.divider()
st.subheader("High vs Low Quality Comparison")
hq = [s for s in sessions if s.simulation_mode == "high_quality"]
lq = [s for s in sessions if s.simulation_mode == "low_quality"]
if hq and lq:
    hq_df = evaluator.to_dataframe(hq)
    lq_df = evaluator.to_dataframe(lq)
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f"**High quality** ({len(hq)} sessions)")
        st.metric("HQ Avg Preference",
                  f"{hq_df['process_preference'].dropna().mean():.1f}/10"
                  if not hq_df['process_preference'].dropna().empty else "—")
        st.metric("HQ Avg Confidence",
                  f"{hq_df['overall_confidence'].dropna().mean():.1f}/10"
                  if not hq_df['overall_confidence'].dropna().empty else "—")
    with col2:
        st.markdown(f"**Low quality** ({len(lq)} sessions)")
        st.metric("LQ Avg Preference",
                  f"{lq_df['process_preference'].dropna().mean():.1f}/10"
                  if not lq_df['process_preference'].dropna().empty else "—")
        st.metric("LQ Avg Confidence",
                  f"{lq_df['overall_confidence'].dropna().mean():.1f}/10"
                  if not lq_df['overall_confidence'].dropna().empty else "—")
else:
    st.caption(f"Comparison needs both modes (have {len(hq)} high_quality, {len(lq)} low_quality).")

# ── Label-draft extension metrics ────────────────────────────────────────────
st.divider()
st.subheader("Label Draft Quality (end-to-end)")
st.caption("The primary end-to-end validation: a draft from a CI-grounded message map should "
           "need fewer content revisions and earn higher quality ratings.")


def _mean(frame, col):
    if frame is None or col not in frame.columns:
        return None
    s = frame[col].dropna()
    return s.mean() if not s.empty else None


dq_overall = _mean(df, "draft_overall_quality")
dq_reg = _mean(df, "draft_reg_language_quality")
dq_prec = _mean(df, "draft_precedent_alignment")
dq_ready = _mean(df, "draft_ready_for_revision")

c1, c2, c3, c4 = st.columns(4)
c1.metric("Avg Draft Quality", f"{dq_overall:.1f}/10" if dq_overall else "—")
c2.metric("Avg Reg Language", f"{dq_reg:.1f}/10" if dq_reg else "—")
c3.metric("Avg Precedent Align", f"{dq_prec:.1f}/10" if dq_prec else "—")
c4.metric("Avg Readiness", f"{dq_ready:.1f}/10" if dq_ready else "—")

if dq_overall:
    (st.success if dq_overall >= 7.0 else st.error)(
        "✅ Draft quality ≥7.0" if dq_overall >= 7.0 else f"❌ Draft quality {dq_overall:.1f}/10 (target ≥7.0)")
if dq_ready:
    (st.success if dq_ready >= 6.5 else st.error)(
        "✅ Readiness ≥6.5" if dq_ready >= 6.5 else f"❌ Readiness {dq_ready:.1f}/10 (target ≥6.5)")

if hq and lq:
    hq_df = evaluator.to_dataframe(hq)
    lq_df = evaluator.to_dataframe(lq)
    hq_rev = _mean(hq_df, "draft_content_revisions")
    lq_rev = _mean(lq_df, "draft_content_revisions")
    col1, col2 = st.columns(2)
    col1.metric("HQ Avg Content Revisions", f"{hq_rev:.1f}" if hq_rev is not None else "—")
    col2.metric("LQ Avg Content Revisions", f"{lq_rev:.1f}" if lq_rev is not None else "—")
    if hq_rev is not None and lq_rev is not None:
        (st.success if hq_rev < lq_rev else st.error)(
            "✅ HQ needs fewer content revisions than LQ (primary hypothesis validated)"
            if hq_rev < lq_rev else
            "❌ HQ does not need fewer content revisions than LQ")

st.divider()
st.subheader("All Sessions")
if not df.empty:
    st.dataframe(df, use_container_width=True)
