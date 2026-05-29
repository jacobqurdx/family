import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import streamlit as st
import pandas as pd

st.set_page_config(page_title="Twin Inspector", layout="wide")
st.title("Digital Twin Inspector")

twin_id = st.text_input("Twin ID", value=st.session_state.get("twin_id", "synth_phase2_trial"))

try:
    from core.twin import DigitalTwin
    twin = DigitalTwin.load(twin_id)
except Exception as e:
    st.error(f"Could not load twin '{twin_id}': {e}")
    st.stop()

st.info(f"Twin: **{twin.twin_id}** | Schema: {twin.schema_id} | Trial: {twin.trial_name}")

elements = twin.get_all()
if not elements:
    st.warning("Twin has no populated elements yet.")
    st.stop()

# Build dataframe
rows = []
for eid, el in elements.items():
    v = el.value
    if isinstance(v, dict):
        preview = f"[dict: {len(v)} keys]" if v else "[empty dict]"
    elif isinstance(v, list) and v and isinstance(v[0], dict):
        keys = list(v[0].keys())[:3]
        preview = f"[{len(v)} items · {', '.join(keys)}{'…' if len(v[0]) > 3 else ''}]"
    elif isinstance(v, list):
        preview = (str(v)[:97] + "…") if len(str(v)) > 100 else str(v)
    elif v is not None:
        preview = str(v)[:100]
    else:
        preview = ""
    rows.append({
        "Element ID": eid,
        "Status": el.status.value if el.status else "empty",
        "Value": preview,
        "Source": el.source or "",
        "Modified By": el.modified_by or "",
    })

df = pd.DataFrame(rows)

# Filter by status
status_filter = st.multiselect(
    "Filter by status",
    options=["verified", "inferred", "overridden", "empty"],
    default=["verified", "inferred", "overridden", "empty"],
)
if status_filter:
    df = df[df["Status"].isin(status_filter)]

st.dataframe(df, use_container_width=True)

# Completeness stats
st.subheader("Completeness")
all_ids = list(twin.get_all().keys())
stats = twin.completeness(all_ids)
col1, col2, col3 = st.columns(3)
col1.metric("Total Elements", stats["total"])
col2.metric("Populated", f"{stats['populated']} ({stats['completeness_pct']}%)")
col3.metric("Verified", f"{stats['verified']} ({stats['verification_pct']}%)")

# Element detail
st.subheader("Element Detail")
selected = st.selectbox("Select element", options=list(elements.keys()))
if selected:
    el = elements[selected]

    meta_col, val_col = st.columns([1, 2])
    with meta_col:
        st.markdown("**Metadata**")
        st.json({
            "element_id": el.element_id,
            "status": el.status.value if el.status else None,
            "source": el.source,
            "override_justification": el.override_justification,
            "last_modified": str(el.last_modified),
            "modified_by": el.modified_by,
        })

    with val_col:
        st.markdown("**Value**")
        val = el.value

        # ── Dict value: render as a table (e.g. SoA visit×activity matrix) ──
        if isinstance(val, dict) and val:
            # Check if all values are lists → render as visit×activity matrix
            if all(isinstance(v, list) for v in val.values()):
                # Build a checkmark matrix: rows = activities, cols = visits
                all_activities = []
                seen = set()
                for activities in val.values():
                    for a in activities:
                        if a not in seen:
                            all_activities.append(a)
                            seen.add(a)
                visits = list(val.keys())
                matrix_rows = []
                for activity in all_activities:
                    row = {"Activity": activity}
                    for visit in visits:
                        row[visit] = "✓" if activity in val[visit] else ""
                    matrix_rows.append(row)
                soa_df = pd.DataFrame(matrix_rows).set_index("Activity")
                st.dataframe(soa_df, use_container_width=True)
            else:
                st.json(val)

        # ── List-of-dicts value: render as a table (USDM structured objects) ──
        elif isinstance(val, list) and val and isinstance(val[0], dict):
            st.dataframe(pd.DataFrame(val), use_container_width=True)

        # ── List value: render as a bulleted list ──
        elif isinstance(val, list) and val:
            for item in val:
                st.markdown(f"- {item}")

        # ── Scalar ──
        elif val is not None:
            st.markdown(
                f"<div style='font-size:1rem; padding:8px; background:#f8f8f8; "
                f"border-radius:4px; border:1px solid #ddd;'>{val}</div>",
                unsafe_allow_html=True,
            )
        else:
            st.caption("_(empty)_")
