"""
MRP integration wrapper.

Imports MRP POC functions directly — no subprocess calls, no HTTP.
If these imports fail, the agent cannot start. This validates the integration
at startup rather than at first use.
"""
from __future__ import annotations
import json
from pathlib import Path

try:
    from mrp.engine import calculate_bom
    from mrp.risk import (
        generate_sensitivity_report,
        apply_tariff_overlay,
        model_cdmo_removal,
    )
    from mrp.loader import load_process, load_price_list, load_risk_profile
    from mrp.domain import ProcessConfig, SensitivityReport as MRPSensitivityReport
    from mrp.units import ureg
    MRP_AVAILABLE = True
    MRP_IMPORT_ERROR = ""
except ImportError as _e:
    MRP_AVAILABLE = False
    MRP_IMPORT_ERROR = str(_e)

from agent.domain import SensitivityContext, SignalPriorityWeight


def assert_mrp_available() -> None:
    if not MRP_AVAILABLE:
        raise RuntimeError(
            f"MRP POC is not installed or importable.\n"
            f"Import error: {MRP_IMPORT_ERROR}\n\n"
            f"Fix: cd pharma-mrp-poc && pip install -e .\n"
            f"Then verify: python -c 'from mrp.engine import calculate_bom'"
        )


def load_sensitivity_context(json_path: Path) -> SensitivityContext:
    """
    Load a sensitivity_report.json produced by `mrp risk-sensitivity`
    into a SensitivityContext. Always reloads from disk — not cached.
    """
    data = json.loads(json_path.read_text())
    weights = [
        SignalPriorityWeight(
            rank=w["rank"],
            parameter_name=w["parameter"],
            parameter_type=w["parameter_type"],
            sensitivity_cost_per_unit=w["sensitivity_cost_per_unit"],
            country_of_origin=w.get("country_of_origin"),
            cdmo_node_name=w.get("cdmo_node"),
            cdmo_node_id=w.get("cdmo_node_id"),
            is_single_source=w.get("is_single_source", False),
            is_indirect_china=w.get("is_indirect_china", False),
            timeline_impact_weeks=w.get("timeline_impact_weeks"),
            risk_flags=w.get("risk_flags", []),
            tariff_impact_at_55pct=w.get("tariff_impact_at_55pct"),
            target_id=w.get("target_id"),
        )
        for w in data.get("signal_priority_weights", [])
    ]
    exp = data.get("exposure_summary", {})
    return SensitivityContext(
        report_id=data.get("report_id", "unknown"),
        scenario_id=data.get("scenario_id", "unknown"),
        process_name=data.get("process_name", "unknown"),
        base_cost_per_kg_api=data["base_cost_per_kg_api"],
        currency=data.get("currency", "USD"),
        china_origin_cost_pct=exp.get("china_origin_cost_pct", 0.0),
        indirect_china_cost_pct=exp.get("indirect_china_cost_pct", 0.0),
        single_source_cost_pct=exp.get("single_source_cost_pct", 0.0),
        cdmo_exposed_cost_pct=exp.get("cdmo_exposed_cost_pct", 0.0),
        signal_priority_weights=weights,
        tariff_sweep=data.get("tariff_sweep", []),
        cdmo_removal_scenarios=data.get("cdmo_removal_scenarios", []),
    )


def rerun_tariff_analysis(
    process_yaml: Path,
    prices_yaml: Path,
    risk_profile_yaml: Path,
    tariff_rates: list[float],
    geography: str,
    batch_size_kg: float = 50.0,
    num_batches: int = 5,
) -> dict:
    assert_mrp_available()
    graph   = load_process(process_yaml)
    prices  = load_price_list(prices_yaml)
    profile = load_risk_profile(risk_profile_yaml)
    config  = ProcessConfig(
        batch_size=ureg.Quantity(batch_size_kg, "kg"),
        num_batches=num_batches,
    )
    bom = calculate_bom(graph, config, prices)
    results = []
    for rate in tariff_rates:
        overlay = apply_tariff_overlay(bom, rate, geography, profile, include_indirect=True)
        results.append({
            "tariff_rate_pct": rate,
            "adjusted_cost_per_kg": overlay.adjusted_cost_per_kg_api,
            "cost_per_kg_delta": overlay.cost_per_kg_delta,
            "tariff_cost_total": overlay.tariff_cost_total,
            "exposed_materials": overlay.exposed_material_lines,
        })
    return {
        "base_cost_per_kg_api": bom.cost_per_kg_api,
        "tariff_sweep_results": results,
        "currency": prices.currency,
    }


def rerun_cdmo_removal_analysis(
    process_yaml: Path,
    prices_yaml: Path,
    risk_profile_yaml: Path,
    cdmo_node_id: str,
    emergency_premium_pct: float = 50.0,
    batch_size_kg: float = 50.0,
    num_batches: int = 5,
) -> dict:
    assert_mrp_available()
    graph   = load_process(process_yaml)
    prices  = load_price_list(prices_yaml)
    profile = load_risk_profile(risk_profile_yaml)
    config  = ProcessConfig(
        batch_size=ureg.Quantity(batch_size_kg, "kg"),
        num_batches=num_batches,
    )
    bom = calculate_bom(graph, config, prices)
    result = model_cdmo_removal(
        graph, config, prices, bom, cdmo_node_id, profile, emergency_premium_pct
    )
    return {
        "cdmo_node_name": result.cdmo_node_name,
        "biosecure_act_listed": result.biosecure_act_listed,
        "affected_steps": result.affected_step_names,
        "affected_materials": result.affected_material_names,
        "base_cost_per_kg": result.base_cost_per_kg_api,
        "emergency_cost_per_kg": result.emergency_cost_per_kg_api,
        "cost_delta_per_kg": result.cost_per_kg_delta,
        "timeline_weeks": result.timeline_critical_path_weeks,
        "timeline_unknown_materials": result.timeline_unknown_materials,
    }


def rerun_full_sensitivity(
    process_yaml: Path,
    prices_yaml: Path,
    risk_profile_yaml: Path,
    batch_size_kg: float = 50.0,
    num_batches: int = 5,
) -> "MRPSensitivityReport":
    assert_mrp_available()
    graph   = load_process(process_yaml)
    prices  = load_price_list(prices_yaml)
    profile = load_risk_profile(risk_profile_yaml)
    config  = ProcessConfig(
        batch_size=ureg.Quantity(batch_size_kg, "kg"),
        num_batches=num_batches,
    )
    bom = calculate_bom(graph, config, prices)
    return generate_sensitivity_report(graph, config, prices, bom, profile)
