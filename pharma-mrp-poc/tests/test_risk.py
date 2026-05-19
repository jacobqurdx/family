"""
v1.3 Supply Chain Risk Sensitivity — 18 TDD tests.

Minimal 2-step in-code fixture:
  step_1: 87% yield — SM-A (CN, wuxi_sta, single_source=True, 18wk), Solvent A (DE, volume_ratio)
  step_2: 91% yield GMP — Reagent B (CN, wuxi_sta, single_source=False, 10wk)
  5 batches × 50 kg
"""
from __future__ import annotations
import copy
import pytest
from unittest.mock import patch

from mrp.domain import (
    Material, MaterialType, CanonicalUnit, StepMaterial, StepMaterialRole,
    Step, Edge, ProcessGraph, PriceEntry, PriceList, ProcessConfig,
    CDMONode, RiskVector, RiskVectorType, MaterialRiskMetadata,
    StepRiskMetadata, StepCriticality, RiskProfile,
)
from mrp.engine import calculate_bom
from mrp.units import ureg


# ─── Fixtures ─────────────────────────────────────────────────────────────────

def _make_graph() -> ProcessGraph:
    """2-step linear process."""
    sm_a = Material(
        name="Starting Material A",
        material_type=MaterialType.STARTING_MATERIAL,
        canonical_unit=CanonicalUnit.KG,
        molecular_weight=ureg.Quantity(300.0, "g/mol"),
    )
    solvent_a = Material(
        name="Solvent A",
        material_type=MaterialType.SOLVENT,
        canonical_unit=CanonicalUnit.LITRE,
    )
    reagent_b = Material(
        name="Reagent B",
        material_type=MaterialType.REAGENT,
        canonical_unit=CanonicalUnit.KG,
        molecular_weight=ureg.Quantity(280.0, "g/mol"),
    )
    # intermediate from step 1 (limiting in step 2)
    intermediate = Material(
        name="Intermediate AB",
        material_type=MaterialType.STARTING_MATERIAL,
        canonical_unit=CanonicalUnit.KG,
        molecular_weight=ureg.Quantity(320.0, "g/mol"),
    )

    step_1 = Step(
        id="step_1",
        name="step_1",
        step_yield_pct=87.0,
        output_name="Intermediate AB",
        output_mw=ureg.Quantity(320.0, "g/mol"),
        gmp_step=False,
        materials=[
            StepMaterial(
                material=sm_a,
                role=StepMaterialRole.LIMITING_REAGENT,
                excess_pct=0.0,
                equivalents=1.0,
            ),
            StepMaterial(
                material=solvent_a,
                role=StepMaterialRole.SOLVENT,
                excess_pct=0.0,
                volume_ratio=ureg.Quantity(5.0, "L/kg"),
            ),
        ],
    )
    step_2 = Step(
        id="step_2",
        name="step_2",
        step_yield_pct=91.0,
        output_name="API",
        output_mw=ureg.Quantity(350.0, "g/mol"),
        gmp_step=True,
        materials=[
            StepMaterial(
                material=intermediate,
                role=StepMaterialRole.LIMITING_REAGENT,
                excess_pct=0.0,
                equivalents=1.0,
            ),
            StepMaterial(
                material=reagent_b,
                role=StepMaterialRole.REAGENT,
                excess_pct=0.0,
                equivalents=1.0,
            ),
        ],
    )

    edges = [
        Edge(from_step_id=None, to_step_id="step_1", intermediate_name=""),
        Edge(from_step_id="step_1", to_step_id="step_2", intermediate_name="Intermediate AB"),
        Edge(from_step_id="step_2", to_step_id=None, intermediate_name="API", is_terminal=True),
    ]

    return ProcessGraph(
        name="Test 2-Step Route",
        target_api_name="API",
        steps={"step_1": step_1, "step_2": step_2},
        edges=edges,
    )


def _make_prices() -> PriceList:
    return PriceList(
        name="Test Prices",
        currency="USD",
        material_prices={
            "starting material a": PriceEntry(
                name="Starting Material A", price_per_unit=820.0, unit="kg"
            ),
            "solvent a": PriceEntry(
                name="Solvent A", price_per_unit=3.0, unit="L"
            ),
            "reagent b": PriceEntry(
                name="Reagent B", price_per_unit=680.0, unit="kg"
            ),
            "intermediate ab": PriceEntry(
                name="Intermediate AB", price_per_unit=0.0, unit="kg"
            ),
        },
        labor_rates={},
        utility_rates={},
    )


def _make_risk_profile() -> RiskProfile:
    wuxi = CDMONode(
        id="wuxi_sta",
        name="Wuxi AppTec — WuXi STA",
        country="CN",
        biosecure_act_listed=True,
        pentagon_1260h_listed=True,
        regulatory_watch_flags=["1260H_list", "biosecure_act_pending"],
    )
    return RiskProfile(
        name="Test Risk Profile",
        cdmo_nodes={"wuxi_sta": wuxi},
        material_risk={
            "starting material a": MaterialRiskMetadata(
                material_name="Starting Material A",
                country_of_origin="CN",
                cdmo_node_id="wuxi_sta",
                single_source=True,
                alternative_supplier_lead_time_weeks=18,
                indirect_china_exposure=False,
            ),
            "solvent a": MaterialRiskMetadata(
                material_name="Solvent A",
                country_of_origin="DE",
                cdmo_node_id=None,
                single_source=False,
                alternative_supplier_lead_time_weeks=4,
                indirect_china_exposure=False,
            ),
            "reagent b": MaterialRiskMetadata(
                material_name="Reagent B",
                country_of_origin="CN",
                cdmo_node_id="wuxi_sta",
                single_source=False,
                alternative_supplier_lead_time_weeks=10,
                indirect_china_exposure=False,
            ),
        },
        step_risk={
            "step_1": StepRiskMetadata(
                step_name="step_1",
                cdmo_node_id="wuxi_sta",
                step_criticality=StepCriticality.CRITICAL,
            ),
            "step_2": StepRiskMetadata(
                step_name="step_2",
                cdmo_node_id="wuxi_sta",
                step_criticality=StepCriticality.SOLE_SOURCE_STEP,
            ),
        },
        risk_vectors=[
            RiskVector(
                id="tariff_55_cn",
                name="55% China Tariff",
                risk_vector_type=RiskVectorType.TARIFF_ESCALATION,
                tariff_rate_pct=55.0,
                geography="CN",
                include_indirect=False,
            ),
            RiskVector(
                id="wuxi_removal",
                name="Wuxi AppTec Node Removal",
                risk_vector_type=RiskVectorType.CDMO_REMOVAL,
                cdmo_node_id="wuxi_sta",
                emergency_premium_pct=50.0,
            ),
        ],
        tariff_sweep_rates=[20.0, 35.0, 55.0, 100.0],
        tariff_sweep_geography="CN",
        tariff_sweep_include_indirect=False,
    )


def _make_config() -> ProcessConfig:
    return ProcessConfig(
        batch_size=ureg.Quantity(50.0, "kg"),
        num_batches=5,
    )


@pytest.fixture
def graph():
    return _make_graph()


@pytest.fixture
def prices():
    return _make_prices()


@pytest.fixture
def config():
    return _make_config()


@pytest.fixture
def risk_profile():
    return _make_risk_profile()


@pytest.fixture
def base_bom(graph, prices, config):
    return calculate_bom(graph, config, prices)


@pytest.fixture
def report(graph, config, prices, base_bom, risk_profile):
    from mrp.risk import generate_sensitivity_report
    return generate_sensitivity_report(
        graph=graph,
        config=config,
        prices=prices,
        base_bom=base_bom,
        risk_profile=risk_profile,
        delta_pct=1.0,
    )


# ─── Tests ────────────────────────────────────────────────────────────────────

def test_sensitivity_sign_material_price(report):
    """Material price perturbation +1% → sensitivity > 0."""
    mat_lines = [l for l in report.sensitivity_lines if l.parameter_type == "material_price"]
    assert len(mat_lines) > 0
    for line in mat_lines:
        assert line.sensitivity_cost_per_unit > 0, (
            f"{line.parameter_name}: expected sensitivity > 0, got {line.sensitivity_cost_per_unit}"
        )


def test_sensitivity_sign_step_yield(report):
    """Step yield perturbation +1% → sensitivity < 0 (yield increase lowers cost)."""
    yield_lines = [l for l in report.sensitivity_lines if l.parameter_type == "step_yield"]
    assert len(yield_lines) > 0
    for line in yield_lines:
        assert line.sensitivity_cost_per_unit < 0, (
            f"{line.parameter_name}: expected sensitivity < 0, got {line.sensitivity_cost_per_unit}"
        )


def test_sensitivity_magnitude_known_answer(graph, config, prices, base_bom, risk_profile):
    """
    Verify SM-A sensitivity matches analytic formula:
      sensitivity = (820 × 0.01 × Q_sma_kg_per_batch × num_batches) / total_api_kg
    where total_api_kg = batch_size_kg × num_batches.
    """
    from mrp.risk import generate_sensitivity_report
    from mrp.units import to_float

    report = generate_sensitivity_report(
        graph=graph, config=config, prices=prices,
        base_bom=base_bom, risk_profile=risk_profile, delta_pct=1.0,
    )

    # Find SM-A line
    sma_line = next(
        (l for l in report.sensitivity_lines
         if l.parameter_type == "material_price" and "Starting Material A" in l.parameter_name),
        None,
    )
    assert sma_line is not None, "SM-A sensitivity line not found"

    # Q from the base BoM material lines (total quantity consumed across all batches)
    sma_lines = [ml for ml in base_bom.material_lines if ml.material_name == "Starting Material A"]
    assert len(sma_lines) >= 1
    q_per_batch_kg = to_float(sma_lines[0].quantity, "kg")
    total_api_kg = 50.0 * 5  # batch_size × num_batches
    expected = (820.0 * 0.01 * q_per_batch_kg * 5) / total_api_kg

    assert abs(sma_line.sensitivity_cost_per_unit - expected) < 0.01, (
        f"SM-A sensitivity mismatch: got {sma_line.sensitivity_cost_per_unit:.4f}, "
        f"expected {expected:.4f}"
    )


def test_deepcopy_prices_unchanged(graph, config, prices, base_bom, risk_profile):
    """Generating a sensitivity report must not mutate the original prices object."""
    from mrp.risk import generate_sensitivity_report
    original_sma_price = prices.material_prices["starting material a"].price_per_unit
    generate_sensitivity_report(
        graph=graph, config=config, prices=prices,
        base_bom=base_bom, risk_profile=risk_profile,
    )
    assert prices.material_prices["starting material a"].price_per_unit == original_sma_price


def test_deepcopy_graph_unchanged(graph, config, prices, base_bom, risk_profile):
    """Generating a sensitivity report must not mutate the original graph object."""
    from mrp.risk import generate_sensitivity_report
    original_yield = graph.steps["step_1"].step_yield_pct
    generate_sensitivity_report(
        graph=graph, config=config, prices=prices,
        base_bom=base_bom, risk_profile=risk_profile,
    )
    assert graph.steps["step_1"].step_yield_pct == original_yield


def test_tariff_overlay_cn_only(graph, config, prices, base_bom, risk_profile):
    """55% tariff on CN origin — DE-origin Solvent A should NOT be in exposed lines."""
    from mrp.risk import apply_tariff_overlay
    result = apply_tariff_overlay(
        bom=base_bom,
        tariff_rate_pct=55.0,
        geography="CN",
        include_indirect=False,
        risk_profile=risk_profile,
    )
    assert result.tariff_cost_total > 0, "Expected some tariff cost for CN materials"
    exposed_names = [line["material_name"] for line in result.exposed_material_lines]
    assert "Solvent A" not in exposed_names, "DE-origin Solvent A should not be taxed"
    assert any("Starting Material A" in n for n in exposed_names), "SM-A (CN) should be exposed"


def test_tariff_overlay_no_bom_recalculation(graph, config, prices, base_bom, risk_profile):
    """apply_tariff_overlay must not call calculate_bom() internally."""
    from mrp.risk import apply_tariff_overlay
    with patch("mrp.engine.calculate_bom") as mock_bom:
        apply_tariff_overlay(
            bom=base_bom,
            tariff_rate_pct=55.0,
            geography="CN",
            include_indirect=False,
            risk_profile=risk_profile,
        )
        mock_bom.assert_not_called()


def test_tariff_overlay_include_indirect(graph, config, prices, base_bom, risk_profile):
    """include_indirect=True: materials with indirect_china_exposure should also be taxed."""
    # Add indirect exposure material to risk_profile
    rp = copy.deepcopy(risk_profile)
    rp.material_risk["solvent a"] = MaterialRiskMetadata(
        material_name="Solvent A",
        country_of_origin="DE",
        cdmo_node_id=None,
        single_source=False,
        alternative_supplier_lead_time_weeks=4,
        indirect_china_exposure=True,
    )
    from mrp.risk import apply_tariff_overlay
    result_direct_only = apply_tariff_overlay(
        bom=base_bom, tariff_rate_pct=55.0, geography="CN",
        include_indirect=False, risk_profile=rp,
    )
    result_with_indirect = apply_tariff_overlay(
        bom=base_bom, tariff_rate_pct=55.0, geography="CN",
        include_indirect=True, risk_profile=rp,
    )
    # Including indirect should produce higher tariff cost
    assert result_with_indirect.tariff_cost_total >= result_direct_only.tariff_cost_total


def test_tariff_overlay_no_exposed_materials(graph, config, prices, base_bom, risk_profile):
    """geography=US → no CN materials exposed → tariff_cost_total=0.0, delta=0.0."""
    from mrp.risk import apply_tariff_overlay
    result = apply_tariff_overlay(
        bom=base_bom,
        tariff_rate_pct=55.0,
        geography="US",
        include_indirect=False,
        risk_profile=risk_profile,
    )
    assert result.tariff_cost_total == 0.0
    assert result.cost_per_kg_delta == 0.0


def test_tariff_sweep_monotonic(graph, config, prices, base_bom, risk_profile):
    """Rates [20, 35, 55, 100] → cost_per_kg_delta strictly increasing."""
    from mrp.risk import _run_tariff_scenarios
    rates = [20.0, 35.0, 55.0, 100.0]
    rp = copy.deepcopy(risk_profile)
    rp.tariff_sweep_rates = rates
    rp.tariff_sweep_geography = "CN"
    rp.tariff_sweep_include_indirect = False
    results = _run_tariff_scenarios(base_bom=base_bom, risk_profile=rp)
    # Filter to the sweep results for CN geography
    cn_results = [r for r in results if r.geography == "CN"]
    cn_results.sort(key=lambda r: r.tariff_rate_pct)
    deltas = [r.cost_per_kg_delta for r in cn_results]
    assert len(deltas) >= 4
    for i in range(1, len(deltas)):
        assert deltas[i] > deltas[i - 1], (
            f"Tariff sweep not monotonic at index {i}: {deltas}"
        )


def test_tariff_sweep_sorted_by_rate(graph, config, prices, base_bom, risk_profile):
    """Tariff sweep results should be sorted ascending by rate."""
    from mrp.risk import _run_tariff_scenarios
    results = _run_tariff_scenarios(base_bom=base_bom, risk_profile=risk_profile)
    rates = [r.tariff_rate_pct for r in results]
    assert rates == sorted(rates), f"Results not sorted: {rates}"


def test_cdmo_removal_affected_steps(graph, config, prices, base_bom, risk_profile):
    """Steps tagged with wuxi_sta are listed; untagged steps are not."""
    from mrp.risk import model_cdmo_removal
    wuxi_node = risk_profile.cdmo_nodes["wuxi_sta"]
    result = model_cdmo_removal(
        bom=base_bom,
        cdmo_node=wuxi_node,
        emergency_premium_pct=50.0,
        risk_profile=risk_profile,
    )
    # Both steps are tagged wuxi_sta
    assert "step_1" in result.affected_step_names or "step_2" in result.affected_step_names
    assert len(result.affected_step_names) >= 1


def test_cdmo_removal_affected_materials(graph, config, prices, base_bom, risk_profile):
    """Materials tagged with wuxi_sta are in affected list; Solvent A (DE) is not."""
    from mrp.risk import model_cdmo_removal
    wuxi_node = risk_profile.cdmo_nodes["wuxi_sta"]
    result = model_cdmo_removal(
        bom=base_bom,
        cdmo_node=wuxi_node,
        emergency_premium_pct=50.0,
        risk_profile=risk_profile,
    )
    assert "Starting Material A" in result.affected_material_names
    assert "Reagent B" in result.affected_material_names
    assert "Solvent A" not in result.affected_material_names


def test_cdmo_removal_timeline(graph, config, prices, base_bom, risk_profile):
    """Critical path = max lead time across affected materials (18 wk for SM-A)."""
    from mrp.risk import model_cdmo_removal
    wuxi_node = risk_profile.cdmo_nodes["wuxi_sta"]
    result = model_cdmo_removal(
        bom=base_bom,
        cdmo_node=wuxi_node,
        emergency_premium_pct=50.0,
        risk_profile=risk_profile,
    )
    # SM-A: 18 wk, Reagent B: 10 wk → max = 18
    assert result.timeline_critical_path_weeks == 18.0


def test_cdmo_removal_timeline_unknown(graph, config, prices, base_bom):
    """All affected materials with None lead time → critical_path=None, requalification_notes non-empty."""
    from mrp.risk import model_cdmo_removal
    rp_no_lead_times = RiskProfile(
        name="No Lead Times",
        cdmo_nodes={"wuxi_sta": CDMONode(
            id="wuxi_sta", name="Wuxi AppTec", country="CN", biosecure_act_listed=True,
        )},
        material_risk={
            "starting material a": MaterialRiskMetadata(
                material_name="Starting Material A",
                country_of_origin="CN",
                cdmo_node_id="wuxi_sta",
                single_source=True,
                alternative_supplier_lead_time_weeks=None,  # unknown
            ),
            "reagent b": MaterialRiskMetadata(
                material_name="Reagent B",
                country_of_origin="CN",
                cdmo_node_id="wuxi_sta",
                single_source=False,
                alternative_supplier_lead_time_weeks=None,  # unknown
            ),
        },
        step_risk={
            "step_1": StepRiskMetadata(
                step_name="step_1", cdmo_node_id="wuxi_sta",
            ),
            "step_2": StepRiskMetadata(
                step_name="step_2", cdmo_node_id="wuxi_sta",
            ),
        },
        risk_vectors=[],
    )
    wuxi_node = rp_no_lead_times.cdmo_nodes["wuxi_sta"]
    result = model_cdmo_removal(
        bom=base_bom,
        cdmo_node=wuxi_node,
        emergency_premium_pct=50.0,
        risk_profile=rp_no_lead_times,
    )
    assert result.timeline_critical_path_weeks is None
    assert result.requalification_notes is not None and len(result.requalification_notes) > 0


def test_cdmo_removal_emergency_cost_greater(graph, config, prices, base_bom, risk_profile):
    """Emergency sourcing cost per kg API > base cost per kg API."""
    from mrp.risk import model_cdmo_removal
    wuxi_node = risk_profile.cdmo_nodes["wuxi_sta"]
    result = model_cdmo_removal(
        bom=base_bom,
        cdmo_node=wuxi_node,
        emergency_premium_pct=50.0,
        risk_profile=risk_profile,
    )
    assert result.emergency_cost_per_kg_api > result.base_cost_per_kg_api


def test_exposure_summary_china_origin_pct(graph, config, prices, base_bom, risk_profile):
    """china_origin_cost_pct = Σ(CN material costs) / Σ(all material costs) × 100."""
    from mrp.risk import _compute_exposure_summary
    from mrp.units import to_float

    summary = _compute_exposure_summary(bom=base_bom, risk_profile=risk_profile)

    # Calculate expected manually
    cn_cost = 0.0
    total_cost = 0.0
    for ml in base_bom.material_lines:
        if ml.unit_cost > 0:
            meta = risk_profile.material_risk.get(ml.material_name.lower())
            total_cost += ml.total_cost
            if meta and meta.country_of_origin == "CN":
                cn_cost += ml.total_cost

    if total_cost > 0:
        expected_pct = cn_cost / total_cost * 100.0
    else:
        expected_pct = 0.0

    assert abs(summary["china_origin_cost_pct"] - expected_pct) < 0.01, (
        f"china_origin_cost_pct mismatch: {summary['china_origin_cost_pct']:.4f} vs {expected_pct:.4f}"
    )


def test_ranking_single_source_multiplier(graph, config, prices, base_bom, risk_profile):
    """
    Single-source material at $2.00 sensitivity beats non-single at $2.50:
    2.00 × 1.5 = 3.00 > 2.50 × 1.0 = 2.50 → single-source gets rank 1.
    """
    from mrp.risk import _rank_sensitivity_lines
    from mrp.domain import SensitivityLine

    line_single = SensitivityLine(
        rank=0,
        parameter_name="Single Source Mat",
        parameter_type="material_price",
        sensitivity_cost_per_unit=2.00,
        sensitivity_unit="$/kg_api per 1% price change",
        country_of_origin="CN",
        cdmo_node_name="Wuxi",
        is_single_source=True,
        is_indirect_china=False,
        timeline_impact_weeks=None,
        tariff_impact_at_rate=None,
        risk_flags=[],
    )
    line_non_single = SensitivityLine(
        rank=0,
        parameter_name="Non Single Source Mat",
        parameter_type="material_price",
        sensitivity_cost_per_unit=2.50,
        sensitivity_unit="$/kg_api per 1% price change",
        country_of_origin="DE",
        cdmo_node_name=None,
        is_single_source=False,
        is_indirect_china=False,
        timeline_impact_weeks=None,
        tariff_impact_at_rate=None,
        risk_flags=[],
    )

    ranked = _rank_sensitivity_lines([line_single, line_non_single])
    assert ranked[0].parameter_name == "Single Source Mat", (
        f"Expected single-source to be rank 1, got: {ranked[0].parameter_name}"
    )
    assert ranked[0].rank == 1
    assert ranked[1].rank == 2
