"""
eval/evaluators.py
==================
One evaluator class per assessment skill.  Each class:
  - Accepts a list[EvalSample] and an LLMClient
  - Generates predictions by calling the same assessor functions used in
    production (no wrapper shim — we test the real code path)
  - Returns an EvalResult with metrics + per-sample prediction log

EvalResult is a plain dataclass — MLflow logging lives in runner.py.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from eval.dataset import EvalSample, filter_samples
from eval.metrics import (
    BinaryMetrics, MulticlassMetrics, RegressionMetrics,
    binary_metrics, multiclass_metrics, regression_metrics,
    confusion_matrix_str,
)

SEVERITY_LABELS = ["routine", "elevated", "high", "critical"]


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------

@dataclass
class EvalResult:
    skill: str
    n_samples: int
    prompt_version: str
    elapsed_sec: float
    metrics: dict[str, Any] = field(default_factory=dict)
    # Per-sample log: signal_id, expected, actual, match, reasoning_snippet
    predictions: list[dict] = field(default_factory=list)
    # Worst cases: samples where the prediction was most wrong
    worst_cases: list[dict] = field(default_factory=list)
    # Rich metric objects (for confusion matrix etc.)
    _binary: BinaryMetrics | None = None
    _multiclass: MulticlassMetrics | None = None
    _regression: RegressionMetrics | None = None

    def summary_str(self) -> str:
        lines = [f"  Skill: {self.skill}  ({self.n_samples} samples, {self.elapsed_sec:.1f}s)"]
        for k, v in self.metrics.items():
            if isinstance(v, float):
                lines.append(f"    {k}: {v:.4f}")
            else:
                lines.append(f"    {k}: {v}")
        return "\n".join(lines)


# ---------------------------------------------------------------------------
# Base
# ---------------------------------------------------------------------------

class BaseEvaluator:
    skill: str = "base"

    def run(
        self,
        samples: list[EvalSample],
        client: Any,
        context: Any,
        cache_dir: Path | None = None,
    ) -> EvalResult:
        raise NotImplementedError

    def _eligible(self, samples: list[EvalSample]) -> list[EvalSample]:
        return filter_samples(samples, self.skill)


# ---------------------------------------------------------------------------
# 1. Relevance
# ---------------------------------------------------------------------------

class RelevanceEvaluator(BaseEvaluator):
    skill = "relevance"

    def run(self, samples, client, context, cache_dir=None) -> EvalResult:
        from agent.assessor import _step_relevance

        eligible = self._eligible(samples)
        t0 = time.perf_counter()
        preds: list[dict] = []
        y_true, y_pred = [], []
        prompt_version = "unknown"

        for s in eligible:
            try:
                result = _step_relevance(s.signal, context, client, cache_dir)
                prompt_version = result.prompt_version
            except Exception as e:
                result = None
                err = str(e)

            gt    = s.relevance_label
            truth = bool(gt["is_relevant"])
            pred  = bool(result.is_relevant) if result else False
            match = truth == pred

            y_true.append(truth)
            y_pred.append(pred)

            preds.append({
                "signal_id":    s.signal_id,
                "expected":     truth,
                "predicted":    pred,
                "match":        match,
                "gt_params":    gt.get("relevant_parameters", []),
                "pred_params":  result.relevant_parameters if result else [],
                "reasoning":    (result.relevance_reasoning[:120] if result else err),
            })

        bm = binary_metrics(y_true, y_pred)
        worst = [p for p in preds if not p["match"]][:5]

        return EvalResult(
            skill=self.skill,
            n_samples=len(eligible),
            prompt_version=prompt_version,
            elapsed_sec=time.perf_counter() - t0,
            metrics=bm.as_dict(),
            predictions=preds,
            worst_cases=worst,
            _binary=bm,
        )


# ---------------------------------------------------------------------------
# 2. Novelty
# ---------------------------------------------------------------------------

class NoveltyEvaluator(BaseEvaluator):
    skill = "novelty"

    def run(self, samples, client, context, cache_dir=None) -> EvalResult:
        from agent.assessor import _step_novelty

        eligible = self._eligible(samples)
        t0 = time.perf_counter()
        preds: list[dict] = []
        y_true, y_pred = [], []
        prompt_version = "unknown"

        for s in eligible:
            # Only evaluate if signal was labeled relevant=True
            if not s.is_relevant:
                continue

            # Novelty needs relevant states — use empty dict for eval
            # (tests LLM's ability to detect novelty from signal content alone)
            try:
                result = _step_novelty(s.signal, {}, client, cache_dir)
                prompt_version = result.prompt_version
            except Exception as e:
                result = None
                err = str(e)

            gt    = s.novelty_label
            truth = bool(gt["is_novel"])
            pred  = bool(result.is_novel) if result else False
            match = truth == pred

            y_true.append(truth)
            y_pred.append(pred)
            preds.append({
                "signal_id": s.signal_id,
                "expected":  truth,
                "predicted": pred,
                "match":     match,
                "reasoning": (result.novelty_reasoning[:120] if result else err),
            })

        bm = binary_metrics(y_true, y_pred)
        worst = [p for p in preds if not p["match"]][:5]

        return EvalResult(
            skill=self.skill,
            n_samples=len(preds),
            prompt_version=prompt_version,
            elapsed_sec=time.perf_counter() - t0,
            metrics=bm.as_dict(),
            predictions=preds,
            worst_cases=worst,
            _binary=bm,
        )


# ---------------------------------------------------------------------------
# 3. Severity
# ---------------------------------------------------------------------------

class SeverityEvaluator(BaseEvaluator):
    skill = "severity"

    def run(self, samples, client, context, cache_dir=None) -> EvalResult:
        from agent.assessor import _step_novelty, _step_severity

        eligible = self._eligible(samples)
        t0 = time.perf_counter()
        preds: list[dict] = []
        y_true, y_pred = [], []
        prompt_version = "unknown"

        for s in eligible:
            if not s.is_novel:
                continue

            gt_sev = s.ground_truth_severity
            if not gt_sev:
                continue

            # Build a minimal novelty result so _step_severity can run
            try:
                novelty = _step_novelty(s.signal, {}, client, cache_dir)
            except Exception:
                from agent.domain import NoveltyResult
                novelty = NoveltyResult(
                    is_novel=True,
                    novelty_reasoning="eval stub",
                    updated_parameter_states=[],
                    prompt_version="stub",
                )

            # Use all weights from context for severity
            relevant_weights = context.signal_priority_weights

            try:
                result = _step_severity(s.signal, novelty, relevant_weights, client, cache_dir)
                prompt_version = result.prompt_version
            except Exception as e:
                result = None
                err = str(e)

            pred = result.severity.value if result else "routine"
            match = pred == gt_sev

            y_true.append(gt_sev)
            y_pred.append(pred)
            preds.append({
                "signal_id": s.signal_id,
                "expected":  gt_sev,
                "predicted": pred,
                "match":     match,
                "reasoning": (result.severity_reasoning[:120] if result else err),
            })

        mm = multiclass_metrics(y_true, y_pred, SEVERITY_LABELS)
        cm_str = confusion_matrix_str(mm.confusion, SEVERITY_LABELS)
        worst = sorted([p for p in preds if not p["match"]], key=lambda p: (
            abs(SEVERITY_LABELS.index(p.get("predicted", "routine")) -
                SEVERITY_LABELS.index(p.get("expected", "routine")))
        ), reverse=True)[:5]

        m = mm.as_dict()
        m["confusion_matrix"] = cm_str  # stored as artifact, not MLflow metric

        return EvalResult(
            skill=self.skill,
            n_samples=len(preds),
            prompt_version=prompt_version,
            elapsed_sec=time.perf_counter() - t0,
            metrics=m,
            predictions=preds,
            worst_cases=worst,
            _multiclass=mm,
        )


# ---------------------------------------------------------------------------
# 4. Impact
# ---------------------------------------------------------------------------

class ImpactEvaluator(BaseEvaluator):
    skill = "impact"

    def run(self, samples, client, context, cache_dir=None) -> EvalResult:
        from agent.assessor import _step_novelty, _step_severity, _step_impact
        from agent.domain import SeverityTier

        eligible = self._eligible(samples)
        t0 = time.perf_counter()
        preds: list[dict] = []
        cost_true, cost_pred = [], []
        qual_true, qual_pred = [], []
        prompt_version = "unknown"

        for s in eligible:
            gt_imp = s.impact_label
            if gt_imp is None:
                continue

            # Build prerequisite results
            try:
                novelty = _step_novelty(s.signal, {}, client, cache_dir)
            except Exception:
                from agent.domain import NoveltyResult
                novelty = NoveltyResult(
                    is_novel=True, novelty_reasoning="eval stub",
                    updated_parameter_states=[], prompt_version="stub",
                )

            try:
                severity = _step_severity(s.signal, novelty, context.signal_priority_weights,
                                          client, cache_dir)
                # Force HIGH so impact step actually runs
                if severity.severity not in (SeverityTier.HIGH, SeverityTier.CRITICAL):
                    severity = severity.__class__(
                        severity=SeverityTier.HIGH,
                        severity_reasoning=severity.severity_reasoning,
                        risk_vector_type=severity.risk_vector_type,
                        affected_geography=severity.affected_geography,
                        affected_cdmo_node_name=severity.affected_cdmo_node_name,
                        prompt_version=severity.prompt_version,
                    )
            except Exception:
                from agent.domain import SeverityResult, SeverityTier, RiskVectorType
                severity = SeverityResult(
                    severity=SeverityTier.HIGH,
                    severity_reasoning="eval stub",
                    risk_vector_type=RiskVectorType.UNKNOWN,
                    affected_geography=None,
                    affected_cdmo_node_name=None,
                    prompt_version="stub",
                )

            try:
                result = _step_impact(s.signal, severity, novelty, context, client, cache_dir)
                prompt_version = result.prompt_version
            except Exception as e:
                result = None
                err = str(e)

            gt_cost = s.ground_truth_cost_impact
            pred_cost = result.estimated_cost_impact_per_kg if result else None
            gt_qual  = bool(gt_imp.get("qualitative_only", False))
            pred_qual = (pred_cost is None) if result else True

            is_numeric = (not gt_qual) and (gt_cost is not None)
            if is_numeric:
                cost_true.append(gt_cost)
                cost_pred.append(pred_cost)

            qual_true.append(gt_qual)
            qual_pred.append(pred_qual)

            preds.append({
                "signal_id":        s.signal_id,
                "gt_cost":          gt_cost,
                "pred_cost":        pred_cost,
                "gt_qualitative":   gt_qual,
                "pred_qualitative": pred_qual,
                "gt_confidence":    gt_imp.get("confidence"),
                "pred_confidence":  result.confidence if result else None,
                "gt_weeks":         gt_imp.get("estimated_timeline_impact_weeks"),
                "pred_weeks":       result.estimated_timeline_impact_weeks if result else None,
                "reasoning":        (result.estimated_cost_impact_reasoning[:120] if result else err),
            })

        # Numeric cost metrics
        reg = regression_metrics(cost_true, cost_pred) if cost_true else None
        # Qualitative-vs-numeric detection metrics
        qual_bm = binary_metrics(qual_true, qual_pred) if qual_true else None

        metrics: dict = {}
        if reg:
            metrics.update(reg.as_dict(prefix="cost_"))
        if qual_bm:
            metrics.update(qual_bm.as_dict(prefix="qualitative_detection_"))

        worst = sorted(
            [p for p in preds if p["gt_cost"] is not None and p["pred_cost"] is not None],
            key=lambda p: abs((p["pred_cost"] or 0) - (p["gt_cost"] or 0)),
            reverse=True,
        )[:5]

        return EvalResult(
            skill=self.skill,
            n_samples=len(preds),
            prompt_version=prompt_version,
            elapsed_sec=time.perf_counter() - t0,
            metrics=metrics,
            predictions=preds,
            worst_cases=worst,
            _regression=reg,
        )


# ---------------------------------------------------------------------------
# 5. Metacognition
# ---------------------------------------------------------------------------

class MetacognitionEvaluator(BaseEvaluator):
    skill = "metacognition"

    def run(self, samples, client, context, cache_dir=None) -> EvalResult:
        from agent.assessor import _step_novelty, _step_severity, _step_metacognition

        eligible = self._eligible(samples)
        t0 = time.perf_counter()
        preds: list[dict] = []
        sev_y_true, sev_y_pred = [], []
        prompt_version = "unknown"

        for s in eligible:
            gt_meta = s.metacognition_label
            if gt_meta is None:
                continue

            # Build severity result for context
            try:
                novelty = _step_novelty(s.signal, {}, client, cache_dir)
                severity = _step_severity(
                    s.signal, novelty, context.signal_priority_weights, client, cache_dir
                )
            except Exception:
                from agent.domain import (
                    NoveltyResult, SeverityResult, SeverityTier, RiskVectorType,
                )
                novelty  = NoveltyResult(
                    is_novel=True, novelty_reasoning="eval stub",
                    updated_parameter_states=[], prompt_version="stub",
                )
                severity = SeverityResult(
                    severity=SeverityTier.HIGH,
                    severity_reasoning="eval stub",
                    risk_vector_type=RiskVectorType.UNKNOWN,
                    affected_geography=None,
                    affected_cdmo_node_name=None,
                    prompt_version="stub",
                )

            context_summary = (
                f"Process: {context.process_name}. "
                f"Base cost: ${context.base_cost_per_kg_api:,.2f}/kg."
            )

            try:
                result = _step_metacognition(
                    step="severity",
                    signal=s.signal,
                    assessment_dict={
                        "severity": severity.severity.value,
                        "severity_reasoning": severity.severity_reasoning,
                        "risk_vector_type": severity.risk_vector_type.value,
                    },
                    context_summary=context_summary,
                    client=client,
                    cache_dir=cache_dir,
                )
                prompt_version = result.prompt_version
            except Exception as e:
                result = None
                err = str(e)

            gt_grade   = str(gt_meta.get("severity_grade", "CERTAIN")).upper()
            pred_grade = result.grade if result else "CERTAIN"
            match      = gt_grade == pred_grade

            sev_y_true.append(gt_grade)
            sev_y_pred.append(pred_grade)
            preds.append({
                "signal_id":  s.signal_id,
                "step":       "severity",
                "expected":   gt_grade,
                "predicted":  pred_grade,
                "match":      match,
                "gt_flags":   gt_meta.get("severity_uncertainty_flags", []),
                "pred_flags": result.uncertainty_flags if result else [],
                "reasoning":  (result.reasoning[:120] if result else err),
            })

        bm = binary_metrics(
            [t == "UNCERTAIN" for t in sev_y_true],
            [p == "UNCERTAIN" for p in sev_y_pred],
        ) if sev_y_true else binary_metrics([], [])

        worst = [p for p in preds if not p["match"]][:5]

        return EvalResult(
            skill=self.skill,
            n_samples=len(preds),
            prompt_version=prompt_version,
            elapsed_sec=time.perf_counter() - t0,
            metrics=bm.as_dict(prefix="uncertain_detection_"),
            predictions=preds,
            worst_cases=worst,
            _binary=bm,
        )


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

_EVALUATORS: dict[str, type[BaseEvaluator]] = {
    "relevance":      RelevanceEvaluator,
    "novelty":        NoveltyEvaluator,
    "severity":       SeverityEvaluator,
    "impact":         ImpactEvaluator,
    "metacognition":  MetacognitionEvaluator,
}

ALL_SKILLS = list(_EVALUATORS.keys())


def get_evaluator(skill: str) -> BaseEvaluator:
    cls = _EVALUATORS.get(skill)
    if cls is None:
        raise ValueError(f"Unknown skill '{skill}'. Valid: {list(_EVALUATORS)}")
    return cls()
