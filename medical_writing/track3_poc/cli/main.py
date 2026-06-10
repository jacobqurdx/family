"""
Track 3 CLI — AI Regulatory Intelligence System.

Command groups: twin · structure · guidance · spec · qc · review
Generated specs/findings are persisted under RESULTS_DIR so the spec → qc →
review commands can be chained across invocations.
"""
import json
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

import config

console = Console()

_SPEC_PATH = Path(config.RESULTS_DIR) / "last_spec.json"
_FINDINGS_PATH = Path(config.RESULTS_DIR) / "last_findings.json"
_CHECKLIST = f"{config.CHECKLISTS_DIR}/eop2_checklist.json"
_FRAMEWORK = "framework_fda_obesity"


@click.group()
def cli():
    """Structure Therapeutics — AI Regulatory Intelligence POC (Track 3)"""
    pass


# ── structure ─────────────────────────────────────────────────────────────────
@cli.group()
def structure():
    """Document structure twin commands"""
    pass


@structure.command("list")
def structure_list():
    """List all document structure twins."""
    from twins.structure.manager import StructureTwinManager
    mgr = StructureTwinManager()
    table = Table(title="Document Structure Twins")
    table.add_column("Structure ID", style="cyan")
    table.add_column("Document Type")
    table.add_column("Body")
    table.add_column("Sections")
    table.add_column("Locked")
    for sid in mgr.list_ids():
        t = mgr.load(sid)
        table.add_row(sid, t.document_type, t.regulatory_body,
                      str(len(t.sections)), "🔒" if t.locked else "")
    console.print(table)


@structure.command("show")
@click.argument("structure_id")
def structure_show(structure_id):
    """Show the sections of a document structure twin."""
    from twins.structure.manager import StructureTwinManager
    t = StructureTwinManager().load(structure_id)
    console.print(f"[bold]{t.document_type}[/bold] ({t.regulatory_body}) v{t.version}")
    table = Table(title=f"Sections — {structure_id}")
    table.add_column("#", style="dim")
    table.add_column("Section ID", style="cyan")
    table.add_column("Title")
    table.add_column("Req")
    table.add_column("Authority")
    table.add_column("Source Elements")
    for s in sorted(t.sections, key=lambda x: x.ordering):
        table.add_row(str(s.ordering), s.section_id, s.section_title,
                      "✓" if s.required else "",
                      s.regulatory_authority, ", ".join(s.source_elements))
    console.print(table)


@structure.command("validate")
@click.argument("structure_id")
def structure_validate(structure_id):
    """Validate a document structure twin."""
    from twins.structure.manager import StructureTwinManager
    mgr = StructureTwinManager()
    errors = mgr.validate(mgr.load(structure_id))
    if errors:
        for e in errors:
            console.print(f"[red]ERROR:[/red] {e}")
    else:
        console.print(f"[green]Structure twin '{structure_id}' is valid.[/green]")


# ── twin (content) ──────────────────────────────────────────────────────────────
@cli.group()
def twin():
    """Content twin commands"""
    pass


@twin.command("show")
@click.argument("twin_id")
def twin_show(twin_id):
    """Show all elements in a content twin."""
    from core.twin import DigitalTwin
    t = DigitalTwin.load(twin_id)
    table = Table(title=f"Content Twin: {twin_id}")
    table.add_column("Element", style="cyan")
    table.add_column("Value")
    table.add_column("Status")
    table.add_column("Source")
    for eid, el in t.get_all().items():
        val = str(el.value)[:50] if el.value is not None else "[dim]empty[/dim]"
        table.add_row(eid, val, el.status.value, el.source or "")
    console.print(table)


@twin.command("set")
@click.argument("twin_id")
@click.argument("element_id")
@click.argument("value")
def twin_set(twin_id, element_id, value):
    """Set an element value on a content twin (back-propagation)."""
    from twins.content.manager import ContentTwinManager
    ContentTwinManager().back_propagate(twin_id, element_id, value,
                                        source="cli", modified_by="cli")
    console.print(f"[green]Set {element_id} = {value} on {twin_id}[/green]")


# ── guidance ────────────────────────────────────────────────────────────────────
@cli.group()
def guidance():
    """Regulatory guidance ingestion commands"""
    pass


@guidance.command("ingest")
@click.option("--path", default=f"{config.GUIDANCE_DOCS_DIR}/fda_obesity_guidance.txt")
@click.option("--doc-type", default="eop2_briefing")
def guidance_ingest(path, doc_type):
    """Ingest a guidance document into structured requirements (stubbed)."""
    from regulatory.guidance_ingestor import GuidanceIngestor
    reqs = GuidanceIngestor().ingest(path, doc_type)
    table = Table(title=f"Extracted Requirements (mode={config.SIMULATION_MODE})")
    table.add_column("ID", style="cyan")
    table.add_column("Section")
    table.add_column("Type")
    table.add_column("Mand")
    table.add_column("Conf")
    for r in reqs:
        table.add_row(r.requirement_id, r.guidance_section, r.requirement_type,
                      "✓" if r.mandatory else "", f"{r.confidence:.2f}")
    console.print(table)
    console.print(f"[green]{len(reqs)} requirements extracted.[/green]")


@guidance.command("status")
@click.option("--framework", default=_FRAMEWORK)
def guidance_status(framework):
    """Show the regulatory framework twin contents."""
    from regulatory.framework_twin import FrameworkTwinManager
    t = FrameworkTwinManager().load(framework)
    console.print(f"[bold]{t.framework_id}[/bold] ({t.regulatory_body}) v{t.version}")
    console.print(f"  Guidance docs: {len(t.guidance_documents)}")
    console.print(f"  Requirements:  {len(t.requirements)}")
    console.print(f"  Agency concerns: {len(t.agency_concerns)}")
    console.print(f"  Prior positions: {len(t.prior_positions)}")


# ── spec ────────────────────────────────────────────────────────────────────────
@cli.group()
def spec():
    """Content specification commands"""
    pass


@spec.command("generate")
@click.option("--structure", "structure_id", default="structure_eop2_fda")
@click.option("--content", "content_id", default=None)
def spec_generate(structure_id, content_id):
    """Generate a content specification from a twin pair and persist it."""
    from twins.registry import TwinRegistry
    from generation.content_spec_generator import ContentSpecGenerator
    reg = TwinRegistry()
    pair = reg.resolve(structure_id, content_id)
    result = ContentSpecGenerator().generate(pair)
    _SPEC_PATH.write_text(result.model_dump_json(indent=2))
    console.print(f"[green]Spec {result.spec_id} generated:[/green] "
                  f"{len(result.sections)} sections, {len(result.gaps_detected)} gaps")
    console.print(f"  Content: {pair.content_twin_id}  Structure: {pair.structure_twin_id}")
    console.print(f"  Gaps: {', '.join(result.gaps_detected)}")
    console.print(f"[dim]Saved to {_SPEC_PATH}[/dim]")


@spec.command("show")
def spec_show():
    """Show the most recently generated content specification."""
    from generation.spec_models import ContentSpec
    if not _SPEC_PATH.exists():
        console.print("[yellow]No spec generated yet. Run 'spec generate'.[/yellow]")
        return
    s = ContentSpec(**json.loads(_SPEC_PATH.read_text()))
    table = Table(title=f"Content Spec — {s.spec_id}")
    table.add_column("Section", style="cyan")
    table.add_column("Conf")
    table.add_column("Review?")
    table.add_column("Claims")
    for sec in s.sections:
        table.add_row(sec.section_title, f"{sec.overall_confidence:.0%}",
                      "⚠️" if sec.needs_human_review else "", str(len(sec.claims)))
    console.print(table)


# ── qc ──────────────────────────────────────────────────────────────────────────
@cli.group()
def qc():
    """QC pipeline commands"""
    pass


@qc.command("run")
def qc_run():
    """Run the five-pass QC pipeline on the most recent spec."""
    from generation.spec_models import ContentSpec
    from regulatory.framework_twin import FrameworkTwinManager
    from qc.pipeline import QCPipeline
    if not _SPEC_PATH.exists():
        console.print("[yellow]No spec generated yet. Run 'spec generate'.[/yellow]")
        return
    s = ContentSpec(**json.loads(_SPEC_PATH.read_text()))
    fw = FrameworkTwinManager().load(_FRAMEWORK)
    s, findings = QCPipeline(fw, _CHECKLIST).run(s)
    _SPEC_PATH.write_text(s.model_dump_json(indent=2))
    _FINDINGS_PATH.write_text(json.dumps([f.model_dump() for f in findings], indent=2, default=str))

    status = "[green]PASSED[/green]" if s.qc_passed else "[red]FAILED (blocking findings)[/red]"
    console.print(f"QC result: {status}  ({len(findings)} findings)")
    table = Table(title="QC Findings")
    table.add_column("Pass", style="dim")
    table.add_column("Severity")
    table.add_column("Section")
    table.add_column("Category")
    sev_color = {"blocking": "red", "major": "yellow", "minor": "blue"}
    for f in findings:
        c = sev_color.get(f.severity, "white")
        table.add_row(str(f.pass_number), f"[{c}]{f.severity}[/{c}]",
                      f.section_id, f.category)
    console.print(table)


@qc.command("findings")
def qc_findings():
    """Show findings from the last QC run with resolutions."""
    if not _FINDINGS_PATH.exists():
        console.print("[yellow]No QC run yet. Run 'qc run'.[/yellow]")
        return
    findings = json.loads(_FINDINGS_PATH.read_text())
    for f in findings:
        console.print(f"[bold]{f['severity'].upper()}[/bold] — {f['category']} "
                      f"(§{f['section_id']}, pass {f['pass_number']})")
        console.print(f"  {f['description']}")
        if f.get("suggested_resolution"):
            console.print(f"  [dim]→ {f['suggested_resolution']}[/dim]")


# ── review ──────────────────────────────────────────────────────────────────────
@cli.group()
def review():
    """Review package commands"""
    pass


@review.command("package")
@click.argument("role", default="regulatory_affairs")
def review_package(role):
    """Build a role-specific review package for the last spec + findings."""
    from generation.spec_models import ContentSpec
    from review.finding_models import QCFinding
    from review.review_package import ReviewPackageBuilder
    if not _SPEC_PATH.exists():
        console.print("[yellow]No spec generated yet. Run 'spec generate' then 'qc run'.[/yellow]")
        return
    s = ContentSpec(**json.loads(_SPEC_PATH.read_text()))
    findings = []
    if _FINDINGS_PATH.exists():
        findings = [QCFinding(**f) for f in json.loads(_FINDINGS_PATH.read_text())]
    pkg = ReviewPackageBuilder().build(s, findings, role)
    console.print(f"[bold]Review Package — {role}[/bold] ({pkg.package_id})")
    console.print(f"  Primary sections: {', '.join(pkg.primary_sections)}")
    console.print(f"  Total findings: {len(pkg.all_findings)}")
    blocking = [f for f in pkg.all_findings if f.severity == "blocking"]
    console.print(f"  Blocking: {len(blocking)}")


if __name__ == "__main__":
    cli()
