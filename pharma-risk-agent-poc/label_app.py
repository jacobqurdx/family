"""
SME Signal Labeling App
========================
Separate Streamlit app for subject-matter experts to apply ground-truth labels
to real signals. Produces a labeled dataset for evaluating and training the
5 assessment prompt skills: relevance, novelty, severity, impact, metacognition.

Usage:
    streamlit run label_app.py

Output:
    labeled_data/labels/{signal_id}.json   — one file per labeled signal
    labeled_data/export.jsonl              — full export for eval pipeline
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SIGNAL_DIR = Path(__file__).parent / "corpus" / "signals"
LABELED_DIR = Path(__file__).parent / "labeled_data" / "labels"
EXPORT_PATH = Path(__file__).parent / "labeled_data" / "export.jsonl"
PROFILE_PATH = Path(__file__).parent / "examples" / "risk_profile.yaml"

SEVERITY_OPTIONS = ["routine", "elevated", "high", "critical"]
RISK_VECTOR_OPTIONS = [
    "tariff_escalation",
    "cdmo_removal",
    "yield_disruption",
    "lead_time_extension",
    "unknown",
]
CONFIDENCE_OPTIONS = ["high", "medium", "low"]

STATUS_COLORS = {
    "complete": "🟢",
    "partial": "🟡",
    "skipped": "⚪",
    "flagged": "🔴",
    "unlabeled": "⬜",
}

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

@st.cache_data
def load_signals(signal_dir: Path) -> list[dict]:
    signals = []
    for f in sorted(signal_dir.glob("*.json")):
        try:
            d = json.loads(f.read_text())
            # normalise: some fixtures use 'content', agent uses 'raw_content'
            d.setdefault("raw_content", d.get("content", ""))
            d["_file"] = str(f)
            signals.append(d)
        except Exception:
            pass
    return signals


@st.cache_data
def load_parameters(profile_path: Path) -> list[str]:
    """Return ordered list of parameter names from the risk profile YAML."""
    try:
        import yaml  # type: ignore

        with open(profile_path) as fh:
            doc = yaml.safe_load(fh)
        params = []
        for p in doc.get("parameters", []):
            name = p.get("name")
            if name:
                params.append(name)
        return params
    except Exception:
        # Fallback if PyYAML not installed or file missing
        return [
            "Amide Coupling Step Yield",
            "Cyclisation Step Yield",
            "Batch Failure Rate",
            "SM-A Purchase Order Delivery Delay",
            "SDD Global Capacity Fraction",
            "SDD Facility Utilisation",
            "WuXi STA CDMO Risk",
            "CN Section 301 Tariff — API Starting Materials",
        ]


def load_label(signal_id: str) -> dict | None:
    path = LABELED_DIR / f"{signal_id}.json"
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            return None
    return None


def save_label(record: dict) -> None:
    LABELED_DIR.mkdir(parents=True, exist_ok=True)
    signal_id = record["signal_id"]
    path = LABELED_DIR / f"{signal_id}.json"
    path.write_text(json.dumps(record, indent=2))
    # Invalidate any cached status
    st.cache_data.clear()


def export_all_labels() -> int:
    """Write combined JSONL export. Returns count written."""
    LABELED_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    for f in sorted(LABELED_DIR.glob("*.json")):
        try:
            records.append(json.loads(f.read_text()))
        except Exception:
            pass
    EXPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    EXPORT_PATH.write_text("\n".join(json.dumps(r) for r in records))
    return len(records)


def get_label_status(signal_id: str) -> str:
    rec = load_label(signal_id)
    if rec is None:
        return "unlabeled"
    return rec.get("status", "partial")


# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Signal Labeling — Pharma Risk Agent",
    page_icon="🏷️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.step-header { font-size: 1.1rem; font-weight: 700; margin-bottom: 0.2rem; }
.step-desc   { font-size: 0.82rem; color: #888; margin-bottom: 0.8rem; }
.signal-meta { font-size: 0.8rem; color: #777; }
.label-saved { background:#1a3a1a; border:1px solid #2d6a2d; border-radius:6px;
               padding:6px 12px; color:#7fcf7f; font-size:0.85rem; }
div[data-testid="stExpander"] > div { padding: 0.5rem 0; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar — labeler identity + signal browser
# ---------------------------------------------------------------------------

with st.sidebar:
    st.title("🏷️ Signal Labeler")
    st.caption("Pharma Risk Agent · Ground-truth dataset")

    st.divider()

    labeler = st.text_input(
        "Your name / initials",
        value=st.session_state.get("labeler", ""),
        placeholder="e.g. JA, Dr. Smith",
        help="Stored on every label you save.",
    )
    st.session_state["labeler"] = labeler

    # Signal directory override
    with st.expander("⚙️ Settings", expanded=False):
        custom_dir = st.text_input(
            "Signal directory",
            value=str(SIGNAL_DIR),
            help="Absolute path to a directory of signal JSON files.",
        )
        signal_dir = Path(custom_dir) if custom_dir else SIGNAL_DIR

    st.divider()

    signals = load_signals(signal_dir if signal_dir.exists() else SIGNAL_DIR)
    parameters = load_parameters(PROFILE_PATH)

    if not signals:
        st.error("No signals found. Check the signal directory path.")
        st.stop()

    # Build status list for sidebar
    st.markdown(f"**{len(signals)} signals**")

    filter_status = st.multiselect(
        "Filter by status",
        options=["unlabeled", "partial", "complete", "flagged", "skipped"],
        default=[],
        placeholder="Show all",
    )

    st.divider()

    signal_options = []
    for s in signals:
        sid = s["id"]
        status = get_label_status(sid)
        if filter_status and status not in filter_status:
            continue
        icon = STATUS_COLORS.get(status, "⬜")
        signal_options.append((f"{icon} {sid}", sid))

    if not signal_options:
        st.info("No signals match the filter.")
        st.stop()

    labels_list = [label for label, _ in signal_options]
    ids_list    = [sid   for _, sid   in signal_options]

    # Preserve selection across reruns
    default_idx = 0
    if "selected_signal_id" in st.session_state:
        try:
            default_idx = ids_list.index(st.session_state["selected_signal_id"])
        except ValueError:
            default_idx = 0

    selected_label = st.radio(
        "Select signal",
        options=labels_list,
        index=default_idx,
        label_visibility="collapsed",
    )
    selected_idx = labels_list.index(selected_label)
    selected_id  = ids_list[selected_idx]
    st.session_state["selected_signal_id"] = selected_id

    st.divider()

    # Progress summary
    statuses = [get_label_status(s["id"]) for s in signals]
    n_complete = statuses.count("complete")
    n_partial  = statuses.count("partial")
    n_flagged  = statuses.count("flagged")
    n_skip     = statuses.count("skipped")
    n_unlabeled = statuses.count("unlabeled")

    st.markdown(f"""
🟢 Complete: **{n_complete}**
🟡 Partial: **{n_partial}**
🔴 Flagged: **{n_flagged}**
⚪ Skipped: **{n_skip}**
⬜ Unlabeled: **{n_unlabeled}**
""")
    st.progress(n_complete / len(signals))

    if st.button("📥 Export JSONL", use_container_width=True):
        n = export_all_labels()
        st.success(f"Exported {n} records → labeled_data/export.jsonl")

# ---------------------------------------------------------------------------
# Main area — labeling form
# ---------------------------------------------------------------------------

signal = next((s for s in signals if s["id"] == selected_id), None)
if signal is None:
    st.error("Signal not found.")
    st.stop()

existing = load_label(selected_id) or {}
ex_labels = existing.get("labels", {})

# ---- Signal header --------------------------------------------------------
col_h1, col_h2 = st.columns([5, 1])
with col_h1:
    st.markdown(f"## {signal['id']}")
    st.markdown(
        f"<span class='signal-meta'>Source: **{signal.get('source_name','?')}** · "
        f"{signal.get('collected_at','')[:10]} · "
        f"<a href='{signal.get('source_url','')}' target='_blank'>link</a></span>",
        unsafe_allow_html=True,
    )
with col_h2:
    current_status = existing.get("status", "unlabeled")
    st.markdown(f"**Status:** {STATUS_COLORS.get(current_status,'')} {current_status}")

# ---- Full signal text -------------------------------------------------------
with st.expander("📄 Full signal text", expanded=True):
    st.markdown(
        f"<div style='white-space: pre-wrap; word-wrap: break-word; font-family: "
        f"monospace; font-size:0.85rem; line-height:1.5; max-height:320px; "
        f"overflow-y:auto; background:#111; padding:12px; border-radius:6px; "
        f"overflow-x: hidden;'>{signal.get('raw_content', signal.get('content',''))}</div>",
        unsafe_allow_html=True,
    )

st.divider()

# ---- Labeling form ----------------------------------------------------------
st.markdown("### Labels")
st.caption(
    "Work through each step in order. Steps that are gated (e.g. novelty requires "
    "relevance=True) are shown greyed-out until the gate is met."
)

notes_global = st.text_area(
    "Notes / comments (optional)",
    value=existing.get("notes", ""),
    placeholder="Any caveats, edge cases, or flags for this signal…",
    height=60,
)

# ---- STEP 1 · RELEVANCE -----------------------------------------------------
st.markdown("---")
st.markdown("<div class='step-header'>① Relevance</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='step-desc'>Does this signal contain information relevant to any "
    "monitored MRP parameter? Gate: must be TRUE to proceed.</div>",
    unsafe_allow_html=True,
)

ex_rel = ex_labels.get("relevance", {})
rel_col1, rel_col2 = st.columns([1, 2])
with rel_col1:
    is_relevant = st.radio(
        "Is relevant?",
        options=["True", "False"],
        index=0 if ex_rel.get("is_relevant", True) else 1,
        key="rel_is_relevant",
        horizontal=True,
    )
    is_relevant_bool = is_relevant == "True"

with rel_col2:
    relevant_parameters = st.multiselect(
        "Relevant parameters",
        options=parameters,
        default=[p for p in ex_rel.get("relevant_parameters", []) if p in parameters],
        key="rel_params",
        disabled=not is_relevant_bool,
        help="Select all parameters this signal could affect.",
    )

relevance_reasoning = st.text_area(
    "Relevance reasoning",
    value=ex_rel.get("relevance_reasoning", ""),
    height=80,
    key="rel_reasoning",
    placeholder="Why is this signal relevant (or not) to the monitored parameters?",
)

# ---- STEP 2 · NOVELTY -------------------------------------------------------
st.markdown("---")
st.markdown("<div class='step-header'>② Novelty</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='step-desc'>Does this signal contain new information not already "
    "reflected in the known signal state? Gate: must be TRUE to proceed.</div>",
    unsafe_allow_html=True,
)

novelty_disabled = not is_relevant_bool
ex_nov = ex_labels.get("novelty", {})

nov_col1, nov_col2 = st.columns([1, 3])
with nov_col1:
    is_novel = st.radio(
        "Is novel?",
        options=["True", "False"],
        index=0 if ex_nov.get("is_novel", True) else 1,
        key="nov_is_novel",
        horizontal=True,
        disabled=novelty_disabled,
    )
    is_novel_bool = (is_novel == "True") and is_relevant_bool

with nov_col2:
    if novelty_disabled:
        st.info("⬆️ Mark signal as relevant first.")

novelty_reasoning = st.text_area(
    "Novelty reasoning",
    value=ex_nov.get("novelty_reasoning", ""),
    height=80,
    key="nov_reasoning",
    placeholder="What new information does this add vs the last known state?",
    disabled=novelty_disabled,
)

# ---- STEP 3 · SEVERITY -------------------------------------------------------
st.markdown("---")
st.markdown("<div class='step-header'>③ Severity</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='step-desc'>How severe is the business impact? "
    "routine → elevated → high → critical. "
    "Impact step only runs for high/critical.</div>",
    unsafe_allow_html=True,
)

severity_disabled = not is_novel_bool
ex_sev = ex_labels.get("severity", {})

sev_col1, sev_col2, sev_col3 = st.columns([2, 2, 2])
with sev_col1:
    saved_sev = ex_sev.get("severity", "routine")
    sev_idx = SEVERITY_OPTIONS.index(saved_sev) if saved_sev in SEVERITY_OPTIONS else 0
    severity = st.selectbox(
        "Severity tier",
        options=SEVERITY_OPTIONS,
        index=sev_idx,
        key="sev_tier",
        disabled=severity_disabled,
    )
with sev_col2:
    saved_rvt = ex_sev.get("risk_vector_type", "unknown")
    rvt_idx = RISK_VECTOR_OPTIONS.index(saved_rvt) if saved_rvt in RISK_VECTOR_OPTIONS else 4
    risk_vector = st.selectbox(
        "Risk vector type",
        options=RISK_VECTOR_OPTIONS,
        index=rvt_idx,
        key="sev_rvt",
        disabled=severity_disabled,
    )
with sev_col3:
    affected_geography = st.text_input(
        "Affected geography (optional)",
        value=ex_sev.get("affected_geography", ""),
        placeholder="e.g. China, India, EU",
        key="sev_geo",
        disabled=severity_disabled,
    )

severity_reasoning = st.text_area(
    "Severity reasoning",
    value=ex_sev.get("severity_reasoning", ""),
    height=80,
    key="sev_reasoning",
    placeholder="Explain your severity assignment citing specific figures or conditions in the signal.",
    disabled=severity_disabled,
)

if severity_disabled:
    st.info("⬆️ Mark signal as novel first.")

# ---- STEP 4 · IMPACT ---------------------------------------------------------
st.markdown("---")
st.markdown("<div class='step-header'>④ Impact</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='step-desc'>Quantify the cost and timeline impact. "
    "Only required for HIGH or CRITICAL signals. "
    "Use 'Qualitative only' if no numeric estimate is supportable.</div>",
    unsafe_allow_html=True,
)

impact_applicable = (not severity_disabled) and (severity in ("high", "critical"))
impact_disabled   = not impact_applicable
ex_imp = ex_labels.get("impact", {})

if not impact_disabled:
    imp_col1, imp_col2, imp_col3 = st.columns([2, 2, 2])
    with imp_col1:
        qualitative_only = st.checkbox(
            "Qualitative only (no $ estimate)",
            value=ex_imp.get("qualitative_only", False),
            key="imp_qualonly",
        )
    with imp_col2:
        cost_impact = st.number_input(
            "Estimated cost impact ($/kg API)",
            min_value=0.0,
            max_value=10000.0,
            value=float(ex_imp.get("estimated_cost_impact_per_kg") or 0.0),
            step=10.0,
            format="%.2f",
            key="imp_cost",
            disabled=qualitative_only,
            help="Best estimate of $/kg API increase. 0 = unknown.",
        )
    with imp_col3:
        confidence = st.selectbox(
            "Confidence",
            options=CONFIDENCE_OPTIONS,
            index=CONFIDENCE_OPTIONS.index(ex_imp.get("confidence", "medium")),
            key="imp_conf",
        )

    imp_col4, imp_col5 = st.columns([2, 4])
    with imp_col4:
        timeline_weeks = st.number_input(
            "Timeline impact (weeks)",
            min_value=0,
            max_value=104,
            value=int(ex_imp.get("estimated_timeline_impact_weeks") or 0),
            step=1,
            key="imp_weeks",
            help="Supply disruption or lead-time extension in weeks. 0 = no timeline impact.",
        )
    with imp_col5:
        impact_reasoning = st.text_area(
            "Impact reasoning",
            value=ex_imp.get("estimated_cost_impact_reasoning", ""),
            height=80,
            key="imp_reasoning",
            placeholder="Cite the MRP sensitivity data or scenario that underpins your estimate.",
        )
else:
    st.info(
        "⬆️ Impact step only applies to HIGH or CRITICAL signals. "
        + ("Mark signal as novel first." if severity_disabled else f"Current severity: **{severity}**.")
    )
    qualitative_only = False
    cost_impact      = 0.0
    confidence       = "low"
    timeline_weeks   = 0
    impact_reasoning = ""

# ---- STEP 5 · METACOGNITION -------------------------------------------------
st.markdown("---")
st.markdown("<div class='step-header'>⑤ Metacognition</div>", unsafe_allow_html=True)
st.markdown(
    "<div class='step-desc'>Would an LLM assessor be CERTAIN or UNCERTAIN about "
    "its severity/impact judgment for this signal? UNCERTAIN = the signal is ambiguous, "
    "contradictory, too thin, or requires specialist knowledge to interpret.</div>",
    unsafe_allow_html=True,
)

meta_disabled = severity_disabled  # need at least severity to have run
ex_meta = ex_labels.get("metacognition", {})

meta_col1, meta_col2 = st.columns(2)

with meta_col1:
    st.markdown("**Severity metacognition**")
    sev_grade = st.radio(
        "Severity grade",
        options=["CERTAIN", "UNCERTAIN"],
        index=0 if ex_meta.get("severity_grade", "CERTAIN") == "CERTAIN" else 1,
        key="meta_sev_grade",
        horizontal=True,
        disabled=meta_disabled,
    )
    sev_flags_raw = st.text_area(
        "Severity uncertainty flags",
        value="\n".join(ex_meta.get("severity_uncertainty_flags", [])),
        height=70,
        key="meta_sev_flags",
        placeholder="One flag per line, e.g.:\nSignal is a proposed rule, not enacted\nNo confirmed volume figures",
        disabled=meta_disabled or sev_grade == "CERTAIN",
    )

with meta_col2:
    st.markdown("**Impact metacognition**")
    imp_grade = st.radio(
        "Impact grade",
        options=["CERTAIN", "UNCERTAIN"],
        index=0 if ex_meta.get("impact_grade", "CERTAIN") == "CERTAIN" else 1,
        key="meta_imp_grade",
        horizontal=True,
        disabled=meta_disabled or not impact_applicable,
    )
    imp_flags_raw = st.text_area(
        "Impact uncertainty flags",
        value="\n".join(ex_meta.get("impact_uncertainty_flags", [])),
        height=70,
        key="meta_imp_flags",
        placeholder="One flag per line",
        disabled=meta_disabled or not impact_applicable or imp_grade == "CERTAIN",
    )

meta_reasoning = st.text_area(
    "Metacognition reasoning (optional)",
    value=ex_meta.get("reasoning", ""),
    height=70,
    key="meta_reasoning",
    placeholder="Explain any ambiguity or why this signal would be hard for the LLM to score.",
    disabled=meta_disabled,
)

if meta_disabled:
    st.info("⬆️ Complete severity labeling first.")

# ---------------------------------------------------------------------------
# Save / Skip / Flag actions
# ---------------------------------------------------------------------------

st.markdown("---")

act_col1, act_col2, act_col3, act_col4 = st.columns([2, 1, 1, 3])

with act_col1:
    save_clicked = st.button("💾 Save labels", type="primary", use_container_width=True)
with act_col2:
    skip_clicked = st.button("⏭ Skip", use_container_width=True)
with act_col3:
    flag_clicked = st.button("🔴 Flag", use_container_width=True,
                              help="Flag this signal for later review or discussion.")
with act_col4:
    if existing.get("status") == "complete":
        st.markdown("🟢 **Labels saved** — editing will update the record.")

# ---- determine completeness for status field --------------------------------
def _is_complete() -> bool:
    if not is_relevant_bool:
        return True  # relevance=False is a complete label (short-circuit)
    if not is_novel_bool:
        return bool(relevance_reasoning.strip())
    if severity_disabled:
        return False
    if severity in ("high", "critical") and not impact_applicable:
        return False
    return bool(severity_reasoning.strip())


if save_clicked or skip_clicked or flag_clicked:
    if not labeler.strip():
        st.error("Please enter your name / initials in the sidebar before saving.")
        st.stop()

    now = datetime.now(timezone.utc).isoformat()
    status = (
        "skipped" if skip_clicked
        else "flagged" if flag_clicked
        else ("complete" if _is_complete() else "partial")
    )

    # Build impact block only if applicable
    impact_block: dict | None = None
    if impact_applicable and not impact_disabled:
        impact_block = {
            "qualitative_only": qualitative_only,
            "estimated_cost_impact_per_kg": None if qualitative_only else (cost_impact or None),
            "estimated_timeline_impact_weeks": timeline_weeks or None,
            "confidence": confidence,
            "estimated_cost_impact_reasoning": impact_reasoning,
        }

    # Build metacognition block only if severity was labeled
    meta_block: dict | None = None
    if not meta_disabled:
        meta_block = {
            "severity_grade": sev_grade,
            "severity_uncertainty_flags": [
                f.strip() for f in sev_flags_raw.splitlines() if f.strip()
            ],
            "impact_grade": imp_grade if impact_applicable else None,
            "impact_uncertainty_flags": (
                [f.strip() for f in imp_flags_raw.splitlines() if f.strip()]
                if impact_applicable else []
            ),
            "reasoning": meta_reasoning,
        }

    record = {
        "signal_id": signal["id"],
        "signal": {
            "id": signal["id"],
            "source_name": signal.get("source_name"),
            "source_url": signal.get("source_url"),
            "collected_at": signal.get("collected_at"),
            "raw_content": signal.get("raw_content", signal.get("content", "")),
        },
        "labeler": labeler.strip(),
        "labeled_at": now,
        "status": status,
        "notes": notes_global,
        "labels": {
            "relevance": {
                "is_relevant": is_relevant_bool,
                "relevant_parameters": relevant_parameters if is_relevant_bool else [],
                "relevance_reasoning": relevance_reasoning,
            },
            "novelty": (
                {
                    "is_novel": is_novel_bool,
                    "novelty_reasoning": novelty_reasoning,
                }
                if is_relevant_bool else None
            ),
            "severity": (
                {
                    "severity": severity,
                    "risk_vector_type": risk_vector,
                    "affected_geography": affected_geography or None,
                    "severity_reasoning": severity_reasoning,
                }
                if is_novel_bool else None
            ),
            "impact": impact_block,
            "metacognition": meta_block,
        },
    }

    save_label(record)
    st.success(f"✅ Saved ({status}) — {signal['id']} · {labeler}")
    st.rerun()

# ---------------------------------------------------------------------------
# Footer — keyboard hint
# ---------------------------------------------------------------------------
st.markdown(
    "<div style='color:#555; font-size:0.75rem; margin-top:2rem;'>"
    "Tip: use the sidebar to jump between signals. "
    "Labels are saved per-signal to <code>labeled_data/labels/</code>. "
    "Click <b>Export JSONL</b> in the sidebar when ready to hand off to the eval pipeline."
    "</div>",
    unsafe_allow_html=True,
)
