from __future__ import annotations
import time
import yaml
from pathlib import Path

from agent.domain import (
    AssessedSignal, CorpusLabel, EvalMetrics, EvalReport,
    SeverityTier, SignalState,
)
from agent.assessor import assess_signal
from agent.collector import collect_from_files
from agent.state import SignalStateStore


def run_evaluation(
    corpus_dir: Path,
    labels_file: Path,
    sensitivity_json: Path,
    client: "LLMClient",
    cache_dir: Path,
    out_dir: Path,
) -> EvalReport:
    from agent.mrp import load_sensitivity_context
    t0 = time.perf_counter()

    context = load_sensitivity_context(sensitivity_json)
    state_store = SignalStateStore(out_dir / "eval_state.json")
    state_store.initialise_from_sensitivity_context(context)

    signals = collect_from_files(corpus_dir)
    labels_raw = yaml.safe_load(labels_file.read_text())
    labels: dict[str, CorpusLabel] = {}
    for item in labels_raw.get("labels", []):
        sev_raw = item.get("expected_severity")
        rv_raw = item.get("expected_risk_vector")
        labels[item["signal_id"]] = CorpusLabel(
            signal_id=item["signal_id"],
            expected_is_relevant=item["expected_is_relevant"],
            expected_is_novel=item["expected_is_novel"],
            expected_severity=SeverityTier(sev_raw) if sev_raw else None,
            expected_risk_vector=None,  # evaluated separately
            notes=item.get("notes"),
        )

    assessments: list[tuple[AssessedSignal, CorpusLabel | None]] = []
    llm_call_count = 0
    for signal in signals:
        label = labels.get(signal.id)
        assessed = assess_signal(
            signal, context, state_store.all(), client,
            cache_dir=cache_dir, skip_impact=True,
        )
        assessments.append((assessed, label))
        llm_call_count += _count_llm_calls(assessed)

    relevance_metrics = _compute_relevance_metrics(assessments)
    novelty_metrics   = _compute_novelty_metrics(assessments)
    severity_metrics, per_class = _compute_severity_metrics(assessments)
    worst_cases = _find_worst_cases(assessments, n=5)
    elapsed = time.perf_counter() - t0
    prompt_versions = _collect_prompt_versions(assessments)

    return EvalReport(
        prompt_versions=prompt_versions,
        relevance_metrics=relevance_metrics,
        novelty_metrics=novelty_metrics,
        severity_metrics=severity_metrics,
        severity_per_class=per_class,
        worst_cases=worst_cases,
        total_llm_calls=llm_call_count,
        total_cost_estimate_usd=llm_call_count * 0.003,
        elapsed_sec=elapsed,
    )


def _compute_relevance_metrics(
    assessments: list[tuple[AssessedSignal, CorpusLabel | None]],
) -> EvalMetrics:
    tp = fp = tn = fn = 0
    for assessed, label in assessments:
        if label is None:
            continue
        predicted = assessed.relevance.is_relevant
        expected  = label.expected_is_relevant
        if predicted and expected:         tp += 1
        elif predicted and not expected:   fp += 1
        elif not predicted and not expected: tn += 1
        else:                              fn += 1
    return _metrics_from_counts(tp, fp, tn, fn)


def _compute_novelty_metrics(
    assessments: list[tuple[AssessedSignal, CorpusLabel | None]],
) -> EvalMetrics:
    tp = fp = tn = fn = 0
    for assessed, label in assessments:
        if label is None or not label.expected_is_relevant:
            continue
        if assessed.novelty is None:
            continue
        predicted = assessed.novelty.is_novel
        expected  = label.expected_is_novel
        if predicted and expected:         tp += 1
        elif predicted and not expected:   fp += 1
        elif not predicted and not expected: tn += 1
        else:                              fn += 1
    return _metrics_from_counts(tp, fp, tn, fn)


def _compute_severity_metrics(
    assessments: list[tuple[AssessedSignal, CorpusLabel | None]],
) -> tuple[EvalMetrics, dict[str, EvalMetrics]]:
    per_class: dict[str, dict] = {t.value: {"tp": 0, "fp": 0, "tn": 0, "fn": 0}
                                   for t in SeverityTier}
    for assessed, label in assessments:
        if label is None or label.expected_severity is None:
            continue
        if assessed.severity is None:
            continue
        predicted = assessed.severity.severity
        expected  = label.expected_severity
        for tier in SeverityTier:
            p = (predicted == tier)
            e = (expected  == tier)
            if p and e:         per_class[tier.value]["tp"] += 1
            elif p and not e:   per_class[tier.value]["fp"] += 1
            elif not p and not e: per_class[tier.value]["tn"] += 1
            else:               per_class[tier.value]["fn"] += 1

    class_metrics = {k: _metrics_from_counts(**v) for k, v in per_class.items()}
    macro = EvalMetrics(
        precision=sum(m.precision for m in class_metrics.values()) / len(class_metrics),
        recall=sum(m.recall for m in class_metrics.values()) / len(class_metrics),
        f1=sum(m.f1 for m in class_metrics.values()) / len(class_metrics),
        n_total=sum(m.n_total for m in class_metrics.values()),
        n_correct=sum(m.n_correct for m in class_metrics.values()),
        confusion={},
    )
    return macro, class_metrics


def _metrics_from_counts(tp: int, fp: int, tn: int, fn: int) -> EvalMetrics:
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) > 0 else 0.0)
    return EvalMetrics(
        precision=round(precision, 3),
        recall=round(recall, 3),
        f1=round(f1, 3),
        n_total=tp + fp + tn + fn,
        n_correct=tp + tn,
        confusion={"tp": tp, "fp": fp, "tn": tn, "fn": fn},
    )


def _find_worst_cases(
    assessments: list[tuple[AssessedSignal, CorpusLabel | None]],
    n: int = 5,
) -> list[dict]:
    worst = []
    for assessed, label in assessments:
        if label is None:
            continue
        if (label.expected_severity in (SeverityTier.HIGH, SeverityTier.CRITICAL)
                and assessed.severity
                and assessed.severity.severity in (SeverityTier.ROUTINE, SeverityTier.ELEVATED)):
            worst.append({
                "signal_id": assessed.signal.id,
                "expected": label.expected_severity.value,
                "actual": assessed.severity.severity.value,
                "reasoning": assessed.severity.severity_reasoning,
                "priority": 2,
            })
        elif label.expected_is_relevant and not assessed.relevance.is_relevant:
            worst.append({
                "signal_id": assessed.signal.id,
                "expected": "relevant",
                "actual": "irrelevant",
                "reasoning": assessed.relevance.relevance_reasoning,
                "priority": 1,
            })
    worst.sort(key=lambda x: -x["priority"])
    return worst[:n]


def _count_llm_calls(assessed: AssessedSignal) -> int:
    count = 1
    if assessed.novelty is not None:  count += 1
    if assessed.severity is not None: count += 1
    if assessed.impact is not None:   count += 1
    return count


def _collect_prompt_versions(
    assessments: list[tuple[AssessedSignal, CorpusLabel | None]],
) -> dict:
    for assessed, _ in assessments:
        if not assessed.assessment_failed:
            return {
                "relevance": assessed.relevance.prompt_version,
                "novelty": assessed.novelty.prompt_version if assessed.novelty else "n/a",
                "severity": assessed.severity.prompt_version if assessed.severity else "n/a",
            }
    return {}
