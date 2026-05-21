"""
Supply Chain Risk Agent — SME Triage Dashboard (POC)
Run: streamlit run dashboard.py
"""
from __future__ import annotations

import json
from collections import defaultdict
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

# SME's 5 process steps — ordered, with display labels
PROCESS_STEPS = [
    ("raw_materials",               "Raw Materials"),
    ("regulated_starting_material", "Regulated Starting Material"),
    ("spray_dry_dispersion",        "Spray Dry Dispersion"),
    ("package_and_label",           "Package & Label"),
    ("distribution",                "Distribution"),
    (None,                          "Unassigned"),
]
PROCESS_STEP_LABEL = {k: v for k, v in PROCESS_STEPS}

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
    "cdmo_removal":        "CDMO Removal",
    "tariff_escalation":   "Tariff Escalation",
    "material_shortage":   "Material Shortage",
    "regulatory_action":   "Regulatory Action",
    "capacity_constraint": "Capacity Constraint",
    "operational":         "Operational",
    None:                  "—",
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


# ─── Sidebar ──────────────────────────────────────────────────────────────────

outputs_root = Path("outputs")
run_files = _find_run_dirs(outputs_root)

with st.sidebar:
    st.title("⚗️ Risk Agent")
    st.caption("Supply Chain Triage Dashboard · POC")
    st.divider()

    if not run_files:
        st.error("No run outputs found.\nRun `python cli.py run ...` first.")
        st.stop()

    run_options = {
        str(p): str(p.parent).replace(str(outputs_root) + "/", "")
        for p in run_files
    }
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

    step_filter = st.multiselect(
        "Filter by process step",
        options=[k for k, _ in PROCESS_STEPS],
        format_func=lambda k: PROCESS_STEP_LABEL.get(k, k or "Unassigned"),
        default=[k for k, _ in PROCESS_STEPS],
    )

    show_irrelevant = st.checkbox("Show irrelevant signals", value=False)
    show_not_novel  = st.checkbox("Show non-novel signals",  value=False)

    st.divider()
    st.caption(
        "Signals marked **UNCERTAIN** by the metacognition layer "
        "need human review before actions execute."
    )


# ─── Load & filter ────────────────────────────────────────────────────────────

signals = load_signals(selected_path)
run_dir = str(Path(selected_path).parent)

filtered = signals
if not show_irrelevant:
    filtered = [s for s in filtered if s["is_relevant"]]
if not show_not_novel:
    filtered = [s for s in filtered if s["is_novel"]]
if severity_filter:
    filtered = [s for s in filtered if s.get("severity") in severity_filter]
if step_filter is not None:
    filtered = [s for s in filtered if s.get("process_step") in step_filter]

# Sort within each step: critical → high → elevated → routine
filtered.sort(key=lambda s: SEVERITY_ORDER.index(s.get("severity")))


# ─── Header metrics ───────────────────────────────────────────────────────────

total   = len(signals)
n_rel   = sum(1 for s in signals if s["is_relevant"])
n_novel = sum(1 for s in signals if s["is_novel"])
by_sev  = {t: sum(1 for s in signals if s.get("severity") == t)
           for t in ["critical", "high", "elevated", "routine"]}
uncertain_count = sum(
    1 for s in signals
    if (s.get("severity_metacognition") or {}).get("grade") == "UNCERTAIN"
    or (s.get("impact_metacognition") or {}).get("grade") == "UNCERTAIN"
)

st.title("Supply Chain Risk Triage")
st.caption(f"Run: `{run_dir}`  ·  {total} signals collected")

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("Collected",   total)
c2.metric("Relevant",    n_rel)
c3.metric("Novel",       n_novel)
c4.metric("🔴 Critical",  by_sev["critical"])
c5.metric("🟠 High",      by_sev["high"])
c6.metric("⚠️ Uncertain", uncertain_count,
          help="Metacognition flagged — needs human review before actions execute")

st.divider()

if not filtered:
    st.info("No signals match the current filters.")
    st.stop()


# ─── Group by process step ────────────────────────────────────────────────────

# Bucket signals into ordered step groups
step_buckets: dict[str | None, list[dict]] = defaultdict(list)
for s in filtered:
    step_buckets[s.get("process_step")].append(s)

for step_key, step_label in PROCESS_STEPS:
    bucket = step_buckets.get(step_key, [])
    if not bucket:
        continue

    # Step-level severity badge — worst in this bucket
    worst = min(bucket, key=lambda s: SEVERITY_ORDER.index(s.get("severity")))
    worst_sev = worst.get("severity")
    worst_color = SEVERITY_COLOR.get(worst_sev, "#94a3b8")
    worst_emoji = SEVERITY_EMOJI.get(worst_sev, "⚪")
    uncertain_in_step = sum(
        1 for s in bucket
        if (s.get("severity_metacognition") or {}).get("grade") == "UNCERTAIN"
        or (s.get("impact_metacognition") or {}).get("grade") == "UNCERTAIN"
    )
    uncertain_badge = "  ⚠️" if uncertain_in_step else ""

    st.subheader(
        f"{worst_emoji} {step_label}"
        f"  ·  {len(bucket)} signal{'s' if len(bucket) != 1 else ''}"
        f"{uncertain_badge}"
    )

    for sig in bucket:
        sev    = sig.get("severity")
        emoji  = SEVERITY_EMOJI.get(sev, "⚪")
        label  = (sev or "unrated").upper()
        cost   = sig.get("estimated_cost_delta")
        cost_str = f"  ·  **+${cost:,.2f}/kg**" if cost else ""

        sev_meta = sig.get("severity_metacognition") or {}
        imp_meta = sig.get("impact_metacognition") or {}
        is_uncertain = (
            sev_meta.get("grade") == "UNCERTAIN"
            or imp_meta.get("grade") == "UNCERTAIN"
        )
        meta_badge = "  ⚠️ *UNCERTAIN — review needed*" if is_uncertain else ""

        header = f"{emoji} **{sig['signal_id']}**  ·  `{label}`{cost_str}{meta_badge}"

        with st.expander(header, expanded=False):
            left, right = st.columns([3, 2])

            with left:
                st.markdown(f"**Source:** {sig['source']}")
                if sig.get("url"):
                    st.markdown(f"**URL:** [{sig['url']}]({sig['url']})")
                rv = RISK_VECTOR_LABEL.get(sig.get("risk_vector"), sig.get("risk_vector", "—"))
                st.markdown(f"**Risk vector:** {rv}")
                if sig.get("relevant_parameters"):
                    params = ", ".join(f"`{p}`" for p in sig["relevant_parameters"])
                    st.markdown(f"**Parameters:** {params}")
                st.markdown("---")
                st.markdown("**Novelty reasoning**")
                st.info(sig.get("novelty_reasoning") or "—")
                st.markdown("**Severity reasoning**")
                st.warning(sig.get("severity_reasoning") or "—")

            with right:
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

                out_prefix = sig["signal_id"][:10]
                available_files = []
                for file_label, fname_tpl in [
                    ("Alert",                "alert_{}.txt"),
                    ("Investigation report", "investigation_report_{}.md"),
                    ("Management briefing",  "management_briefing_{}.md"),
                ]:
                    fp = Path(run_dir) / fname_tpl.format(out_prefix)
                    if fp.exists():
                        available_files.append((file_label, fp))

                if available_files:
                    st.markdown("---")
                    st.markdown("**Generated outputs**")
                    for file_label, fp in available_files:
                        st.download_button(
                            label=f"⬇ {file_label}",
                            data=fp.read_text(),
                            file_name=fp.name,
                            mime="text/plain",
                            key=f"{sig['signal_id']}_{fp.stem}",
                        )

    st.divider()


# ─── Footer ───────────────────────────────────────────────────────────────────

st.caption(
    "Supply Chain Risk Agent POC  ·  "
    "Stub mode — no live API calls  ·  "
    "External signals: LLM pipeline  ·  Internal MES/QMS signals: rule engine"
)
