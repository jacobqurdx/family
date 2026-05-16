import typer
from pathlib import Path
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn
from rich.table import Table
from mrp.loader import load_process, load_price_list, load_sweep, load_mc_definition
from mrp.engine import calculate_bom
from mrp.sweep import run_sweep
from mrp.montecarlo import run_monte_carlo, compute_percentiles, check_convergence
from mrp.optimisation import (
    OptimisationConfig, OptimisationParameter, OptimisationConstraint,
    run_optimisation, validate_all_constraints,
)
from mrp.reporter import (
    make_output_dir, write_bom, write_sweep_results,
    write_mc_results, write_optimisation_result,
)
from mrp.domain import ProcessConfig, ParameterType
from mrp.units import ureg

app = typer.Typer(
    name="mrp",
    help="Pharma MRP simulation engine — technical POC",
    add_completion=False,
)
console = Console()


@app.command()
def calculate(
    process: Path = typer.Argument(..., help="Path to process YAML file"),
    prices:  Path = typer.Argument(..., help="Path to price list YAML file"),
    batch_size_kg:  float = typer.Option(50.0,  help="Target batch size in kg"),
    num_batches:    int   = typer.Option(1,     help="Number of batches in campaign"),
    output_dir:     Path  = typer.Option(Path("outputs"), help="Output directory"),
):
    """Calculate a single BoM for a process + price list."""
    graph  = load_process(process)
    pl     = load_price_list(prices)
    config = ProcessConfig(
        batch_size=ureg.Quantity(batch_size_kg, "kg"),
        num_batches=num_batches,
    )

    _warn_unpriced_materials(graph, pl)

    console.print(f"[bold]Calculating BoM:[/bold] {graph.name}")
    console.print(f"  Batch size: {batch_size_kg} kg × {num_batches} batches")
    console.print(f"  Convergent route: {graph.is_convergent()}")

    bom = calculate_bom(graph, config, pl)

    table = Table(title=f"BoM Summary — {graph.name}")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_row("Overall route yield", f"{bom.overall_route_yield_pct:.1f}%")
    table.add_row("Total material cost", f"${bom.total_material_cost:,.0f}")
    table.add_row("Total equipment cost", f"${bom.total_equipment_cost:,.0f}")
    table.add_row("Total labor cost", f"${bom.total_labor_cost:,.0f}")
    table.add_row("Total utility cost", f"${bom.total_utility_cost:,.0f}")
    table.add_row("Total campaign cost", f"${bom.total_cost:,.0f}", style="bold")
    table.add_row("Cost per kg API", f"${bom.cost_per_kg_api:,.2f}", style="bold green")
    console.print(table)

    out = make_output_dir(output_dir, graph.name)
    write_bom(bom, out)
    console.print(f"\n[green]Outputs written to:[/green] {out}")


@app.command()
def sweep(
    process:    Path  = typer.Argument(..., help="Process YAML file"),
    prices:     Path  = typer.Argument(..., help="Price list YAML file"),
    sweep_file: Path  = typer.Argument(..., help="Sweep definition YAML file"),
    workers:    int   = typer.Option(0, help="Parallel workers (0 = auto)"),
    output_dir: Path  = typer.Option(Path("outputs"), help="Output directory"),
):
    """Run a parametric sweep over a process."""
    graph  = load_process(process)
    pl     = load_price_list(prices)
    config = ProcessConfig(batch_size=ureg.Quantity(50.0, "kg"), num_batches=5)
    defn   = load_sweep(sweep_file, config)

    _warn_unpriced_materials(graph, pl)

    from mrp.sweep import expand_sweep
    combos = expand_sweep(defn)
    console.print(f"[bold]Parametric sweep:[/bold] {defn.name}")
    console.print(f"  Mode: {defn.mode.value}  |  Scenarios: {len(combos)}")
    console.print(f"  Workers: {workers or 'auto'}")

    n_workers = workers if workers > 0 else None

    with Progress(
        SpinnerColumn(), "[progress.description]{task.description}",
        BarColumn(), TaskProgressColumn(), TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Running scenarios...", total=len(combos))

        def update(done, total):
            progress.update(task, completed=done)

        results, elapsed = run_sweep(graph, config, pl, defn, workers=n_workers, progress_callback=update)

    success = sum(1 for r in results if r.status == "success")
    costs = [r.cost_per_kg_api for r in results if r.status == "success"]

    console.print(f"\n[bold]Sweep complete[/bold] — {elapsed:.1f}s — "
                  f"{len(combos)/elapsed:.0f} scenarios/sec")
    console.print(f"  Successful: {success}/{len(results)}")
    if costs:
        import numpy as np
        console.print(f"  Cost/kg API: min=${min(costs):,.0f}  p50=${np.percentile(costs,50):,.0f}"
                      f"  max=${max(costs):,.0f}")

    out = make_output_dir(output_dir, defn.name)
    write_sweep_results(results, elapsed, out)
    console.print(f"\n[green]Outputs written to:[/green] {out}")


@app.command()
def montecarlo(
    process:    Path  = typer.Argument(..., help="Process YAML file"),
    prices:     Path  = typer.Argument(..., help="Price list YAML file"),
    mc_file:    Path  = typer.Argument(..., help="Monte Carlo definition YAML file"),
    workers:    int   = typer.Option(0, help="Parallel workers (0 = auto)"),
    output_dir: Path  = typer.Option(Path("outputs"), help="Output directory"),
):
    """Run a Monte Carlo simulation over a process."""
    graph = load_process(process)
    pl    = load_price_list(prices)
    defn  = load_mc_definition(mc_file)

    _warn_unpriced_materials(graph, pl)

    console.print(f"[bold]Monte Carlo:[/bold] {defn.name}")
    console.print(f"  Iterations: {defn.n_iterations:,}  |  Parameters: {len(defn.distributions)}")
    console.print(f"  Correlations: {len(defn.correlations)}")
    console.print(f"  Seed: {defn.random_seed or 'random'}")

    n_workers = workers if workers > 0 else None

    with Progress(
        SpinnerColumn(), "[progress.description]{task.description}",
        BarColumn(), TaskProgressColumn(), TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Running iterations...", total=defn.n_iterations)

        def update(done, total):
            progress.update(task, completed=done)

        results, elapsed = run_monte_carlo(
            graph, defn.base_config, pl, defn,
            workers=n_workers, progress_callback=update,
        )

    pcts  = compute_percentiles(results, "cost_per_kg_api")
    conv  = check_convergence(results)

    table = Table(title="Monte Carlo Results — cost_per_kg_api")
    table.add_column("Percentile"); table.add_column("USD/kg", justify="right")
    for label, key in [("P5","p5"),("P10","p10"),("P25","p25"),("Median","p50"),
                        ("P75","p75"),("P90","p90"),("P95","p95")]:
        table.add_row(label, f"${pcts.get(key, 0):,.0f}")
    table.add_row("Mean", f"${pcts.get('mean', 0):,.0f}", style="bold")
    table.add_row("Std Dev", f"${pcts.get('std', 0):,.0f}")
    console.print(table)

    console.print(f"\n[bold]Performance:[/bold] {elapsed:.1f}s — "
                  f"{defn.n_iterations/elapsed:.0f} iterations/sec")
    conv_str = (f"at iteration {conv['at_iteration']}" if conv.get("converged")
                else "not achieved within run")
    console.print(f"[bold]Convergence:[/bold] {conv_str}")

    out = make_output_dir(output_dir, defn.name)
    write_mc_results(results, pcts, conv, elapsed, out)
    console.print(f"\n[green]Outputs written to:[/green] {out}")


@app.command()
def optimise(
    process:    Path  = typer.Argument(..., help="Process YAML file"),
    prices:     Path  = typer.Argument(..., help="Price list YAML file"),
    output_dir: Path  = typer.Option(Path("outputs"), help="Output directory"),
    max_evals:  int   = typer.Option(500, help="Maximum BoM evaluations"),
    objective:  str   = typer.Option("min_cost_per_kg", help="min_cost_per_kg | min_total_cost | max_yield"),
    seed:       int   = typer.Option(42, help="Random seed for reproducibility"),
):
    """Run differential evolution optimisation over step yields and material prices."""
    graph = load_process(process)
    pl    = load_price_list(prices)
    config = ProcessConfig(batch_size=ureg.Quantity(50.0, "kg"), num_batches=5)

    gmp_steps = [sid for sid, s in graph.steps.items() if s.gmp_step]
    params = [
        OptimisationParameter(
            param_type=ParameterType.STEP_YIELD,
            target_id=sid,
            label=f"{graph.steps[sid].name} Yield",
            lower_bound=50.0,
            upper_bound=99.0,
            baseline=graph.steps[sid].step_yield_pct,
            unit="%",
        )
        for sid in gmp_steps
    ] + [
        OptimisationParameter(
            param_type=ParameterType.MATERIAL_PRICE,
            target_id="Starting Material A",
            label="SM-A Price",
            lower_bound=400.0,
            upper_bound=1500.0,
            baseline=820.0,
            unit="USD/kg",
        ),
    ]

    constraints = [
        OptimisationConstraint(
            metric="overall_route_yield_pct",
            operator=">=",
            threshold=35.0,
            description="Minimum acceptable route yield",
        ),
    ]

    errors = validate_all_constraints(constraints)
    if errors:
        for e in errors:
            console.print(f"[red]Constraint error:[/red] {e}")
        raise typer.Exit(1)

    opt_config = OptimisationConfig(
        objective=objective,
        parameters=params,
        constraints=constraints,
        method="differential_evolution",
        max_evaluations=max_evals,
        seed=seed,
    )

    console.print(f"[bold]Optimisation:[/bold] {objective}")
    console.print(f"  Parameters: {len(params)}  |  Constraints: {len(constraints)}")
    console.print(f"  Max evaluations: {max_evals}  |  Method: differential_evolution")

    with Progress(
        SpinnerColumn(), "[progress.description]{task.description}",
        BarColumn(), TaskProgressColumn(), TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Optimising...", total=max_evals)
        result = run_optimisation(
            graph, config, pl, opt_config,
            progress_callback=lambda done, total: progress.update(task, completed=done),
        )

    console.print(f"\n[bold]Result:[/bold] {'Converged ✓' if result.converged else 'Did not converge'}")
    console.print(f"  Best cost/kg API: [bold green]${result.best_cost_per_kg_api:,.2f}[/bold green]")
    console.print(f"  Best route yield: {result.best_overall_yield_pct:.1f}%")
    console.print(f"  Evaluations used: {result.n_evaluations} ({result.n_feasible} feasible)")
    console.print(f"  Elapsed: {result.elapsed_sec:.1f}s")
    console.print("\n  [bold]Best parameters:[/bold]")
    for k, v in result.best_parameter_values.items():
        console.print(f"    {k}: {v:.3f}")

    out = make_output_dir(output_dir, f"optimisation_{objective}")
    write_optimisation_result(result, out)
    console.print(f"\n[green]Outputs written to:[/green] {out}")


def _warn_unpriced_materials(graph, pl) -> None:
    for step in graph.steps.values():
        for sm in step.materials:
            if pl.get_material_price(sm.material.name) is None:
                console.print(
                    f"[yellow]WARNING:[/yellow] No price found for '{sm.material.name}' "
                    f"(step '{step.name}') — will be costed at $0"
                )


if __name__ == "__main__":
    app()
