"""
Supply Chain Risk Agent — SME Triage Dashboard (POC)
Run: streamlit run dashboard.py
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
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

PROCESS_STEPS = [
    ("raw_materials",               "Raw Materials"),
    ("regulated_starting_material", "Regulated Starting Material"),
    ("spray_dry_dispersion",        "Spray Dry Dispersion"),
    ("package_and_label",           "Package & Label"),
    ("distribution",                "Distribution"),
    (None,                          "Unassigned"),
]
PROCESS_STEP_LABEL = {k: v for k, v in PROCESS_STEPS}

SEVERITY_TIERS = ["critical", "high", "elevated", "routine"]
SEVERITY_ORDER = SEVERITY_TIERS + [None]
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


# ─── Persistence helpers ──────────────────────────────────────────────────────

def _adjudications_path(run_dir: str) -> Path:
    return Path(run_dir) / "adjudications.json"


def load_adjudications(run_dir: str) -> dict:
    """Returns {signal_id: {severity, reason, adjudicated_by, adjudicated_at}}"""
    p = _adjudications_path(run_dir)
    return json.loads(p.read_text()) if p.exists() else {}


def save_adjudication(run_dir: str, signal_id: str, severity: str, reason: str) -> None:
    adj = load_adjudications(run_dir)
    adj[signal_id] = {
        "severity":       severity,
        "reason":         reason,
        "adjudicated_by": "SME (dashboard)",
        "adjudicated_at": datetime.now(timezone.utc).isoformat(),
    }
    _adjudications_path(run_dir).write_text(json.dumps(adj, indent=2))


def clear_adjudication(run_dir: str, signal_id: str) -> None:
    adj = load_adjudications(run_dir)
    adj.pop(signal_id, None)
    _adjudications_path(run_dir).write_text(json.dumps(adj, indent=2))


# ─── Data loading ─────────────────────────────────────────────────────────────

def _find_run_dirs(outputs_root: Path) -> list[Path]:
    return sorted(outputs_root.rglob("assessed_signals.json"), reverse=True)


@st.cache_data
def load_signals(path: str) -> list[dict]:
    return json.loads(Path(path).read_text())


# ─── Rendering helpers ────────────────────────────────────────────────────────

def _meta_pill(label: str, meta: dict, adj: dict | None) -> None:
    grade = meta.get("grade", "—")
    conf  = meta.get("confidence")
    flags = meta.get("uncertainty_flags", [])
    overridden = adj is not None and grade == "UNCERTAIN"
    color_css = "green" if grade == "CERTAIN" or overridden else "red"
    display_grade = "UNCERTAIN → adjudicated" if overridden else grade
    conf_str = f"  ({conf:.0%})" if conf else ""
    st.markdown(
        f"<span style='color:{color_css}; font-weight:600'>{display_grade}</span>"
        f"{conf_str}  — *{label}*",
        unsafe_allow_html=True,
    )
    if flags and not overridden:
        for f in flags:
            st.caption(f"  · {f}")


def _render_signal_card(sig: dict, run_dir: str) -> None:
    sig_id   = sig["signal_id"]
    adj      = sig.get("_adj")
    eff_sev  = adj["severity"] if adj else sig.get("severity")

    emoji    = SEVERITY_EMOJI.get(eff_sev, "⚪")
    label    = (eff_sev or "unrated").upper()
    cost     = sig.get("estimated_cost_delta")
    cost_str = f"  ·  **+${cost:,.2f}/kg**" if cost else ""

    sev_meta = sig.get("severity_metacognition") or {}
    imp_meta = sig.get("impact_metacognition") or {}
    is_uncertain = (
        sev_meta.get("grade") == "UNCERTAIN"
        or imp_meta.get("grade") == "UNCERTAIN"
    )

    if adj:
        adj_badge = "  ✅ *adjudicated*"
    elif is_uncertain:
        adj_badge = "  ⚠️ *UNCERTAIN — adjudication needed*"
    else:
        adj_badge = ""

    header = f"{emoji} **{sig_id}**  ·  `{label}`{cost_str}{adj_badge}"

    with st.expander(header, expanded=is_uncertain and not adj):

        # ── Assessment columns ─────────────────────────────────────────────
        left, right = st.columns([3, 2])

        with left:
            st.markdown(f"**Source:** {sig['source']}")
            if sig.get("url"):
                st.markdown(f"**URL:** [{sig['url']}]({sig['url']})")
            if sig.get("collected_at"):
                st.caption(f"Collected: {sig['collected_at'][:10]}")
            rv = RISK_VECTOR_LABEL.get(sig.get("risk_vector"), sig.get("risk_vector", "—"))
            st.markdown(f"**Risk vector:** {rv}")
            if sig.get("relevant_parameters"):
                params = ", ".join(f"`{p}`" for p in sig["relevant_parameters"])
                st.markdown(f"**Parameters:** {params}")

            st.markdown("---")
            st.markdown("**Novelty reasoning**")
            st.info(sig.get("novelty_reasoning") or "—")
            st.markdown("**Severity reasoning**")
            if adj:
                st.success(
                    f"**Adjudicated → {adj['severity'].upper()}**\n\n"
                    f"{adj['reason']}\n\n"
                    f"*{adj['adjudicated_by']} · {adj['adjudicated_at'][:10]}*"
                )
            else:
                st.warning(sig.get("severity_reasoning") or "—")

        with right:
            st.markdown("**Metacognition grades**")
            if sev_meta:
                _meta_pill("severity", sev_meta, adj)
            if imp_meta:
                _meta_pill("impact", imp_meta, adj)

            st.markdown("---")
            st.markdown("**Recommended actions**")
            for action in sig.get("recommended_actions", []):
                color = "red" if "alert" in action or "removal" in action else "blue"
                st.markdown(
                    f"<span style='color:{color}'>▸</span> `{action}`",
                    unsafe_allow_html=True,
                )

            out_prefix = sig_id[:10]
            available = []
            for file_label, fname_tpl in [
                ("Alert",                "alert_{}.txt"),
                ("Investigation report", "investigation_report_{}.md"),
                ("Management briefing",  "management_briefing_{}.md"),
            ]:
                fp = Path(run_dir) / fname_tpl.format(out_prefix)
                if fp.exists():
                    available.append((file_label, fp))
            if available:
                st.markdown("---")
                st.markdown("**Generated outputs**")
                for file_label, fp in available:
                    st.download_button(
                        label=f"⬇ {file_label}",
                        data=fp.read_text(),
                        file_name=fp.name,
                        mime="text/plain",
                        key=f"{sig_id}_{fp.stem}",
                    )

        # ── Full signal text drill-down ────────────────────────────────────
        raw = (sig.get("raw_content") or "").strip()
        if raw:
            st.markdown("---")
            with st.expander("📄 Full signal text", expanded=False):
                st.markdown(
                    f"<div style='"
                    f"white-space: pre-wrap; word-wrap: break-word; "
                    f"font-family: monospace; font-size: 0.85rem; "
                    f"background: #1e1e1e; color: #d4d4d4; "
                    f"padding: 1rem; border-radius: 0.375rem; "
                    f"line-height: 1.5; overflow-x: hidden;"
                    f"'>{raw}</div>",
                    unsafe_allow_html=True,
                )

        # ── Adjudication panel ─────────────────────────────────────────────
        if is_uncertain or adj:
            st.markdown("---")
            st.markdown("### 🧑‍⚕️ SME Adjudication")

            if adj:
                st.success(
                    f"Adjudicated as **{adj['severity'].upper()}**  \n"
                    f"{adj['reason']}  \n"
                    f"*{adj['adjudicated_by']} · {adj['adjudicated_at'][:10]}*"
                )
                if st.button("↩ Reopen", key=f"reopen_{sig_id}", type="secondary"):
                    clear_adjudication(run_dir, sig_id)
                    st.rerun()
            else:
                st.caption(
                    "The metacognition layer flagged this assessment as uncertain. "
                    "Accept the automated severity or override it before actions execute."
                )
                orig_sev = sig.get("severity") or "elevated"
                tier_idx = SEVERITY_TIERS.index(orig_sev) if orig_sev in SEVERITY_TIERS else 0

                acol, ocol = st.columns([1, 2])
                with acol:
                    if st.button(
                        f"✅ Accept  `{orig_sev.upper()}`",
                        key=f"accept_{sig_id}",
                        type="primary",
                    ):
                        save_adjudication(
                            run_dir, sig_id, orig_sev,
                            "Accepted automated assessment without changes.",
                        )
                        st.rerun()

                with ocol:
                    with st.form(key=f"override_form_{sig_id}"):
                        new_tier = st.selectbox(
                            "Override severity",
                            options=SEVERITY_TIERS,
                            index=tier_idx,
                            key=f"tier_{sig_id}",
                        )
                        reason = st.text_area(
                            "Reason for override",
                            placeholder=(
                                "e.g. Signal is unconfirmed; downgrading to ELEVATED "
                                "pending verification from FDA website."
                            ),
                            key=f"reason_{sig_id}",
                            height=80,
                        )
                        if st.form_submit_button("💾 Save override"):
                            if not reason.strip():
                                st.error("Please provide a reason before saving.")
                            else:
                                save_adjudication(run_dir, sig_id, new_tier, reason.strip())
                                st.rerun()


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
        options=SEVERITY_TIERS,
        default=SEVERITY_TIERS,
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
        "**UNCERTAIN** signals are flagged by the metacognition layer and "
        "require SME adjudication before actions execute."
    )


# ─── Load & merge adjudications ───────────────────────────────────────────────

run_dir  = str(Path(selected_path).parent)
signals  = load_signals(selected_path)
adj_store = load_adjudications(run_dir)
signals = [{**s, "_adj": adj_store.get(s["signal_id"])} for s in signals]


# ─── Filter ───────────────────────────────────────────────────────────────────

filtered = signals
if not show_irrelevant:
    filtered = [s for s in filtered if s["is_relevant"]]
if not show_not_novel:
    filtered = [s for s in filtered if s["is_novel"]]
if severity_filter:
    filtered = [
        s for s in filtered
        if (s["_adj"]["severity"] if s.get("_adj") else s.get("severity")) in severity_filter
    ]
if step_filter is not None:
    filtered = [s for s in filtered if s.get("process_step") in step_filter]

filtered.sort(key=lambda s: SEVERITY_ORDER.index(s.get("severity")))


# ─── Header metrics ───────────────────────────────────────────────────────────

total   = len(signals)
n_rel   = sum(1 for s in signals if s["is_relevant"])
n_novel = sum(1 for s in signals if s["is_novel"])
by_sev  = {t: sum(1 for s in signals if s.get("severity") == t) for t in SEVERITY_TIERS}
uncertain     = [
    s for s in signals
    if (s.get("severity_metacognition") or {}).get("grade") == "UNCERTAIN"
    or (s.get("impact_metacognition") or {}).get("grade") == "UNCERTAIN"
]
n_uncertain   = len(uncertain)
n_adjudicated = sum(1 for s in uncertain if s.get("_adj"))
n_pending     = n_uncertain - n_adjudicated

st.title("Supply Chain Risk Triage")
st.caption(f"Run: `{run_dir}`  ·  {total} signals collected")

c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("Collected",     total)
c2.metric("Relevant",      n_rel)
c3.metric("Novel",         n_novel)
c4.metric("🔴 Critical",    by_sev["critical"])
c5.metric("🟠 High",        by_sev["high"])
c6.metric("⚠️ Uncertain",   n_uncertain,
          help="Metacognition flagged — adjudication required")
c7.metric("✅ Adjudicated",  n_adjudicated,
          delta=f"{n_pending} pending" if n_pending else None,
          delta_color="inverse" if n_pending else "off")

if n_pending:
    st.warning(
        f"**{n_pending} signal{'s' if n_pending != 1 else ''} awaiting adjudication.**  "
        "Signals marked ⚠️ are expanded automatically below.",
        icon="⚠️",
    )

st.divider()

if not filtered:
    st.info("No signals match the current filters.")
    st.stop()


# ─── Signal cards grouped by process step ────────────────────────────────────

step_buckets: dict[str | None, list[dict]] = defaultdict(list)
for s in filtered:
    step_buckets[s.get("process_step")].append(s)

for step_key, step_label in PROCESS_STEPS:
    bucket = step_buckets.get(step_key, [])
    if not bucket:
        continue

    worst_sev = min(
        (s.get("severity") for s in bucket if s.get("severity")),
        key=lambda sv: SEVERITY_ORDER.index(sv),
        default=None,
    )
    n_unc_step = sum(
        1 for s in bucket
        if (
            (s.get("severity_metacognition") or {}).get("grade") == "UNCERTAIN"
            or (s.get("impact_metacognition") or {}).get("grade") == "UNCERTAIN"
        ) and not s.get("_adj")
    )

    st.subheader(
        f"{SEVERITY_EMOJI.get(worst_sev, '⚪')} {step_label}"
        f"  ·  {len(bucket)} signal{'s' if len(bucket) != 1 else ''}"
        + (f"  ·  ⚠️ {n_unc_step} pending adjudication" if n_unc_step else "")
    )

    for sig in bucket:
        _render_signal_card(sig, run_dir)

    st.divider()


# ─── Footer ───────────────────────────────────────────────────────────────────

st.caption(
    "Supply Chain Risk Agent POC  ·  "
    "External signals: LLM pipeline  ·  Internal MES/QMS: rule engine  ·  "
    "Adjudications saved to `adjudications.json` in the run output directory"
)
