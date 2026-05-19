"""
mrp/risk.py — Supply Chain Risk Sensitivity Engine (v1.3)

Key constraints:
- apply_tariff_overlay MUST NOT call calculate_bom() — pure arithmetic over bom.material_lines
- All perturbations use copy.deepcopy(), never mutate originals
- Sensitivity coefficient = (perturbed_cost_per_kg - base_cost_per_kg) / delta_pct (signed)
"""
from __future__ import annotations
import copy
import time
from datetime import datetime, timezone

from mrp.domain import (
    ProcessGraph, ProcessConfig, PriceList, BoMResult,
    RiskProfile, MaterialRiskMetadata, StepRiskMetadata,
    RiskVector, RiskVectorType,
    SensitivityLine, TariffOverlayResult, CDMORemovalResult, SensitivityReport,
    CDMONode,
)
from mrp.engine import calculate_bom
from mrp.units import to_float


# ─── Public API ───────────────────────────────────────────────────────────────

def generate_sensitivity_report(
    graph: ProcessGraph,
    config: ProcessConfig,
    prices: PriceList,
    base_bom: BoMResult,
    risk_profile: RiskProfile,
    delta_pct: float = 1.0,
) -> SensitivityReport:
    """Generate a full supply chain risk sensitivity report."""
    t0 = time.perf_counter()

    # 1. Parameter sensitivity (material prices + step yields)
    raw_lines = _compute_parameter_sensitivity(
        graph=graph,
        config=config,
        prices=prices,
        base_bom=base_bom,
        risk_profile=risk_profile,
        delta_pct=delta_pct,
    )
    ranked_lines = _rank_sensitivity_lines(raw_lines)

    # 2. Tariff scenarios
    tariff_results = _run_tariff_scenarios(base_bom=base_bom, risk_profile=risk_profile)

    # 3. CDMO removal scenarios
    cdmo_results = _run_cdmo_removal_scenarios(
        graph=graph, config=config, prices=prices,
        base_bom=base_bom, risk_profile=risk_profile,
    )

    # 4. Exposure summary
    exposure = _compute_exposure_summary(bom=base_bom, risk_profile=risk_profile)

    elapsed = time.perf_counter() - t0

    return SensitivityReport(
        scenario_name=risk_profile.name,
        process_name=graph.name,
        generated_at=_utcnow_iso(),
        base_cost_per_kg_api=base_bom.cost_per_kg_api,
        currency=base_bom.currency,
        china_origin_cost_pct=exposure["china_origin_cost_pct"],
        indirect_china_cost_pct=exposure["indirect_china_cost_pct"],
        single_source_cost_pct=exposure["single_source_cost_pct"],
        cdmo_exposed_cost_pct=exposure["cdmo_exposed_cost_pct"],
        sensitivity_lines=ranked_lines,
        tariff_sweep_results=tariff_results,
        cdmo_removal_results=cdmo_results,
        generation_time_sec=elapsed,
    )


def _compute_parameter_sensitivity(
    graph: ProcessGraph,
    config: ProcessConfig,
    prices: PriceList,
    base_bom: BoMResult,
    risk_profile: RiskProfile,
    delta_pct: float = 1.0,
) -> list[SensitivityLine]:
    """Compute one-at-a-time sensitivity for each unique material price and step yield."""
    lines: list[SensitivityLine] = []
    base_cost = base_bom.cost_per_kg_api

    # --- Material price sensitivities (deduplicate by material name) ---
    seen_materials: set[str] = set()
    for ml in base_bom.material_lines:
        mat_name = ml.material_name
        if mat_name in seen_materials:
            continue
        # Only perturb materials with a non-zero price
        if ml.unit_cost <= 0:
            continue
        seen_materials.add(mat_name)

        # Perturb price
        perturbed_prices = copy.deepcopy(prices)
        key = mat_name.lower()
        if key not in perturbed_prices.material_prices:
            continue
        original_price = perturbed_prices.material_prices[key].price_per_unit
        perturbed_prices.material_prices[key].price_per_unit = original_price * (1 + delta_pct / 100.0)

        perturbed_bom = calculate_bom(copy.deepcopy(graph), config, perturbed_prices)
        sensitivity = (perturbed_bom.cost_per_kg_api - base_cost) / delta_pct

        meta = risk_profile.material_risk.get(key, MaterialRiskMetadata(material_name=mat_name))
        cdmo_name = _resolve_cdmo_name(meta.cdmo_node_id, risk_profile)
        risk_flags = _build_risk_flags(meta, risk_profile)

        lines.append(SensitivityLine(
            rank=0,  # assigned later
            parameter_name=mat_name,
            parameter_type="material_price",
            sensitivity_cost_per_unit=sensitivity,
            sensitivity_unit="$/kg_api per 1% price change",
            country_of_origin=meta.country_of_origin,
            cdmo_node_name=cdmo_name,
            is_single_source=meta.single_source,
            is_indirect_china=meta.indirect_china_exposure,
            timeline_impact_weeks=float(meta.alternative_supplier_lead_time_weeks)
            if meta.alternative_supplier_lead_time_weeks is not None else None,
            tariff_impact_at_rate=None,
            risk_flags=risk_flags,
        ))

    # --- Step yield sensitivities ---
    for step_id, step in graph.steps.items():
        perturbed_graph = copy.deepcopy(graph)
        original_yield = perturbed_graph.steps[step_id].step_yield_pct
        perturbed_graph.steps[step_id].step_yield_pct = min(
            original_yield * (1 + delta_pct / 100.0), 100.0
        )
        perturbed_bom = calculate_bom(perturbed_graph, config, prices)
        sensitivity = (perturbed_bom.cost_per_kg_api - base_cost) / delta_pct

        step_meta = risk_profile.step_risk.get(
            step_id, StepRiskMetadata(step_name=step.name)
        )
        cdmo_name = _resolve_cdmo_name(step_meta.cdmo_node_id, risk_profile)
        risk_flags = _build_step_risk_flags(step_meta, risk_profile)

        lines.append(SensitivityLine(
            rank=0,
            parameter_name=step.name,
            parameter_type="step_yield",
            sensitivity_cost_per_unit=sensitivity,
            sensitivity_unit="$/kg_api per 1% yield increase",
            country_of_origin=None,
            cdmo_node_name=cdmo_name,
            is_single_source=False,
            is_indirect_china=False,
            timeline_impact_weeks=None,
            tariff_impact_at_rate=None,
            risk_flags=risk_flags,
        ))

    return lines


def apply_tariff_overlay(
    bom: BoMResult,
    tariff_rate_pct: float,
    geography: str,
    include_indirect: bool,
    risk_profile: RiskProfile,
) -> TariffOverlayResult:
    """
    Pure arithmetic overlay — MUST NOT call calculate_bom().
    Applies tariff_rate_pct to materials matching geography (and optionally indirect exposure).
    """
    total_api_kg = _total_api_kg_from_bom(bom)
    tariff_total = 0.0
    exposed_lines: list[dict] = []

    for ml in bom.material_lines:
        if ml.unit_cost <= 0 or ml.total_cost <= 0:
            continue
        meta = risk_profile.material_risk.get(
            ml.material_name.lower(),
            MaterialRiskMetadata(material_name=ml.material_name),
        )
        is_direct = (meta.country_of_origin == geography)
        is_indirect = include_indirect and meta.indirect_china_exposure

        if is_direct or is_indirect:
            tariff_on_line = ml.total_cost * (tariff_rate_pct / 100.0)
            tariff_total += tariff_on_line
            exposed_lines.append({
                "material_name": ml.material_name,
                "step_name": ml.step_name,
                "total_cost": ml.total_cost,
                "tariff_cost": tariff_on_line,
                "country_of_origin": meta.country_of_origin,
                "is_indirect": is_indirect and not is_direct,
            })

    # Scale tariff by num_batches already embedded in bom.total_material_cost
    # bom.material_lines have per-batch costs; bom.total_material_cost is for all batches
    # But material_lines total_cost is per-batch (the engine accumulates then multiplies)
    # Actually looking at the engine: material_lines totals are per-batch quantities × price
    # and total_material_cost = sum(step_summaries.material_cost) * num_batches
    # So tariff_total here is the per-batch sum. We need total across all batches.
    tariff_total_campaign = tariff_total * bom.config.num_batches
    tariff_per_kg = tariff_total_campaign / total_api_kg if total_api_kg > 0 else 0.0

    return TariffOverlayResult(
        tariff_rate_pct=tariff_rate_pct,
        geography=geography,
        include_indirect=include_indirect,
        base_cost_per_kg_api=bom.cost_per_kg_api,
        tariff_cost_total=tariff_total_campaign,
        adjusted_cost_per_kg_api=bom.cost_per_kg_api + tariff_per_kg,
        cost_per_kg_delta=tariff_per_kg,
        exposed_material_lines=exposed_lines,
    )


def model_cdmo_removal(
    bom: BoMResult,
    cdmo_node: CDMONode,
    emergency_premium_pct: float,
    risk_profile: RiskProfile,
) -> CDMORemovalResult:
    """
    Model the cost impact of removing a CDMO node (emergency sourcing).
    Uses 1 + premium_pct/100 multiplier on affected material prices.
    """
    node_id = cdmo_node.id

    # Identify affected steps
    affected_step_names = [
        step_name
        for step_name, step_meta in risk_profile.step_risk.items()
        if step_meta.cdmo_node_id == node_id
    ]

    # Identify affected materials (from bom.material_lines that match cdmo_node_id)
    affected_material_names: list[str] = []
    seen_affected: set[str] = set()
    for ml in bom.material_lines:
        meta = risk_profile.material_risk.get(
            ml.material_name.lower(),
            MaterialRiskMetadata(material_name=ml.material_name),
        )
        if meta.cdmo_node_id == node_id and ml.material_name not in seen_affected:
            seen_affected.add(ml.material_name)
            affected_material_names.append(ml.material_name)

    # Compute emergency cost by scaling affected material lines
    total_api_kg = _total_api_kg_from_bom(bom)
    premium_multiplier = 1 + emergency_premium_pct / 100.0

    # Base cost is per_kg from bom
    base_cost_per_kg = bom.cost_per_kg_api

    # Emergency cost: add premium on affected materials
    emergency_extra_per_batch = 0.0
    for ml in bom.material_lines:
        if ml.material_name in seen_affected:
            emergency_extra_per_batch += ml.total_cost * (emergency_premium_pct / 100.0)

    emergency_extra_campaign = emergency_extra_per_batch * bom.config.num_batches
    emergency_extra_per_kg = emergency_extra_campaign / total_api_kg if total_api_kg > 0 else 0.0
    emergency_cost_per_kg = base_cost_per_kg + emergency_extra_per_kg

    # Timeline: max alternative_supplier_lead_time_weeks across affected materials
    lead_times: list[int] = []
    unknown_materials: list[str] = []
    for mat_name in affected_material_names:
        meta = risk_profile.material_risk.get(
            mat_name.lower(),
            MaterialRiskMetadata(material_name=mat_name),
        )
        if meta.alternative_supplier_lead_time_weeks is not None:
            lead_times.append(meta.alternative_supplier_lead_time_weeks)
        else:
            unknown_materials.append(mat_name)

    critical_path = float(max(lead_times)) if lead_times else None

    requalification_notes: str | None = None
    if unknown_materials:
        requalification_notes = (
            f"Lead time unknown for: {', '.join(unknown_materials)}. "
            "Requalification timeline TBD — requires vendor assessment."
        )

    return CDMORemovalResult(
        cdmo_node_name=cdmo_node.name,
        biosecure_act_listed=cdmo_node.biosecure_act_listed,
        affected_step_names=affected_step_names,
        affected_material_names=affected_material_names,
        base_cost_per_kg_api=base_cost_per_kg,
        emergency_cost_per_kg_api=emergency_cost_per_kg,
        cost_per_kg_delta=emergency_cost_per_kg - base_cost_per_kg,
        timeline_critical_path_weeks=critical_path,
        timeline_unknown_materials=unknown_materials,
        requalification_notes=requalification_notes,
    )


def _run_tariff_scenarios(
    base_bom: BoMResult,
    risk_profile: RiskProfile,
) -> list[TariffOverlayResult]:
    """
    Run tariff overlay for all risk_vectors of type TARIFF_ESCALATION
    plus the tariff_sweep rates. Deduplicate by (rate, geography, include_indirect).
    Results sorted ascending by tariff_rate_pct.
    """
    seen: set[tuple] = set()
    scenarios: list[tuple[float, str, bool]] = []

    # From risk_vectors
    for rv in risk_profile.risk_vectors:
        if rv.risk_vector_type == RiskVectorType.TARIFF_ESCALATION:
            if rv.tariff_rate_pct is not None and rv.geography is not None:
                key = (rv.tariff_rate_pct, rv.geography, rv.include_indirect)
                if key not in seen:
                    seen.add(key)
                    scenarios.append(key)

    # From tariff_sweep
    if risk_profile.tariff_sweep_rates and risk_profile.tariff_sweep_geography:
        for rate in risk_profile.tariff_sweep_rates:
            key = (rate, risk_profile.tariff_sweep_geography, risk_profile.tariff_sweep_include_indirect)
            if key not in seen:
                seen.add(key)
                scenarios.append(key)

    results = []
    for rate, geo, indirect in scenarios:
        result = apply_tariff_overlay(
            bom=base_bom,
            tariff_rate_pct=rate,
            geography=geo,
            include_indirect=indirect,
            risk_profile=risk_profile,
        )
        results.append(result)

    results.sort(key=lambda r: r.tariff_rate_pct)
    return results


def _run_cdmo_removal_scenarios(
    graph: ProcessGraph,
    config: ProcessConfig,
    prices: PriceList,
    base_bom: BoMResult,
    risk_profile: RiskProfile,
) -> list[CDMORemovalResult]:
    """Run CDMO removal scenario for each CDMO_REMOVAL risk vector."""
    results = []
    for rv in risk_profile.risk_vectors:
        if rv.risk_vector_type == RiskVectorType.CDMO_REMOVAL:
            node_id = rv.cdmo_node_id
            if node_id is None or node_id not in risk_profile.cdmo_nodes:
                continue
            cdmo_node = risk_profile.cdmo_nodes[node_id]
            result = model_cdmo_removal(
                bom=base_bom,
                cdmo_node=cdmo_node,
                emergency_premium_pct=rv.emergency_premium_pct,
                risk_profile=risk_profile,
            )
            results.append(result)
    return results


def _compute_exposure_summary(
    bom: BoMResult,
    risk_profile: RiskProfile,
) -> dict:
    """Compute four exposure percentages over priced material costs."""
    total_cost = 0.0
    cn_cost = 0.0
    indirect_cn_cost = 0.0
    single_source_cost = 0.0
    cdmo_cost = 0.0

    for ml in bom.material_lines:
        if ml.unit_cost <= 0 or ml.total_cost <= 0:
            continue
        cost = ml.total_cost
        total_cost += cost

        meta = risk_profile.material_risk.get(
            ml.material_name.lower(),
            MaterialRiskMetadata(material_name=ml.material_name),
        )
        if meta.country_of_origin == "CN":
            cn_cost += cost
        if meta.indirect_china_exposure:
            indirect_cn_cost += cost
        if meta.single_source:
            single_source_cost += cost
        if meta.cdmo_node_id is not None:
            cdmo_cost += cost

    def pct(num: float) -> float:
        return (num / total_cost * 100.0) if total_cost > 0 else 0.0

    return {
        "china_origin_cost_pct": pct(cn_cost),
        "indirect_china_cost_pct": pct(indirect_cn_cost),
        "single_source_cost_pct": pct(single_source_cost),
        "cdmo_exposed_cost_pct": pct(cdmo_cost),
    }


def _rank_sensitivity_lines(lines: list[SensitivityLine]) -> list[SensitivityLine]:
    """
    Sort by score = abs(sensitivity) × (1.5 if single_source else 1.0), descending.
    Assign rank 1..N.
    """
    def score(line: SensitivityLine) -> float:
        multiplier = 1.5 if line.is_single_source else 1.0
        return abs(line.sensitivity_cost_per_unit) * multiplier

    sorted_lines = sorted(lines, key=score, reverse=True)
    for i, line in enumerate(sorted_lines):
        line.rank = i + 1
    return sorted_lines


def _resolve_cdmo_name(cdmo_node_id: str | None, risk_profile: RiskProfile) -> str | None:
    if cdmo_node_id is None:
        return None
    node = risk_profile.cdmo_nodes.get(cdmo_node_id)
    return node.name if node else cdmo_node_id


def _build_risk_flags(meta: MaterialRiskMetadata, risk_profile: RiskProfile) -> list[str]:
    flags: list[str] = []
    if meta.country_of_origin == "CN":
        flags.append("china_origin")
    if meta.indirect_china_exposure:
        flags.append("indirect_china_exposure")
    if meta.single_source:
        flags.append("single_source")
    if meta.cdmo_node_id is not None:
        node = risk_profile.cdmo_nodes.get(meta.cdmo_node_id)
        if node:
            if node.biosecure_act_listed:
                flags.append("biosecure_act_listed")
            if node.pentagon_1260h_listed:
                flags.append("pentagon_1260h_listed")
            flags.extend(node.regulatory_watch_flags)
    return flags


def _build_step_risk_flags(meta: StepRiskMetadata, risk_profile: RiskProfile) -> list[str]:
    flags: list[str] = []
    flags.append(f"criticality:{meta.step_criticality.value}")
    if meta.cdmo_node_id is not None:
        node = risk_profile.cdmo_nodes.get(meta.cdmo_node_id)
        if node:
            if node.biosecure_act_listed:
                flags.append("biosecure_act_listed")
            if node.pentagon_1260h_listed:
                flags.append("pentagon_1260h_listed")
    return flags


def _total_api_kg(config: ProcessConfig) -> float:
    return to_float(config.batch_size, "kg") * config.num_batches


def _total_api_kg_from_bom(bom: BoMResult) -> float:
    return to_float(bom.config.batch_size, "kg") * bom.config.num_batches


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
