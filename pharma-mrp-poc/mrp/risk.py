"""
Supply chain risk sensitivity module (v1.3).

Provides:
  generate_sensitivity_report  — one-at-a-time sensitivity analysis + exposure metrics
  apply_tariff_overlay         — cost impact of a tariff rate on geography-origin materials
  model_cdmo_removal           — emergency-sourcing cost when a CDMO node is removed
"""
from __future__ import annotations

import copy
import uuid
from datetime import datetime, timezone

from mrp.domain import (
    ProcessGraph, ProcessConfig, PriceList, BoMResult,
    RiskProfile, SensitivityReport, SensitivityWeightEntry,
    TariffOverlayResult, CDMORemovalResult, ExposureSummary,
)
from mrp.engine import calculate_bom
from mrp.units import to_float


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_sensitivity_report(
    graph: ProcessGraph,
    config: ProcessConfig,
    prices: PriceList,
    bom: BoMResult,
    profile: RiskProfile,
) -> SensitivityReport:
    """
    One-at-a-time sensitivity analysis for all material prices and step yields.

    For material prices: bumps price by 1% and measures $/kg_api impact.
    For step yields: bumps yield by +1% and measures $/kg_api impact (typically negative).

    Returns a SensitivityReport with ranked weights, exposure summary,
    tariff sweep, and CDMO removal scenarios.
    """
    base_cost = bom.cost_per_kg_api
    raw_weights: list[dict] = []

    # 1. Material price sensitivities
    seen_materials: set[str] = set()
    for line in bom.material_lines:
        mat_name = line.material_name
        if mat_name in seen_materials:
            continue
        seen_materials.add(mat_name)

        key = mat_name.lower()
        price_entry = prices.material_prices.get(key)
        if price_entry is None or price_entry.price_per_unit <= 0:
            continue

        prices_bumped = copy.deepcopy(prices)
        base_price = prices_bumped.material_prices[key].price_per_unit
        delta_price = base_price * 0.01
        if delta_price <= 0:
            continue
        prices_bumped.material_prices[key].price_per_unit = base_price + delta_price

        try:
            bom_bumped = calculate_bom(graph, config, prices_bumped)
            sensitivity = bom_bumped.cost_per_kg_api - base_cost
        except Exception:
            continue

        if abs(sensitivity) < 0.001:
            continue

        risk_info = profile.get_material_risk(mat_name)
        cdmo_node_id = risk_info.cdmo_node_id if risk_info else None
        cdmo_node_name = None
        if cdmo_node_id:
            node = profile.get_cdmo_node(cdmo_node_id)
            cdmo_node_name = node.name if node else None

        raw_weights.append({
            "parameter_type": "material_price",
            "target_id": mat_name,
            "parameter": f"{mat_name} price",
            "sensitivity": sensitivity,
            "country_of_origin": risk_info.country_of_origin if risk_info else None,
            "cdmo_node": cdmo_node_name,
            "cdmo_node_id": cdmo_node_id,
            "is_single_source": risk_info.is_single_source if risk_info else False,
            "is_indirect_china": risk_info.is_indirect_china if risk_info else False,
            "timeline_impact_weeks": risk_info.lead_time_weeks if risk_info else None,
            "risk_flags": risk_info.risk_flags if risk_info else [],
        })

    # 2. Step yield sensitivities
    for step_id, step in graph.steps.items():
        base_yield = step.step_yield_pct
        if base_yield >= 99.9:
            continue
        graph_bumped = copy.deepcopy(graph)
        graph_bumped.steps[step_id].step_yield_pct = min(base_yield + 1.0, 100.0)

        try:
            bom_bumped = calculate_bom(graph_bumped, config, prices)
            sensitivity = bom_bumped.cost_per_kg_api - base_cost
        except Exception:
            continue

        raw_weights.append({
            "parameter_type": "step_yield",
            "target_id": step_id,
            "parameter": f"{step.name} yield",
            "sensitivity": sensitivity,
            "country_of_origin": None,
            "cdmo_node": None,
            "cdmo_node_id": None,
            "is_single_source": False,
            "is_indirect_china": False,
            "timeline_impact_weeks": None,
            "risk_flags": ["gmp_step"] if step.gmp_step else [],
        })

    # 3. Rank by |sensitivity| descending
    raw_weights.sort(key=lambda w: abs(w["sensitivity"]), reverse=True)

    # 4. Compute tariff impact at 55% for material_price weights
    tariff_55_map: dict[str, float] = {}
    for rw in raw_weights:
        if rw["parameter_type"] == "material_price":
            ri = profile.get_material_risk(rw["target_id"])
            if ri and (ri.country_of_origin == "CN" or ri.is_indirect_china):
                overlay = apply_tariff_overlay(bom, 55.0, "CN", profile, include_indirect=True)
                tariff_55_map[rw["target_id"]] = overlay.cost_per_kg_delta

    # 5. Build SensitivityWeightEntry list
    weights: list[SensitivityWeightEntry] = []
    for rank, rw in enumerate(raw_weights, start=1):
        weights.append(SensitivityWeightEntry(
            rank=rank,
            parameter=rw["parameter"],
            parameter_type=rw["parameter_type"],
            target_id=rw["target_id"],
            sensitivity_cost_per_unit=round(rw["sensitivity"], 4),
            country_of_origin=rw["country_of_origin"],
            cdmo_node=rw["cdmo_node"],
            cdmo_node_id=rw["cdmo_node_id"],
            is_single_source=rw["is_single_source"],
            is_indirect_china=rw["is_indirect_china"],
            timeline_impact_weeks=rw["timeline_impact_weeks"],
            risk_flags=rw["risk_flags"],
            tariff_impact_at_55pct=tariff_55_map.get(rw["target_id"]),
        ))

    # 6. Exposure summary
    exposure = _compute_exposure(bom, profile)

    # 7. Tariff sweep
    tariff_sweep = [
        apply_tariff_overlay(bom, rate, "CN", profile, include_indirect=True)
        for rate in profile.tariff_sweep_rates
    ]

    # 8. CDMO removal scenarios
    cdmo_scenarios: list[CDMORemovalResult] = []
    for node in profile.cdmo_nodes:
        try:
            result = model_cdmo_removal(graph, config, prices, bom, node.id, profile)
            cdmo_scenarios.append(result)
        except Exception:
            continue

    return SensitivityReport(
        report_id=str(uuid.uuid4()),
        scenario_id=f"{graph.name.replace(' ', '_').lower()}",
        process_name=graph.name,
        base_cost_per_kg_api=round(base_cost, 4),
        currency=prices.currency,
        exposure_summary=exposure,
        signal_priority_weights=weights,
        tariff_sweep=tariff_sweep,
        cdmo_removal_scenarios=cdmo_scenarios,
    )


def apply_tariff_overlay(
    bom: BoMResult,
    tariff_rate_pct: float,
    geography: str,
    profile: RiskProfile,
    include_indirect: bool = True,
) -> TariffOverlayResult:
    """
    Compute the cost impact of applying tariff_rate_pct to all materials
    originating from geography (and optionally indirect-origin materials).

    Tariff is applied to per-batch material cost, then scaled by num_batches.
    """
    tariff_rate = tariff_rate_pct / 100.0
    tariff_cost_total = 0.0
    exposed_names: list[str] = []

    # Deduplicate material costs across lines (sum per material name)
    mat_costs: dict[str, float] = {}
    for line in bom.material_lines:
        mat_costs[line.material_name] = mat_costs.get(line.material_name, 0.0) + line.total_cost

    for mat_name, cost_per_batch in mat_costs.items():
        if cost_per_batch <= 0:
            continue
        risk_info = profile.get_material_risk(mat_name)
        if risk_info is None:
            continue
        is_exposed = (risk_info.country_of_origin == geography)
        if include_indirect:
            is_exposed = is_exposed or risk_info.is_indirect_china
        if is_exposed:
            tariff_cost_total += cost_per_batch * bom.config.num_batches * tariff_rate
            exposed_names.append(mat_name)

    total_api_kg = to_float(bom.config.batch_size, "kg") * bom.config.num_batches
    cost_per_kg_delta = tariff_cost_total / total_api_kg if total_api_kg > 0 else 0.0

    return TariffOverlayResult(
        tariff_rate_pct=tariff_rate_pct,
        adjusted_cost_per_kg_api=round(bom.cost_per_kg_api + cost_per_kg_delta, 4),
        cost_per_kg_delta=round(cost_per_kg_delta, 4),
        tariff_cost_total=round(tariff_cost_total, 4),
        exposed_material_lines=exposed_names,
    )


def model_cdmo_removal(
    graph: ProcessGraph,
    config: ProcessConfig,
    prices: PriceList,
    bom: BoMResult,
    cdmo_node_id: str,
    profile: RiskProfile,
    emergency_premium_pct: float = 50.0,
) -> CDMORemovalResult:
    """
    Model the cost of emergency sourcing when cdmo_node_id is removed.

    Applies emergency_premium_pct markup to all materials assigned to this CDMO,
    re-runs the BoM, and returns the cost delta and timeline.
    """
    cdmo_node = profile.get_cdmo_node(cdmo_node_id)
    if cdmo_node is None:
        raise ValueError(f"CDMO node '{cdmo_node_id}' not found in risk profile")

    affected_materials = [
        m.material_name
        for m in profile.material_risk
        if m.cdmo_node_id == cdmo_node_id
    ]

    prices_emergency = copy.deepcopy(prices)
    for mat_name in affected_materials:
        key = mat_name.lower()
        if key in prices_emergency.material_prices:
            base_price = prices_emergency.material_prices[key].price_per_unit
            prices_emergency.material_prices[key].price_per_unit = (
                base_price * (1 + emergency_premium_pct / 100.0)
            )

    bom_emergency = calculate_bom(graph, config, prices_emergency)

    # Affected steps
    affected_steps: list[str] = []
    for step in graph.steps.values():
        for sm in step.materials:
            if sm.material.name in affected_materials and step.name not in affected_steps:
                affected_steps.append(step.name)

    # Timeline: critical path = max lead time across affected materials
    timeline_weeks: float | None = None
    unknown_timeline: list[str] = []
    for mat_name in affected_materials:
        ri = profile.get_material_risk(mat_name)
        if ri and ri.lead_time_weeks is not None:
            if timeline_weeks is None or ri.lead_time_weeks > timeline_weeks:
                timeline_weeks = ri.lead_time_weeks
        else:
            unknown_timeline.append(mat_name)

    return CDMORemovalResult(
        cdmo_node_name=cdmo_node.name,
        cdmo_node_id=cdmo_node_id,
        biosecure_act_listed=cdmo_node.biosecure_act_listed,
        affected_step_names=affected_steps,
        affected_material_names=affected_materials,
        base_cost_per_kg_api=round(bom.cost_per_kg_api, 4),
        emergency_cost_per_kg_api=round(bom_emergency.cost_per_kg_api, 4),
        cost_per_kg_delta=round(bom_emergency.cost_per_kg_api - bom.cost_per_kg_api, 4),
        timeline_critical_path_weeks=timeline_weeks,
        timeline_unknown_materials=unknown_timeline,
    )


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _compute_exposure(bom: BoMResult, profile: RiskProfile) -> ExposureSummary:
    """Compute exposure percentages from BoM material lines."""
    total_mat = sum(line.total_cost for line in bom.material_lines)
    if total_mat <= 0:
        return ExposureSummary(0.0, 0.0, 0.0, 0.0)

    # Sum per material (deduplicate)
    mat_costs: dict[str, float] = {}
    for line in bom.material_lines:
        mat_costs[line.material_name] = mat_costs.get(line.material_name, 0.0) + line.total_cost

    cn_cost = indirect_cn_cost = single_source_cost = cdmo_cost = 0.0
    for mat_name, cost in mat_costs.items():
        ri = profile.get_material_risk(mat_name)
        if ri is None:
            continue
        if ri.country_of_origin == "CN":
            cn_cost += cost
        if ri.is_indirect_china:
            indirect_cn_cost += cost
        if ri.is_single_source:
            single_source_cost += cost
        if ri.cdmo_node_id:
            cdmo_cost += cost

    return ExposureSummary(
        china_origin_cost_pct=round(cn_cost / total_mat * 100, 2),
        indirect_china_cost_pct=round(indirect_cn_cost / total_mat * 100, 2),
        single_source_cost_pct=round(single_source_cost / total_mat * 100, 2),
        cdmo_exposed_cost_pct=round(cdmo_cost / total_mat * 100, 2),
    )
