from llm.stub import LLMStub
from llm.client import LLMClient
from core.models import GeneratedSection, QCResult
import config


class QCAgent:
    def __init__(self, use_real_llm: bool = False):
        self._llm = LLMClient() if (use_real_llm and config.ANTHROPIC_API_KEY) else LLMStub()

    def check(self, section: GeneratedSection, source_data: dict) -> QCResult:
        return self._llm.run_qc(section, source_data)
