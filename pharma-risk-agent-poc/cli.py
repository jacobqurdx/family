from __future__ import annotations
import os
import time
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, BarColumn, TimeElapsedColumn

from agent.domain import SeverityTier, RunResult
from agent.mrp import assert_mrp_available, load_sensitivity_context
from agent.state import SignalStateStore
from agent.collector import collect_from_files, collect_from_web
from agent.assessor import assess_signal
from agent.actions import execute_actions
from agent.eval import run_evaluation
from agent.reporter import make_output_dir, write_run_summary, write_assessed_signals, write_eval_report
from agent.llm import LLMClient

app = typer.Typer(
    name="agent",
    help="Supply chain risk investigation agent — POC",
    add_completion=False,
)
console = Console()


def _make_client(stub: bool, no_cache: bool) -> tuple[LLMClient, Optional[Path]]:
    use_stub = stub or os.environ.get("AGENT_STUB_LLM", "false").lower() in ("true", "1", "yes")
    cache_dir = None if no_cache or use_stub else Path("cache")
    if use_stub:
        console.print("  [yellow]Mode: STUB (pre-written responses — no API calls)[/yellow]")
        return LLMClient(stub=True, cache_dir=None), None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        console.print(
            "[red]ANTHROPIC_API_KEY not set.[/red]\n"
            "Either set the environment variable or run in stub mode:\n"
            "  export AGENT_STUB_LLM=true\n"
            "  agent evaluate --stub"
        )
        raise typer.Exit(1)
    console.print("  Mode: real Claude API")
    return LLMClient(stub=False, cache_dir=cache_dir), cache_dir


@app.command()
def evaluate(
    corpus_dir: Path = typer.Argument(
        Path("corpus/signals"),
        help="Directory of signal files (.txt or .json)",
    ),
    labels:      Path = typer.Option(Path("corpus/labels.yaml"), help="Ground-truth labels YAML"),
    sensitivity: Path = typer.Option(
        Path("examples/sensitivity_report_wuxi.json"),
        help="MRP sensitivity report JSON",
    ),
    output_dir:  Path = typer.Option(Path("outputs"), help="Output directory"),
    no_cache:    bool = typer.Option(False, help="Disable LLM response cache"),
    stub:        bool = typer.Option(False, "--stub", help="Use stub LLM responses (no API key needed)"),
):
    """
    Evaluate the assessment pipeline against a labelled signal corpus.
    Produces precision/recall/F1 metrics for each assessment step.

    Example (stub mode — no API key required):
      agent evaluate --stub
    """
    assert_mrp_available()
    client, cache_dir = _make_client(stub, no_cache)
    out_dir = make_output_dir(output_dir, "evaluate")

    console.print(f"[bold]Assessment Pipeline Evaluation[/bold]")
    console.print(f"  Corpus: {corpus_dir}  |  Labels: {labels}")
    console.print(f"  Cache: {'disabled' if no_cache or stub else f'enabled (cache/)'}")
    console.print(f"  Output: {out_dir}")

    with Progress(
        SpinnerColumn(), "[progress.description]{task.description}",
        TimeElapsedColumn(), console=console,
    ) as progress:
        task = progress.add_task("Running evaluation...", total=None)
        report = run_evaluation(
            corpus_dir, labels, sensitivity, client,
            cache_dir or Path("cache"), out_dir,
        )
        progress.update(task, completed=True)

    table = Table(title="Evaluation Results")
    table.add_column("Step")
    table.add_column("Precision")
    table.add_column("Recall")
    table.add_column("F1")
    table.add_row(
        "Relevance",
        _fmt(report.relevance_metrics.precision),
        _fmt(report.relevance_metrics.recall),
        _fmt(report.relevance_metrics.f1),
        style="green" if report.relevance_metrics.f1 >= 0.85 else "red",
    )
    table.add_row(
        "Novelty",
        _fmt(report.novelty_metrics.precision),
        _fmt(report.novelty_metrics.recall),
        _fmt(report.novelty_metrics.f1),
        style="green" if report.novelty_metrics.f1 >= 0.80 else "red",
    )
    table.add_row(
        "Severity (macro)",
        _fmt(report.severity_metrics.precision),
        _fmt(report.severity_metrics.recall),
        _fmt(report.severity_metrics.f1),
        style="green" if report.severity_metrics.f1 >= 0.80 else "red",
    )
    console.print(table)
    console.print(
        f"\n  LLM calls: {report.total_llm_calls}  |  "
        f"Est. cost: ${report.total_cost_estimate_usd:.4f}  |  "
        f"Time: {report.elapsed_sec:.1f}s"
    )

    passed = (
        report.relevance_metrics.precision >= 0.85
        and report.relevance_metrics.recall >= 0.85
        and report.novelty_metrics.f1 >= 0.80
        and report.severity_metrics.f1 >= 0.80
    )
    if passed:
        console.print("\n[bold green]✓ POC SUCCESS: Assessment pipeline meets quality thresholds[/bold green]")
    else:
        console.print("\n[bold red]✗ Quality thresholds not met — review worst-case misclassifications[/bold red]")

    if report.worst_cases:
        console.print("\n[bold]Top misclassifications:[/bold]")
        for wc in report.worst_cases[:3]:
            console.print(f"  • {wc['signal_id']}: expected {wc['expected']}, got {wc['actual']}")

    eval_path = write_eval_report(report, out_dir)
    console.print(f"\n[green]Full report:[/green] {eval_path}")


@app.command()
def run(
    sensitivity: Path = typer.Argument(
        ...,
        help="MRP sensitivity report JSON (from mrp risk-sensitivity)",
    ),
    state_file:   Path       = typer.Option(Path("outputs/signal_state.json"), help="Signal state file"),
    process:      Optional[Path] = typer.Option(None, help="MRP process YAML"),
    prices:       Optional[Path] = typer.Option(None, help="MRP prices YAML"),
    risk_profile: Optional[Path] = typer.Option(None, help="MRP risk profile YAML"),
    signal_dir:   Optional[Path] = typer.Option(None, help="Use file-based signals instead of live search"),
    top_n:        int         = typer.Option(5, help="Top N parameters for signal collection"),
    output_dir:   Path        = typer.Option(Path("outputs"), help="Output directory"),
    no_cache:     bool        = typer.Option(False, help="Disable LLM cache"),
    stub:         bool        = typer.Option(False, "--stub", help="Use stub LLM responses (no API key needed)"),
):
    """
    Run the full signal collection → assessment → action loop.

    Example (stub mode — no API key):
      agent run examples/sensitivity_report_wuxi.json \\
        --signal-dir corpus/signals \\
        --process pharma-mrp-poc/examples/linear_5step.yaml \\
        --prices pharma-mrp-poc/examples/prices_q2_2026.yaml \\
        --risk-profile pharma-mrp-poc/examples/risk_profile_wuxi.yaml \\
        --stub
    """
    assert_mrp_available()
    client, cache_dir = _make_client(stub, no_cache)
    out_dir = make_output_dir(output_dir, "run")
    t0 = time.perf_counter()

    context = load_sensitivity_context(sensitivity)
    console.print(f"[bold]Risk Agent Run[/bold]")
    console.print(f"  Scenario: {context.process_name}  |  Base cost: ${context.base_cost_per_kg_api:,.2f}/kg")
    console.print(f"  Priority weights: {len(context.signal_priority_weights)} parameters")
    console.print(
        f"  CN exposure: {context.china_origin_cost_pct:.1f}%  |  "
        f"CDMO exposed: {context.cdmo_exposed_cost_pct:.1f}%"
    )

    state_store = SignalStateStore(state_file)
    if not state_file.exists():
        console.print(
            f"\n[yellow]No state file found at {state_file}. "
            f"Initialising from sensitivity report.[/yellow]"
        )
        state_store.initialise_from_sensitivity_context(context)
    else:
        console.print(f"\n  State loaded from: {state_file}")

    console.print(f"\n[bold]Collecting signals...[/bold]")
    if signal_dir:
        console.print(f"  Mode: file-based ({signal_dir})")
        signals = collect_from_files(signal_dir)
    else:
        console.print(f"  Mode: live web search (top {top_n} parameters)")
        signals = collect_from_web(context.signal_priority_weights, client, top_n_parameters=top_n)
    console.print(f"  Collected: {len(signals)} signals")

    console.print(f"\n[bold]Assessing signals...[/bold]")
    assessed_signals = []
    all_actions = []

    with Progress(
        SpinnerColumn(), "[progress.description]{task.description}",
        BarColumn(), TimeElapsedColumn(), console=console,
    ) as progress:
        task = progress.add_task("Assessing...", total=len(signals))
        for signal in signals:
            assessed = assess_signal(
                signal, context, state_store.all(), client, cache_dir,
            )
            assessed_signals.append(assessed)

            if assessed.novelty and assessed.novelty.is_novel:
                for param in assessed.relevance.relevant_parameters:
                    state_store.apply_novelty_updates(assessed, param)

            if assessed.severity and assessed.severity.severity in (
                SeverityTier.HIGH, SeverityTier.CRITICAL
            ):
                actions = execute_actions(
                    assessed, context, client, out_dir,
                    process, prices, risk_profile, cache_dir,
                )
                all_actions.extend(actions)
            progress.advance(task)

    n_relevant = sum(1 for a in assessed_signals if a.relevance.is_relevant)
    n_novel    = sum(1 for a in assessed_signals if a.novelty and a.novelty.is_novel)
    severity_counts: dict[str, int] = {t.value: 0 for t in SeverityTier}
    for a in assessed_signals:
        if a.severity:
            severity_counts[a.severity.severity.value] += 1

    table = Table(title="Signal Assessment Results")
    table.add_column("Metric")
    table.add_column("Count", justify="right")
    table.add_row("Signals collected", str(len(signals)))
    table.add_row("Relevant", str(n_relevant))
    table.add_row("Novel", str(n_novel))
    table.add_row("ROUTINE",  str(severity_counts["routine"]))
    table.add_row("ELEVATED", str(severity_counts["elevated"]))
    table.add_row("HIGH",     str(severity_counts["high"]),
                  style="yellow" if severity_counts["high"] > 0 else "")
    table.add_row("CRITICAL", str(severity_counts["critical"]),
                  style="red" if severity_counts["critical"] > 0 else "")
    console.print(table)

    if all_actions:
        console.print(f"\n[bold]Actions taken:[/bold]")
        for action in all_actions:
            status = "[green]✓[/green]" if action.success else "[red]✗[/red]"
            console.print(f"  {status} {action.action_type.value}: {action.summary}")
            if action.output_file:
                console.print(f"       → {action.output_file}")
    else:
        console.print(f"\n  No HIGH/CRITICAL signals — no MRP actions triggered")

    elapsed = time.perf_counter() - t0
    console.print(f"\n  Elapsed: {elapsed:.1f}s")

    state_store.save()
    console.print(f"  Signal state updated: {state_file}")

    result = RunResult(
        mode="run",
        started_at=str(t0),
        completed_at=str(time.perf_counter()),
        signals_collected=len(signals),
        signals_relevant=n_relevant,
        signals_novel=n_novel,
        signals_by_severity=severity_counts,
        actions_taken=all_actions,
        output_dir=out_dir,
    )
    write_run_summary(result, out_dir)
    write_assessed_signals(assessed_signals, out_dir)

    if (severity_counts["high"] + severity_counts["critical"]) > 0:
        console.print(
            f"\n[bold yellow]⚠ HIGH/CRITICAL signals detected. "
            f"Review outputs in {out_dir}[/bold yellow]"
        )
    else:
        console.print(f"\n[green]✓ Run complete. No HIGH/CRITICAL signals.[/green]")


def _fmt(v: float) -> str:
    return f"{v:.3f}"


if __name__ == "__main__":
    app()
