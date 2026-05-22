from __future__ import annotations
import json
import re
from pathlib import Path

from agent.domain import (
    Signal, SensitivityContext, SignalState,
    RelevanceResult, NoveltyResult, SeverityResult, ImpactResult,
    MetacognitionResult, AssessedSignal, SeverityTier, RiskVectorType, ActionType,
)

PROMPT_DIR = Path(__file__).parent.parent / "prompts"


def load_prompt(name: str) -> tuple[str, str]:
    """Returns (template_text, version_string) for a named prompt."""
    matches = list(PROMPT_DIR.glob(f"{name}_v*.txt"))
    if not matches:
        raise FileNotFoundError(f"No prompt file found for '{name}' in {PROMPT_DIR}")
    latest = sorted(matches, key=lambda p: p.stem.split("_v")[1])[-1]
    version = latest.stem.split("_v")[1]
    return latest.read_text(), version


def assess_signal(
    signal: Signal,
    context: SensitivityContext,
    states: dict[str, SignalState],
    client: "LLMClient",
    cache_dir: Path | None = None,
    skip_impact: bool = False,
    interactive: bool | None = None,
) -> AssessedSignal:
    """
    Run the 4-step assessment pipeline for one signal.
    Short-circuits at the first negative gate (irrelevant or not novel).
    After severity and impact, runs a metacognition grader; if the grade is
    UNCERTAIN and we are in an interactive terminal, prompts a human adjudicator.
    """
    from agent.adjudicator import is_interactive as _is_tty, adjudicate_severity, adjudicate_impact
    _interactive = interactive if interactive is not None else _is_tty()

    try:
        relevance = _step_relevance(signal, context, client, cache_dir)
        if not relevance.is_relevant:
            return AssessedSignal(
                signal=signal, relevance=relevance,
                novelty=None, severity=None, impact=None,
                recommended_actions=[ActionType.ADD_TO_DIGEST],
            )

        relevant_states = {
            name: states[name] for name in relevance.relevant_parameters
            if name in states
        }
        novelty = _step_novelty(signal, relevant_states, client, cache_dir)
        if not novelty.is_novel:
            return AssessedSignal(
                signal=signal, relevance=relevance, novelty=novelty,
                severity=None, impact=None,
                recommended_actions=[ActionType.ADD_TO_DIGEST],
            )

        relevant_weights = [
            w for w in context.signal_priority_weights
            if w.parameter_name in relevance.relevant_parameters
        ]
        severity = _step_severity(signal, novelty, relevant_weights, client, cache_dir)

        context_summary = (
            f"Process: {context.process_name}. "
            f"Base cost: ${context.base_cost_per_kg_api:,.2f}/kg. "
            f"CN exposure: {context.china_origin_cost_pct:.1f}%. "
            f"CDMO exposed: {context.cdmo_exposed_cost_pct:.1f}%."
        )
        severity_meta = _step_metacognition(
            step="severity",
            signal=signal,
            assessment_dict={
                "severity": severity.severity.value,
                "severity_reasoning": severity.severity_reasoning,
                "risk_vector_type": severity.risk_vector_type.value,
                "affected_geography": severity.affected_geography,
                "affected_cdmo_node_name": severity.affected_cdmo_node_name,
            },
            context_summary=context_summary,
            client=client,
            cache_dir=cache_dir,
        )
        if severity_meta.grade == "UNCERTAIN" and _interactive:
            severity, severity_meta = adjudicate_severity(severity, severity_meta, signal)

        impact = None
        impact_meta = None
        if not skip_impact and severity.severity in (SeverityTier.HIGH, SeverityTier.CRITICAL):
            impact = _step_impact(signal, severity, novelty, context, client, cache_dir)
            impact_meta = _step_metacognition(
                step="impact",
                signal=signal,
                assessment_dict={
                    "estimated_cost_impact_per_kg": impact.estimated_cost_impact_per_kg,
                    "estimated_cost_impact_reasoning": impact.estimated_cost_impact_reasoning,
                    "estimated_timeline_impact_weeks": impact.estimated_timeline_impact_weeks,
                    "confidence": impact.confidence,
                },
                context_summary=context_summary,
                client=client,
                cache_dir=cache_dir,
            )
            if impact_meta.grade == "UNCERTAIN" and _interactive:
                impact, impact_meta = adjudicate_impact(impact, impact_meta, signal)

        actions = _select_actions(severity, relevance, novelty)
        return AssessedSignal(
            signal=signal, relevance=relevance, novelty=novelty,
            severity=severity, impact=impact,
            recommended_actions=actions,
            severity_metacognition=severity_meta,
            impact_metacognition=impact_meta,
        )
    except Exception as e:
        return AssessedSignal(
            signal=signal,
            relevance=RelevanceResult(
                is_relevant=False, relevant_parameters=[],
                relevance_reasoning="Assessment failed",
                prompt_version="unknown",
            ),
            novelty=None, severity=None, impact=None,
            recommended_actions=[],
            assessment_failed=True,
            failure_reason=str(e),
        )


def _step_relevance(
    signal: Signal,
    context: SensitivityContext,
    client: "LLMClient",
    cache_dir: Path | None,
) -> RelevanceResult:
    template, version = load_prompt("relevance")
    weights_summary = json.dumps([
        {
            "rank": w.rank,
            "parameter_name": w.parameter_name,
            "parameter_type": w.parameter_type,
            "cdmo_node": w.cdmo_node_name,
            "country_of_origin": w.country_of_origin,
            "risk_flags": w.risk_flags,
        }
        for w in context.signal_priority_weights[:10]
    ], indent=2)
    prompt = template.format(
        signal_priority_weights_json=weights_summary,
        source_name=signal.source_name,
        source_url=signal.source_url or "unknown",
        collected_date=signal.collected_at[:10],
        raw_content=signal.raw_content[:3000],
    )
    response = _call_claude(prompt, client, cache_dir, step="relevance")
    data = _parse_llm_json(response, required_fields=["is_relevant", "relevance_reasoning"])
    return RelevanceResult(
        is_relevant=bool(data["is_relevant"]),
        relevant_parameters=data.get("relevant_parameters", []),
        relevance_reasoning=data["relevance_reasoning"],
        prompt_version=version,
    )


def _step_novelty(
    signal: Signal,
    relevant_states: dict[str, SignalState],
    client: "LLMClient",
    cache_dir: Path | None,
) -> NoveltyResult:
    template, version = load_prompt("novelty")
    states_summary = json.dumps({
        name: {
            "current_state_summary": s.current_state_summary,
            "baseline_value": s.baseline_value,
            "baseline_value_unit": s.baseline_value_unit,
            "risk_level": s.risk_level,
            "last_updated": s.last_updated_at[:10],
        }
        for name, s in relevant_states.items()
    }, indent=2)
    prompt = template.format(
        signal_states_json=states_summary,
        raw_content=signal.raw_content[:3000],
        source_name=signal.source_name,
        collected_date=signal.collected_at[:10],
    )
    response = _call_claude(prompt, client, cache_dir, step="novelty")
    data = _parse_llm_json(response, required_fields=["is_novel", "novelty_reasoning"])
    return NoveltyResult(
        is_novel=bool(data["is_novel"]),
        novelty_reasoning=data["novelty_reasoning"],
        updated_parameter_states=data.get("updated_parameter_states", []),
        prompt_version=version,
    )


def _step_severity(
    signal: Signal,
    novelty: NoveltyResult,
    relevant_weights: list,
    client: "LLMClient",
    cache_dir: Path | None,
) -> SeverityResult:
    template, version = load_prompt("severity")
    weights_summary = json.dumps([
        {
            "parameter_name": w.parameter_name,
            "sensitivity_cost_per_unit": w.sensitivity_cost_per_unit,
            "is_single_source": w.is_single_source,
            "cdmo_node": w.cdmo_node_name,
            "risk_flags": w.risk_flags,
            "timeline_impact_weeks": w.timeline_impact_weeks,
        }
        for w in relevant_weights
    ], indent=2)
    prompt = template.format(
        affected_parameters_with_weights_json=weights_summary,
        novelty_reasoning=novelty.novelty_reasoning,
        relevant_parameters=", ".join(
            s.get("parameter_name", "") for s in novelty.updated_parameter_states
        ),
        source_name=signal.source_name,
        collected_date=signal.collected_at[:10],
        raw_content=signal.raw_content[:2000],
    )
    response = _call_claude(prompt, client, cache_dir, step="severity")
    data = _parse_llm_json(response, required_fields=["severity", "severity_reasoning"])

    severity_str = str(data["severity"]).upper()
    try:
        severity = SeverityTier(severity_str.lower())
    except ValueError:
        severity = SeverityTier.ROUTINE

    rvt_str = data.get("risk_vector_type", "unknown")
    try:
        risk_vector = RiskVectorType(rvt_str)
    except ValueError:
        risk_vector = RiskVectorType.UNKNOWN

    return SeverityResult(
        severity=severity,
        severity_reasoning=data["severity_reasoning"],
        risk_vector_type=risk_vector,
        affected_geography=data.get("affected_geography"),
        affected_cdmo_node_name=data.get("affected_cdmo_node_name"),
        prompt_version=version,
    )


def _step_impact(
    signal: Signal,
    severity: SeverityResult,
    novelty: NoveltyResult,
    context: SensitivityContext,
    client: "LLMClient",
    cache_dir: Path | None,
) -> ImpactResult:
    template, version = load_prompt("impact")
    relevant_weights = [
        w for w in context.signal_priority_weights
        if (severity.affected_cdmo_node_name and w.cdmo_node_name == severity.affected_cdmo_node_name)
        or (severity.affected_geography and w.country_of_origin == severity.affected_geography)
    ] or context.signal_priority_weights[:3]
    prompt = template.format(
        affected_parameters_with_weights_json=json.dumps([
            {
                "parameter_name": w.parameter_name,
                "sensitivity_cost_per_unit": w.sensitivity_cost_per_unit,
                "sensitivity_unit": "$/kg_api per 1% change",
            }
            for w in relevant_weights
        ], indent=2),
        base_cost_per_kg=context.base_cost_per_kg_api,
        tariff_sweep_json=json.dumps(context.tariff_sweep, indent=2),
        cdmo_removal_json=json.dumps(context.cdmo_removal_scenarios, indent=2),
        source_name=signal.source_name,
        collected_date=signal.collected_at[:10],
        raw_content=signal.raw_content[:1500],
        novelty_reasoning=novelty.novelty_reasoning,
    )
    response = _call_claude(prompt, client, cache_dir, step="impact")
    data = _parse_llm_json(response, required_fields=["estimated_cost_impact_reasoning"])
    return ImpactResult(
        estimated_cost_impact_per_kg=data.get("estimated_cost_impact_per_kg"),
        estimated_cost_impact_reasoning=data["estimated_cost_impact_reasoning"],
        estimated_timeline_impact_weeks=data.get("estimated_timeline_impact_weeks"),
        estimated_timeline_reasoning=data.get("estimated_timeline_reasoning", ""),
        confidence=data.get("confidence", "low"),
        caveats=data.get("caveats", []),
        prompt_version=version,
    )


def _step_metacognition(
    step: str,
    signal: Signal,
    assessment_dict: dict,
    context_summary: str,
    client: "LLMClient",
    cache_dir: Path | None,
) -> MetacognitionResult:
    template, version = load_prompt("metacognition")
    prompt = template.format(
        step=step,
        assessment_json=json.dumps(assessment_dict, indent=2),
        source_name=signal.source_name,
        collected_date=signal.collected_at[:10],
        raw_content=signal.raw_content[:2000],
        context_summary=context_summary,
    )
    response = _call_claude(prompt, client, cache_dir, step="metacognition")
    try:
        data = _parse_llm_json(response, required_fields=["grade", "reasoning"])
    except LLMResponseParseError:
        return MetacognitionResult(
            grade="CERTAIN",
            confidence=0.5,
            uncertainty_flags=["metacognition parse failed — defaulting to CERTAIN"],
            reasoning="Metacognition response could not be parsed.",
            step=step,
            prompt_version=version,
        )
    grade = str(data.get("grade", "CERTAIN")).upper()
    if grade not in ("CERTAIN", "UNCERTAIN"):
        grade = "CERTAIN"
    return MetacognitionResult(
        grade=grade,
        confidence=float(data.get("confidence", 0.8)),
        uncertainty_flags=data.get("uncertainty_flags", []),
        reasoning=data["reasoning"],
        step=step,
        prompt_version=version,
    )


def _select_actions(
    severity: SeverityResult,
    relevance: RelevanceResult,
    novelty: NoveltyResult,
) -> list[ActionType]:
    if severity.severity == SeverityTier.ROUTINE:
        return [ActionType.ADD_TO_DIGEST]
    actions = [ActionType.SEND_ALERT]
    if severity.risk_vector_type == RiskVectorType.TARIFF_ESCALATION:
        actions.append(ActionType.TRIGGER_TARIFF_SWEEP)
    if severity.risk_vector_type == RiskVectorType.CDMO_REMOVAL:
        actions.append(ActionType.TRIGGER_CDMO_REMOVAL)
    if severity.severity in (SeverityTier.HIGH, SeverityTier.CRITICAL):
        actions.append(ActionType.DRAFT_INVESTIGATION_REPORT)
        if severity.severity == SeverityTier.CRITICAL:
            actions.append(ActionType.DRAFT_MANAGEMENT_BRIEFING)
    return actions


def _call_claude(
    prompt: str,
    client: "LLMClient",
    cache_dir: Path | None,
    step: str = "unknown",
    retry: bool = True,
) -> str:
    from agent.llm import _safe_fallback_json
    try:
        return client.complete(prompt, step)
    except Exception as e:
        if retry:
            try:
                return client.complete(
                    prompt + "\n\nReturn only a valid JSON object. No markdown. No preamble.",
                    step,
                )
            except Exception:
                pass
        return _safe_fallback_json(step, str(e))


def _parse_llm_json(text: str, required_fields: list[str]) -> dict:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.MULTILINE)
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        text = match.group(0)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise LLMResponseParseError(f"JSON parse failed: {e}\nRaw: {text[:200]}")
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise LLMResponseParseError(f"Missing required fields: {missing}")
    return data


class LLMResponseParseError(ValueError):
    pass
