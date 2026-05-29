import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Results Dashboard", layout="wide")
st.title("Results Dashboard")
st.markdown("Operator view of all completed sessions.")

try:
    from workflow.session import WorkflowSessionManager
    from workflow.evaluation import WorkflowEvaluator

    mgr = WorkflowSessionManager()
    evaluator = WorkflowEvaluator()
    sessions = mgr.list_sessions()
except Exception as e:
    st.error(f"Could not load sessions: {e}")
    st.stop()

if not sessions:
    st.info("No workflow sessions found. Complete a session first.")
    st.stop()

# Compute metrics for all sessions
metrics_rows = []
for session in sessions:
    try:
        m = evaluator.evaluate(session)
        metrics_rows.append({
            "session_id": m.session_id,
            "simulation_mode": m.simulation_mode,
            "total_sections": m.total_sections,
            "approved_count": m.approved_count,
            "revised_count": m.revised_count,
            "escalated_count": m.escalated_count,
            "time_savings_pct": m.time_savings_pct,
            "avg_survey_score": m.avg_survey_score,
            "adoption_threshold_met": m.adoption_threshold_met,
            "status": session.status,
        })
    except Exception:
        pass

if not metrics_rows:
    st.info("No metrics to display yet.")
    st.stop()

df = pd.DataFrame(metrics_rows)

# Summary by mode
st.subheader("Summary by Simulation Mode")
if len(df) > 0:
    summary = df.groupby("simulation_mode").agg(
        sessions=("session_id", "count"),
        avg_time_savings=("time_savings_pct", "mean"),
        avg_survey=("avg_survey_score", "mean"),
        approval_rate=("approved_count", lambda x: (x / df.loc[x.index, "total_sections"].replace(0, 1)).mean() * 100),
    ).round(2)
    st.dataframe(summary, use_container_width=True)

st.subheader("All Sessions")
st.dataframe(df, use_container_width=True)

# Charts
if len(df) > 0:
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Time Savings % by Mode")
        if df["time_savings_pct"].sum() > 0:
            fig = px.bar(
                df,
                x="session_id",
                y="time_savings_pct",
                color="simulation_mode",
                title="Time Savings % per Session",
                labels={"time_savings_pct": "Time Savings (%)", "session_id": "Session"},
            )
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No time savings data yet (sessions need adjudication records).")

    with col2:
        st.subheader("Survey Scores by Mode")
        survey_df = df[df["avg_survey_score"].notna()]
        if len(survey_df) > 0:
            fig2 = px.bar(
                survey_df,
                x="session_id",
                y="avg_survey_score",
                color="simulation_mode",
                title="Average Survey Score per Session",
                labels={"avg_survey_score": "Avg Survey Score (1-10)", "session_id": "Session"},
            )
            fig2.add_hline(y=7.0, line_dash="dash", annotation_text="Adoption threshold (7.0)")
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No survey data yet.")

    # Adjudication breakdown
    st.subheader("Adjudication Decisions")
    decision_df = df[["session_id", "simulation_mode", "approved_count", "revised_count", "escalated_count"]].copy()
    decision_df_melted = decision_df.melt(
        id_vars=["session_id", "simulation_mode"],
        value_vars=["approved_count", "revised_count", "escalated_count"],
        var_name="decision",
        value_name="count",
    )
    decision_df_melted["decision"] = decision_df_melted["decision"].str.replace("_count", "")
    if decision_df_melted["count"].sum() > 0:
        fig3 = px.bar(
            decision_df_melted,
            x="session_id",
            y="count",
            color="decision",
            barmode="stack",
            title="Adjudication Decisions per Session",
        )
        st.plotly_chart(fig3, use_container_width=True)
