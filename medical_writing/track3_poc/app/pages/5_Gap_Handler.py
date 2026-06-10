import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
from generation.gap_handler import GapHandler

st.set_page_config(page_title="Gap Handler", layout="wide")
role = st.session_state.get("session_role", config.SESSION_ROLE)

st.title("Just-in-Time Gap Handler")
st.caption("Fill required elements missing from the content twin. Optionally "
           "back-propagate the value so future documents inherit it.")

spec = st.session_state.get("current_spec")
if spec is None:
    st.warning("No content specification loaded. Generate a spec first (page 4).")
    st.stop()

st.markdown(f"**Spec:** `{spec.spec_id}` · Content twin: `{spec.content_twin_id}`")

if not spec.gaps_detected:
    st.success("✅ No outstanding gaps. All required elements are populated.")
    if spec.gaps_filled:
        st.caption(f"Filled this session: {', '.join(spec.gaps_filled)}")
    st.stop()

st.warning(f"{len(spec.gaps_detected)} content gap(s) outstanding.")

handler = GapHandler()
for element_id in list(spec.gaps_detected):
    with st.form(f"gap_{element_id}"):
        st.markdown(f"**Missing element:** `{element_id}`")
        value = st.text_area("Provide the value", key=f"val_{element_id}")
        back_prop = st.checkbox(
            "Save to the content twin for future documents (back-propagate)",
            key=f"bp_{element_id}",
            help="Writes the value with provenance source='jit_gap_fill'.",
        )
        submitted = st.form_submit_button("Fill Gap")
        if submitted and value:
            handler.fill_gap(spec, element_id, value, filled_by=role,
                             back_propagate=back_prop)
            st.session_state["current_spec"] = spec
            msg = f"Filled `{element_id}`."
            if back_prop:
                msg += " Back-propagated to content twin (source=jit_gap_fill)."
            st.success(msg)
            st.rerun()

st.divider()
c1, c2 = st.columns(2)
c1.metric("Gaps remaining", len(spec.gaps_detected))
c2.metric("Gaps filled", len(spec.gaps_filled))
