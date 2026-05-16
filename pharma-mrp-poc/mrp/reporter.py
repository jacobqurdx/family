import json
import csv
import numpy as np
from pathlib import Path
from datetime import datetime
from mrp.domain import BoMResult, ScenarioResult, MCResult
from mrp.optimisation import OptimisationResult
from mrp.units import to_float


def make_output_dir(base: Path, run_name: str) -> Path:
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = run_name.replace(" ", "_").replace("/", "-")[:40]
    out = base / f"{ts}_{safe_name}"
    out.mkdir(parents=True, exist_ok=True)
    return out


def write_bom(bom: BoMResult, out_dir: Path) -> None:
    detail_path = out_dir / "bom_detail.csv"
    with detail_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=[
            "step_id", "step_name", "material_name", "role",
            "quantity_value", "quantity_unit", "unit_cost_usd", "total_cost_usd", "gmp_step"
        ])
        writer.writeheader()
        for line in bom.material_lines:
            unit = str(line.quantity.units)
            writer.writerow({
                "step_id": line.step_id,
                "step_name": line.step_name,
                "material_name": line.material_name,
                "role": line.role,
                "quantity_value": round(to_float(line.quantity, unit), 4),
                "quantity_unit": unit,
                "unit_cost_usd": round(line.unit_cost, 4),
                "total_cost_usd": round(line.total_cost, 2),
                "gmp_step": line.gmp_step,
            })

    summary = {
        "process_name": bom.process_name,
        "price_list": bom.price_list_name,
        "batch_size_kg": to_float(bom.config.batch_size, "kg"),
        "num_batches": bom.config.num_batches,
        "overall_route_yield_pct": round(bom.overall_route_yield_pct, 2),
        "total_material_cost_usd": round(bom.total_material_cost, 2),
        "total_equipment_cost_usd": round(bom.total_equipment_cost, 2),
        "total_labor_cost_usd": round(bom.total_labor_cost, 2),
        "total_utility_cost_usd": round(bom.total_utility_cost, 2),
        "total_cost_usd": round(bom.total_cost, 2),
        "cost_per_kg_api_usd": round(bom.cost_per_kg_api, 2),
        "currency": bom.currency,
        "steps": [
            {
                "step_id": s.step_id,
                "step_name": s.step_name,
                "yield_pct": s.step_yield_pct,
                "required_input_kg": round(to_float(s.required_input, "kg"), 4),
                "material_cost_usd": round(s.material_cost, 2),
                "equipment_cost_usd": round(s.equipment_cost, 2),
                "labor_cost_usd": round(s.labor_cost, 2),
                "utility_cost_usd": round(s.utility_cost, 2),
                "total_cost_usd": round(s.total_cost, 2),
                "gmp_step": s.gmp_step,
            }
            for s in bom.step_summaries
        ],
    }
    (out_dir / "bom_summary.json").write_text(json.dumps(summary, indent=2))


def write_sweep_results(
    results: list[ScenarioResult],
    elapsed_sec: float,
    out_dir: Path,
) -> None:
    if not results:
        return
    fields = (
        ["scenario_label", "status", "error"]
        + list(results[0].parameter_values.keys())
        + ["cost_per_kg_api", "total_cost", "total_material_cost",
           "total_equipment_cost", "total_labor_cost", "total_utility_cost",
           "overall_route_yield_pct"]
    )
    with (out_dir / "sweep_results.csv").open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for r in results:
            row = {"scenario_label": r.scenario_label, "status": r.status, "error": r.error or ""}
            row.update(r.parameter_values)
            row.update({
                "cost_per_kg_api": round(r.cost_per_kg_api, 2),
                "total_cost": round(r.total_cost, 2),
                "total_material_cost": round(r.total_material_cost, 2),
                "total_equipment_cost": round(r.total_equipment_cost, 2),
                "total_labor_cost": round(r.total_labor_cost, 2),
                "total_utility_cost": round(r.total_utility_cost, 2),
                "overall_route_yield_pct": round(r.overall_route_yield_pct, 2),
            })
            writer.writerow(row)

    success = [r for r in results if r.status == "success"]
    costs = [r.cost_per_kg_api for r in success]
    summary = {
        "n_total": len(results),
        "n_success": len(success),
        "n_failed": len(results) - len(success),
        "elapsed_sec": round(elapsed_sec, 2),
        "throughput_scenarios_per_sec": round(len(results) / elapsed_sec, 1) if elapsed_sec > 0 else 0,
        "cost_per_kg_api": {
            "min": round(min(costs), 2),
            "p10": round(float(np.percentile(costs, 10)), 2),
            "p50": round(float(np.percentile(costs, 50)), 2),
            "p90": round(float(np.percentile(costs, 90)), 2),
            "max": round(max(costs), 2),
        } if costs else {},
    }
    (out_dir / "sweep_summary.json").write_text(json.dumps(summary, indent=2))


def write_mc_results(
    results: list[MCResult],
    percentiles: dict,
    convergence: dict,
    elapsed_sec: float,
    out_dir: Path,
) -> None:
    if results:
        fields = (
            ["iteration", "status", "error"]
            + list(results[0].sampled_inputs.keys())
            + ["cost_per_kg_api", "total_cost", "total_material_cost",
               "total_equipment_cost", "total_labor_cost", "total_utility_cost",
               "overall_route_yield_pct"]
        )
        with (out_dir / "mc_samples.csv").open("w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in results:
                row = {"iteration": r.iteration, "status": r.status, "error": r.error or ""}
                row.update(r.sampled_inputs)
                row.update({
                    "cost_per_kg_api": round(r.cost_per_kg_api, 2),
                    "total_cost": round(r.total_cost, 2),
                    "total_material_cost": round(r.total_material_cost, 2),
                    "total_equipment_cost": round(r.total_equipment_cost, 2),
                    "total_labor_cost": round(r.total_labor_cost, 2),
                    "total_utility_cost": round(r.total_utility_cost, 2),
                    "overall_route_yield_pct": round(r.overall_route_yield_pct, 2),
                })
                writer.writerow(row)

    (out_dir / "mc_percentiles.json").write_text(
        json.dumps({"elapsed_sec": round(elapsed_sec, 2), **percentiles}, indent=2)
    )
    (out_dir / "mc_convergence.json").write_text(json.dumps(convergence, indent=2))


def write_optimisation_result(result: OptimisationResult, out_dir: Path) -> None:
    best = {
        "converged": result.converged,
        "n_evaluations": result.n_evaluations,
        "n_feasible": result.n_feasible,
        "elapsed_sec": round(result.elapsed_sec, 2),
        "best_cost_per_kg_api": round(result.best_cost_per_kg_api, 2),
        "best_overall_yield_pct": round(result.best_overall_yield_pct, 2),
        "best_parameters": {k: round(v, 4) for k, v in result.best_parameter_values.items()},
    }
    (out_dir / "opt_best.json").write_text(json.dumps(best, indent=2))

    with (out_dir / "opt_evaluations.csv").open("w", newline="") as f:
        if result.evaluations:
            fields = (
                ["index", "is_feasible", "objective_value", "cost_per_kg_api",
                 "total_cost", "overall_route_yield_pct"]
                + list(result.evaluations[0].parameter_values.keys())
            )
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for e in result.evaluations:
                row = {
                    "index": e.index,
                    "is_feasible": e.is_feasible,
                    "objective_value": round(e.objective_value, 4),
                    "cost_per_kg_api": round(e.cost_per_kg_api, 2),
                    "total_cost": round(e.total_cost, 2),
                    "overall_route_yield_pct": round(e.overall_route_yield_pct, 2),
                }
                row.update({k: round(v, 4) for k, v in e.parameter_values.items()})
                writer.writerow(row)
