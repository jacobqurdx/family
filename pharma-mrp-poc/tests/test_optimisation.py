import pytest
import numpy as np
from mrp.constraints import validate_constraint, ConstraintRegistryError, InfeasibleConstraintError
from mrp.optimisation import (
    OptimisationConfig, OptimisationParameter, OptimisationConstraint,
    validate_all_constraints, run_optimisation,
)
from mrp.domain import ParameterType, ProcessConfig
from mrp.units import ureg


def test_validate_unregistered_metric():
    errors = validate_all_constraints([
        OptimisationConstraint(metric="nonexistent_metric", operator="<=", threshold=1000.0)
    ])
    assert len(errors) == 1
    assert "nonexistent_metric" in errors[0]


def test_validate_infeasible_yield_constraint():
    errors = validate_all_constraints([
        OptimisationConstraint(metric="overall_route_yield_pct", operator=">=", threshold=110.0)
    ])
    assert len(errors) == 1
    assert "110" in errors[0]


def test_validate_valid_constraints_empty_errors():
    errors = validate_all_constraints([
        OptimisationConstraint(metric="overall_route_yield_pct", operator=">=", threshold=35.0),
        OptimisationConstraint(metric="cost_per_kg_api", operator="<=", threshold=10000.0),
    ])
    assert errors == []


def test_optimisation_finds_minimum_synthetic():
    """
    Synthetic test: optimise a 1-parameter quadratic cost surface.
    Uses the linear_5step.yaml with step_3 yield as parameter.
    The cheapest BoM is at maximum yield (99%) since higher yield = less input material.
    """
    from pathlib import Path
    from mrp.loader import load_process, load_price_list

    examples = Path(__file__).parent.parent / "examples"
    graph  = load_process(examples / "linear_5step.yaml")
    prices = load_price_list(examples / "prices_q2_2026.yaml")
    config = ProcessConfig(batch_size=ureg.Quantity(50.0, "kg"), num_batches=1)

    opt_config = OptimisationConfig(
        objective="min_cost_per_kg",
        parameters=[
            OptimisationParameter(
                param_type=ParameterType.STEP_YIELD,
                target_id="step_3",
                label="Step 3 Yield",
                lower_bound=50.0,
                upper_bound=99.0,
                baseline=74.0,
                unit="%",
            ),
        ],
        constraints=[
            OptimisationConstraint(
                metric="overall_route_yield_pct",
                operator=">=",
                threshold=20.0,
            )
        ],
        method="differential_evolution",
        max_evaluations=300,
        seed=42,
    )

    result = run_optimisation(graph, config, prices, opt_config)
    # Optimal step_3 yield should be close to maximum (99%)
    # since higher yield reduces material input, lowering cost
    assert result.best_parameter_values["Step 3 Yield"] > 85.0
    assert result.n_feasible > 0


def test_infeasible_constraint_penalises_solution():
    """Infeasible evaluation should have is_feasible=False and a penalty on objective."""
    from pathlib import Path
    from mrp.loader import load_process, load_price_list

    examples = Path(__file__).parent.parent / "examples"
    graph  = load_process(examples / "linear_5step.yaml")
    prices = load_price_list(examples / "prices_q2_2026.yaml")
    config = ProcessConfig(batch_size=ureg.Quantity(50.0, "kg"), num_batches=1)

    # Constraint: yield >= 99% (nearly impossible for a 5-step process)
    opt_config = OptimisationConfig(
        objective="min_cost_per_kg",
        parameters=[
            OptimisationParameter(
                param_type=ParameterType.STEP_YIELD,
                target_id="step_3",
                label="Step 3 Yield",
                lower_bound=50.0,
                upper_bound=80.0,   # cap at 80% so constraint is never satisfied
                baseline=74.0,
                unit="%",
            ),
        ],
        constraints=[
            OptimisationConstraint(
                metric="overall_route_yield_pct",
                operator=">=",
                threshold=99.0,   # physically impossible with this setup
            )
        ],
        method="differential_evolution",
        max_evaluations=60,
        seed=99,
    )

    result = run_optimisation(graph, config, prices, opt_config)
    # All evaluations should be infeasible given the impossible constraint
    infeasible = [e for e in result.evaluations if not e.is_feasible]
    assert len(infeasible) > 0
    # Infeasible objectives should be large (penalty applied)
    assert any(e.objective_value > 1e4 for e in infeasible)
