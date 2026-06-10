"""
Track 4 CLI — RA Workflow Integration.

Command groups: session · participant · handoff · evaluate
Sessions persist to SESSIONS_DIR so commands chain across invocations.
"""
import json
import uuid
import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

import config

console = Console()

ROLES = ["regulatory_affairs", "medical_writing", "clinical_science", "clinical_operations"]


def _mgr():
    from workflow.session import SessionManager
    return SessionManager()


@click.group()
def cli():
    """Structure Therapeutics — RA Workflow Integration POC (Track 4)"""
    pass


# ── session ─────────────────────────────────────────────────────────────────
@cli.group()
def session():
    """Alignment session commands"""
    pass


@session.command("start")
@click.option("--mode", type=click.Choice(["high_quality", "low_quality"]),
              default="high_quality")
@click.option("--roles", default=",".join(ROLES), help="Comma-separated participant roles")
def session_start(mode, roles):
    """Create a new alignment session with participants."""
    from workflow.session import AlignmentSession, ParticipantRecord
    participants = [
        ParticipantRecord(participant_id=f"{r}_p1", role=r)
        for r in roles.split(",") if r
    ]
    s = AlignmentSession(
        session_id=f"t4_{uuid.uuid4().hex[:8]}",
        simulation_mode=mode,
        document_type="eop2_briefing",
        content_twin_id="molecule_aleniglipron",
        structure_twin_id="structure_eop2_fda",
        participants=participants,
    )
    _mgr().save(s)
    console.print(f"[green]Session created:[/green] {s.session_id} "
                  f"(mode={mode}, {len(participants)} participants)")


@session.command("list")
def session_list():
    """List all persisted sessions."""
    sessions = _mgr().list_sessions()
    table = Table(title="Alignment Sessions")
    table.add_column("Session ID", style="cyan")
    table.add_column("Mode")
    table.add_column("Phase")
    table.add_column("Participants")
    table.add_column("Status")
    for s in sessions:
        table.add_row(s.session_id, s.simulation_mode, s.phase.value,
                      str(len(s.participants)), s.status)
    console.print(table)


@session.command("status")
@click.argument("session_id")
def session_status(session_id):
    """Show a session's phase, timings, and outcome counters."""
    s = _mgr().load(session_id)
    console.print(f"[bold]{s.session_id}[/bold] — phase: {s.phase.value} "
                  f"| mode: {s.simulation_mode} | status: {s.status}")
    console.print(f"  Gaps: {s.gaps_detected} detected, {s.gaps_filled_jit} filled JIT")
    console.print(f"  QC: {s.qc_findings_total} findings ({s.qc_findings_blocking} blocking)")
    console.print(f"  Decisions: {s.review_decisions_total} "
                  f"| Content revisions: {len(s.content_revision_requests)}")
    if s.step_timings:
        table = Table(title="Step Timings")
        table.add_column("Step", style="cyan")
        table.add_column("Duration (min)")
        for t in s.step_timings:
            table.add_row(t.step_name, str(t.duration_minutes) if t.duration_minutes is not None else "running")
        console.print(table)


@session.command("complete")
@click.argument("session_id")
def session_complete(session_id):
    """Mark a session complete."""
    from workflow.session import SessionPhase
    s = _mgr().load(session_id)
    s.phase = SessionPhase.COMPLETE
    s.status = "complete"
    _mgr().save(s)
    console.print(f"[green]Session {session_id} marked complete.[/green]")


# ── participant ─────────────────────────────────────────────────────────────
@cli.group()
def participant():
    """Participant commands"""
    pass


@participant.command("add")
@click.argument("session_id")
@click.argument("role")
@click.option("--pid", default=None)
def participant_add(session_id, role, pid):
    """Add a participant to a session."""
    from workflow.participant import add_participant
    s = _mgr().load(session_id)
    add_participant(s, pid or f"{role}_p1", role)
    _mgr().save(s)
    console.print(f"[green]Added {role} to {session_id}.[/green]")


@participant.command("review")
@click.argument("session_id")
@click.argument("role")
@click.option("--decisions", default=0, type=int)
def participant_review(session_id, role, decisions):
    """Record a participant's completed review (start + complete + decisions)."""
    from workflow.participant import start_review, complete_review
    s = _mgr().load(session_id)
    start_review(s, role)
    complete_review(s, role, decisions)
    _mgr().save(s)
    console.print(f"[green]{role} review recorded ({decisions} decisions).[/green]")


@participant.command("survey")
@click.argument("session_id")
@click.argument("role")
@click.option("--ratings", default="7,7,7,7,7,7",
              help="Six comma-separated 1-10 ratings (preference,quality,qc,clarity,confidence,no-revisions)")
def participant_survey(session_id, role, ratings):
    """Submit a survey response for a participant."""
    from workflow.session import SurveyResponse
    from workflow.survey import submit_survey, SURVEY_QUESTIONS
    vals = [int(x) for x in ratings.split(",")]
    if len(vals) != 6:
        console.print("[red]Need exactly 6 ratings.[/red]")
        return
    fields = [q[0] for q in SURVEY_QUESTIONS]
    s = _mgr().load(session_id)
    submit_survey(s, SurveyResponse(
        participant_id=f"{role}_p1", role=role, **dict(zip(fields, vals))
    ))
    _mgr().save(s)
    console.print(f"[green]Survey recorded for {role}.[/green]")


# ── handoff ─────────────────────────────────────────────────────────────────
@cli.group()
def handoff():
    """Handoff package commands"""
    pass


@handoff.command("generate")
@click.argument("session_id")
@click.option("--notes", default="")
def handoff_generate(session_id, notes):
    """Generate spec → lock → handoff package for a session (POC shortcut)."""
    from workflow.session import SessionPhase
    from workflow.handoff import HandoffManager
    from twins.registry import TwinRegistry
    from generation.content_spec_generator import ContentSpecGenerator
    from governance.versioning import VersionManager

    s = _mgr().load(session_id)
    config.SIMULATION_MODE = s.simulation_mode
    pair = TwinRegistry().resolve(s.structure_twin_id, s.content_twin_id)
    spec = ContentSpecGenerator().generate(pair)
    s.spec_id = spec.spec_id
    s.gaps_detected = len(spec.gaps_detected)

    VersionManager().version_lock(spec, "regulatory_affairs")
    pkg = HandoffManager().create(session_id, spec, ra_notes=notes)
    s.handoff_id = pkg.handoff_id
    s.phase = SessionPhase.HANDOFF
    _mgr().save(s)
    console.print(f"[green]Handoff created:[/green] {pkg.handoff_id} "
                  f"({len(pkg.sections)} sections, locked {pkg.locked_spec_version})")


@handoff.command("status")
@click.argument("handoff_id", required=False)
def handoff_status(handoff_id):
    """Show a handoff package (or list all)."""
    from workflow.handoff import HandoffManager
    mgr = HandoffManager()
    if not handoff_id:
        for hid in mgr.list_ids():
            console.print(f"  {hid}")
        return
    h = mgr.load(handoff_id)
    console.print(f"[bold]{h.handoff_id}[/bold] — {h.document_type}")
    console.print(f"  Locked: {h.locked_spec_version} by {h.locked_by} at {h.locked_at}")
    console.print(f"  Sections: {len(h.sections)} | Gaps filled: {len(h.gaps_filled)}")
    if h.ra_notes:
        console.print(f"  RA notes: {h.ra_notes}")


# ── evaluate ─────────────────────────────────────────────────────────────────
@cli.group()
def evaluate():
    """Evaluation commands"""
    pass


@evaluate.command("session")
@click.argument("session_id")
def evaluate_session(session_id):
    """Compute all metrics for one session."""
    from workflow.evaluator import WorkflowEvaluator
    s = _mgr().load(session_id)
    metrics = WorkflowEvaluator().evaluate_session(s)
    for k, v in metrics.items():
        console.print(f"  {k}: {v}")


@evaluate.command("all")
def evaluate_all():
    """Cross-session metrics table."""
    from workflow.evaluator import WorkflowEvaluator
    sessions = _mgr().list_sessions()
    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        return
    df = WorkflowEvaluator().to_dataframe(sessions)
    cols = ["session_id", "simulation_mode", "participants", "gaps_detected",
            "qc_findings_total", "content_revision_requests",
            "avg_alignment_process_preference", "avg_confidence_in_document"]
    console.print(df[cols].to_string(index=False))


@evaluate.command("dashboard")
def evaluate_dashboard():
    """High vs low quality comparison with validation flags."""
    from workflow.evaluator import WorkflowEvaluator
    sessions = _mgr().list_sessions()
    hq = [s for s in sessions if s.simulation_mode == "high_quality"]
    lq = [s for s in sessions if s.simulation_mode == "low_quality"]
    if not hq or not lq:
        console.print(f"[yellow]Need both modes (have {len(hq)} HQ, {len(lq)} LQ).[/yellow]")
        return
    cmp = WorkflowEvaluator().compare_modes(hq, lq)
    console.print(json.dumps(cmp, indent=2, default=str))


if __name__ == "__main__":
    cli()
