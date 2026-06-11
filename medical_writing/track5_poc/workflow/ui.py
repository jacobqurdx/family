"""
Shared UI helpers for the v2 wizard-first / hub-after navigation.

render_stepper() draws the 8-step wizard progress bar shown on pages 1-8.
step_rows() computes per-step status for the Hub (page 0). Status is derived
from the session phase plus concrete signals in st.session_state (generated map,
QC findings, draft, draft review, survey).
"""
import streamlit as st

# (num, title, page path relative to app/) — the 8 wizard steps
WIZARD_STEPS = [
    (1, "Operator Setup", "pages/1_Operator_Setup.py"),
    (2, "CI Review", "pages/2_CI_Review.py"),
    (3, "Message Map", "pages/3_Message_Map_Review.py"),
    (4, "QC Pipeline", "pages/4_QC_Pipeline.py"),
    (5, "Lock", "pages/5_Message_Map_Lock.py"),
    (6, "Draft Bridge", "pages/6_Draft_Bridge.py"),
    (7, "Claim Inspector", "pages/7_Claim_Inspector.py"),
    (8, "Survey", "pages/8_Survey.py"),
]

_STATUS_COLOR = {
    "done": ("#1a7f37", "#ffffff"),       # green
    "locked": ("#1a7f37", "#ffffff"),     # green + lock
    "active": ("#0969da", "#ffffff"),     # blue
    "attention": ("#bf8700", "#ffffff"),  # amber
    "todo": ("#e1e4e8", "#57606a"),       # grey
}


def _ss():
    return st.session_state


def _has_blocking_qc() -> bool:
    findings = _ss().get("qc_findings") or []
    return any(getattr(f, "severity", None) == "blocking" for f in findings)


def compute_status(session, active_step: int = None) -> list:
    """Return [{num, title, page, status, detail}] for all 8 steps."""
    ss = _ss()
    mm = ss.get("message_map")
    timings = {t["step"] for t in (session.step_timings if session else [])}

    done = {
        1: session is not None,
        2: "ci_review_complete" in timings or bool(session and session.map_id),
        3: bool(session and session.map_id) and mm is not None,
        4: ss.get("qc_findings") is not None,
        5: bool(mm is not None and getattr(mm, "locked", False)),
        6: ss.get("label_draft") is not None or bool(session and session.draft_id),
        7: ss.get("draft_review") is not None
           or bool(session and session.draft_overall_quality_rating is not None),
        8: bool(session and session.survey_response),
    }
    details = {
        1: "Program, reference label and simulation mode",
        2: "Competitive intelligence read-out",
        3: "Claim-by-claim message map",
        4: "Labeling checklist QC",
        5: "Lock the message map",
        6: "Locked claims → generated prose",
        7: "Claim-by-claim draft inspection",
        8: "Post-session ratings",
    }

    rows = []
    for num, title, page in WIZARD_STEPS:
        if num == active_step:
            status = "active"
        elif num == 5 and done[5]:
            status = "locked"
        elif num == 4 and ss.get("qc_findings") is not None and _has_blocking_qc():
            status = "attention"
        elif done[num]:
            status = "done"
        else:
            status = "todo"
        rows.append({"num": num, "title": title, "page": page,
                     "status": status, "detail": details[num]})
    return rows


def render_stepper(active_step: int):
    """Compact 8-step progress bar for pages 1-8."""
    session = _ss().get("labeling_session")
    rows = compute_status(session, active_step=active_step)
    chips = []
    for r in rows:
        bg, fg = _STATUS_COLOR[r["status"]]
        mark = "🔒" if r["status"] == "locked" else (
            "✓" if r["status"] == "done" else (
                "⚠" if r["status"] == "attention" else str(r["num"])))
        chips.append(
            f"<span style='display:inline-block;padding:3px 10px;margin:2px;border-radius:12px;"
            f"background:{bg};color:{fg};font-size:0.78rem;white-space:nowrap;'>"
            f"{mark} {r['title']}</span>"
        )
    st.markdown(
        "<div style='display:flex;flex-wrap:wrap;gap:2px;margin-bottom:8px;'>"
        + "".join(chips) + "</div>",
        unsafe_allow_html=True,
    )
    st.markdown(
        "<a href='/Hub' target='_self' style='font-size:0.8rem;'>↩ Back to Hub</a>",
        unsafe_allow_html=True,
    )
