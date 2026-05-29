"""
LayerRunner: orchestrates extraction + verification for a single layer,
updating the IngestionSession state after each layer completes.
"""
from __future__ import annotations
import datetime
from typing import Any, Dict, List, Optional

from ingestion.verification import (
    IngestionSession, LayerExtractionResult, NodeVerificationRecord,
    ExtractedItem, VerificationDecision,
)
from usdm.graph_walk import get_layer_nodes, ALL_LAYERS
from usdm.extractor import LayerExtractor
from core.models import ElementStatus
from core.twin import DigitalTwin


def _normalize_keys(d: dict) -> dict:
    """Re-key a dict converting string int keys back to int (JSON round-trip fix)."""
    result = {}
    for k, v in d.items():
        try:
            result[int(k)] = v
        except (ValueError, TypeError):
            result[k] = v
    return result


class LayerRunner:
    def __init__(self, extractor: Optional[LayerExtractor] = None, use_stub: bool = False):
        self._extractor = extractor or LayerExtractor(use_stub=use_stub)

    def run_extraction(
        self,
        session: IngestionSession,
        document: Any,
    ) -> LayerExtractionResult:
        """Run extraction for session.current_layer."""
        layer_index = session.current_layer
        result = self._extractor.extract_layer(
            layer_index, document, session.confirmed_values
        )

        # Store raw extraction results
        extraction_results = _normalize_keys(dict(session.extraction_results))
        extraction_results[layer_index] = [item.model_dump() for item in result.extracted_nodes]
        session.extraction_results = extraction_results  # type: ignore[assignment]
        return result

    def commit_layer_verifications(
        self,
        session: IngestionSession,
        layer_index: int,
        verification_records: List[NodeVerificationRecord],
        twin: Optional[DigitalTwin] = None,
    ) -> None:
        """
        Apply a list of NodeVerificationRecord decisions to the session state
        and optionally to the DigitalTwin.
        """
        nodes = get_layer_nodes(layer_index)
        node_map = {n.id: n for n in nodes}

        vr_dicts: List[dict] = []
        for record in verification_records:
            decision_list = record.decisions
            if not decision_list:
                continue

            # Take the first (or only) decision
            decision = decision_list[0]
            corrected = record.corrected_values[0] if record.corrected_values else None
            justification = record.override_justifications[0] if record.override_justifications else None

            if decision == VerificationDecision.CONFIRMED:
                # Use extracted value
                final_val = record.extracted_items[0].value if record.extracted_items else None
                session.confirmed_values[record.node_id] = final_val
                session.total_nodes_confirmed += 1
                if twin:
                    twin.set(record.node_id, final_val, source="extraction", status=ElementStatus.VERIFIED)

            elif decision == VerificationDecision.CORRECTED:
                final_val = corrected
                session.confirmed_values[record.node_id] = final_val
                session.total_nodes_corrected += 1
                if twin:
                    twin.set(record.node_id, final_val, source="writer_correction", status=ElementStatus.VERIFIED)

            elif decision == VerificationDecision.OVERRIDDEN:
                final_val = corrected
                session.confirmed_values[record.node_id] = final_val
                session.total_nodes_overridden += 1
                if twin:
                    twin.override(record.node_id, final_val, justification or "", modified_by=session.writer_id)

            elif decision == VerificationDecision.MISSING:
                if corrected is not None:
                    # Writer provided a value
                    final_val = corrected
                    session.confirmed_values[record.node_id] = final_val
                    session.total_nodes_confirmed += 1
                    if twin:
                        twin.set(record.node_id, final_val, source="writer_manual", status=ElementStatus.VERIFIED)
                else:
                    session.total_nodes_missing += 1
                    final_val = None
                    # Do not add to confirmed_values; twin element stays EMPTY

            vr_dicts.append(record.model_dump(mode="json"))

        # Store verification records
        vr_map = _normalize_keys(dict(session.verification_records))
        vr_map[layer_index] = vr_dicts
        session.verification_records = vr_map  # type: ignore[assignment]

    def advance_layer(self, session: IngestionSession) -> None:
        """Move to the next layer. Mark complete if done."""
        session.current_layer += 1
        if session.current_layer >= session.total_layers:
            session.status = "complete"
            session.completed_at = datetime.datetime.utcnow()

    def auto_verify_layer(
        self,
        session: IngestionSession,
        layer_index: int,
        extraction_result: LayerExtractionResult,
        twin: Optional[DigitalTwin] = None,
    ) -> List[NodeVerificationRecord]:
        """
        Auto-verify all items in a layer as CONFIRMED (useful for testing).
        Returns the list of records committed.
        """
        nodes = get_layer_nodes(layer_index)
        records: List[NodeVerificationRecord] = []

        for i, node in enumerate(nodes):
            extracted_item = (
                extraction_result.extracted_nodes[i]
                if i < len(extraction_result.extracted_nodes)
                else ExtractedItem(item_index=i)
            )
            record = NodeVerificationRecord(
                node_id=node.id,
                node_label=node.label,
                is_list_node=node.data_type == "list",
                extracted_items=[extracted_item],
                decisions=[VerificationDecision.CONFIRMED],
                corrected_values=[None],
                override_justifications=[None],
                final_value=extracted_item.value,
                final_status="confirmed",
                verified_at=datetime.datetime.utcnow(),
            )
            records.append(record)

        self.commit_layer_verifications(session, layer_index, records, twin)
        return records
