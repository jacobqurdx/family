from __future__ import annotations
import copy
import time
import numpy as np
from dataclasses import dataclass, field
from scipy.optimize import differential_evolution, OptimizeResult
from mrp.domain import ProcessGraph, ProcessConfig, PriceList, ParameterType, BoMResult
from mrp.engine import calculate_bom
from mrp.units import ureg
from mrp.constraints import CONSTRAINT_REGISTRY, validate_constraint, ConstraintRegistryError


@dataclass
class OptimisationParameter:
    param_type: ParameterType
    target_id: str
    label: str
    lower_bound: float
    upper_bound: float
    baseline: float
    unit: str
    is_integer: bool = False

@dataclass
class OptimisationConstraint:
    metric: str
    operator: str
    threshold: float
    description: str = ""

@dataclass
class OptimisationConfig:
    objective: str
    parameters: list[OptimisationParameter]
    constraints: list[OptimisationConstraint]
    method: str = "differential_evolution"
    max_evaluations: int = 500
    seed: int | None = None

@dataclass
class EvaluationRecord:
    index: int
    parameter_values: dict[str, float]
    cost_per_kg_api: float
    total_cost: float
    overall_route_yield_pct: float
    is_feasible: bool
    objective_value: float

@dataclass
class OptimisationResult:
    best_parameter_values: dict[str, float]
    best_objective_value: float
    best_cost_per_kg_api: float
    best_overall_yield_pct: float
    n_evaluations: int
    n_feasible: int
    evaluations: list[EvaluationRecord]
    elapsed_sec: float
    converged: bool


def validate_all_constraints(constraints: list[OptimisationConstraint]) -> list[str]:
    errors = []
    for c in constraints:
        try:
            validate_constraint(c.metric, c.operator, c.threshold)
        except (ConstraintRegistryError, ValueError) as e:
            errors.append(str(e))
    return errors


def run_optimisation(
    graph: ProcessGraph,
    config: ProcessConfig,
    prices: PriceList,
    opt_config: OptimisationConfig,
    progress_callback=None,
) -> OptimisationResult:
    errors = validate_all_constraints(opt_config.constraints)
    if errors:
        raise ValueError(f"Constraint validation failed:\n" + "\n".join(f"  • {e}" for e in errors))

    evaluations: list[EvaluationRecord] = []
    eval_count = 0

    def objective(x: np.ndarray) -> float:
        nonlocal eval_count
        eval_count += 1

        param_values = {
            p.label: (round(float(x[i])) if p.is_integer else float(x[i]))
            for i, p in enumerate(opt_config.parameters)
        }

        try:
            g, c, p = _apply_opt_params(graph, config, prices, param_values, opt_config)
            bom = calculate_bom(g, c, p)
        except Exception:
            return 1e12

        penalty = 0.0
        feasible = True
        for constraint in opt_config.constraints:
            defn = CONSTRAINT_REGISTRY[constraint.metric]
            actual = defn.extractor_bom(bom)
            if constraint.operator == "<=" and actual > constraint.threshold:
                penalty += (actual - constraint.threshold) ** 2 * 1e6
                feasible = False
            elif constraint.operator == ">=" and actual < constraint.threshold:
                penalty += (constraint.threshold - actual) ** 2 * 1e6
                feasible = False

        obj_raw = {
            "min_cost_per_kg": bom.cost_per_kg_api,
            "min_total_cost": bom.total_cost,
            "max_yield": -bom.overall_route_yield_pct,
        }.get(opt_config.objective, bom.cost_per_kg_api)

        obj_total = obj_raw + penalty

        evaluations.append(EvaluationRecord(
            index=eval_count,
            parameter_values=param_values,
            cost_per_kg_api=bom.cost_per_kg_api,
            total_cost=bom.total_cost,
            overall_route_yield_pct=bom.overall_route_yield_pct,
            is_feasible=feasible,
            objective_value=obj_total,
        ))
        if progress_callback:
            progress_callback(eval_count, opt_config.max_evaluations)
        return obj_total

    bounds = [(p.lower_bound, p.upper_bound) for p in opt_config.parameters]
    t0 = time.perf_counter()

    if opt_config.method == "differential_evolution":
        # Progress is tracked via nonlocal eval_count inside objective(), not via
        # scipy's callback (which fires per generation, not per evaluation).
        result: OptimizeResult = differential_evolution(
            objective,
            bounds=bounds,
            maxiter=opt_config.max_evaluations // max(len(bounds) * 15, 1),
            seed=opt_config.seed,
            tol=1e-4,
            polish=True,
        )
        converged = result.success
    else:
        raise NotImplementedError(f"Method '{opt_config.method}' not yet implemented")

    elapsed = time.perf_counter() - t0

    best_params = {
        p.label: float(result.x[i])
        for i, p in enumerate(opt_config.parameters)
    }
    best_bom_g, best_bom_c, best_bom_p = _apply_opt_params(
        graph, config, prices, best_params, opt_config
    )
    best_bom = calculate_bom(best_bom_g, best_bom_c, best_bom_p)

    feasible_evals = [e for e in evaluations if e.is_feasible]

    return OptimisationResult(
        best_parameter_values=best_params,
        best_objective_value=float(result.fun),
        best_cost_per_kg_api=best_bom.cost_per_kg_api,
        best_overall_yield_pct=best_bom.overall_route_yield_pct,
        n_evaluations=eval_count,
        n_feasible=len(feasible_evals),
        evaluations=evaluations,
        elapsed_sec=elapsed,
        converged=converged,
    )


def _apply_opt_params(
    graph, config, prices, param_values, opt_config
) -> tuple:
    graph  = copy.deepcopy(graph)
    config = copy.deepcopy(config)
    prices = copy.deepcopy(prices)
    for i, p in enumerate(opt_config.parameters):
        value = param_values[p.label]
        if p.param_type == ParameterType.STEP_YIELD:
            graph.steps[p.target_id].step_yield_pct = float(value)
        elif p.param_type == ParameterType.MATERIAL_PRICE:
            key = p.target_id.lower()
            if key in prices.material_prices:
                prices.material_prices[key].price_per_unit = float(value)
        elif p.param_type == ParameterType.BATCH_SIZE:
            config.batch_size = ureg.Quantity(float(value), "kg")
    return graph, config, prices
