from llm.stub import LLMStub
from llm.client import LLMClient
from llm.prompts import get_generation_prompt
from core.models import GeneratedSection
import config


class ProseGenerator:
    def __init__(self, use_real_llm: bool = False):
        self._llm = LLMClient() if (use_real_llm and config.ANTHROPIC_API_KEY) else LLMStub()

    def generate(self, section_id: str, section_title: str, source_data: dict) -> GeneratedSection:
        prompt = get_generation_prompt(section_id)
        return self._llm.generate_section(section_id, section_title, source_data, prompt)
