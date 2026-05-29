import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import datetime
import streamlit as st
import pandas as pd

st.set_page_config(page_title="Layer Verification", layout="wide")
st.title("Layer Verification")

if "ingestion_session_id" not in st.session_state:
    st.warning("No active ingestion session. Please go to **1 Protocol Upload** first.")
    st.stop()

session_id = st.session_state["ingestion_session_id"]
use_stub = st.session_state.get("use_stub", True)

try:
    from ingestion.ingestion_session import IngestionSessionManager
    from ingestion.layer_runner import LayerRunner
    from usdm.graph_walk import LAYER_METADATA, get_layer_nodes

    mgr = IngestionSessionManager()
    session = mgr.load(session_id)
except Exception as e:
    st.error(f"Could not load session {session_id}: {e}")
    st.stop()

st.info(
    f"Session: **{session_id}** | Document: {session.document_filename} "
    f"| Layer {session.current_layer}/{session.total_layers}"
)

if session.status == "complete":
    st.success("All layers complete! Navigate to **3 Twin Inspector** to review the populated twin.")
    st.stop()

layer_idx = session.current_layer
layer_meta = LAYER_METADATA[layer_idx]
nodes = get_layer_nodes(layer_idx)

st.subheader(f"Layer {layer_idx}: {layer_meta['name']}")
st.markdown(f"*{layer_meta['description']}*")
st.caption(layer_meta['extraction_note'])

# ── Run extraction ──────────────────────────────────────────────────────────
if st.button(f"Extract Layer {layer_idx}", type="primary"):
    runner = LayerRunner(use_stub=use_stub)
    result = runner.run_extraction(session, None)
    st.session_state[f"extraction_result_{layer_idx}"] = result
    mgr.save(session)
    st.success(f"Extracted {len(result.extracted_nodes)} nodes from Layer {layer_idx}.")
    st.rerun()

# ── Restore result from session if page reloads ─────────────────────────────
result_key = f"extraction_result_{layer_idx}"
if result_key not in st.session_state:
    extraction_results = dict(session.extraction_results)
    if layer_idx in extraction_results:
        from ingestion.verification import ExtractedItem, LayerExtractionResult
        items = [ExtractedItem(**d) for d in extraction_results[layer_idx]]
        st.session_state[result_key] = type("R", (), {
            "extracted_nodes": items,
            "layer_index": layer_idx,
            "layer_name": layer_meta["name"],
        })()

# ── Verification UI ─────────────────────────────────────────────────────────
if result_key in st.session_state:
    result = st.session_state[result_key]

    from ingestion.verification import VerificationDecision, NodeVerificationRecord, ExtractedItem

    st.subheader("Verify Extracted Values")

    # Helper: find the confirmed (or best available) value for a parent node
    def _parent_display_value(parent_id: str) -> str:
        val = session.confirmed_values.get(parent_id)
        if val is None:
            return "_not yet confirmed_"
        if isinstance(val, list):
            if len(val) == 0:
                return "_empty list_"
            # USDM structured objects: summarise by key field
            if isinstance(val[0], dict):
                # Try common name/label fields
                for key in ("name", "text", "identifier", "level"):
                    if key in val[0]:
                        names = [str(v.get(key, "?")) for v in val[:3]]
                        suffix = f" … (+{len(val) - 3} more)" if len(val) > 3 else ""
                        return " · ".join(names) + suffix
                return f"[{len(val)} items]"
            if len(val) <= 3:
                return " · ".join(str(v) for v in val)
            return " · ".join(str(v) for v in val[:3]) + f" … (+{len(val) - 3} more)"
        return str(val)

    verification_records = []

    for i, node in enumerate(nodes):
        extracted_item = (
            result.extracted_nodes[i]
            if i < len(result.extracted_nodes)
            else ExtractedItem(item_index=i)
        )

        has_value = extracted_item.value is not None
        has_quote = bool(extracted_item.source_quote)

        with st.expander(
            f"**{node.label}** `{node.id}` — cardinality {node.cardinality}",
            expanded=(not has_value),
        ):
            # ── Three columns ────────────────────────────────────────────────
            col_prov, col_decision, col_source = st.columns([2, 2, 3])

            # ── Column 1: Provenance chain ──────────────────────────────────
            with col_prov:
                st.markdown("##### Ancestor Context")
                _predicates = getattr(node, "parent_predicates", {}) or {}
                if _predicates:
                    for parent_id, predicate in _predicates.items():
                        parent_val = _parent_display_value(parent_id)
                        # Render: PARENT_LABEL —[PREDICATE]→ this node
                        st.markdown(
                            f"<div style='"
                            f"border-left: 3px solid #4A90D9; "
                            f"padding: 6px 10px; "
                            f"margin-bottom: 8px; "
                            f"background: #f0f6ff; "
                            f"border-radius: 0 4px 4px 0;"
                            f"'>"
                            f"<span style='font-size:0.75rem; color:#666; font-weight:600; "
                            f"text-transform:uppercase; letter-spacing:0.05em;'>"
                            f"{parent_id.replace('_', ' ')}"
                            f"</span><br/>"
                            f"<span style='font-size:0.72rem; color:#4A90D9; font-weight:700; "
                            f"letter-spacing:0.04em;'>⟶ {predicate}</span><br/>"
                            f"<span style='font-size:0.88rem; color:#1a1a1a;'>{parent_val}</span>"
                            f"</div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.caption("No ancestor constraints for this node (root layer).")

            # ── Column 2: Extracted value + decision ────────────────────────
            with col_decision:
                st.markdown("##### Extracted Value")
                if has_value:
                    display_val = extracted_item.value
                    if isinstance(display_val, list) and display_val and isinstance(display_val[0], dict):
                        # USDM structured objects → render as compact table
                        st.dataframe(
                            pd.DataFrame(display_val),
                            use_container_width=True,
                            height=min(200 + len(display_val) * 30, 400),
                        )
                    elif isinstance(display_val, list):
                        display_str = "\n".join(f"• {v}" for v in display_val)
                        st.markdown(
                            f"<div style='"
                            f"border: 1px solid #d0d0d0; "
                            f"border-radius: 5px; "
                            f"padding: 8px 10px; "
                            f"background: #f8f8f8; "
                            f"font-size: 0.9rem; "
                            f"line-height: 1.55; "
                            f"color: #1a1a1a; "
                            f"white-space: pre-wrap; "
                            f"word-break: break-word;"
                            f"'>{display_str}</div>",
                            unsafe_allow_html=True,
                        )
                    else:
                        st.markdown(
                            f"<div style='"
                            f"border: 1px solid #d0d0d0; "
                            f"border-radius: 5px; "
                            f"padding: 8px 10px; "
                            f"background: #f8f8f8; "
                            f"font-size: 0.9rem; "
                            f"line-height: 1.55; "
                            f"color: #1a1a1a; "
                            f"white-space: pre-wrap; "
                            f"word-break: break-word;"
                            f"'>{display_val}</div>",
                            unsafe_allow_html=True,
                        )
                else:
                    st.warning("No value extracted.")

                confidence_pct = f"{extracted_item.confidence:.0%}"
                st.caption(f"Confidence: {confidence_pct}")

                if extracted_item.extraction_notes:
                    with st.expander("Extraction notes", expanded=False):
                        st.write(extracted_item.extraction_notes)

                st.markdown("##### Decision")
                decision = st.radio(
                    "Decision",
                    options=["confirmed", "corrected", "overridden", "missing"],
                    key=f"dec_{layer_idx}_{node.id}",
                    index=0 if has_value else 3,
                    label_visibility="collapsed",
                )

                corrected_val = None
                justification = None
                if decision in ("corrected", "overridden", "missing"):
                    corrected_val = st.text_input(
                        "Corrected / override value",
                        key=f"corr_{layer_idx}_{node.id}",
                        placeholder="Enter the correct value…",
                    )
                    if decision == "overridden":
                        justification = st.text_input(
                            "Override justification",
                            key=f"just_{layer_idx}_{node.id}",
                            placeholder="Reason for manual override…",
                        )

            # ── Column 3: Source section full text ──────────────────────────
            with col_source:
                st.markdown("##### Source Evidence")
                section_label = extracted_item.source_section or "Unknown section"
                st.markdown(
                    f"<span style='font-size:0.75rem; font-weight:700; "
                    f"text-transform:uppercase; letter-spacing:0.06em; color:#888;'>"
                    f"📄 {section_label}</span>",
                    unsafe_allow_html=True,
                )

                section_text = getattr(extracted_item, "source_section_text", None)
                if section_text:
                    # Render the full section text in a scrollable panel
                    st.markdown(
                        f"<div style='"
                        f"border: 1px solid #e0e0e0; "
                        f"border-radius: 6px; "
                        f"padding: 12px 14px; "
                        f"background: #fafafa; "
                        f"max-height: 320px; "
                        f"overflow-y: auto; "
                        f"font-size: 0.85rem; "
                        f"line-height: 1.6; "
                        f"color: #222; "
                        f"white-space: pre-wrap; "
                        f"font-family: inherit;"
                        f"'>{section_text}</div>",
                        unsafe_allow_html=True,
                    )
                elif has_quote:
                    # Fallback: show just the quote if no full text available
                    st.markdown(
                        f"<blockquote style='"
                        f"border-left: 4px solid #E67E22; "
                        f"margin: 8px 0; "
                        f"padding: 10px 14px; "
                        f"background: #fffaf5; "
                        f"border-radius: 0 6px 6px 0; "
                        f"font-size: 0.92rem; "
                        f"line-height: 1.55; "
                        f"color: #2c2c2c; "
                        f"font-style: italic;"
                        f"'>{extracted_item.source_quote}</blockquote>",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        "<div style='color:#aaa; font-style:italic; margin-top:8px;'>"
                        "No source text available for this extraction.</div>",
                        unsafe_allow_html=True,
                    )

        # Build verification record
        record = NodeVerificationRecord(
            node_id=node.id,
            node_label=node.label,
            is_list_node=node.data_type == "list",
            extracted_items=[extracted_item],
            decisions=[VerificationDecision(decision)],
            corrected_values=[corrected_val or None],
            override_justifications=[justification or None],
            verified_at=datetime.datetime.utcnow(),
        )
        verification_records.append(record)

    # ── Commit button ────────────────────────────────────────────────────────
    st.divider()
    if st.button("Commit Layer & Advance", type="primary"):
        from core.twin import DigitalTwin
        runner = LayerRunner(use_stub=use_stub)
        try:
            twin = DigitalTwin.load(session.twin_id)
        except Exception:
            twin = None

        runner.commit_layer_verifications(session, layer_idx, verification_records, twin)
        runner.advance_layer(session)
        if twin:
            twin.save()
        mgr.save(session)

        if result_key in st.session_state:
            del st.session_state[result_key]

        st.success(f"Layer {layer_idx} committed. Now on layer {session.current_layer}.")
        st.rerun()

# ── Progress bar ─────────────────────────────────────────────────────────────
progress = session.current_layer / session.total_layers
st.progress(progress, text=f"Layers complete: {session.current_layer}/{session.total_layers}")
