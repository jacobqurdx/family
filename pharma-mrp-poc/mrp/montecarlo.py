from __future__ import annotations
import copy
import time
import numpy as np
from scipy import stats
from multiprocessing import Pool, cpu_count
from mrp.domain import (
    MCDefinition, DistributionType, ParameterType, ProcessGraph,
    ProcessConfig, PriceList, MCResult, CorrelationPair,
)
from mrp.engine import calculate_bom
from mrp.units import ureg


def _build_sampler(dist_spec):
    p = dist_spec.params
    d = dist_spec.distribution

    if d == DistributionType.NORMAL:
        rv = stats.truncnorm(
            a=(dist_spec.clip_low  - p["mean"]) / p["std"] if dist_spec.clip_low  is not None else -np.inf,
            b=(dist_spec.clip_high - p["mean"]) / p["std"] if dist_spec.clip_high is not None else  np.inf,
            loc=p["mean"], scale=p["std"]
        )
    elif d == DistributionType.LOGNORMAL:
        rv = stats.lognorm(s=p["std"], scale=np.exp(p["mean"]))
    elif d == DistributionType.UNIFORM:
        rv = stats.uniform(loc=p["low"], scale=p["high"] - p["low"])
    elif d == DistributionType.TRIANGULAR:
        lo, hi, mode = p["min"], p["max"], p["most_likely"]
        c = (mode - lo) / (hi - lo)
        rv = stats.triang(c=c, loc=lo, scale=hi - lo)
    elif d == DistributionType.PERT:
        lo, hi, mode = p["min"], p["max"], p["most_likely"]
        mu = (lo + 4 * mode + hi) / 6.0
        sigma2 = ((mu - lo) * (hi - mu)) / 7.0
        if sigma2 <= 0:
            return None
        alpha = ((mu - lo) / (hi - lo)) * ((mu - lo) * (hi - mu) / sigma2 - 1)
        beta_param = alpha * (hi - mu) / (mu - lo)
        rv = stats.beta(a=alpha, b=beta_param, loc=lo, scale=hi - lo)
    elif d == DistributionType.FIXED:
        return None
    else:
        raise ValueError(f"Unknown distribution type: {d}")

    return rv


def draw_samples(defn: MCDefinition) -> np.ndarray:
    """
    Draw all n_iterations samples in a single vectorised call.
    Returns array of shape (n_iterations, n_params).

    All samples are drawn here before the iteration loop — this is the
    primary performance mechanism. Drawing n=10,000 samples at once is
    orders of magnitude faster than drawing 1 sample per iteration.
    """
    rng = np.random.default_rng(defn.random_seed)
    n = defn.n_iterations
    k = len(defn.distributions)

    if not defn.correlations:
        samples = np.zeros((n, k))
        for j, dist_spec in enumerate(defn.distributions):
            rv = _build_sampler(dist_spec)
            if rv is None:
                samples[:, j] = dist_spec.params.get("value", dist_spec.params.get("most_likely", 0.0))
            else:
                samples[:, j] = rv.rvs(size=n, random_state=rng)
        return samples

    # Gaussian copula for correlated sampling
    label_to_idx = {d.label: i for i, d in enumerate(defn.distributions)}
    corr_matrix = np.eye(k)
    for cp in defn.correlations:
        i, j = label_to_idx[cp.label_a], label_to_idx[cp.label_b]
        corr_matrix[i, j] = cp.pearson_r
        corr_matrix[j, i] = cp.pearson_r

    try:
        L = np.linalg.cholesky(corr_matrix)
    except np.linalg.LinAlgError:
        raise ValueError(
            "Correlation matrix is not positive semi-definite. "
            "Reduce correlation magnitudes or check for contradictory correlations."
        )

    z = rng.standard_normal((n, k)) @ L.T
    u = stats.norm.cdf(z)

    samples = np.zeros((n, k))
    for j, dist_spec in enumerate(defn.distributions):
        rv = _build_sampler(dist_spec)
        if rv is None:
            samples[:, j] = dist_spec.params.get("value", 0.0)
        else:
            samples[:, j] = rv.ppf(np.clip(u[:, j], 1e-10, 1 - 1e-10))

    return samples


def _apply_mc_params(
    graph: ProcessGraph,
    config: ProcessConfig,
    prices: PriceList,
    param_values: dict[str, float],
    defn: MCDefinition,
) -> tuple[ProcessGraph, ProcessConfig, PriceList]:
    graph  = copy.deepcopy(graph)
    config = copy.deepcopy(config)
    prices = copy.deepcopy(prices)
    label_to_dist = {d.label: d for d in defn.distributions}

    for label, value in param_values.items():
        dist_spec = label_to_dist.get(label)
        if dist_spec is None:
            continue
        if dist_spec.param_type == ParameterType.STEP_YIELD:
            graph.steps[dist_spec.target_id].step_yield_pct = float(value)
        elif dist_spec.param_type == ParameterType.MATERIAL_PRICE:
            key = dist_spec.target_id.lower()
            if key in prices.material_prices:
                prices.material_prices[key].price_per_unit = float(value)
        elif dist_spec.param_type == ParameterType.BATCH_SIZE:
            config.batch_size = ureg.Quantity(float(value), "kg")

    return graph, config, prices


def _run_single_iteration(args: tuple) -> MCResult:
    """
    Top-level module function required for multiprocessing.Pool pickling.
    Must NOT be moved inside a class, closure, or nested function.
    """
    graph, config, prices, param_values, iteration, defn = args
    try:
        g, c, p = _apply_mc_params(graph, config, prices, param_values, defn)
        bom = calculate_bom(g, c, p)
        return MCResult(
            iteration=iteration,
            sampled_inputs=param_values,
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
        return MCResult(
            iteration=iteration,
            sampled_inputs=param_values,
            cost_per_kg_api=0.0, total_cost=0.0,
            total_material_cost=0.0, total_equipment_cost=0.0,
            total_labor_cost=0.0, total_utility_cost=0.0,
            overall_route_yield_pct=0.0,
            status="failed", error=str(e),
        )


def run_monte_carlo(
    graph: ProcessGraph,
    config: ProcessConfig,
    prices: PriceList,
    defn: MCDefinition,
    workers: int | None = None,
    progress_callback=None,
) -> tuple[list[MCResult], float]:
    t0 = time.perf_counter()

    samples = draw_samples(defn)
    labels  = [d.label for d in defn.distributions]
    n = defn.n_iterations

    args_list = [
        (graph, config, prices,
         {labels[j]: samples[i, j] for j in range(len(labels))},
         i, defn)
        for i in range(n)
    ]

    n_workers = workers or min(cpu_count(), n, 8)
    results: list[MCResult] = []

    with Pool(processes=n_workers) as pool:
        for i, result in enumerate(pool.imap_unordered(_run_single_iteration, args_list, chunksize=50)):
            results.append(result)
            if progress_callback:
                progress_callback(i + 1, n)

    results.sort(key=lambda r: r.iteration)
    elapsed = time.perf_counter() - t0
    return results, elapsed


def compute_percentiles(
    results: list[MCResult],
    metric: str = "cost_per_kg_api",
) -> dict[str, float]:
    values = np.array([
        getattr(r, metric) for r in results if r.status == "success"
    ])
    if len(values) == 0:
        return {}
    return {
        "n":    len(values),
        "mean": float(np.mean(values)),
        "std":  float(np.std(values)),
        "min":  float(np.min(values)),
        "p5":   float(np.percentile(values, 5)),
        "p10":  float(np.percentile(values, 10)),
        "p25":  float(np.percentile(values, 25)),
        "p50":  float(np.percentile(values, 50)),
        "p75":  float(np.percentile(values, 75)),
        "p90":  float(np.percentile(values, 90)),
        "p95":  float(np.percentile(values, 95)),
        "max":  float(np.max(values)),
    }


def check_convergence(
    results: list[MCResult],
    metric: str = "cost_per_kg_api",
    window: int = 200,
    tolerance: float = 0.001,
) -> dict:
    values = [getattr(r, metric) for r in results if r.status == "success"]
    if len(values) < window * 2:
        return {"converged": False, "at_iteration": None}

    arr = np.array(values)
    for i in range(window, len(arr)):
        prev_mean = np.mean(arr[i - window : i])
        curr_mean = np.mean(arr[max(0, i - window // 2) : i])
        if abs(curr_mean - prev_mean) / max(abs(prev_mean), 1e-10) < tolerance:
            return {"converged": True, "at_iteration": i, "final_mean": float(curr_mean)}

    return {"converged": False, "at_iteration": None, "final_mean": float(np.mean(arr))}
