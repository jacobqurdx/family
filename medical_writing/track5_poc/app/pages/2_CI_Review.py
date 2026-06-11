import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd
import config
from labeling.ci_twin import CITwinManager
from labeling.labeling_models import ApprovedClaim
from labeling.ci_analysis import (
    achievability_table, strategic_insight, comparator_detail,
    list_comparators, reference_sections, SIGNAL_COLOR, CCDS_SECTIONS_5, ACTION_COLOR,
)
from workflow.session import SessionManager
from workflow.timer import StepTimer
from workflow.ui import render_stepper

st.set_page_config(page_title="CI Review", layout="wide")
render_stepper(active_step=2)

st.title("Competitive Intelligence Review")
st.caption("Strategic read of the approved-label landscape — editable before message map generation")

if "labeling_session" not in st.session_state:
    st.warning("No active session. Return to Operator Setup.")
    st.page_link("pages/1_Operator_Setup.py", label="← Operator Setup")
    st.stop()

session = st.session_state["labeling_session"]
mgr = CITwinManager()
ci_twin = mgr.load(session.ci_twin_id)
SIGNALS = ["HIGH", "MED", "GAP"]
ACTIONS = ["adopt", "adapt", "new", "skip"]


def _save():
    SessionManager().save(session)


tab_review, tab_library = st.tabs(["📋 Strategic Review", "✏️ Edit CI Library"])

# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — STRATEGIC REVIEW (program-specific overrides; do not touch the twin)
# ════════════════════════════════════════════════════════════════════════════
with tab_review:
    # Sync override dicts from widget state FIRST, so the achievability table and
    # the comparator chips render in lock-step with their dropdowns (Streamlit
    # widget state is the source of truth; reading it up front avoids a one-run lag).
    for _section in CCDS_SECTIONS_5:
        _sk = f"sig_{_section}"
        if _sk in st.session_state:
            _v = st.session_state[_sk]
            if _v == "(auto)":
                session.ci_signal_overrides.pop(_section, None)
            else:
                session.ci_signal_overrides[_section] = _v
        _ak = f"act_{_section}"
        if _ak in st.session_state:
            _v = st.session_state[_ak]
            if _v == "(auto)":
                session.ci_action_overrides.pop(_section, None)
            else:
                session.ci_action_overrides[_section] = _v

    # ── Strategic insight bar (editable) ─────────────────────────────────────
    generated_insight = strategic_insight(ci_twin, session.program_name.lower(), session.reference_label)
    effective_insight = session.strategic_insight_override or generated_insight
    st.markdown(
        f"<div style='background:#0b3d91;color:#fff;padding:14px 18px;border-radius:8px;"
        f"margin-bottom:8px;line-height:1.5;'>"
        f"<strong>Strategic read — {session.program_name} / {session.indication}"
        + ("  ·  ✏️ edited" if session.strategic_insight_override else "")
        + f":</strong><br>{effective_insight}</div>",
        unsafe_allow_html=True,
    )
    with st.expander("✏️ Edit strategic read"):
        new_insight = st.text_area("Strategic read", value=effective_insight, height=120,
                                   label_visibility="collapsed")
        c1, c2 = st.columns(2)
        if c1.button("Save insight"):
            session.strategic_insight_override = new_insight if new_insight != generated_insight else None
            _save()
            st.rerun()
        if c2.button("↺ Regenerate from CI twin"):
            session.strategic_insight_override = None
            _save()
            st.rerun()

    left, right = st.columns([1, 1.4])

    with left:
        st.subheader("Comparators")
        comparators = list_comparators(ci_twin)
        selected = st.radio(
            "Select a comparator to inspect", comparators,
            index=comparators.index(session.reference_label) if session.reference_label in comparators else 0,
        )
        st.session_state["selected_comparator"] = selected

        st.subheader("Achievability ceiling")
        st.caption("Strategic pre-read. Override any signal — saved to this session only.")
        table = achievability_table(ci_twin, signal_overrides=session.ci_signal_overrides)
        header = ("<table style='width:100%;border-collapse:collapse;font-size:0.85rem;'>"
                  "<tr style='text-align:left;border-bottom:1px solid #d0d7de;'>"
                  "<th>CCDS Section</th><th>Precedents</th><th>Our data</th><th>Signal</th></tr>")
        body = ""
        for r in table:
            sc = SIGNAL_COLOR.get(r["signal"], "gray")
            mark = " ✏️" if r.get("overridden") else ""
            body += (
                f"<tr style='border-bottom:1px solid #eaeef2;'>"
                f"<td style='padding:6px 4px;'>{r['section']}</td><td>{r['precedents']}</td>"
                f"<td>{r['our_data']}</td>"
                f"<td><span style='background:{sc};color:#fff;padding:1px 8px;border-radius:10px;"
                f"font-size:0.75rem;'>{r['signal']}</span>{mark}</td></tr>"
            )
        st.markdown(header + body + "</table>", unsafe_allow_html=True)

        with st.expander("Override signals"):
            st.caption("Change a signal to override the machine read for this session. "
                       "The table above updates immediately.")
            for r in table:
                opts = ["(auto)"] + SIGNALS
                cur = session.ci_signal_overrides.get(r["section"], "(auto)")
                # Widget state (synced at top of run) drives the value; index only
                # seeds the first render.
                st.selectbox(r["section"], opts, index=opts.index(cur) if cur in opts else 0,
                             key=f"sig_{r['section']}")
            if st.button("Save signal overrides"):
                _save()
                st.success("Signal overrides saved to session.")

    with right:
        detail = comparator_detail(ci_twin, selected, action_overrides=session.ci_action_overrides)
        header_claim = next((c for c in ci_twin.approved_claims if c.drug_name == selected), None)
        st.subheader(selected)
        if header_claim:
            st.caption(f"Approved {header_claim.approval_date} · {ci_twin.drug_class}")

        ACTION_LABEL = {"adopt": "🟣 ADOPT", "adapt": "🟡 ADAPT", "new": "🔵 NEW", "skip": "🔴 SKIP"}
        ACTION_HEX = {"purple": "#6f42c1", "amber": "#bf8700", "blue": "#0969da", "red": "#cf222e"}
        for d in detail:
            chip = ACTION_LABEL.get(d["action"], d["action"].upper())
            border = ACTION_HEX.get(d["color"], "#d0d7de")
            mark = " ✏️" if d.get("overridden") else ""
            st.markdown(
                f"<div style='border-left:4px solid {border};padding:8px 12px;margin:8px 0;"
                f"background:#fbfbfd;border-radius:4px;'>"
                f"<div style='font-size:0.8rem;color:#57606a;'>{d['section']} "
                f"<span style='float:right;'>{chip}{mark}</span></div>"
                f"<div style='font-family:Georgia,serif;margin-top:4px;'>{d['claim_text']}</div>"
                + (f"<div style='font-size:0.8rem;color:#bf8700;margin-top:6px;'>Δ {d['delta']}</div>"
                   if d['delta'] else "")
                + "</div>",
                unsafe_allow_html=True,
            )
            sect = d["section"]
            opts = ["(auto)"] + ACTIONS
            cur = session.ci_action_overrides.get(sect, "(auto)")
            # Widget state (synced at top of run) drives the value; index seeds first render.
            st.selectbox(f"Action for {sect}", opts,
                         index=opts.index(cur) if cur in opts else 0,
                         key=f"act_{sect}", label_visibility="collapsed")
        if st.button("Save action overrides"):
            _save()
            st.success("Action overrides saved — they flow into the Message Map decisions.")

    st.divider()
    if st.button("CI Reviewed — Generate Message Map →", type="primary"):
        session.phase = "map_review"
        StepTimer(session).mark("ci_review_complete")
        _save()
        st.page_link("pages/3_Message_Map_Review.py", label="Next: Message Map →", icon="➡️")

# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — EDIT CI LIBRARY (shared twin; deliberate, versioned)
# ════════════════════════════════════════════════════════════════════════════
with tab_library:
    st.warning(
        "⚠️ The CI library is **shared across every program** in this indication class. "
        "Edits here change the approved-label record for all of them and bump the twin "
        "version. In production this is curated by CI/RA (or auto-populated by LLM-13) "
        "with verification.",
        icon="⚠️",
    )
    st.caption(f"`{ci_twin.ci_twin_id}` · version {ci_twin.version} · "
               f"{len(ci_twin.approved_claims)} approved claims · "
               f"last updated {ci_twin.last_updated.strftime('%Y-%m-%d %H:%M')}")

    df = pd.DataFrame([{
        "claim_id": c.claim_id, "drug_name": c.drug_name, "label_section": c.label_section,
        "claim_text": c.claim_text, "evidence_standard": c.evidence_standard,
        "quantitative_threshold": c.quantitative_threshold or "",
        "approval_date": c.approval_date, "source_label": c.source_label,
        "source_url": c.source_url, "regulatory_notes": c.regulatory_notes,
    } for c in ci_twin.approved_claims])

    edited = st.data_editor(
        df, num_rows="dynamic", use_container_width=True, key="ci_editor",
        column_config={
            "label_section": st.column_config.SelectboxColumn(
                "label_section", options=CCDS_SECTIONS_5, required=True),
            "claim_text": st.column_config.TextColumn("claim_text", width="large"),
            "regulatory_notes": st.column_config.TextColumn("regulatory_notes", width="medium"),
        },
    )

    if st.button("💾 Save to CI library (bumps version)", type="primary"):
        new_claims, errors = [], []
        for i, row in edited.iterrows():
            cid = (row.get("claim_id") or "").strip()
            text = (row.get("claim_text") or "").strip()
            section = (row.get("label_section") or "").strip()
            if not (cid and text and section):
                errors.append(f"Row {i + 1}: claim_id, claim_text and label_section are required.")
                continue
            new_claims.append(ApprovedClaim(
                claim_id=cid, drug_name=(row.get("drug_name") or "").strip() or "unknown",
                indication=ci_twin.indication_class, label_section=section, claim_text=text,
                evidence_standard=(row.get("evidence_standard") or ""),
                quantitative_threshold=(row.get("quantitative_threshold") or None),
                approval_date=(row.get("approval_date") or ""),
                source_label=(row.get("source_label") or ""),
                source_url=(row.get("source_url") or ""),
                regulatory_notes=(row.get("regulatory_notes") or ""),
            ))
        ids = [c.claim_id for c in new_claims]
        if len(ids) != len(set(ids)):
            errors.append("Duplicate claim_id values — each claim needs a unique id.")
        if errors:
            for e in errors:
                st.error(e)
        else:
            ci_twin.approved_claims = new_claims
            mgr.save(ci_twin)   # rebuilds index + bumps version
            st.success(f"CI library saved — now version {ci_twin.version}, "
                       f"{len(new_claims)} claims. Reopen the Strategic Review tab to see the effect.")
            st.rerun()
