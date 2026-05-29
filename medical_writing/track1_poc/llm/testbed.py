"""
LLMTestBed: evaluates LLM (real or stub) against ground truth pairs.
Produces accuracy and calibration reports.
"""
import json
from pathlib import Path
from core.models import GroundTruthPair, EvaluationResult
from generation.generator import ProseGenerator
import config
import pandas as pd


class LLMTestBed:
    def __init__(self, use_real_llm: bool = False):
        self._generator = ProseGenerator(use_real_llm=use_real_llm)
        self._ground_truth = self._load_ground_truth()

    def _load_ground_truth(self) -> list[GroundTruthPair]:
        path = Path(config.GROUND_TRUTH_DIR) / "protocol_sections.json"
        raw = json.loads(path.read_text())
        return [GroundTruthPair(**item) for item in raw]

    def run_accuracy_eval(self) -> list[EvaluationResult]:
        """
        Runs all ground truth pairs through the generator.
        Returns EvaluationResult for each — auto_score uses simple keyword overlap.
        Expert rating field is left empty for human completion.
        """
        results = []
        for pair in self._ground_truth:
            generated = self._generator.generate(
                section_id=pair.section_id,
                section_title=pair.section_id.replace("_", " ").title(),
                source_data=pair.source_elements
            )
            auto_score = self._keyword_overlap(generated.prose, pair.gold_prose)
            results.append(EvaluationResult(
                pair_id=pair.pair_id,
                section_id=pair.section_id,
                generated_prose=generated.prose,
                gold_prose=pair.gold_prose,
                expert_rating=None,
                auto_score=auto_score,
                confidence=generated.confidence,
                notes=pair.notes
            ))
        return results

    def run_calibration_eval(self, results: list[EvaluationResult]) -> dict:
        """
        Calibration check: do high-confidence outputs have higher auto_scores?
        """
        high = [r for r in results if r.confidence >= 0.7]
        low = [r for r in results if r.confidence < 0.7]

        def avg_score(items):
            if not items:
                return None
            return sum(r.auto_score for r in items if r.auto_score) / len(items)

        return {
            "high_confidence_count": len(high),
            "low_confidence_count": len(low),
            "high_confidence_avg_score": avg_score(high),
            "low_confidence_avg_score": avg_score(low),
            "calibration_delta": (
                (avg_score(high) or 0) - (avg_score(low) or 0)
            ),
            "calibration_passed": (
                (avg_score(high) or 0) > (avg_score(low) or 0)
            )
        }

    def to_dataframe(self, results: list[EvaluationResult]) -> pd.DataFrame:
        return pd.DataFrame([r.model_dump() for r in results])

    @staticmethod
    def _keyword_overlap(generated: str, gold: str) -> float:
        """Simple keyword overlap score as proxy for accuracy. Range 0-1."""
        gen_words = set(generated.lower().split())
        gold_words = set(gold.lower().split())
        if not gold_words:
            return 0.0
        overlap = gen_words & gold_words
        return len(overlap) / len(gold_words)
