from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, Field
import datetime


class DependencyType(str, Enum):
    ENFORCED = "enforced"       # downstream cannot differ; override requires admin approval
    REQUIRED = "required"       # should match; divergence flagged, must be acknowledged
    INFORMATIONAL = "informational"  # typically consistent; divergence noted only


class ElementStatus(str, Enum):
    EMPTY = "empty"             # not yet populated
    INFERRED = "inferred"       # auto-populated by dependency propagation; needs verification
    VERIFIED = "verified"       # confirmed by human author
    OVERRIDDEN = "overridden"   # human departed from dependency-inferred value; justified


class TwinTier(str, Enum):
    """
    Three tiers of the digital twin hierarchy.
    - COMPANY:  document templates, style guides, regulatory policies, SOPs.
    - MOLECULE: one twin per molecular program (e.g. aleniglipron).
    - TRIAL:    one twin per clinical trial (e.g. ACCESS II). Child of molecule twin.
    """
    COMPANY  = "company"
    MOLECULE = "molecule"
    TRIAL    = "trial"


class DocumentArchetype(str, Enum):
    """
    Distinguishes the two fundamentally different document production workflows.

    INFORMATION_HEAVY: CSR, IND, IB, NDA.
      Most effort is in collecting and structuring the data. Drafting is largely
      boilerplate once data is assembled. System value = information collection
      and deterministic section generation.

    REVISION_HEAVY: protocol, briefing documents, EOP2 meeting packages.
      Most effort is in iterative content refinement across review cycles.
      System value = structured first-draft generation and change tracking.
    """
    INFORMATION_HEAVY = "information_heavy"
    REVISION_HEAVY    = "revision_heavy"


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
    # Clinical judgment required: "low" | "medium" | "high"
    judgment_complexity: str = "low"


class DocumentSchema(BaseModel):
    id: str
    name: str
    version: str
    description: str
    tier: TwinTier = TwinTier.TRIAL
    archetype: DocumentArchetype = DocumentArchetype.INFORMATION_HEAVY
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
    tier: TwinTier = TwinTier.TRIAL
    program_name: str = ""
    trial_name: Optional[str] = None
    parent_twin_id: Optional[str] = None
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    elements: dict[str, TwinElement] = Field(default_factory=dict)


class IncrementalPopulationPlan(BaseModel):
    """
    Captures just-in-time population for a given document type.
    When a document type is demanded, this plan shows which elements are
    already available and which require new input from the writer.
    """
    document_type: str
    twin_id: str
    required_elements: list[str]
    already_populated: list[str]
    needs_collection: list[str]
    inherited_from_parent: list[str]


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
    judgment_complexity: str = "low"


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
