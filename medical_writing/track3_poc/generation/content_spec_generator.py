"""
ContentSpecGenerator: produces a structured ContentSpec from a (content twin,
structure twin) pair.

Generation of the claims themselves is performed by the ContentSpecGenerator
LLM component, which is stubbed in Track 3. This wrapper owns:
  - resolving the twin pair into concrete twins,
  - invoking the (stub or functional) generator,
  - running real GapDetector logic so gaps_detected reflects the actual content
    twin state rather than a canned list.
"""
from typing import Optional

from generation.spec_models import ContentSpec
from twins.content.gap_detector import GapDetector
from twins.registry import TwinRegistry
import config


class ContentSpecGenerator:
    def __init__(self, use_real_llm: bool = False):
        self._use_real_llm = use_real_llm and not config.USE_STUB
        self._generator = self._load_generator()
        self._gap_detector = GapDetector()
        self._registry = TwinRegistry()

    def _load_generator(self):
        if self._use_real_llm:
            # PROMOTION: import functional ContentSpecGenerator here when available
            raise NotImplementedError(
                "Functional ContentSpecGenerator not yet promoted. Set USE_STUB=true."
            )
        from llm.stubs.content_spec_stub import ContentSpecGeneratorStub
        return ContentSpecGeneratorStub()

    def generate(self, twin_pair, content_twin=None, structure_twin=None) -> ContentSpec:
        if content_twin is None:
            content_twin = self._registry.get_content_twin(twin_pair.content_twin_id)
        if structure_twin is None:
            structure_twin = self._registry.get_structure_twin(twin_pair.structure_twin_id)

        spec = self._generator.generate(twin_pair, content_twin, structure_twin)

        # Override the canned gap list with real gap detection against the twin pair.
        detected = self._gap_detector.detect(content_twin, structure_twin)
        spec.gaps_detected = detected
        return spec
