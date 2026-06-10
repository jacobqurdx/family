"""
GuidanceIngestor: turns an FDA/EMA guidance document (PDF / DOCX / TXT) into a
list of structured RegulatoryRequirement objects.

Extraction itself is performed by the GuidanceExtractor LLM component, which is
stubbed in Track 3 (see llm/stubs/guidance_extractor_stub.py). This class owns
reading the source document and routing to the (stub or functional) extractor.
"""
from pathlib import Path
from typing import Optional

import config


class GuidanceIngestor:
    def __init__(self, use_real_llm: bool = False):
        self._use_real_llm = use_real_llm and not config.USE_STUB
        self._extractor = self._load_extractor()

    def _load_extractor(self):
        if self._use_real_llm:
            # PROMOTION: import functional GuidanceExtractor here when available
            raise NotImplementedError(
                "Functional GuidanceExtractor not yet promoted. Set USE_STUB=true."
            )
        from llm.stubs.guidance_extractor_stub import GuidanceExtractorStub
        return GuidanceExtractorStub()

    def read_text(self, document_path: str) -> str:
        """Read a guidance document. Supports .txt, .pdf (pypdf), .docx (python-docx)."""
        path = Path(document_path)
        if not path.exists():
            return ""
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            try:
                from pypdf import PdfReader
                reader = PdfReader(str(path))
                return "\n".join((page.extract_text() or "") for page in reader.pages)
            except Exception:
                return ""
        if suffix == ".docx":
            try:
                from docx import Document
                doc = Document(str(path))
                return "\n".join(p.text for p in doc.paragraphs)
            except Exception:
                return ""
        # default: plain text
        return path.read_text()

    def ingest(self, document_path: str, document_type: str = "eop2_briefing") -> list:
        """Read the guidance document and extract structured requirements."""
        text = self.read_text(document_path)
        return self._extractor.extract_requirements(text, document_type)
