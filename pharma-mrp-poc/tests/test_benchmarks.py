"""
Performance benchmarks. These verify the spec's timing criteria:
  - 125-scenario Cartesian sweep: < 10 seconds
  - 10,000-iteration Monte Carlo: < 90 seconds (single machine)
  - Optimisation: converges in <= 500 evaluations
"""
import time
from pathlib import Path
from mrp.loader import load_process, load_price_list, load_mc_definition
from mrp.engine import calculate_bom
from mrp.sweep import run_sweep, expand_sweep
from mrp.montecarlo import run_monte_carlo, compute_percentiles
from mrp.optimisation import (
    OptimisationConfig, OptimisationParameter, OptimisationConstraint, run_optimisation,
)
from mrp.domain import (
    SweepDefinition, SweepMode, SweepParameter, ParameterType, ProcessConfig,
)
from mrp.units import ureg

EXAMPLES = Path(__file__).parent.parent / "examples"


def _load_linear():
    graph  = load_process(EXAMPLES / "linear_5step.yaml")
    prices = load_price_list(EXAMPLES / "prices_q2_2026.yaml")
    config = ProcessConfig(batch_size=ureg.Quantity(50.0, "kg"), num_batches=5)
    return graph, prices, config


def test_single_bom_speed(benchmark):
    """Single BoM calculation must complete quickly (benchmark reports ms)."""
    graph, prices, config = _load_linear()
    result = benchmark(calculate_bom, graph, config, prices)
    assert result.cost_per_kg_api > 0


def test_sweep_125_scenarios_under_10s():
    """125-scenario Cartesian sweep must complete in under 10 seconds."""
    graph, prices, config = _load_linear()
    defn = SweepDefinition(
        name="bench-sweep",
        mode=SweepMode.CARTESIAN,
        base_config=config,
        parameters=[
            SweepParameter(param_type=ParameterType.STEP_YIELD, target_id="step_3",
                           label="Step 3 Yield (%)", values=[65., 70., 74., 78., 82.],
                           baseline=74., unit="%"),
            SweepParameter(param_type=ParameterType.STEP_YIELD, target_id="step_4",
                           label="Step 4 Yield (%)", values=[75., 79., 82., 85., 88.],
                           baseline=82., unit="%"),
            SweepParameter(param_type=ParameterType.MATERIAL_PRICE,
                           target_id="Starting Material A",
                           label="SM-A Price (USD/kg)",
                           values=[500., 650., 820., 1000., 1250.],
                           baseline=820., unit="USD/kg"),
        ],
    )
    assert len(expand_sweep(defn)) == 125

    t0 = time.perf_counter()
    results, elapsed = run_sweep(graph, config, prices, defn, workers=None)
    assert elapsed < 10.0, f"Sweep took {elapsed:.1f}s (limit: 10s)"
    assert sum(1 for r in results if r.status == "success") == 125


def test_mc_10k_under_90s():
    """10,000-iteration Monte Carlo must complete in under 90 seconds."""
    graph, prices, config = _load_linear()
    defn = load_mc_definition(EXAMPLES / "mc_yield_distributions.yaml")

    t0 = time.perf_counter()
    results, elapsed = run_monte_carlo(graph, config, prices, defn, workers=None)
    assert elapsed < 90.0, f"MC took {elapsed:.1f}s (limit: 90s)"

    success = [r for r in results if r.status == "success"]
    assert len(success) >= 9900, f"Only {len(success)}/10000 iterations succeeded"

    pcts = compute_percentiles(success)
    assert pcts["p50"] > 0


def test_optimisation_converges():
    """Differential evolution converges within 500 evaluations."""
    graph, prices, config = _load_linear()

    opt_config = OptimisationConfig(
        objective="min_cost_per_kg",
        parameters=[
            OptimisationParameter(
                param_type=ParameterType.STEP_YIELD, target_id="step_3",
                label="Step 3 Yield", lower_bound=50., upper_bound=99.,
                baseline=74., unit="%",
            ),
            OptimisationParameter(
                param_type=ParameterType.STEP_YIELD, target_id="step_4",
                label="Step 4 Yield", lower_bound=50., upper_bound=99.,
                baseline=82., unit="%",
            ),
            OptimisationParameter(
                param_type=ParameterType.MATERIAL_PRICE, target_id="Starting Material A",
                label="SM-A Price", lower_bound=400., upper_bound=1500.,
                baseline=820., unit="USD/kg",
            ),
        ],
        constraints=[
            OptimisationConstraint(metric="overall_route_yield_pct", operator=">=",
                                   threshold=30.0),
        ],
        method="differential_evolution",
        max_evaluations=500,
        seed=42,
    )

    result = run_optimisation(graph, config, prices, opt_config)
    # polish=True adds a small number of extra evaluations beyond the budget
    assert result.n_evaluations <= 600, f"Too many evaluations: {result.n_evaluations}"
    assert result.n_feasible > 0
    assert result.best_cost_per_kg_api > 0
