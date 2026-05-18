"""
Tests for mrp/network.py — multi-plant network analysis.

All plants and networks are constructed in-code; no YAML loading required.
"""
from __future__ import annotations
import pytest
from datetime import date
from mrp.domain import (
    Plant, PlantAsset, DepreciationMethod, PlantNetwork,
    NetworkPlantMembership, VolumeTarget, ProcessConfig,
)
from mrp.units import ureg


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_plant(
    pid: str,
    name: str,
    capacity_kg: float,
    capex: float,
) -> Plant:
    asset = PlantAsset(
        id=f"{pid}_reactor",
        plant_id=pid,
        name="Reactor",
        asset_class="reactor",
        capex_cost=capex,
        useful_life_years=10.0,
        salvage_value=0.0,
        depreciation_method=DepreciationMethod.STRAIGHT_LINE,
        gmp_qualified=True,
    )
    return Plant(
        id=pid,
        name=name,
        currency="USD",
        annual_capacity_kg_api=capacity_kg,
        gmp_facility=True,
        assets=[asset],
    )


def _make_network(
    plants: list[tuple[Plant, date, float, float]],  # (plant, commissioned, target_util, allocation_kg)
    volume_targets: list[tuple[int, float]],
    start_year: int = 2025,
    end_year: int = 2030,
    annual_default_kg: float = 500.0,
) -> PlantNetwork:
    memberships = [
        NetworkPlantMembership(
            plant_id=p.id,
            volume_allocation_kg=alloc,
            start_year=commissioned.year,
        )
        for p, commissioned, target_util, alloc in plants
    ]
    vt = [VolumeTarget(year=y, volume_kg_api=kg) for y, kg in volume_targets]
    return PlantNetwork(
        id="test_network",
        name="Test Network",
        currency="USD",
        plants=memberships,
        volume_targets=vt,
    )


def _make_simple_process():
    """Minimal process + price list for engine calls."""
    from mrp.domain import (
        ProcessGraph, Step, Edge, StepMaterial, Material,
        MaterialType, CanonicalUnit, StepMaterialRole, PriceList,
    )
    from mrp.units import ureg, parse_molar_mass

    mat = Material(
        name="SM",
        material_type=MaterialType.STARTING_MATERIAL,
        canonical_unit=CanonicalUnit.KG,
        molecular_weight=parse_molar_mass(100.0),
    )
    sm = StepMaterial(material=mat, role=StepMaterialRole.LIMITING_REAGENT, equivalents=1.0)
    step = Step(
        id="step_1",
        name="Synthesis",
        step_yield_pct=100.0,
        output_name="API",
        output_mw=parse_molar_mass(100.0),
        materials=[sm],
    )
    graph = ProcessGraph(
        name="Test Process",
        target_api_name="API",
        steps={"step_1": step},
        edges=[
            Edge(from_step_id=None, to_step_id="step_1"),
            Edge(from_step_id="step_1", to_step_id=None, is_terminal=True),
        ],
    )
    prices = PriceList(
        name="Test Prices",
        currency="USD",
        material_prices={},
        labor_rates={},
        utility_rates={},
    )
    return graph, prices


# ---------------------------------------------------------------------------
# PlantNetwork helper methods
# ---------------------------------------------------------------------------

class TestNetworkHelpers:
    def test_commissioned_plants_filter_by_year(self):
        """Plant commissioned in 2026 is not available in 2025."""
        from mrp.network import commissioned_plants_for_year
        plant_a = _make_plant("a", "Site A", 400, 4_000_000)
        plant_b = _make_plant("b", "Site B", 350, 3_500_000)
        memberships = [
            NetworkPlantMembership(plant_id="a", volume_allocation_kg=400, start_year=2025),
            NetworkPlantMembership(plant_id="b", volume_allocation_kg=350, start_year=2026),
        ]
        plant_map = {"a": plant_a, "b": plant_b}
        active_2025 = commissioned_plants_for_year(memberships, plant_map, 2025)
        active_2026 = commissioned_plants_for_year(memberships, plant_map, 2026)
        assert len(active_2025) == 1
        assert active_2025[0][0].id == "a"
        assert len(active_2026) == 2

    def test_volume_target_lookup_explicit(self):
        """Explicit per-year target is returned for listed years."""
        from mrp.network import volume_target_for_year
        targets = [VolumeTarget(year=2025, volume_kg_api=150.0), VolumeTarget(year=2026, volume_kg_api=300.0)]
        assert volume_target_for_year(targets, 2025, default=500.0) == 150.0
        assert volume_target_for_year(targets, 2026, default=500.0) == 300.0

    def test_volume_target_lookup_fallback(self):
        """Unlisted years fall back to the default."""
        from mrp.network import volume_target_for_year
        targets = [VolumeTarget(year=2025, volume_kg_api=150.0)]
        assert volume_target_for_year(targets, 2028, default=800.0) == 800.0


# ---------------------------------------------------------------------------
# Minimum network configuration (§2.8.4)
# ---------------------------------------------------------------------------

class TestMinimumNetworkConfiguration:
    def test_single_plant_sufficient(self):
        """One plant with capacity >= target is selected."""
        from mrp.network import minimum_network_configuration
        plant_a = _make_plant("a", "Site A", 500, 5_000_000)
        result = minimum_network_configuration(
            plants=[plant_a],
            required_capacity_kg=400.0,
        )
        assert result.best_plant_ids == ["a"]
        assert result.total_capex == 5_000_000
        assert result.total_capacity_kg == 500.0

    def test_two_plants_needed_when_neither_sufficient_alone(self):
        """When no single plant meets target, the smallest sufficient pair is selected."""
        from mrp.network import minimum_network_configuration
        plant_a = _make_plant("a", "Site A", 200, 2_000_000)
        plant_b = _make_plant("b", "Site B", 200, 2_000_000)
        result = minimum_network_configuration(
            plants=[plant_a, plant_b],
            required_capacity_kg=350.0,
        )
        assert set(result.best_plant_ids) == {"a", "b"}
        assert result.total_capacity_kg == 400.0

    def test_lowest_capex_wins_over_greedy(self):
        """
        §2.8.4 edge case: brute-force picks B+C ($3.5M) not A ($5M),
        even though A alone meets the target.
        """
        from mrp.network import minimum_network_configuration
        plant_a = _make_plant("a", "Site A", 350, 5_000_000)
        plant_b = _make_plant("b", "Site B", 200, 2_000_000)
        plant_c = _make_plant("c", "Site C", 150, 1_500_000)
        result = minimum_network_configuration(
            plants=[plant_a, plant_b, plant_c],
            required_capacity_kg=300.0,
        )
        # B+C (200+150=350>=300, $3.5M) beats A alone (350>=300, $5M)
        assert set(result.best_plant_ids) == {"b", "c"}
        assert result.total_capex == 3_500_000

    def test_no_plant_meets_target(self):
        """Returns best_plant_ids=[] and meets_target=False when capacity is insufficient."""
        from mrp.network import minimum_network_configuration
        plant_a = _make_plant("a", "Site A", 100, 1_000_000)
        result = minimum_network_configuration(
            plants=[plant_a],
            required_capacity_kg=500.0,
        )
        assert result.meets_target is False

    def test_empty_plant_list(self):
        """Empty commissioned plant list returns meets_target=False."""
        from mrp.network import minimum_network_configuration
        result = minimum_network_configuration(plants=[], required_capacity_kg=300.0)
        assert result.meets_target is False


# ---------------------------------------------------------------------------
# Network analysis — volume allocation
# ---------------------------------------------------------------------------

class TestNetworkAnalysis:
    def setup_method(self):
        self.graph, self.prices = _make_simple_process()
        self.config = ProcessConfig(batch_size=ureg.Quantity(50.0, "kg"), num_batches=1)

    def test_single_plant_volume_equals_target(self):
        """With one plant, produced volume equals target (rounded to batches)."""
        from mrp.network import allocate_volume
        plant_a = _make_plant("a", "Site A", 500, 5_000_000)
        memberships = [
            NetworkPlantMembership(plant_id="a", volume_allocation_kg=500, start_year=2025),
        ]
        plant_map = {"a": plant_a}
        allocations = allocate_volume(memberships, plant_map, 2025, target_kg=200.0)
        # total allocation should be ≈ 200 kg (proportional, single plant gets all)
        assert abs(sum(v for _, v in allocations) - 200.0) < 1.0

    def test_two_plants_proportional_allocation(self):
        """With two plants, volume is split proportionally by volume_allocation_kg."""
        from mrp.network import allocate_volume
        plant_a = _make_plant("a", "Site A", 400, 4_000_000)
        plant_b = _make_plant("b", "Site B", 200, 2_000_000)
        memberships = [
            NetworkPlantMembership(plant_id="a", volume_allocation_kg=400, start_year=2025),
            NetworkPlantMembership(plant_id="b", volume_allocation_kg=200, start_year=2025),
        ]
        plant_map = {"a": plant_a, "b": plant_b}
        allocations = allocate_volume(memberships, plant_map, 2025, target_kg=300.0)
        alloc_dict = {pid: kg for pid, kg in allocations}
        # A gets 2/3, B gets 1/3
        assert abs(alloc_dict["a"] - 200.0) < 1.0
        assert abs(alloc_dict["b"] - 100.0) < 1.0
        assert abs(sum(alloc_dict.values()) - 300.0) < 1.0

    def test_volume_gap_when_capacity_insufficient(self):
        """Volume gap is positive when total capacity < target."""
        from mrp.network import analyse_network
        plant_a = _make_plant("a", "Site A", 100, 1_000_000)  # only 100 kg capacity
        memberships = [
            NetworkPlantMembership(plant_id="a", volume_allocation_kg=100, start_year=2025),
        ]
        plant_map = {"a": plant_a}
        result = analyse_network(
            memberships=memberships,
            plant_map=plant_map,
            volume_targets=[VolumeTarget(year=2025, volume_kg_api=300.0)],
            default_volume_kg=300.0,
            years=[2025],
            graph=self.graph,
            config=self.config,
            prices=self.prices,
        )
        ys = result.year_summaries[0]
        # plant can only produce up to capacity, so gap = 300 - actual_produced
        assert ys.volume_gap_kg > 0

    def test_cogs_total_variable_plus_fixed(self):
        """total_cogs = total_variable_cost + total_fixed_cost for network year."""
        from mrp.network import analyse_network
        plant_a = _make_plant("a", "Site A", 500, 5_000_000)
        memberships = [
            NetworkPlantMembership(plant_id="a", volume_allocation_kg=500, start_year=2025),
        ]
        plant_map = {"a": plant_a}
        result = analyse_network(
            memberships=memberships,
            plant_map=plant_map,
            volume_targets=[VolumeTarget(year=2025, volume_kg_api=200.0)],
            default_volume_kg=200.0,
            years=[2025],
            graph=self.graph,
            config=self.config,
            prices=self.prices,
        )
        ys = result.year_summaries[0]
        assert abs(ys.total_cogs - (ys.total_variable_cost + ys.total_fixed_cost)) < 0.01


# ---------------------------------------------------------------------------
# Breakeven
# ---------------------------------------------------------------------------

class TestBreakeven:
    def test_breakeven_with_no_variable_cost(self):
        """When variable_per_kg = 0 and fixed > 0, breakeven returns None."""
        from mrp.network import compute_plant_breakeven
        # Breakeven = fixed / variable_per_kg; undefined when variable_per_kg = 0
        result = compute_plant_breakeven(
            total_fixed_annual=500_000.0,
            variable_cost_per_kg=0.0,
        )
        assert result is None

    def test_breakeven_calculation(self):
        """Breakeven = total_fixed / variable_per_kg."""
        from mrp.network import compute_plant_breakeven
        result = compute_plant_breakeven(
            total_fixed_annual=500_000.0,
            variable_cost_per_kg=200.0,
        )
        assert abs(result - 2_500.0) < 0.01
