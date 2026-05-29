from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import datetime


class DependencyType(str, Enum):
    ENFORCED = "enforced"
    REQUIRED = "required"
    INFORMATIONAL = "informational"


class ElementStatus(str, Enum):
    EMPTY = "empty"
    INFERRED = "inferred"
    VERIFIED = "verified"
    OVERRIDDEN = "overridden"


class SchemaElement(BaseModel):
    id: str
    label: str
    description: str
    data_type: str
    required: bool = True
    example: Optional[Any] = None
    depends_on: list[str] = Field(default_factory=list)
    dependency_type: DependencyType = DependencyType.REQUIRED
    inference_rule: Optional[str] = None


class DocumentSection(BaseModel):
    id: str
    title: str
    source_elements: list[str]
    prompt_template: str


class DocumentSchema(BaseModel):
    id: str
    name: str
    version: str
    description: str
    elements: list[SchemaElement]
    sections: list[DocumentSection]


class TwinElement(BaseModel):
    element_id: str
    value: Optional[Any] = None
    status: ElementStatus = ElementStatus.EMPTY
    source: Optional[str] = None
    override_justification: Optional[str] = None
    last_modified: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    modified_by: str = "system"


class DigitalTwinRecord(BaseModel):
    twin_id: str
    schema_id: str
    trial_name: str
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    elements: dict[str, TwinElement] = Field(default_factory=dict)


class DependencyViolation(BaseModel):
    element_id: str
    upstream_element_id: str
    dependency_type: DependencyType
    expected_value: Any
    actual_value: Any
    message: str


class PropagationResult(BaseModel):
    changed_element_id: str
    affected_elements: list[str]
    violations: list[DependencyViolation]
    inferred_updates: dict[str, Any]


class GeneratedSection(BaseModel):
    section_id: str
    section_title: str
    prose: str
    source_elements: dict[str, Any]
    model_used: str
    prompt_version: str
    confidence: float
    confidence_rationale: str


class QCFinding(BaseModel):
    finding_id: str
    section_id: str
    severity: str
    category: str
    description: str
    offending_text: Optional[str] = None
    source_element: Optional[str] = None


class QCResult(BaseModel):
    section_id: str
    passed: bool
    findings: list[QCFinding]
    overall_confidence: float
    recommendation: str


class GroundTruthPair(BaseModel):
    pair_id: str
    section_id: str
    source_elements: dict[str, Any]
    gold_prose: str
    complexity: str
    notes: Optional[str] = None


class EvaluationResult(BaseModel):
    pair_id: str
    section_id: str
    generated_prose: str
    gold_prose: str
    expert_rating: Optional[str] = None
    auto_score: Optional[float] = None
    confidence: float
    notes: Optional[str] = None
