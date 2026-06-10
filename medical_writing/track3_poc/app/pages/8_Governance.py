import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
import datetime
from governance.permissions import PermissionEngine, Permission
from governance.versioning import VersionManager

st.set_page_config(page_title="Governance", layout="wide")
role = st.session_state.get("session_role", config.SESSION_ROLE)
engine = PermissionEngine()
versions = VersionManager()

st.title("Governance — Permissions, Locking, Versioning")
st.caption("Simulated in POC. Full 21 CFR Part 11 compliance deferred to production.")

st.warning(
    "**POC Simulation Note:** Lock state and versioning are simulated. Role-based "
    "access is enforced in the UI but is not cryptographically signed. Full audit "
    "trail and 21 CFR Part 11 compliance are production requirements."
)

st.subheader(f"Current Session Role: {role.replace('_', ' ').title()}")
st.caption("Permissions for this role:")
perm_map = {
    "Content Twin": "content_twin",
    "Document Structure Twin": "structure_twin",
    "Document (owned sections)": "document_ra_sections",
}
for label, resource in perm_map.items():
    perms = engine.get_permissions(role, resource)
    perm_str = ", ".join(p.value for p in perms) if perms else "none"
    st.write(f"**{label}:** {perm_str}")

st.divider()
st.subheader("Document Locking")
spec = st.session_state.get("current_spec")
if spec is not None:
    st.write(f"Current spec: `{spec.spec_id}` | Status: "
             f"{'🔒 Locked (' + spec.version + ')' if spec.locked else '🔓 Unlocked'}")
    can_lock = engine.can(role, "document_ra_sections", Permission.LOCK)
    can_admin = engine.can(role, "document_ra_sections", Permission.ADMIN)
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        if st.button("Review Lock", disabled=not can_lock):
            versions.review_lock(spec, role)
            st.success("Review lock applied. Editing disabled until lock is released.")
    with col2:
        if st.button("Version Lock", disabled=not can_lock):
            versions.version_lock(spec, role)
            st.success(f"Version locked: {spec.version}. Twin snapshot recorded.")
    with col3:
        if st.button("Submission Lock", disabled=not can_admin,
                     help="Requires ADMIN (eCTD compile)."):
            versions.submission_lock(spec, role)
            st.success("Submission lock applied — compiled into eCTD.")
    with col4:
        if st.button("Release Lock", disabled=not can_admin):
            versions.release(spec)
            st.success("Lock released.")
    if not can_admin:
        st.caption(f"Submission lock & release require ADMIN — not available to {role}.")
else:
    st.info("No spec loaded. Generate a spec (page 4) to exercise locking.")

st.divider()
st.subheader("Audit Trail (Simulated)")
decisions = st.session_state.get("review_decisions")
if decisions:
    import pandas as pd
    df = pd.DataFrame([{
        "Decision ID": d.decision_id,
        "Section": d.section_id,
        "Role": d.reviewer_role,
        "Decision": d.decision,
        "From": (d.from_value or "")[:60],
        "To": (d.to_value or "")[:60],
        "Back-propagate": d.back_propagate,
        "Timestamp": d.decided_at.isoformat(),
    } for d in decisions])
    st.dataframe(df, use_container_width=True)
else:
    st.caption("No decisions recorded yet. Complete a review session first (page 7).")
