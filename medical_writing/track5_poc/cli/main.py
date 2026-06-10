"""
Track 5 CLI — Labeling Workflow Integration.

Command groups: ci · map · session · evaluate
Sessions and message maps persist to disk so commands chain across invocations.
"""
import uuid
import datetime

import click
from rich.console import Console
from rich.table import Table

import config

console = Console()


def _sm():
    from workflow.session import SessionManager
    return SessionManager()


@click.group()
def cli():
    """Structure Therapeutics — Labeling Workflow Integration POC (Track 5)"""
    pass


# ── ci ──────────────────────────────────────────────────────────────────────
@cli.group()
def ci():
    """Competitive intelligence twin commands"""
    pass


@ci.command("show")
@click.argument("ci_twin_id", default="ci_glp1_obesity_fda")
def ci_show(ci_twin_id):
    """Show the CI twin's approved claims grouped by label section."""
    from labeling.ci_twin import CITwinManager
    twin = CITwinManager().load(ci_twin_id)
    console.print(f"[bold]{twin.ci_twin_id}[/bold] — {twin.drug_class} / {twin.indication_class} "
                  f"({twin.regulatory_body}) · {len(twin.approved_claims)} claims")
    table = Table(title="Approved Claims")
    table.add_column("ID", style="cyan")
    table.add_column("Drug")
    table.add_column("Section")
    table.add_column("Approved")
    for c in twin.approved_claims:
        table.add_row(c.claim_id, c.drug_name, c.label_section, c.approval_date)
    console.print(table)


@ci.command("query")
@click.argument("section")
@click.option("--ci-twin", default="ci_glp1_obesity_fda")
def ci_query(section, ci_twin):
    """Show approved claims for a label section (e.g. 'Indications and Usage')."""
    from labeling.ci_twin import CITwinManager
    mgr = CITwinManager()
    twin = mgr.load(ci_twin)
    claims = mgr.get_claims_for_section(twin, section)
    if not claims:
        console.print(f"[yellow]No approved claims for section '{section}'.[/yellow]")
        return
    for c in claims:
        console.print(f"[cyan]{c.claim_id}[/cyan] [bold]{c.drug_name}[/bold]")
        console.print(f"  {c.claim_text}")
        if c.quantitative_threshold:
            console.print(f"  [dim]threshold: {c.quantitative_threshold}[/dim]")


@ci.command("compare")
@click.option("--ci-twin", default="ci_glp1_obesity_fda")
def ci_compare(ci_twin):
    """Section coverage across competitors."""
    from labeling.ci_twin import CITwinManager
    twin = CITwinManager().load(ci_twin)
    by_section = {}
    for c in twin.approved_claims:
        by_section.setdefault(c.label_section, set()).add(c.drug_name)
    table = Table(title="Competitive Coverage by Section")
    table.add_column("Section", style="cyan")
    table.add_column("Drugs with approved language")
    for sec, drugs in by_section.items():
        table.add_row(sec, ", ".join(sorted(drugs)))
    console.print(table)


# ── map ──────────────────────────────────────────────────────────────────────
@cli.group()
def map():
    """Message map commands"""
    pass


@map.command("generate")
@click.option("--ci-twin", default="ci_glp1_obesity_fda")
@click.option("--content", default="molecule_aleniglipron")
def map_generate(ci_twin, content):
    """Generate a message map from the CI twin + content twin and persist it."""
    from labeling.ci_twin import CITwinManager
    from labeling.message_map_generator import MessageMapGenerator
    from labeling.message_map import MessageMapManager
    from core.twin import DigitalTwin
    twin = CITwinManager().load(ci_twin)
    ct = DigitalTwin.load(content)
    m = MessageMapGenerator().generate(twin, ct)
    MessageMapManager().save(m)
    console.print(f"[green]Map {m.map_id} generated (mode={config.SIMULATION_MODE}):[/green] "
                  f"{len(m.claims)} claims | high={m.high_achievability_count} "
                  f"med={m.medium_achievability_count} low={m.low_achievability_count} "
                  f"gaps={len(m.gaps_detected)}")


@map.command("show")
@click.argument("map_id")
def map_show(map_id):
    """Show a message map's claims and achievability."""
    from labeling.message_map import MessageMapManager
    m = MessageMapManager().load(map_id)
    table = Table(title=f"Message Map {m.map_id} ({'locked '+m.version if m.locked else 'draft'})")
    table.add_column("Claim", style="cyan")
    table.add_column("Section")
    table.add_column("Achiev")
    table.add_column("Gap")
    table.add_column("Precedent")
    for c in m.claims:
        table.add_row(c.claim_id, c.label_section, c.achievability.value,
                      "yes" if c.is_gap else "", ", ".join(c.regulatory_precedent_ids) or "—")
    console.print(table)


@map.command("qc")
@click.argument("map_id")
def map_qc(map_id):
    """Run the labeling QC checklist against a message map."""
    from labeling.message_map import MessageMapManager
    from labeling.labeling_qc import LabelingQCValidator
    m = MessageMapManager().load(map_id)
    findings = LabelingQCValidator().validate(m)
    blocking = [f for f in findings if f.severity == "blocking"]
    status = "[red]FAILED[/red]" if blocking else "[green]PASSED[/green]"
    console.print(f"QC: {status} ({len(findings)} findings, {len(blocking)} blocking)")
    for f in findings:
        c = {"blocking": "red", "major": "yellow", "minor": "blue"}.get(f.severity, "white")
        console.print(f"  [{c}]{f.severity}[/{c}] {f.finding_id} — {f.description}")


@map.command("lock")
@click.argument("map_id")
def map_lock(map_id):
    """Lock a message map (requires no remaining gaps and no blocking findings)."""
    from labeling.message_map import MessageMapManager
    from labeling.labeling_qc import LabelingQCValidator
    mgr = MessageMapManager()
    m = mgr.load(map_id)
    gaps = [c.claim_id for c in m.claims if c.is_gap]
    blocking = [f for f in LabelingQCValidator().validate(m) if f.severity == "blocking"]
    if gaps:
        console.print(f"[red]Cannot lock: {len(gaps)} unresolved gap(s): {', '.join(gaps)}[/red]")
        return
    if blocking:
        console.print(f"[red]Cannot lock: {len(blocking)} blocking QC finding(s).[/red]")
        return
    m.locked = True
    m.locked_by = "regulatory_affairs"
    m.locked_at = datetime.datetime.utcnow()
    m.version = f"v{datetime.datetime.utcnow().strftime('%Y%m%d_%H%M')}"
    m.qc_passed = True
    mgr.save(m)
    console.print(f"[green]Message map locked: {m.version}[/green]")


# ── session ──────────────────────────────────────────────────────────────────
@cli.group()
def session():
    """Labeling session commands"""
    pass


@session.command("start")
@click.option("--mode", type=click.Choice(["high_quality", "low_quality"]), default="high_quality")
def session_start(mode):
    """Create a new labeling session."""
    from labeling.labeling_models import LabelingSession
    s = LabelingSession(
        session_id=f"t5_{uuid.uuid4().hex[:8]}", simulation_mode=mode,
        program_name="Aleniglipron", indication="obesity",
        ci_twin_id="ci_glp1_obesity_fda", content_twin_id="molecule_aleniglipron",
    )
    _sm().save(s)
    console.print(f"[green]Session created:[/green] {s.session_id} (mode={mode})")


@session.command("status")
@click.argument("session_id")
def session_status(session_id):
    """Show a session's phase and outcome counters."""
    s = _sm().load(session_id)
    console.print(f"[bold]{s.session_id}[/bold] — phase: {s.phase} | mode: {s.simulation_mode}")
    console.print(f"  Claims: {s.claims_total} (high {s.claims_high} / med {s.claims_medium} / low {s.claims_low})")
    console.print(f"  Gaps: {s.gaps_detected} detected, {s.gaps_filled_jit} filled | "
                  f"back-props: {s.back_propagations} | decisions: {s.reviewer_decisions}")


@session.command("complete")
@click.argument("session_id")
def session_complete(session_id):
    """Mark a session complete."""
    s = _sm().load(session_id)
    s.phase = "complete"
    s.status = "complete"
    _sm().save(s)
    console.print(f"[green]Session {session_id} marked complete.[/green]")


# ── evaluate ─────────────────────────────────────────────────────────────────
@cli.group()
def evaluate():
    """Evaluation commands"""
    pass


@evaluate.command("session")
@click.argument("session_id")
def evaluate_session(session_id):
    """Compute metrics for one session."""
    from workflow.evaluator import LabelingEvaluator
    s = _sm().load(session_id)
    for k, v in LabelingEvaluator().evaluate_session(s).items():
        console.print(f"  {k}: {v}")


@evaluate.command("all")
def evaluate_all():
    """Cross-session metrics table."""
    from workflow.evaluator import LabelingEvaluator
    sessions = _sm().list_sessions()
    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return
    df = LabelingEvaluator().to_dataframe(sessions)
    cols = ["session_id", "simulation_mode", "claims_total", "claims_high",
            "gaps_filled_jit", "process_preference", "overall_confidence"]
    console.print(df[cols].to_string(index=False))


if __name__ == "__main__":
    cli()
