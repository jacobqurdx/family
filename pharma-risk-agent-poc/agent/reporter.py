import json
from datetime import datetime, timezone
from pathlib import Path

from agent.domain import AssessedSignal, RunResult, EvalReport


def make_output_dir(base: Path, run_name: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    out = base / f"{ts}_{run_name[:30].replace(' ', '_')}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_run_summary(result: RunResult, out_dir: Path) -> Path:
    summary = {
        "mode": result.mode,
        "started_at": result.started_at,
        "completed_at": result.completed_at,
        "signals_collected": result.signals_collected,
        "signals_relevant": result.signals_relevant,
        "signals_novel": result.signals_novel,
        "signals_by_severity": result.signals_by_severity,
        "actions": [
            {
                "type": a.action_type.value,
                "success": a.success,
                "output": str(a.output_file) if a.output_file else None,
                "summary": a.summary,
            }
            for a in result.actions_taken
        ],
    }
    path = out_dir / "run_summary.json"
    path.write_text(json.dumps(summary, indent=2))
    return path


def write_assessed_signals(signals: list[AssessedSignal], out_dir: Path) -> Path:
    data = []
    for a in signals:
        data.append({
            "signal_id": a.signal.id,
            "source": a.signal.source_name,
            "url": a.signal.source_url,
            "is_relevant": a.relevance.is_relevant,
            "relevant_parameters": a.relevance.relevant_parameters,
            "process_step": getattr(a, "process_step", None),
            "is_novel": a.novelty.is_novel if a.novelty else None,
            "severity": a.severity.severity.value if a.severity else None,
            "risk_vector": a.severity.risk_vector_type.value if a.severity else None,
            "recommended_actions": [x.value for x in a.recommended_actions],
            "assessment_failed": a.assessment_failed,
            "novelty_reasoning": a.novelty.novelty_reasoning if a.novelty else None,
            "severity_reasoning": a.severity.severity_reasoning if a.severity else None,
            "estimated_cost_delta": (
                a.impact.estimated_cost_impact_per_kg if a.impact else None
            ),
            "severity_metacognition": (
                {
                    "grade": a.severity_metacognition.grade,
                    "confidence": a.severity_metacognition.confidence,
                    "uncertainty_flags": a.severity_metacognition.uncertainty_flags,
                    "adjudicated": a.severity_metacognition.adjudicated,
                    "adjudicated_by": a.severity_metacognition.adjudicated_by,
                }
                if a.severity_metacognition else None
            ),
            "impact_metacognition": (
                {
                    "grade": a.impact_metacognition.grade,
                    "confidence": a.impact_metacognition.confidence,
                    "uncertainty_flags": a.impact_metacognition.uncertainty_flags,
                    "adjudicated": a.impact_metacognition.adjudicated,
                    "adjudicated_by": a.impact_metacognition.adjudicated_by,
                }
                if a.impact_metacognition else None
            ),
        })
    path = out_dir / "assessed_signals.json"
    path.write_text(json.dumps(data, indent=2))
    return path


def write_eval_report(report: EvalReport, out_dir: Path) -> Path:
    lines = [
        "# Assessment Pipeline Evaluation Report",
        "",
        f"**Prompt versions:** {report.prompt_versions}",
        f"**Total LLM calls:** {report.total_llm_calls}",
        f"**Estimated cost:** ${report.total_cost_estimate_usd:.4f}",
        f"**Elapsed:** {report.elapsed_sec:.1f}s",
        "",
        "## Relevance Classification",
        _metrics_table(report.relevance_metrics),
        "",
        "## Novelty Detection",
        _metrics_table(report.novelty_metrics),
        "",
        "## Severity Classification (macro-average)",
        _metrics_table(report.severity_metrics),
        "",
        "### Per-Class Severity Metrics",
    ]
    for cls, m in report.severity_per_class.items():
        lines.append(f"**{cls.upper()}:** {_metrics_inline(m)}")
    if report.worst_cases:
        lines += ["", "## Worst-Case Misclassifications (top 5)", ""]
        for i, wc in enumerate(report.worst_cases, 1):
            lines += [
                f"### {i}. {wc.get('signal_id', '?')}",
                f"- Expected: `{wc.get('expected')}`  Got: `{wc.get('actual')}`",
                f"- Reasoning: {wc.get('reasoning', 'N/A')}",
                "",
            ]
    path = out_dir / "eval_report.md"
    path.write_text("\n".join(lines))
    return path


def _metrics_table(m) -> str:
    return (
        "| Metric | Value |\n|---|---|\n"
        f"| Precision | {m.precision:.3f} |\n"
        f"| Recall | {m.recall:.3f} |\n"
        f"| F1 | {m.f1:.3f} |\n"
        f"| N total | {m.n_total} |\n"
        f"| N correct | {m.n_correct} |"
    )


def _metrics_inline(m) -> str:
    return f"P={m.precision:.2f} R={m.recall:.2f} F1={m.f1:.2f} (n={m.n_total})"
