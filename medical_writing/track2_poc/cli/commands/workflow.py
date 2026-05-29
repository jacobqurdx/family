"""
CLI commands for workflow processing.
"""
from __future__ import annotations
import click
from rich.console import Console
from rich.panel import Panel

console = Console()


@click.group("workflow")
def workflow_group():
    """Workflow processing commands."""
    pass


@workflow_group.command("step")
@click.argument("session_id")
@click.argument("section_id")
def workflow_step(session_id: str, section_id: str):
    """Process one section: load simulated output and record adjudication."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    from workflow.session import WorkflowSessionManager
    from workflow.simulator import OutputSimulator
    from workflow.adjudication import AdjudicationManager
    from workflow.models import AdjudicationDecision

    mgr = WorkflowSessionManager()
    session = mgr.load(session_id)

    sim = OutputSimulator(mode=session.simulation_mode)
    output = sim.load_section(section_id)

    console.print(Panel(output.prose, title=f"[bold]{output.section_title}[/bold]", expand=False))
    console.print(f"[dim]Confidence: {output.simulated_confidence:.0%}[/dim]")

    decision_str = click.prompt(
        "Decision [approve/revise/escalate]",
        type=click.Choice(["approve", "revise", "escalate"]),
        default="approve",
    )
    decision_map = {
        "approve": AdjudicationDecision.APPROVED,
        "revise": AdjudicationDecision.REVISED,
        "escalate": AdjudicationDecision.ESCALATED,
    }
    decision = decision_map[decision_str]

    final_prose = output.prose
    revision_notes = None
    if decision == AdjudicationDecision.REVISED:
        revision_notes = click.prompt("Revision notes")
        final_prose = click.prompt("Enter revised prose (or press Enter to keep original)", default=output.prose)

    adj_mgr = AdjudicationManager()
    record = adj_mgr.record_decision(
        session=session,
        section_id=section_id,
        section_title=output.section_title,
        decision=decision,
        simulated_prose=output.prose,
        final_prose=final_prose,
        revision_notes=revision_notes,
    )

    mgr.save(session)
    console.print(f"[green]Recorded {decision.value} for {section_id}[/green]")


@workflow_group.command("complete")
@click.argument("session_id")
def workflow_complete(session_id: str):
    """Mark session complete and run evaluation."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    from workflow.session import WorkflowSessionManager
    from workflow.evaluation import WorkflowEvaluator

    mgr = WorkflowSessionManager()
    session = mgr.load(session_id)
    mgr.complete(session)

    evaluator = WorkflowEvaluator()
    metrics = evaluator.evaluate(session)

    console.print(f"\n[bold green]Session {session_id} completed.[/bold green]")
    console.print(f"  Sections: {metrics.total_sections}")
    console.print(f"  Approved: {metrics.approved_count} | Revised: {metrics.revised_count} | Escalated: {metrics.escalated_count}")
    console.print(f"  Time savings: {metrics.time_savings_pct:.1f}%")
    console.print(f"  Adoption threshold met: {metrics.adoption_threshold_met}")
