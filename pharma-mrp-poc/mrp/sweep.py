from __future__ import annotations
import copy
import itertools
import time
from multiprocessing import Pool, cpu_count
from mrp.domain import (
    SweepDefinition, SweepMode, ParameterType, ProcessGraph,
    ProcessConfig, PriceList, ScenarioResult,
)
from mrp.engine import calculate_bom
from mrp.units import ureg


def expand_sweep(defn: SweepDefinition) -> list[dict[str, float]]:
    params = defn.parameters

    if defn.mode == SweepMode.CARTESIAN:
        keys = [p.label for p in params]
        value_lists = [p.values for p in params]
        return [dict(zip(keys, combo)) for combo in itertools.product(*value_lists)]

    elif defn.mode == SweepMode.ONE_AT_A_TIME:
        baseline = {p.label: p.baseline for p in params}
        scenarios = []
        for p in params:
            for v in p.values:
                scenario = dict(baseline)
                scenario[p.label] = v
                if v != p.baseline:
                    scenarios.append(scenario)
        return scenarios

    elif defn.mode == SweepMode.NAMED_LIST:
        return getattr(defn, "named_scenarios", [])

    raise ValueError(f"Unknown sweep mode: {defn.mode}")


def _apply_param_values(
    graph: ProcessGraph,
    config: ProcessConfig,
    prices: PriceList,
    param_values: dict[str, float],
    defn: SweepDefinition,
) -> tuple[ProcessGraph, ProcessConfig, PriceList]:
    graph  = copy.deepcopy(graph)
    config = copy.deepcopy(config)
    prices = copy.deepcopy(prices)

    label_to_param = {p.label: p for p in defn.parameters}

    for label, value in param_values.items():
        param = label_to_param.get(label)
        if param is None:
            continue

        if param.param_type == ParameterType.STEP_YIELD:
            graph.steps[param.target_id].step_yield_pct = float(value)

        elif param.param_type == ParameterType.MATERIAL_PRICE:
            key = param.target_id.lower()
            if key in prices.material_prices:
                prices.material_prices[key].price_per_unit = float(value)

        elif param.param_type == ParameterType.BATCH_SIZE:
            config.batch_size = ureg.Quantity(float(value), "kg")

        elif param.param_type == ParameterType.NUM_BATCHES:
            config.num_batches = int(value)

        elif param.param_type == ParameterType.MATERIAL_EQUIVALENTS:
            step_id, mat_name = param.target_id.split("::", 1)
            for sm in graph.steps[step_id].materials:
                if sm.material.name.lower() == mat_name.lower():
                    sm.equivalents = float(value)

        elif param.param_type == ParameterType.MATERIAL_EXCESS:
            step_id, mat_name = param.target_id.split("::", 1)
            for sm in graph.steps[step_id].materials:
                if sm.material.name.lower() == mat_name.lower():
                    sm.excess_pct = float(value)

    return graph, config, prices


def _run_single_scenario(args: tuple) -> ScenarioResult:
    """
    Top-level module function required for multiprocessing.Pool pickling.
    Must NOT be moved inside a class, closure, or nested function.
    """
    graph, config, prices, param_values, defn, label = args
    try:
        g, c, p = _apply_param_values(graph, config, prices, param_values, defn)
        bom = calculate_bom(g, c, p)
        return ScenarioResult(
            scenario_label=label,
            parameter_values=param_values,
            cost_per_kg_api=bom.cost_per_kg_api,
            total_cost=bom.total_cost,
            total_material_cost=bom.total_material_cost,
            total_equipment_cost=bom.total_equipment_cost,
            total_labor_cost=bom.total_labor_cost,
            total_utility_cost=bom.total_utility_cost,
            overall_route_yield_pct=bom.overall_route_yield_pct,
            status="success",
        )
    except Exception as e:
        return ScenarioResult(
            scenario_label=label,
            parameter_values=param_values,
            cost_per_kg_api=0.0,
            total_cost=0.0,
            total_material_cost=0.0,
            total_equipment_cost=0.0,
            total_labor_cost=0.0,
            total_utility_cost=0.0,
            overall_route_yield_pct=0.0,
            status="failed",
            error=str(e),
        )


def run_sweep(
    graph: ProcessGraph,
    config: ProcessConfig,
    prices: PriceList,
    defn: SweepDefinition,
    workers: int | None = None,
    progress_callback=None,
) -> tuple[list[ScenarioResult], float]:
    combinations = expand_sweep(defn)
    n = len(combinations)

    def make_label(param_values: dict[str, float]) -> str:
        parts = [f"{k}={v}" for k, v in param_values.items()]
        label = "__".join(parts)
        return label[:120] + ("..." if len(label) > 120 else "")

    args_list = [
        (graph, config, prices, pv, defn, make_label(pv))
        for pv in combinations
    ]

    n_workers = workers or min(cpu_count(), n)
    results: list[ScenarioResult] = []

    t0 = time.perf_counter()
    with Pool(processes=n_workers) as pool:
        for i, result in enumerate(pool.imap_unordered(_run_single_scenario, args_list)):
            results.append(result)
            if progress_callback:
                progress_callback(i + 1, n)
    elapsed = time.perf_counter() - t0

    return results, elapsed
