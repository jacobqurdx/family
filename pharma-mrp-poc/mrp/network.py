from __future__ import annotations
import copy
import itertools
import math
from mrp.domain import (
    Plant, PlantAsset, NetworkPlantMembership, VolumeTarget,
    PlantNetwork, NetworkAnalysisResult, NetworkYearSummary, PlantYearResult,
    MinimumNetworkResult, NetworkBreakevenResult, ProcessGraph, ProcessConfig, PriceList,
)
from mrp.capex import overlay_capex, annual_depreciation_for_plant, annual_maintenance_cost
from mrp.engine import calculate_bom


# ---------------------------------------------------------------------------
# Pure utility functions (also exported for tests)
# ---------------------------------------------------------------------------

def commissioned_plants_for_year(
    memberships: list[NetworkPlantMembership],
    plant_map: dict[str, Plant],
    year: int,
) -> list[tuple[Plant, NetworkPlantMembership]]:
    """Return (Plant, membership) pairs where start_year <= year."""
    result = []
    for m in memberships:
        if (m.start_year is None or m.start_year <= year):
            plant = plant_map.get(m.plant_id)
            if plant is not None:
                result.append((plant, m))
    return result


def volume_target_for_year(
    targets: list[VolumeTarget],
    year: int,
    default: float,
) -> float:
    """Return explicit target for year, or default if not listed."""
    for vt in targets:
        if vt.year == year:
            return vt.volume_kg_api
    return default


def allocate_volume(
    memberships: list[NetworkPlantMembership],
    plant_map: dict[str, Plant],
    year: int,
    target_kg: float,
) -> list[tuple[str, float]]:
    """
    Proportionally allocate target_kg across commissioned plants by
    their volume_allocation_kg membership field.

    Returns list of (plant_id, allocated_kg).
    """
    active = commissioned_plants_for_year(memberships, plant_map, year)
    if not active:
        return []
    total_alloc = sum(m.volume_allocation_kg for _, m in active)
    if total_alloc <= 0:
        return [(p.id, 0.0) for p, _ in active]
    result = []
    for plant, m in active:
        fraction = m.volume_allocation_kg / total_alloc
        allocated = target_kg * fraction
        # Cap at plant nameplate capacity
        allocated = min(allocated, plant.annual_capacity_kg_api)
        result.append((plant.id, allocated))
    return result


def compute_plant_breakeven(
    total_fixed_annual: float,
    variable_cost_per_kg: float,
) -> float | None:
    """Breakeven kg = total_fixed / variable_cost_per_kg. None if variable is zero."""
    if variable_cost_per_kg <= 0:
        return None
    return total_fixed_annual / variable_cost_per_kg


# ---------------------------------------------------------------------------
# Minimum network configuration (§2.8.4 — brute-force for ≤10 plants)
# ---------------------------------------------------------------------------

def minimum_network_configuration(
    plants: list[Plant],
    required_capacity_kg: float,
) -> MinimumNetworkResult:
    """
    Find the minimum-CapEx subset of plants whose combined nameplate capacity
    meets or exceeds required_capacity_kg.

    Uses brute-force itertools.combinations (correct for ≤10 plants).
    Avoids the greedy algorithm edge case where two smaller plants cost
    less than one large plant that alone meets the target (§2.8.4).
    """
    if not plants:
        return MinimumNetworkResult(
            required_capacity_kg=required_capacity_kg,
            best_plant_ids=[],
            best_plant_names=[],
            total_capex=0.0,
            total_capacity_kg=0.0,
            n_evaluated=0,
            meets_target=False,
        )

    best_subset: tuple[Plant, ...] | None = None
    best_capex = float("inf")
    n_evaluated = 0

    for r in range(1, len(plants) + 1):
        for subset in itertools.combinations(plants, r):
            n_evaluated += 1
            total_capacity = sum(p.annual_capacity_kg_api for p in subset)
            if total_capacity >= required_capacity_kg:
                capex = sum(p.total_capex() for p in subset)
                if capex < best_capex:
                    best_capex = capex
                    best_subset = subset

    if best_subset is None:
        total_cap = sum(p.annual_capacity_kg_api for p in plants)
        return MinimumNetworkResult(
            required_capacity_kg=required_capacity_kg,
            best_plant_ids=[p.id for p in plants],
            best_plant_names=[p.name for p in plants],
            total_capex=sum(p.total_capex() for p in plants),
            total_capacity_kg=total_cap,
            n_evaluated=n_evaluated,
            meets_target=False,
        )

    return MinimumNetworkResult(
        required_capacity_kg=required_capacity_kg,
        best_plant_ids=[p.id for p in best_subset],
        best_plant_names=[p.name for p in best_subset],
        total_capex=best_capex,
        total_capacity_kg=sum(p.annual_capacity_kg_api for p in best_subset),
        n_evaluated=n_evaluated,
        meets_target=True,
    )


# ---------------------------------------------------------------------------
# Multi-year network analysis
# ---------------------------------------------------------------------------

def analyse_network(
    memberships: list[NetworkPlantMembership],
    plant_map: dict[str, Plant],
    volume_targets: list[VolumeTarget],
    default_volume_kg: float,
    years: list[int],
    graph: ProcessGraph,
    config: ProcessConfig,
    prices: PriceList,
) -> NetworkAnalysisResult:
    """
    Multi-year COGS analysis across all plants in the network.

    For each year:
      1. Identify commissioned plants.
      2. Allocate volume proportionally by membership volume_allocation_kg.
      3. For each plant: derive batches needed, run calculate_bom(), overlay_capex().
      4. Aggregate into NetworkYearSummary.

    year_index per plant = year - plant's commission year (floored at 0).
    """
    batch_size_kg = config.batch_size.to("kg").magnitude
    year_summaries: list[NetworkYearSummary] = []

    for year in years:
        target_kg = volume_target_for_year(volume_targets, year, default_volume_kg)
        allocations = allocate_volume(memberships, plant_map, year, target_kg)

        plant_results: list[PlantYearResult] = []
        total_variable = total_fixed = total_cogs = volume_produced = 0.0

        for plant_id, allocated_kg in allocations:
            plant = plant_map[plant_id]
            m = next(m for m in memberships if m.plant_id == plant_id)

            batches = math.ceil(allocated_kg / batch_size_kg) if batch_size_kg > 0 else 0
            actual_kg = batches * batch_size_kg

            # Build per-batch config
            batch_config = copy.deepcopy(config)
            batch_config.num_batches = batches

            bom = calculate_bom(graph, batch_config, prices)

            # year_index = years since commissioning (0-based)
            commission_year = m.start_year or year
            year_index = max(0, year - commission_year)

            cx = overlay_capex(bom, plant, analysis_year=year, year_index=year_index)

            volume_produced += actual_kg
            total_variable += cx.total_variable_cost
            total_fixed += cx.total_fixed_cost
            total_cogs += cx.total_cogs

            plant_results.append(PlantYearResult(
                plant_id=plant.id,
                plant_name=plant.name,
                year=year,
                allocated_volume_kg=round(allocated_kg, 2),
                utilisation_pct=round(cx.utilisation_pct, 2),
                total_depreciation=round(cx.total_depreciation_cost, 2),
                total_maintenance=round(cx.total_maintenance_cost, 2),
                total_variable_cost=round(cx.total_variable_cost, 2),
                total_fixed_cost=round(cx.total_fixed_cost, 2),
                total_cogs=round(cx.total_cogs, 2),
                cogs_per_kg_api=round(cx.cogs_per_kg_api, 2),
            ))

        avg_cogs = total_cogs / volume_produced if volume_produced > 0 else 0.0
        year_summaries.append(NetworkYearSummary(
            year=year,
            total_volume_kg=target_kg,
            total_cogs=round(total_cogs, 2),
            network_cogs_per_kg_api=round(avg_cogs, 2),
            total_variable_cost=round(total_variable, 2),
            total_fixed_cost=round(total_fixed, 2),
            volume_gap_kg=round(target_kg - volume_produced, 2),
            plant_results=plant_results,
        ))

    total_capex = sum(plant_map[m.plant_id].total_capex() for m in memberships)
    return NetworkAnalysisResult(
        network_name="Network Analysis",
        currency="USD",
        year_summaries=year_summaries,
        total_network_capex=round(total_capex, 2),
    )


def compute_network_breakeven(
    analysis_result: NetworkAnalysisResult,
) -> list[NetworkBreakevenResult]:
    """
    Compute breakeven volume for each plant from the first year's data.
    Returns one NetworkBreakevenResult per plant.
    """
    if not analysis_result.year_summaries:
        return []

    first_year = analysis_result.year_summaries[0]
    results = []
    for pr in first_year.plant_results:
        variable_per_kg = (
            pr.total_variable_cost / pr.allocated_volume_kg
            if pr.allocated_volume_kg > 0 else 0.0
        )
        bep = compute_plant_breakeven(pr.total_fixed_cost, variable_per_kg)
        results.append(NetworkBreakevenResult(
            plant_id=pr.plant_id,
            plant_name=pr.plant_name,
            fixed_cost_annual=pr.total_fixed_cost,
            variable_cost_per_kg=variable_per_kg,
            breakeven_kg_api=bep,
            currency=analysis_result.currency,
        ))
    return results
