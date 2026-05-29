import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
from core.twin import DigitalTwin
from core.schema import SchemaRegistry
from core.dependency import DependencyGraph
from core.models import ElementStatus
import config

st.title("Twin Editor")
st.caption("Guided authoring with dependency propagation")

twin_files = list(Path(config.TWINS_DIR).glob("*.json"))
twin_id = st.selectbox("Select Twin", [f.stem for f in twin_files])
twin = DigitalTwin.load(twin_id)
registry = SchemaRegistry()
schema = registry.get(twin.schema_id)
dep_graph = DependencyGraph(schema)

st.subheader(f"Trial: {twin.trial_name}")

required_ids = [el.id for el in schema.elements if el.required]
stats = twin.completeness(required_ids)
col1, col2, col3 = st.columns(3)
col1.metric("Elements Populated", f"{stats['populated']} / {stats['total']}")
col2.metric("Completeness", f"{stats['completeness_pct']}%")
col3.metric("Verified", f"{stats['verification_pct']}%")

st.divider()

st.subheader("Guided Authoring")
ordered_elements = registry.get_authoring_order(schema.id)

for el in ordered_elements:
    current = twin.get(el.id)
    current_val = current.value if current else None
    status = current.status if current else ElementStatus.EMPTY

    status_color = {
        ElementStatus.EMPTY: "🔴",
        ElementStatus.INFERRED: "🟡",
        ElementStatus.VERIFIED: "🟢",
        ElementStatus.OVERRIDDEN: "🟠"
    }.get(status, "⚪")

    with st.expander(f"{status_color} {el.label} ({el.id})", expanded=(status == ElementStatus.EMPTY)):
        st.caption(el.description)
        if el.depends_on:
            st.caption(f"Depends on: {', '.join(el.depends_on)} | Type: {el.dependency_type.value}")

        if el.data_type == "list":
            val_str = "\n".join(current_val) if current_val else ""
            new_val_str = st.text_area("Values (one per line)", val_str, key=f"ta_{el.id}")
            new_val = [v.strip() for v in new_val_str.splitlines() if v.strip()]
        else:
            new_val = st.text_input("Value", str(current_val) if current_val is not None else "", key=f"ti_{el.id}")

        if st.button("Set & Propagate", key=f"btn_{el.id}"):
            twin.set(el.id, new_val)
            result = dep_graph.propagate(el.id, twin)
            twin.save()
            if result.violations:
                for v in result.violations:
                    st.warning(v.message)
            if result.inferred_updates:
                for eid, val in result.inferred_updates.items():
                    twin.set_inferred(eid, val, el.id)
                    st.info(f"Inferred: {eid} → {val}")
                twin.save()
            st.success(f"Saved. {len(result.affected_elements)} downstream elements affected.")
            st.rerun()
