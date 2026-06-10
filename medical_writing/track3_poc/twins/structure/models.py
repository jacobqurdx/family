"""
Document structure twin data models.

The document structure twin is the "how this document must be shaped" store —
the blueprint of required/optional sections, ordering, content expectations and
the regulatory authority behind each requirement. It is distinct from and
independent of the content twin ("what we know").
"""
from typing import Optional
from pydantic import BaseModel, Field
import datetime


class SectionRequirement(BaseModel):
    """
    A single required or optional section in a document structure twin.
    Specifies WHAT must exist in the document, not WHAT the content should say
    (that comes from the content twin).
    """
    section_id: str
    section_title: str
    required: bool = True
    regulatory_authority: str = ""           # which guidance mandates this section
    content_expectations: list[str] = Field(default_factory=list)
    source_elements: list[str] = Field(default_factory=list)  # content twin element IDs
    judgment_complexity: str = "low"         # "low" | "medium" | "high"
    role_primary: list[str] = Field(default_factory=list)     # roles that own this section
    ordering: int = 0                        # section order in document


class DocumentStructureTwin(BaseModel):
    """
    The document structure twin for a specific document type.
    One per document type per regulatory body. Independent of content twins.
    """
    structure_id: str
    document_type: str
    regulatory_body: str                     # "FDA" | "EMA" | "PMDA"
    version: str
    source_guidances: list[str] = Field(default_factory=list)
    sections: list[SectionRequirement] = Field(default_factory=list)
    created_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
    locked: bool = False
    locked_at: Optional[datetime.datetime] = None
    locked_by: Optional[str] = None


class TwinPair(BaseModel):
    """
    Resolves the content twin + structure twin pair for a document generation
    request. This is the input to the content specification generator.
    """
    document_type: str
    content_twin_id: str                     # e.g. "molecule_aleniglipron"
    structure_twin_id: str                   # e.g. "structure_eop2_fda"
    requesting_role: str
    requested_at: datetime.datetime = Field(default_factory=datetime.datetime.utcnow)
