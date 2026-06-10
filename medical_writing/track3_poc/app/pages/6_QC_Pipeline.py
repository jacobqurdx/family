import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import config
from regulatory.framework_twin import FrameworkTwinManager
from qc.pipeline import QCPipeline

st.set_page_config(page_title="QC Pipeline", layout="wide")
role = st.session_state.get("session_role", config.SESSION_ROLE)

st.title("Five-Pass QC Pipeline")
st.caption("Consistency · Historical · Checklist · Metacognitive · Role routing")

spec = st.session_state.get("current_spec")
if spec is None:
    st.warning("No content specification loaded. Generate a spec first (page 4).")
    st.stop()

framework_id = st.sidebar.selectbox("Framework twin", FrameworkTwinManager().list_ids())
checklist_path = f"{config.CHECKLISTS_DIR}/eop2_checklist.json"

PASS_NAMES = {1: "Consistency", 2: "Historical", 3: "Checklist",
              4: "Metacognitive", 5: "Role routing"}

if st.button("Run QC Pipeline"):
    fw = FrameworkTwinManager().load(framework_id)
    spec, findings = QCPipeline(fw, checklist_path).run(spec)
    st.session_state["current_spec"] = spec
    st.session_state["qc_findings"] = findings

findings = st.session_state.get("qc_findings")
if findings is not None:
    status = "✅ PASSED" if spec.qc_passed else "❌ FAILED — blocking findings present"
    (st.success if spec.qc_passed else st.error)(f"QC result: {status}")

    blocking = [f for f in findings if f.severity == "blocking"]
    major = [f for f in findings if f.severity == "major"]
    minor = [f for f in findings if f.severity == "minor"]
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total", len(findings))
    c2.metric("Blocking", len(blocking))
    c3.metric("Major", len(major))
    c4.metric("Minor", len(minor))

    st.divider()
    for pass_no in sorted(PASS_NAMES):
        pass_findings = [f for f in findings if f.pass_number == pass_no]
        st.markdown(f"**Pass {pass_no} — {PASS_NAMES[pass_no]}** "
                    f"({len(pass_findings)} finding(s))")
        for f in pass_findings:
            sev_color = {"blocking": "red", "major": "orange", "minor": "blue"}.get(f.severity, "gray")
            st.markdown(f":{sev_color}[**{f.severity.upper()}**] `{f.category}` "
                        f"— §{f.section_id}")
            st.caption(f.description)
            if f.suggested_resolution:
                st.caption(f"→ {f.suggested_resolution}")
