from __future__ import annotations
import json
from pathlib import Path

from agent.domain import (
    AssessedSignal, ActionType, ActionResult, SensitivityContext,
    SeverityTier, RiskVectorType,
)
from agent.mrp import rerun_tariff_analysis, rerun_cdmo_removal_analysis


def execute_actions(
    assessed: AssessedSignal,
    context: SensitivityContext,
    client: "LLMClient",
    out_dir: Path,
    process_yaml: Path | None = None,
    prices_yaml: Path | None = None,
    risk_profile_yaml: Path | None = None,
    cache_dir: Path | None = None,
) -> list[ActionResult]:
    results = []
    for action_type in assessed.recommended_actions:
        result = _execute_one(
            action_type, assessed, context, client,
            out_dir, process_yaml, prices_yaml, risk_profile_yaml, cache_dir,
        )
        results.append(result)
    return results


def _execute_one(
    action_type: ActionType,
    assessed: AssessedSignal,
    context: SensitivityContext,
    client: "LLMClient",
    out_dir: Path,
    process_yaml: Path | None,
    prices_yaml: Path | None,
    risk_profile_yaml: Path | None,
    cache_dir: Path | None,
) -> ActionResult:
    try:
        if action_type == ActionType.ADD_TO_DIGEST:
            return ActionResult(
                action_type=action_type, success=True,
                output_file=None,
                summary=f"Added to digest: {assessed.signal.source_name}",
            )

        elif action_type == ActionType.SEND_ALERT:
            alert_path = out_dir / f"alert_{assessed.signal.id[:8]}.txt"
            alert_path.write_text(_format_alert(assessed, context))
            return ActionResult(
                action_type=action_type, success=True,
                output_file=alert_path,
                summary=f"Alert written: {alert_path.name}",
            )

        elif action_type == ActionType.TRIGGER_TARIFF_SWEEP:
            if not all([process_yaml, prices_yaml, risk_profile_yaml]):
                return ActionResult(
                    action_type=action_type, success=False,
                    output_file=None,
                    summary="Skipped: --process, --prices, --risk-profile required for MRP actions",
                )
            rates = [r.get("tariff_rate_pct", r) for r in context.tariff_sweep] if context.tariff_sweep else [20.0, 35.0, 55.0, 100.0]
            if rates and isinstance(rates[0], dict):
                rates = [r["tariff_rate_pct"] for r in rates]
            geography = assessed.severity.affected_geography or "CN"
            mrp_result = rerun_tariff_analysis(
                process_yaml, prices_yaml, risk_profile_yaml, rates, geography,
            )
            result_path = out_dir / f"tariff_sweep_{assessed.signal.id[:8]}.json"
            result_path.write_text(json.dumps(mrp_result, indent=2))
            return ActionResult(
                action_type=action_type, success=True,
                output_file=result_path,
                summary=f"Tariff sweep at {len(rates)} rates. Base: ${mrp_result['base_cost_per_kg_api']:,.2f}/kg",
            )

        elif action_type == ActionType.TRIGGER_CDMO_REMOVAL:
            if not all([process_yaml, prices_yaml, risk_profile_yaml]):
                return ActionResult(
                    action_type=action_type, success=False,
                    output_file=None,
                    summary="Skipped: MRP file paths required",
                )
            cdmo_name = assessed.severity.affected_cdmo_node_name if assessed.severity else None
            cdmo_scenario = next(
                (s for s in context.cdmo_removal_scenarios
                 if s.get("cdmo_node_name") == cdmo_name or s.get("cdmo_name") == cdmo_name),
                context.cdmo_removal_scenarios[0] if context.cdmo_removal_scenarios else None,
            )
            if not cdmo_scenario:
                return ActionResult(
                    action_type=action_type, success=False,
                    output_file=None,
                    summary=f"No CDMO removal scenario found for: {cdmo_name}",
                )
            node_id = cdmo_scenario.get("cdmo_node_id") or cdmo_scenario.get("cdmo_node_name", "")
            mrp_result = rerun_cdmo_removal_analysis(
                process_yaml, prices_yaml, risk_profile_yaml, node_id,
            )
            result_path = out_dir / f"cdmo_removal_{assessed.signal.id[:8]}.json"
            result_path.write_text(json.dumps(mrp_result, indent=2))
            return ActionResult(
                action_type=action_type, success=True,
                output_file=result_path,
                summary=(
                    f"CDMO removal: {mrp_result['cdmo_node_name']}. "
                    f"Emergency cost: ${mrp_result['emergency_cost_per_kg']:,.2f}/kg "
                    f"(+${mrp_result['cost_delta_per_kg']:,.2f}). "
                    f"Timeline: {mrp_result.get('timeline_weeks', 'unknown')} weeks."
                ),
            )

        elif action_type == ActionType.DRAFT_INVESTIGATION_REPORT:
            report_path = _draft_investigation_report(
                assessed, context, client, out_dir, cache_dir,
            )
            return ActionResult(
                action_type=action_type, success=True,
                output_file=report_path,
                summary=f"Investigation report: {report_path.name}",
            )

        elif action_type == ActionType.DRAFT_MANAGEMENT_BRIEFING:
            briefing_path = _draft_management_briefing(
                assessed, context, client, out_dir, cache_dir,
            )
            return ActionResult(
                action_type=action_type, success=True,
                output_file=briefing_path,
                summary=f"Management briefing: {briefing_path.name}",
            )

        else:
            return ActionResult(
                action_type=action_type, success=False,
                output_file=None,
                summary=f"Action type not implemented in POC: {action_type}",
            )

    except Exception as e:
        return ActionResult(
            action_type=action_type, success=False,
            output_file=None, summary="Action failed", error=str(e),
        )


def _draft_investigation_report(
    assessed: AssessedSignal,
    context: SensitivityContext,
    client: "LLMClient",
    out_dir: Path,
    cache_dir: Path | None,
) -> Path:
    from agent.assessor import load_prompt, _call_claude
    mrp_context = _gather_mrp_context(out_dir, assessed.signal.id)
    template, version = load_prompt("briefing")
    prompt = template.format(
        signal_summary=(
            f"Source: {assessed.signal.source_name}\n"
            f"Date: {assessed.signal.collected_at[:10]}\n"
            f"Novelty: {assessed.novelty.novelty_reasoning if assessed.novelty else 'N/A'}"
        ),
        severity=assessed.severity.severity.value.upper() if assessed.severity else "UNKNOWN",
        sensitivity_data=json.dumps([
            {
                "parameter": w.parameter_name,
                "sensitivity_$/kg_per_1pct": w.sensitivity_cost_per_unit,
                "risk_flags": w.risk_flags,
            }
            for w in context.signal_priority_weights[:5]
        ], indent=2),
        base_cost_per_kg=context.base_cost_per_kg_api,
        mrp_analysis_results=json.dumps(mrp_context, indent=2) if mrp_context else "Not yet run",
        source_url=assessed.signal.source_url or "unavailable",
        impact_reasoning=(
            assessed.impact.estimated_cost_impact_reasoning
            if assessed.impact else "Impact not yet quantified"
        ),
        estimated_cost_delta=(
            f"${assessed.impact.estimated_cost_impact_per_kg:,.2f}/kg"
            if assessed.impact and assessed.impact.estimated_cost_impact_per_kg
            else "not quantified"
        ),
    )
    report_text = _call_claude(prompt, client, cache_dir, step="briefing")
    _validate_citations(report_text, assessed.signal.source_url)
    report_path = out_dir / f"investigation_report_{assessed.signal.id[:8]}.md"
    report_path.write_text(report_text)
    return report_path


def _draft_management_briefing(
    assessed: AssessedSignal,
    context: SensitivityContext,
    client: "LLMClient",
    out_dir: Path,
    cache_dir: Path | None,
) -> Path:
    from agent.assessor import _call_claude
    investigation = out_dir / f"investigation_report_{assessed.signal.id[:8]}.md"
    investigation_text = investigation.read_text() if investigation.exists() else "Not available"
    briefing_prompt = (
        "Write a one-page management briefing for the VP Manufacturing and CFO based on:\n\n"
        "---\n"
        f"{investigation_text[:3000]}\n"
        "---\n\n"
        "Structure:\n"
        "1. Situation (2-3 sentences)\n"
        "2. Impact on Cost and Timeline (bullet points with dollar figures; cite source for each)\n"
        "3. Options Available (2-3 options with trade-offs)\n"
        "4. Recommended Action (one specific recommendation)\n"
        "5. Decision Required (what leadership must decide and by when)\n\n"
        "Constraints: No jargon. Max 400 words. Every dollar figure cites its source.\n"
        "Cite MRP figures as [MRP sensitivity report]. Cite signals as [source URL or publication]."
    )
    briefing_path = out_dir / f"management_briefing_{assessed.signal.id[:8]}.md"
    response = _call_claude(briefing_prompt, client, cache_dir, step="briefing")
    _validate_citations(response, assessed.signal.source_url)
    briefing_path.write_text(response)
    return briefing_path


def _format_alert(assessed: AssessedSignal, context: SensitivityContext) -> str:
    sev = assessed.severity.severity.value.upper() if assessed.severity else "UNKNOWN"
    lines = [
        f"[{sev}] Supply Chain Alert",
        f"Source: {assessed.signal.source_name}",
        f"Date: {assessed.signal.collected_at[:10]}",
        f"URL: {assessed.signal.source_url or 'N/A'}",
        "",
        "WHAT IS NEW:",
        assessed.novelty.novelty_reasoning if assessed.novelty else "N/A",
        "",
        "SEVERITY REASONING:",
        assessed.severity.severity_reasoning if assessed.severity else "N/A",
    ]
    if assessed.impact and assessed.impact.estimated_cost_impact_per_kg:
        lines += [
            "",
            f"ESTIMATED COST IMPACT: +${assessed.impact.estimated_cost_impact_per_kg:,.2f}/kg API",
            f"Confidence: {assessed.impact.confidence}",
        ]
    lines += ["", "ACTIONS QUEUED:", *[f"  - {a.value}" for a in assessed.recommended_actions]]
    return "\n".join(lines)


def _validate_citations(text: str, source_url: str | None) -> None:
    import re
    dollar_mentions = re.findall(r'\$[\d,]+(?:\.\d+)?(?:/kg)?', text)
    week_mentions = re.findall(r'\d+ weeks?', text)
    cited = (
        "[MRP" in text
        or "[source" in text.lower()
        or (source_url and source_url[:20] in text)
    )
    if (dollar_mentions or week_mentions) and not cited:
        print(
            f"WARNING: Citation check failed. "
            f"{len(dollar_mentions)} dollar figures, {len(week_mentions)} week references "
            "found but no citation markers detected. Review output before sharing."
        )


def _gather_mrp_context(out_dir: Path, signal_id: str) -> dict | None:
    prefix = signal_id[:8]
    results = {}
    for suffix in ["tariff_sweep", "cdmo_removal"]:
        f = out_dir / f"{suffix}_{prefix}.json"
        if f.exists():
            results[suffix] = json.loads(f.read_text())
    return results if results else None
