import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
from twins.registry import TwinRegistry
from twins.content.manager import ContentTwinManager
from twins.structure.manager import StructureTwinManager

st.set_page_config(page_title="Twin Registry", layout="wide")
role = st.session_state.get("session_role", config.SESSION_ROLE)

st.title("Twin Registry")
st.caption("Every document draws from exactly two twins: a Content Twin (what we know) "
           "and a Document Structure Twin (how the document must be shaped).")

registry = TwinRegistry()
content_mgr = ContentTwinManager()
structure_mgr = StructureTwinManager()

st.subheader("Resolved Document Pairs")
st.caption("f(Content Twin, Document Structure Twin) → Document")
pairs = registry.list_pairs()
for p in pairs:
    cols = st.columns([3, 3, 3])
    cols[0].markdown(f"**{p.document_type}**")
    cols[1].markdown(f"🧬 Content: `{p.content_twin_id}`")
    cols[2].markdown(f"📐 Structure: `{p.structure_twin_id}`")

st.divider()
c1, c2 = st.columns(2)

with c1:
    st.subheader("🧬 Content Twins")
    st.caption("The 'what we know' store — program facts. Owned at molecule/trial tier.")
    for tid in content_mgr.list_ids():
        meta = content_mgr.meta(tid)
        st.markdown(
            f"**`{tid}`** · {meta.get('tier')} · "
            f"{meta.get('program_name') or meta.get('trial_name') or '—'} · "
            f"{meta['n_elements']} elements"
        )

with c2:
    st.subheader("📐 Document Structure Twins")
    st.caption("The 'how the doc must be shaped' store — section blueprints. "
               "Owned at company/framework tier.")
    for sid in structure_mgr.list_ids():
        t = structure_mgr.load(sid)
        st.markdown(
            f"**`{sid}`** · {t.regulatory_body} · "
            f"{t.document_type} · {len(t.sections)} sections"
            f"{' · 🔒 locked' if t.locked else ''}"
        )
