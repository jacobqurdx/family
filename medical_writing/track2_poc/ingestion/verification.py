from __future__ import annotations
from enum import Enum
from typing import Any, Optional, List, Dict
from pydantic import BaseModel, Field
import datetime


class VerificationDecision(str, Enum):
    CONFIRMED = "confirmed"
    CORRECTED = "corrected"
    OVERRIDDEN = "overridden"
    MISSING = "missing"


class ExtractedItem(BaseModel):
    item_index: Optional[int] = None
    value: Optional[Any] = None
    confidence: float = 0.0
    source_section: Optional[str] = None
    source_section_text: Optional[str] = None   # full text of the source section
    source_quote: Optional[str] = None           # verbatim sentence/phrase containing the value
    extraction_notes: Optional[str] = None


class NodeVerificationRecord(BaseModel):
    node_id: str
    node_label: str
    is_list_node: bool
    extracted_items: List[ExtractedItem] = Field(default_factory=list)
    decisions: List[VerificationDecision] = Field(default_factory=list)
    corrected_values: List[Optional[Any]] = Field(default_factory=list)
    override_justifications: List[Optional[str]] = Field(default_factory=list)
    final_value: Optional[Any] = None
    final_status: str = "pending"
    verified_at: Optional[datetime.datetime] = None
    verified_by: str = "writer"


class LayerExtractionResult(BaseModel):
    layer_index: int
    layer_name: str
    extracted_nodes: List[ExtractedItem]
    model_used: str
    prompt_version: str
    extraction_timestamp: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    raw_llm_response: Optional[str] = None


class IngestionSession(BaseModel):
    session_id: str
    document_filename: str
    document_path: str
    twin_id: str
    schema_id: str
    writer_id: str
    started_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    completed_at: Optional[datetime.datetime] = None
    current_layer: int = 0
    total_layers: int = 9
    extraction_results: Dict[int, List[dict]] = Field(default_factory=dict)
    verification_records: Dict[int, List[dict]] = Field(default_factory=dict)
    confirmed_values: Dict[str, Any] = Field(default_factory=dict)
    total_nodes_confirmed: int = 0
    total_nodes_corrected: int = 0
    total_nodes_overridden: int = 0
    total_nodes_missing: int = 0
    status: str = "in_progress"
