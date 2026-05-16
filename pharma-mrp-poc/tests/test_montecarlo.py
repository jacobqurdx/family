import pytest
import numpy as np
from pathlib import Path
from mrp.domain import (
    MCDefinition, DistributionSpec, DistributionType, ParameterType,
    CorrelationPair, ProcessConfig,
)
from mrp.montecarlo import draw_samples, run_monte_carlo, compute_percentiles, check_convergence
from mrp.loader import load_process, load_price_list
from mrp.units import ureg


EXAMPLES = Path(__file__).parent.parent / "examples"


def _make_normal_defn(n: int = 1000, seed: int = 42) -> MCDefinition:
    return MCDefinition(
        name="test",
        n_iterations=n,
        distributions=[
            DistributionSpec(
                param_type=ParameterType.STEP_YIELD,
                target_id="step_1",
                label="Step 1 Yield",
                distribution=DistributionType.NORMAL,
                unit="%",
                params={"mean": 87.0, "std": 4.0},
                clip_low=60.0, clip_high=99.0,
            ),
        ],
        base_config=ProcessConfig(batch_size=ureg.Quantity(50.0, "kg"), num_batches=1),
        random_seed=seed,
    )


def test_draw_samples_reproducible():
    defn = _make_normal_defn(n=500, seed=42)
    s1 = draw_samples(defn)
    s2 = draw_samples(defn)
    np.testing.assert_array_equal(s1, s2)


def test_normal_distribution_mean():
    """Sample mean should be within 1% of specified mean at n=10,000."""
    defn = _make_normal_defn(n=10000, seed=99)
    samples = draw_samples(defn)
    assert abs(np.mean(samples[:, 0]) - 87.0) / 87.0 < 0.01


def test_pert_samples_within_bounds():
    """At least 95% of PERT samples should be within [min, max]."""
    defn = MCDefinition(
        name="pert-test",
        n_iterations=5000,
        distributions=[
            DistributionSpec(
                param_type=ParameterType.STEP_YIELD,
                target_id="step_3",
                label="PERT Yield",
                distribution=DistributionType.PERT,
                unit="%",
                params={"min": 60.0, "most_likely": 74.0, "max": 88.0},
            ),
        ],
        base_config=ProcessConfig(batch_size=ureg.Quantity(50.0, "kg"), num_batches=1),
        random_seed=7,
    )
    samples = draw_samples(defn)
    within = np.sum((samples[:, 0] >= 60.0) & (samples[:, 0] <= 88.0))
    assert within / 5000.0 >= 0.95


def test_compute_percentiles_keys():
    """compute_percentiles must return all required keys."""
    from mrp.domain import MCResult
    results = [
        MCResult(iteration=i, sampled_inputs={}, cost_per_kg_api=float(i),
                 total_cost=0.0, total_material_cost=0.0, total_equipment_cost=0.0,
                 total_labor_cost=0.0, total_utility_cost=0.0, overall_route_yield_pct=50.0,
                 status="success")
        for i in range(1, 101)
    ]
    pcts = compute_percentiles(results)
    for key in ("n", "mean", "std", "min", "p5", "p10", "p25", "p50", "p75", "p90", "p95", "max"):
        assert key in pcts


def test_check_convergence_fixed_distribution():
    """A fixed-value distribution should converge quickly."""
    from mrp.domain import MCResult
    results = [
        MCResult(iteration=i, sampled_inputs={}, cost_per_kg_api=1000.0,
                 total_cost=0.0, total_material_cost=0.0, total_equipment_cost=0.0,
                 total_labor_cost=0.0, total_utility_cost=0.0, overall_route_yield_pct=50.0,
                 status="success")
        for i in range(5000)
    ]
    conv = check_convergence(results)
    assert conv["converged"] is True


def test_correlated_samples_pearson_r():
    """Correlated columns should have Pearson r within 0.05 of specified at n=10,000."""
    defn = MCDefinition(
        name="corr-test",
        n_iterations=10000,
        distributions=[
            DistributionSpec(
                param_type=ParameterType.MATERIAL_PRICE,
                target_id="SM-A Price",
                label="SM-A Price",
                distribution=DistributionType.LOGNORMAL,
                unit="USD/kg",
                params={"mean": 6.71, "std": 0.18},
            ),
            DistributionSpec(
                param_type=ParameterType.MATERIAL_PRICE,
                target_id="Pd/C Price",
                label="Pd/C Price",
                distribution=DistributionType.UNIFORM,
                unit="USD/kg",
                params={"low": 1000.0, "high": 1800.0},
            ),
        ],
        base_config=ProcessConfig(batch_size=ureg.Quantity(50.0, "kg"), num_batches=1),
        correlations=[CorrelationPair(label_a="SM-A Price", label_b="Pd/C Price", pearson_r=0.65)],
        random_seed=42,
    )
    samples = draw_samples(defn)
    actual_r = np.corrcoef(samples[:, 0], samples[:, 1])[0, 1]
    assert abs(actual_r - 0.65) < 0.05
