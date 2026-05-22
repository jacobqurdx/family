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
    write_plant_cogs, write_network_analysis,
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


@app.command()
def plant_cogs(
    process:        Path  = typer.Argument(..., help="Process YAML file"),
    prices:         Path  = typer.Argument(..., help="Price list YAML file"),
    plant:          Path  = typer.Argument(..., help="Plant definition YAML file"),
    year:           int   = typer.Option(2026, help="Analysis year"),
    batches:        int   = typer.Option(5, help="Number of batches produced in the year"),
    batch_size_kg:  float = typer.Option(50.0, help="Batch size in kg API"),
    year_index:     int   = typer.Option(0, help="0-based year index into asset depreciation schedule"),
    output_dir:     Path  = typer.Option(Path("outputs"), help="Output directory"),
):
    """
    Calculate COGS for a single plant in a given year: variable BoM costs
    overlaid with fixed CapEx costs (depreciation + maintenance).

    Example:
      mrp plant-cogs examples/linear_5step.yaml examples/prices_q2_2026.yaml examples/plant_site_a.yaml --year 2027 --batches 6
    """
    from mrp.loader import load_plant
    from mrp.capex import overlay_capex

    graph  = load_process(process)
    pl     = load_price_list(prices)
    plt    = load_plant(plant)
    config = ProcessConfig(
        batch_size=ureg.Quantity(batch_size_kg, "kg"),
        num_batches=batches,
    )

    _warn_unpriced_materials(graph, pl)

    console.print(f"[bold]Plant COGS:[/bold] {plt.name}")
    console.print(f"  Year: {year}  |  Batches: {batches}  |  Batch size: {batch_size_kg} kg")
    console.print(f"  Plant capacity: {plt.annual_capacity_kg_api} kg/yr nameplate")
    console.print(f"  Total plant CapEx: ${plt.total_capex():,.0f}")

    bom = calculate_bom(graph, config, pl)
    cx  = overlay_capex(bom, plt, analysis_year=year, year_index=year_index)

    total_kg = batches * batch_size_kg
    table = Table(title=f"COGS Summary — {plt.name} — {year}")
    table.add_column("Cost Component", style="cyan")
    table.add_column("Amount", justify="right")
    table.add_column("Per kg API", justify="right")

    table.add_row("Materials",
                  f"${bom.total_material_cost:,.0f}", f"${bom.total_material_cost/total_kg:,.2f}")
    table.add_row(f"Labor ({cx.active_band_label})",
                  f"${cx.adjusted_labor_cost:,.0f}", f"${cx.adjusted_labor_cost/total_kg:,.2f}")
    table.add_row(f"Utilities ({cx.active_band_label})",
                  f"${cx.adjusted_utility_cost:,.0f}", f"${cx.adjusted_utility_cost/total_kg:,.2f}")
    table.add_row("Equipment",
                  f"${bom.total_equipment_cost:,.0f}", f"${bom.total_equipment_cost/total_kg:,.2f}")
    table.add_row("Total Variable",
                  f"${cx.total_variable_cost:,.0f}", f"${cx.variable_cost_per_kg_api:,.2f}",
                  style="bold")
    table.add_row("Annual Depreciation",
                  f"${cx.total_depreciation_cost:,.0f}",
                  f"${cx.total_depreciation_cost/total_kg:,.2f}")
    table.add_row("Annual Maintenance",
                  f"${cx.total_maintenance_cost:,.0f}",
                  f"${cx.total_maintenance_cost/total_kg:,.2f}")
    table.add_row("Total Fixed",
                  f"${cx.total_fixed_cost:,.0f}", f"${cx.fixed_cost_per_kg_api:,.2f}",
                  style="bold")
    table.add_row("TOTAL COGS",
                  f"${cx.total_cogs:,.0f}", f"${cx.cogs_per_kg_api:,.2f}",
                  style="bold green")
    if cx.breakeven_kg_api:
        table.add_row("Breakeven Volume", f"{cx.breakeven_kg_api:,.1f} kg", "—")
    console.print(table)
    console.print(f"\n  Utilisation: {cx.utilisation_pct:.1f}%  ({cx.active_band_label})")

    out = make_output_dir(output_dir, f"plant_cogs_{plt.name.replace(' ', '_')[:20]}_{year}")
    write_plant_cogs(cx, plt, out)
    console.print(f"\n[green]Outputs written to:[/green] {out}")


@app.command()
def network_analyse(
    process:       Path  = typer.Argument(..., help="Process YAML file"),
    prices:        Path  = typer.Argument(..., help="Price list YAML file"),
    network_file:  Path  = typer.Argument(..., help="Plant network YAML file"),
    batch_size_kg: float = typer.Option(50.0, help="Batch size in kg API"),
    output_dir:    Path  = typer.Option(Path("outputs"), help="Output directory"),
):
    """
    Run full multi-year COGS analysis across a plant network.

    Example:
      mrp network-analyse examples/linear_5step.yaml examples/prices_q2_2026.yaml examples/network_commercial.yaml
    """
    from mrp.loader import load_network
    from mrp.network import analyse_network

    graph  = load_process(process)
    pl     = load_price_list(prices)
    net, plant_map = load_network(network_file, network_file.parent.parent)
    config = ProcessConfig(batch_size=ureg.Quantity(batch_size_kg, "kg"), num_batches=1)

    data   = __import__("yaml").safe_load(network_file.read_text())["network"]
    start  = int(data.get("analysis_start_year", 2025))
    end    = int(data.get("analysis_end_year", 2030))
    default_kg = float(data.get("default_volume_kg_api_annual", 800.0))
    years  = list(range(start, end + 1))

    total_capex = sum(p.total_capex() for p in plant_map.values())
    console.print(f"[bold]Network Analysis:[/bold] {net.name}")
    console.print(f"  Analysis period: {start}–{end}  |  Plants: {len(plant_map)}")
    console.print(f"  Total CapEx: ${total_capex:,.0f}")

    result = analyse_network(
        memberships=net.plants,
        plant_map=plant_map,
        volume_targets=net.volume_targets,
        default_volume_kg=default_kg,
        years=years,
        graph=graph,
        config=config,
        prices=pl,
    )
    result.network_name = net.name
    result.total_network_capex = total_capex

    table = Table(title=f"Network COGS by Year — {net.name}")
    table.add_column("Year")
    table.add_column("Target kg", justify="right")
    table.add_column("Variable $", justify="right")
    table.add_column("Fixed $", justify="right")
    table.add_column("Total COGS", justify="right")
    table.add_column("COGS/kg", justify="right", style="bold")
    table.add_column("Gap kg", justify="right")

    for ys in result.year_summaries:
        gap_str = (f"[red]{ys.volume_gap_kg:+.0f}[/red]" if ys.volume_gap_kg > 0.5
                   else f"[green]{ys.volume_gap_kg:+.0f}[/green]")
        table.add_row(
            str(ys.year),
            f"{ys.total_volume_kg:,.0f}",
            f"${ys.total_variable_cost:,.0f}",
            f"${ys.total_fixed_cost:,.0f}",
            f"${ys.total_cogs:,.0f}",
            f"${ys.network_cogs_per_kg_api:,.2f}",
            gap_str,
        )
    console.print(table)

    out = make_output_dir(output_dir, f"network_{net.name.replace(' ', '_')[:20]}")
    write_network_analysis(result, out)
    console.print(f"\n[green]Outputs written to:[/green] {out}")


@app.command()
def network_minimise(
    network_file: Path  = typer.Argument(..., help="Plant network YAML file"),
    year:         int   = typer.Option(..., help="Target year for volume requirement"),
    max_util:     float = typer.Option(90.0, help="Maximum utilisation % allowed"),
    output_dir:   Path  = typer.Option(Path("outputs"), help="Output directory"),
):
    """
    Find the minimum-CapEx set of plants that meets the volume target for a given year.

    Example:
      mrp network-minimise examples/network_commercial.yaml --year 2028 --max-util 85
    """
    from mrp.loader import load_network
    from mrp.network import (
        minimum_network_configuration, commissioned_plants_for_year,
        volume_target_for_year,
    )
    import json, dataclasses

    net, plant_map = load_network(network_file, network_file.parent.parent)
    data       = __import__("yaml").safe_load(network_file.read_text())["network"]
    default_kg = float(data.get("default_volume_kg_api_annual", 800.0))

    target_kg = volume_target_for_year(net.volume_targets, year, default_kg)
    required_capacity = target_kg / (max_util / 100.0)

    active = commissioned_plants_for_year(net.plants, plant_map, year)
    active_plants = [p for p, _ in active]

    console.print(f"[bold]Minimum Network Configuration:[/bold] {net.name}")
    console.print(f"  Target year: {year}  |  Volume target: {target_kg:,.0f} kg"
                  f"  |  Max utilisation: {max_util}%")
    console.print(f"  Required capacity: {required_capacity:,.0f} kg/yr"
                  f"  |  Commissioned plants: {len(active_plants)}")

    result = minimum_network_configuration(active_plants, required_capacity)

    if result.meets_target:
        console.print(f"\n[green]✓ Target can be met[/green] with "
                      f"{len(result.best_plant_ids)} plant(s):")
    else:
        console.print(f"\n[red]✗ Target CANNOT be met[/red] with available commissioned plants:")
    for name in result.best_plant_names:
        console.print(f"  • {name}")

    table = Table(title="Minimum Configuration Result")
    table.add_column("Metric")
    table.add_column("Value", justify="right")
    table.add_row("Plants selected", str(len(result.best_plant_ids)))
    table.add_row("Total CapEx", f"${result.total_capex:,.0f}")
    table.add_row("Total capacity", f"{result.total_capacity_kg:,.0f} kg/yr")
    table.add_row("Volume target", f"{result.required_capacity_kg:,.0f} kg")
    table.add_row("Meets target", "✓ Yes" if result.meets_target else "✗ No")
    console.print(table)

    out = make_output_dir(output_dir, f"min_config_{year}")
    (out / "minimum_config.json").write_text(
        json.dumps(dataclasses.asdict(result), indent=2)
    )
    console.print(f"\n[green]Outputs written to:[/green] {out}")


@app.command()
def risk_sensitivity(
    process:       Path  = typer.Argument(..., help="Process YAML file"),
    prices:        Path  = typer.Argument(..., help="Price list YAML file"),
    risk_profile:  Path  = typer.Argument(..., help="Risk profile YAML file"),
    batch_size_kg: float = typer.Option(50.0, help="Batch size in kg API"),
    num_batches:   int   = typer.Option(1,    help="Number of batches"),
    output_dir:    Path  = typer.Option(Path("outputs"), help="Output directory"),
):
    """
    Generate a supply chain risk sensitivity report.

    Runs one-at-a-time sensitivity for all material prices and step yields,
    computes exposure metrics, tariff sweep, and CDMO removal scenarios.
    Writes sensitivity_report.json for use by the risk agent POC.

    Example:
      mrp risk-sensitivity examples/linear_5step.yaml examples/prices_q2_2026.yaml \\
        examples/risk_profile_wuxi.yaml
    """
    from mrp.loader import load_risk_profile as _load_risk_profile
    from mrp.risk import generate_sensitivity_report
    import json, dataclasses

    graph   = load_process(process)
    pl      = load_price_list(prices)
    profile = _load_risk_profile(risk_profile)
    config  = ProcessConfig(
        batch_size=ureg.Quantity(batch_size_kg, "kg"),
        num_batches=num_batches,
    )

    _warn_unpriced_materials(graph, pl)
    console.print(f"[bold]Risk Sensitivity Analysis:[/bold] {graph.name}")
    console.print(f"  Batch: {batch_size_kg} kg × {num_batches}  |  CDMO nodes: {len(profile.cdmo_nodes)}")
    console.print(f"  Tariff sweep rates: {profile.tariff_sweep_rates}")

    bom    = calculate_bom(graph, config, pl)
    report = generate_sensitivity_report(graph, config, pl, bom, profile)

    console.print(f"\n  Base cost/kg API: ${report.base_cost_per_kg_api:,.2f}")
    console.print(f"  CN origin: {report.exposure_summary.china_origin_cost_pct:.1f}%  |  "
                  f"Single-source: {report.exposure_summary.single_source_cost_pct:.1f}%  |  "
                  f"CDMO exposed: {report.exposure_summary.cdmo_exposed_cost_pct:.1f}%")
    console.print(f"\n  Top 5 sensitivity weights:")
    for w in report.signal_priority_weights[:5]:
        console.print(f"    #{w.rank} {w.parameter}: {w.sensitivity_cost_per_unit:+.3f} $/kg per 1%")

    out = make_output_dir(output_dir, f"risk_sensitivity_{graph.name.replace(' ','_')[:20]}")
    report_dict = report.to_dict()
    (out / "sensitivity_report.json").write_text(json.dumps(report_dict, indent=2))
    console.print(f"\n[green]Sensitivity report written to:[/green] {out / 'sensitivity_report.json'}")


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
