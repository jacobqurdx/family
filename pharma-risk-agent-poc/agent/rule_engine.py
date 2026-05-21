from __future__ import annotations
"""
Rule engine for structured internal signals (MES / QMS / ERP / capacity tracker).

Assesses InternalSignal objects using deterministic threshold logic — no LLM calls.
Produces AssessedSignal objects in the same format as the LLM pipeline so downstream
reporters and action selectors handle them identically.
"""

import hashlib
import json
import yaml
from datetime import datetime, timezone
from pathlib import Path

from agent.domain import (
    Signal, SignalSourceType,
    InternalSignal, RiskProfile, RiskProfileParameter, RiskProfileScenario,
    InternalThresholds, DefaultThresholds,
    RelevanceResult, NoveltyResult, SeverityResult,
    AssessedSignal, SignalState, SensitivityContext, ScenarioImpact,
    SeverityTier, RiskVectorType, ActionType,
)

_NOVELTY_CHANGE_THRESHOLD_PCT = 5.0
_PROMPT_VERSION = "rule_engine_1.0"


# ─── YAML loader ──────────────────────────────────────────────────────────────

def load_risk_profile_yaml(path: Path) -> RiskProfile:
    """Load a risk_profile.yaml and return a RiskProfile domain object."""
    data = yaml.safe_load(path.read_text())

    scenarios = [
        RiskProfileScenario(
            id=s["id"],
            name=s["name"],
            is_primary=s.get("is_primary", False),
            mrp_scenario_id=s.get("mrp_scenario_id"),
            notes=s.get("notes"),
        )
        for s in data.get("scenarios", [])
    ]

    parameters = []
    for p in data.get("parameters", []):
        thresh_data = p.get("internal_thresholds")
        thresholds = None
        if thresh_data:
            thresholds = InternalThresholds(
                planned_value=float(thresh_data["planned_value"]),
                unit=str(thresh_data.get("unit", "")),
                elevated_threshold=float(thresh_data["elevated_threshold"]),
                high_threshold=float(thresh_data["high_threshold"]),
                critical_threshold=float(thresh_data["critical_threshold"]),
                threshold_type=str(thresh_data.get("threshold_type", "ratio")),
            )
        parameters.append(RiskProfileParameter(
            id=p["id"],
            name=p["name"],
            category=p["category"],
            risk_tier=p["risk_tier"],
            applies_to_scenarios=list(p.get("applies_to_scenarios", [])),
            description=p.get("description"),
            internal_thresholds=thresholds,
            sources_to_monitor=list(p.get("sources_to_monitor", [])),
            notes=p.get("notes"),
        ))

    default_thresholds = None
    if "default_thresholds" in data:
        dt = data["default_thresholds"]
        default_thresholds = DefaultThresholds(
            yield_parameters=dict(dt.get("yield_parameters", {})),
            rate_parameters=dict(dt.get("rate_parameters", {})),
            price_parameters=dict(dt.get("price_parameters", {})),
        )

    return RiskProfile(
        name=data["name"],
        version=str(data.get("version", "1.0")),
        scenarios=scenarios,
        parameters=parameters,
        default_thresholds=default_thresholds,
    )


# ─── Signal converter ─────────────────────────────────────────────────────────

def _internal_to_signal(internal: InternalSignal) -> Signal:
    """Convert an InternalSignal into a Signal for use in AssessedSignal."""
    lines = [
        f"Internal signal: {internal.signal_type}",
        f"Parameter: {internal.parameter_id}",
        f"Source system: {internal.source_system}",
        f"Actual value: {internal.actual_value} {internal.unit}",
        f"Planned value: {internal.planned_value} {internal.unit}",
        f"Measured: {internal.measurement_timestamp}",
    ]
    for k, v in internal.context.items():
        lines.append(f"{k}: {v}")
    content = "\n".join(lines)
    return Signal(
        id=internal.id,
        source_type=SignalSourceType.FILE,
        source_name=internal.source_system,
        source_url=None,
        collected_at=internal.measurement_timestamp,
        raw_content=content,
        raw_content_hash=hashlib.sha256(content.encode()).hexdigest(),
    )


# ─── Core assessment ──────────────────────────────────────────────────────────

def assess_internal_signal(
    signal: InternalSignal,
    profile: RiskProfile,
    states: dict[str, SignalState],
) -> AssessedSignal:
    """
    Assess a structured internal signal using deterministic threshold rules.
    No LLM calls. Returns AssessedSignal with assessment_engine="rule_engine".
    """
    ext_signal = _internal_to_signal(signal)

    # Step 1: Relevance — parameter must exist in profile
    param = profile.get_parameter(signal.parameter_id)
    if param is None:
        return AssessedSignal(
            signal=ext_signal,
            relevance=RelevanceResult(
                is_relevant=False,
                relevant_parameters=[],
                relevance_reasoning=(
                    f"Parameter id '{signal.parameter_id}' not found in risk profile. "
                    "No monitoring rules configured."
                ),
                prompt_version=_PROMPT_VERSION,
            ),
            novelty=None, severity=None, impact=None,
            recommended_actions=[ActionType.ADD_TO_DIGEST],
            assessment_engine="rule_engine",
        )

    relevance = RelevanceResult(
        is_relevant=True,
        relevant_parameters=[param.name],
        relevance_reasoning=(
            f"Internal {signal.signal_type} signal for '{param.name}' "
            f"(category: {param.category}, risk tier: {param.risk_tier}). "
            f"Applies to scenarios: {', '.join(param.applies_to_scenarios)}."
        ),
        prompt_version=_PROMPT_VERSION,
    )

    # Step 2: Novelty — compare actual vs prior baseline
    is_novel, novelty_reasoning, updated_states = _check_novelty(signal, param, states)
    novelty = NoveltyResult(
        is_novel=is_novel,
        novelty_reasoning=novelty_reasoning,
        updated_parameter_states=updated_states,
        prompt_version=_PROMPT_VERSION,
    )

    if not is_novel:
        return AssessedSignal(
            signal=ext_signal, relevance=relevance, novelty=novelty,
            severity=None, impact=None,
            recommended_actions=[ActionType.ADD_TO_DIGEST],
            assessment_engine="rule_engine",
        )

    # Step 3: Severity — apply threshold rules
    thresholds = profile.thresholds_for(param)
    if thresholds is None:
        return AssessedSignal(
            signal=ext_signal, relevance=relevance, novelty=novelty,
            severity=SeverityResult(
                severity=SeverityTier.ELEVATED,
                severity_reasoning=(
                    f"No thresholds configured for '{param.name}'. "
                    "Defaulting to ELEVATED for manual review."
                ),
                risk_vector_type=_category_to_risk_vector(param.category),
                affected_geography=None,
                affected_cdmo_node_name=None,
                prompt_version=_PROMPT_VERSION,
            ),
            impact=None,
            recommended_actions=[ActionType.SEND_ALERT],
            assessment_engine="rule_engine",
        )

    severity_tier, severity_reasoning = _compute_severity(
        signal.actual_value, thresholds
    )
    severity = SeverityResult(
        severity=severity_tier,
        severity_reasoning=severity_reasoning,
        risk_vector_type=_category_to_risk_vector(param.category),
        affected_geography=None,
        affected_cdmo_node_name=None,
        prompt_version=_PROMPT_VERSION,
    )

    actions = _select_rule_engine_actions(severity_tier, param)
    return AssessedSignal(
        signal=ext_signal, relevance=relevance, novelty=novelty,
        severity=severity, impact=None,
        recommended_actions=actions,
        assessment_engine="rule_engine",
    )


# ─── Threshold computation ────────────────────────────────────────────────────

def _compute_severity(
    actual: float,
    thresholds: InternalThresholds,
) -> tuple[SeverityTier, str]:
    """
    For threshold_type="ratio":   severity_value = actual / planned_value
    For threshold_type="absolute": severity_value = actual  (direct comparison)

    Ratio: lower is worse (yield). Absolute: higher is worse (failure rate, delays, SDD %).
    """
    if thresholds.threshold_type == "ratio":
        planned = thresholds.planned_value
        if planned == 0:
            return SeverityTier.ROUTINE, "Planned value is 0; cannot compute yield ratio."
        ratio = actual / planned
        pct = ratio * 100
        if ratio < thresholds.critical_threshold:
            return SeverityTier.CRITICAL, (
                f"Actual {actual:.1f} = {pct:.1f}% of planned {planned:.1f}. "
                f"Below CRITICAL threshold ({thresholds.critical_threshold * 100:.1f}%)."
            )
        if ratio < thresholds.high_threshold:
            return SeverityTier.HIGH, (
                f"Actual {actual:.1f} = {pct:.1f}% of planned {planned:.1f}. "
                f"Below HIGH threshold ({thresholds.high_threshold * 100:.1f}%)."
            )
        if ratio < thresholds.elevated_threshold:
            return SeverityTier.ELEVATED, (
                f"Actual {actual:.1f} = {pct:.1f}% of planned {planned:.1f}. "
                f"Below ELEVATED threshold ({thresholds.elevated_threshold * 100:.1f}%)."
            )
        return SeverityTier.ROUTINE, (
            f"Actual {actual:.1f} = {pct:.1f}% of planned {planned:.1f}. Within normal range."
        )
    else:  # absolute — compare actual directly to threshold
        if actual > thresholds.critical_threshold:
            return SeverityTier.CRITICAL, (
                f"Actual {actual:.1f} exceeds CRITICAL threshold ({thresholds.critical_threshold:.1f})."
            )
        if actual > thresholds.high_threshold:
            return SeverityTier.HIGH, (
                f"Actual {actual:.1f} exceeds HIGH threshold ({thresholds.high_threshold:.1f})."
            )
        if actual > thresholds.elevated_threshold:
            return SeverityTier.ELEVATED, (
                f"Actual {actual:.1f} exceeds ELEVATED threshold ({thresholds.elevated_threshold:.1f})."
            )
        return SeverityTier.ROUTINE, (
            f"Actual {actual:.1f} within normal range "
            f"(below ELEVATED threshold {thresholds.elevated_threshold:.1f})."
        )


# ─── Novelty check ────────────────────────────────────────────────────────────

def _check_novelty(
    signal: InternalSignal,
    param: RiskProfileParameter,
    states: dict[str, SignalState],
) -> tuple[bool, str, list[dict]]:
    """
    Returns (is_novel, reasoning, updated_parameter_states).
    Novel if actual value changed > 5% vs prior baseline (or no prior baseline).
    For planned_value == 0 (e.g. batch failures, PO delays): novel if actual > 0.
    """
    state = states.get(param.name)

    if state is None or state.baseline_value is None:
        planned = signal.planned_value
        if planned == 0:
            is_novel = signal.actual_value > 0
            if is_novel:
                return True, (
                    f"No prior baseline. Actual {signal.actual_value} {signal.unit} "
                    f"deviates from planned 0."
                ), _build_state_update(signal, param)
            return False, (
                f"No prior baseline. Actual matches planned (both 0). No change."
            ), []

        change_pct = abs(signal.actual_value - planned) / max(abs(planned), 1e-9) * 100
        if change_pct > _NOVELTY_CHANGE_THRESHOLD_PCT:
            return True, (
                f"No prior state. Actual {signal.actual_value} differs from "
                f"planned {planned} by {change_pct:.1f}% (threshold: 5%)."
            ), _build_state_update(signal, param)
        return False, (
            f"No prior state. Actual {signal.actual_value} is within "
            f"{change_pct:.1f}% of planned {planned} — no material change."
        ), []

    prior = state.baseline_value
    change_pct = abs(signal.actual_value - prior) / max(abs(prior), 1e-9) * 100
    if change_pct > _NOVELTY_CHANGE_THRESHOLD_PCT:
        return True, (
            f"Value changed {change_pct:.1f}% from prior baseline "
            f"({prior} → {signal.actual_value} {signal.unit})."
        ), _build_state_update(signal, param)
    return False, (
        f"Value unchanged within 5% tolerance "
        f"(prior: {prior}, current: {signal.actual_value} {signal.unit}, "
        f"change: {change_pct:.1f}%)."
    ), []


def _build_state_update(signal: InternalSignal, param: RiskProfileParameter) -> list[dict]:
    return [{
        "parameter_name": param.name,
        "new_state_summary": (
            f"{param.name}: actual={signal.actual_value} {signal.unit} "
            f"(planned={signal.planned_value}). "
            f"Measured {signal.measurement_timestamp[:10]} by {signal.source_system}."
        ),
        "new_baseline_value": signal.actual_value,
        "new_baseline_value_unit": signal.unit,
        "change_direction": (
            "increasing" if signal.actual_value > signal.planned_value
            else "decreasing" if signal.actual_value < signal.planned_value
            else "stable"
        ),
    }]


# ─── Multi-scenario comparator ────────────────────────────────────────────────

def compare_across_scenarios(
    assessed: AssessedSignal,
    profile: RiskProfile,
    context: SensitivityContext | None = None,
) -> list[ScenarioImpact]:
    """
    For a given assessed signal, return one ScenarioImpact per profile scenario
    where at least one of the relevant parameters applies.

    If MRP context is available AND the scenario has an mrp_scenario_id AND
    the signal has an impact result, cost figures are populated from MRP data.
    Otherwise qualitative_impact is derived from the highest risk_tier of any
    applicable affected parameter.
    """
    relevant = set(assessed.relevance.relevant_parameters)
    tier_rank = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}

    results: list[ScenarioImpact] = []
    for scenario in profile.scenarios:
        # Find parameters that (a) appear in relevant_parameters and (b) apply to this scenario
        applicable = [
            p for p in profile.parameters
            if p.name in relevant and scenario.id in p.applies_to_scenarios
        ]
        if not applicable:
            continue

        best_tier = max(applicable, key=lambda p: tier_rank.get(p.risk_tier, 0))
        qualitative = best_tier.risk_tier  # "HIGH" | "MEDIUM" | "LOW"

        cost_delta = None
        timeline = None
        data_source = "estimated"

        if (context is not None
                and scenario.mrp_scenario_id is not None
                and assessed.impact is not None):
            cost_delta = assessed.impact.estimated_cost_impact_per_kg
            timeline = assessed.impact.estimated_timeline_impact_weeks
            data_source = "mrp"
        elif assessed.assessment_engine == "rule_engine":
            data_source = "rule_engine"

        results.append(ScenarioImpact(
            scenario_id=scenario.id,
            scenario_name=scenario.name,
            is_primary=scenario.is_primary,
            qualitative_impact=qualitative,
            cost_delta_per_kg=cost_delta,
            timeline_impact_weeks=timeline,
            data_source=data_source,
        ))

    return results


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _category_to_risk_vector(category: str) -> RiskVectorType:
    return {
        "tariff_escalation": RiskVectorType.TARIFF_ESCALATION,
        "cdmo_removal": RiskVectorType.CDMO_REMOVAL,
        "operational": RiskVectorType.YIELD_DISRUPTION,
        "material_price": RiskVectorType.LEAD_TIME_EXTENSION,
        "capacity_constraint": RiskVectorType.YIELD_DISRUPTION,
    }.get(category, RiskVectorType.UNKNOWN)


def _select_rule_engine_actions(
    tier: SeverityTier, param: RiskProfileParameter
) -> list[ActionType]:
    if tier == SeverityTier.ROUTINE:
        return [ActionType.ADD_TO_DIGEST]
    actions = [ActionType.SEND_ALERT]
    if tier in (SeverityTier.HIGH, SeverityTier.CRITICAL):
        actions.append(ActionType.DRAFT_INVESTIGATION_REPORT)
        if tier == SeverityTier.CRITICAL:
            actions.append(ActionType.DRAFT_MANAGEMENT_BRIEFING)
    return actions
