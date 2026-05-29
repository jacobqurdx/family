"""
CLI commands for evaluation.
"""
from __future__ import annotations
import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group("evaluate")
def evaluate_group():
    """Evaluation commands."""
    pass


@evaluate_group.command("session")
@click.argument("session_id")
def evaluate_session(session_id: str):
    """Print metrics for a single SESSION_ID."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    from workflow.session import WorkflowSessionManager
    from workflow.evaluation import WorkflowEvaluator

    mgr = WorkflowSessionManager()
    session = mgr.load(session_id)
    evaluator = WorkflowEvaluator()
    metrics = evaluator.evaluate(session)

    console.print(f"\n[bold]Metrics for session {session_id}[/bold]")
    console.print(f"  Mode: {metrics.simulation_mode}")
    console.print(f"  Total sections: {metrics.total_sections}")
    console.print(f"  Approved: {metrics.approved_count}")
    console.print(f"  Revised: {metrics.revised_count}")
    console.print(f"  Escalated: {metrics.escalated_count}")
    console.print(f"  AI time (sec): {metrics.total_ai_time_seconds:.1f}")
    console.print(f"  Baseline (min): {metrics.total_baseline_minutes:.1f}")
    console.print(f"  Time savings: {metrics.time_savings_pct:.1f}%")
    console.print(f"  Avg survey score: {metrics.avg_survey_score}")
    console.print(f"  Adoption threshold met: {metrics.adoption_threshold_met}")


@evaluate_group.command("all")
def evaluate_all():
    """Compare all sessions, grouped by simulation mode."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    from workflow.session import WorkflowSessionManager
    from workflow.evaluation import WorkflowEvaluator

    mgr = WorkflowSessionManager()
    sessions = mgr.list_sessions()
    evaluator = WorkflowEvaluator()

    if not sessions:
        console.print("[yellow]No workflow sessions found.[/yellow]")
        return

    table = Table(title="All Session Metrics")
    table.add_column("Session ID")
    table.add_column("Mode")
    table.add_column("Sections")
    table.add_column("Approved")
    table.add_column("Time Savings %")
    table.add_column("Avg Survey")
    table.add_column("Adoption")

    for session in sessions:
        metrics = evaluator.evaluate(session)
        table.add_row(
            metrics.session_id,
            metrics.simulation_mode,
            str(metrics.total_sections),
            str(metrics.approved_count),
            f"{metrics.time_savings_pct:.1f}%",
            str(metrics.avg_survey_score) if metrics.avg_survey_score else "N/A",
            "YES" if metrics.adoption_threshold_met else "NO",
        )

    console.print(table)
