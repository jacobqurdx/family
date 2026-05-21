"""
Supply Chain Risk Agent — SME Triage Dashboard (POC)
Run: streamlit run dashboard.py
"""
from __future__ import annotations

import json
from pathlib import Path

import streamlit as st

# ─── Page config ──────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Supply Chain Risk Dashboard",
    page_icon="⚗️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ─── Constants ────────────────────────────────────────────────────────────────

SEVERITY_ORDER = ["critical", "high", "elevated", "routine", None]
SEVERITY_COLOR = {
    "critical": "#ef4444",
    "high":     "#f97316",
    "elevated": "#eab308",
    "routine":  "#22c55e",
    None:       "#94a3b8",
}
SEVERITY_EMOJI = {
    "critical": "🔴",
    "high":     "🟠",
    "elevated": "🟡",
    "routine":  "🟢",
    None:       "⚪",
}
RISK_VECTOR_LABEL = {
    "cdmo_removal":       "CDMO Removal",
    "tariff_escalation":  "Tariff Escalation",
    "material_shortage":  "Material Shortage",
    "regulatory_action":  "Regulatory Action",
    "capacity_constraint":"Capacity Constraint",
    "operational":        "Operational",
    None:                 "—",
}


# ─── Data loading ─────────────────────────────────────────────────────────────

def _find_run_dirs(outputs_root: Path) -> list[Path]:
    return sorted(
        [p for p in outputs_root.rglob("assessed_signals.json")],
        reverse=True,
    )


@st.cache_data
def load_signals(path: str) -> list[dict]:
    return json.loads(Path(path).read_text())


@st.cache_data
def load_run_summary(run_dir: str) -> dict | None:
    p = Path(run_dir) / "run_summary.json"
    return json.loads(p.read_text()) if p.exists() else None


# ─── Sidebar — file picker ─────────────────────────────────────────────────────

outputs_root = Path("outputs")
run_files = _find_run_dirs(outputs_root)

with st.sidebar:
    st.title("⚗️ Risk Agent")
    st.caption("Supply Chain Triage Dashboard · POC")
    st.divider()

    if not run_files:
        st.error("No run outputs found.\nRun `python cli.py run ...` first.")
        st.stop()

    run_options = {str(p): str(p.parent).replace(str(outputs_root) + "/", "") for p in run_files}
    selected_path = st.selectbox(
        "Run output",
        options=list(run_options.keys()),
        format_func=lambda k: run_options[k],
    )

    st.divider()

    severity_filter = st.multiselect(
        "Filter by severity",
        options=["critical", "high", "elevated", "routine"],
        default=["critical", "high", "elevated", "routine"],
    )

    show_irrelevant = st.checkbox("Show irrelevant signals", value=False)
    show_not_novel  = st.checkbox("Show non-novel signals",  value=False)

    st.divider()
    st.caption("Signals marked UNCERTAIN by the metacognition layer need human review before actions execute.")


# ─── Load data ────────────────────────────────────────────────────────────────

signals    = load_signals(selected_path)
run_dir    = str(Path(selected_path).parent)
summary    = load_run_summary(run_dir)

# Apply filters
filtered = signals
if not show_irrelevant:
    filtered = [s for s in filtered if s["is_relevant"]]
if not show_not_novel:
    filtered = [s for s in filtered if s["is_novel"]]
if severity_filter:
    filtered = [s for s in filtered if s.get("severity") in severity_filter]

# Sort: critical → high → elevated → routine → None
filtered.sort(key=lambda s: SEVERITY_ORDER.index(s.get("severity")))


# ─── Header metrics ───────────────────────────────────────────────────────────

total   = len(signals)
n_rel   = sum(1 for s in signals if s["is_relevant"])
n_novel = sum(1 for s in signals if s["is_novel"])
by_sev  = {t: sum(1 for s in signals if s.get("severity") == t) for t in ["critical", "high", "elevated", "routine"]}
uncertain_count = sum(
    1 for s in signals
    if (s.get("severity_metacognition") or {}).get("grade") == "UNCERTAIN"
    or (s.get("impact_metacognition") or {}).get("grade") == "UNCERTAIN"
)

st.title("Supply Chain Risk Triage")
if summary:
    st.caption(f"Run: `{run_dir}`  ·  {total} signals collected")

col1, col2, col3, col4, col5, col6 = st.columns(6)
col1.metric("Collected",  total)
col2.metric("Relevant",   n_rel)
col3.metric("Novel",      n_novel)
col4.metric("🔴 Critical", by_sev["critical"])
col5.metric("🟠 High",     by_sev["high"])
col6.metric("⚠️ Uncertain", uncertain_count, help="Metacognition flagged — needs human review")

st.divider()


# ─── Signal list ──────────────────────────────────────────────────────────────

if not filtered:
    st.info("No signals match the current filters.")
    st.stop()

st.subheader(f"Signals ({len(filtered)} shown)")

for sig in filtered:
    sev   = sig.get("severity")
    color = SEVERITY_COLOR.get(sev, "#94a3b8")
    emoji = SEVERITY_EMOJI.get(sev, "⚪")
    label = (sev or "unrated").upper()

    # Metacognition flags
    sev_meta    = sig.get("severity_metacognition") or {}
    imp_meta    = sig.get("impact_metacognition") or {}
    is_uncertain = sev_meta.get("grade") == "UNCERTAIN" or imp_meta.get("grade") == "UNCERTAIN"
    meta_badge   = "  ⚠️ *UNCERTAIN — review needed*" if is_uncertain else ""

    cost = sig.get("estimated_cost_delta")
    cost_str = f"  ·  **+${cost:,.2f}/kg**" if cost else ""

    header = f"{emoji} **{sig['signal_id']}**  ·  `{label}`{cost_str}{meta_badge}"

    with st.expander(header, expanded=(sev == "critical" and not is_uncertain is False)):

        left, right = st.columns([3, 2])

        with left:
            st.markdown(f"**Source:** {sig['source']}")
            if sig.get("url"):
                st.markdown(f"**URL:** [{sig['url']}]({sig['url']})")

            st.markdown(f"**Risk vector:** {RISK_VECTOR_LABEL.get(sig.get('risk_vector'), sig.get('risk_vector', '—'))}")

            if sig.get("relevant_parameters"):
                params = ", ".join(f"`{p}`" for p in sig["relevant_parameters"])
                st.markdown(f"**Parameters:** {params}")

            st.markdown("---")
            st.markdown("**Novelty reasoning**")
            st.info(sig.get("novelty_reasoning") or "—")

            st.markdown("**Severity reasoning**")
            st.warning(sig.get("severity_reasoning") or "—")

        with right:
            # Metacognition panel
            st.markdown("**Metacognition grades**")

            def _meta_pill(label: str, meta: dict) -> None:
                grade = meta.get("grade", "—")
                conf  = meta.get("confidence")
                flags = meta.get("uncertainty_flags", [])
                adj   = meta.get("adjudicated", False)
                color_css = "green" if grade == "CERTAIN" else "red"
                conf_str  = f"  ({conf:.0%} confidence)" if conf else ""
                adj_str   = "  ✏️ adjudicated" if adj else ""
                st.markdown(
                    f"<span style='color:{color_css}; font-weight:600'>{grade}</span>"
                    f"{conf_str}{adj_str}  — *{label}*",
                    unsafe_allow_html=True,
                )
                for f in flags:
                    st.caption(f"  · {f}")

            if sev_meta:
                _meta_pill("severity", sev_meta)
            if imp_meta:
                _meta_pill("impact", imp_meta)

            st.markdown("---")
            st.markdown("**Recommended actions**")
            for action in sig.get("recommended_actions", []):
                action_color = "red" if "alert" in action or "removal" in action else "blue"
                st.markdown(
                    f"<span style='color:{action_color}'>▸</span> `{action}`",
                    unsafe_allow_html=True,
                )

            # Output files
            out_prefix = sig["signal_id"][:10]
            alert_path = Path(run_dir) / f"alert_{out_prefix}.txt"
            report_path = Path(run_dir) / f"investigation_report_{out_prefix}.md"
            briefing_path = Path(run_dir) / f"management_briefing_{out_prefix}.md"

            available_files = []
            if alert_path.exists():
                available_files.append(("Alert", alert_path))
            if report_path.exists():
                available_files.append(("Investigation report", report_path))
            if briefing_path.exists():
                available_files.append(("Management briefing", briefing_path))

            if available_files:
                st.markdown("---")
                st.markdown("**Generated outputs**")
                for file_label, file_path in available_files:
                    content = file_path.read_text()
                    st.download_button(
                        label=f"⬇ {file_label}",
                        data=content,
                        file_name=file_path.name,
                        mime="text/plain",
                        key=f"{sig['signal_id']}_{file_path.stem}",
                    )


# ─── Footer ───────────────────────────────────────────────────────────────────

st.divider()
st.caption(
    "Supply Chain Risk Agent POC · "
    "Stub mode — no live API calls · "
    "Severity assessed by LLM pipeline (external) or rule engine (internal MES/QMS signals)"
)
