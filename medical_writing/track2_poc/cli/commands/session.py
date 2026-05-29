"""
CLI commands for workflow sessions.
"""
from __future__ import annotations
import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group("session")
def session_group():
    """Workflow session management commands."""
    pass


@session_group.command("start")
@click.argument("writer_id")
@click.argument("assignment_id")
@click.option("--twin-id", default="synth_phase2_trial", help="Digital twin ID")
@click.option("--mode", default="high_quality", help="Simulation mode: high_quality or low_quality")
def session_start(writer_id: str, assignment_id: str, twin_id: str, mode: str):
    """Start a new workflow session for WRITER_ID with ASSIGNMENT_ID."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    from workflow.session import WorkflowSessionManager

    mgr = WorkflowSessionManager()
    session = mgr.create(writer_id, assignment_id, twin_id, mode)
    console.print(f"[green]Created workflow session: {session.session_id}[/green]")
    console.print(f"  Writer: {session.writer_id}")
    console.print(f"  Assignment: {session.assignment_id}")
    console.print(f"  Mode: {session.simulation_mode}")


@session_group.command("list")
def session_list():
    """List all workflow sessions."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    from workflow.session import WorkflowSessionManager

    mgr = WorkflowSessionManager()
    sessions = mgr.list_sessions()

    if not sessions:
        console.print("[yellow]No workflow sessions found.[/yellow]")
        return

    table = Table(title="Workflow Sessions")
    table.add_column("Session ID")
    table.add_column("Writer")
    table.add_column("Assignment")
    table.add_column("Mode")
    table.add_column("Status")
    table.add_column("Sections")

    for s in sessions:
        table.add_row(
            s.session_id,
            s.writer_id,
            s.assignment_id,
            s.simulation_mode,
            s.status,
            str(len(s.adjudication_records)),
        )
    console.print(table)


@session_group.command("status")
@click.argument("session_id")
def session_status(session_id: str):
    """Show status of SESSION_ID."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    from workflow.session import WorkflowSessionManager

    mgr = WorkflowSessionManager()
    session = mgr.load(session_id)
    summary = mgr.get_summary(session)

    console.print(f"\n[bold]Session {session_id}[/bold]")
    for k, v in summary.items():
        console.print(f"  {k}: {v}")
