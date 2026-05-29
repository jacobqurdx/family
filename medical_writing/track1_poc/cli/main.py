import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group()
def cli():
    """Structure Therapeutics — Clinical Document Intelligence POC (Track 1)"""
    pass


@cli.group()
def schema():
    """Schema registry commands"""
    pass


@schema.command("list")
def schema_list():
    """List all registered document schemas."""
    from core.schema import SchemaRegistry
    registry = SchemaRegistry()
    table = Table(title="Registered Schemas")
    table.add_column("ID", style="cyan")
    table.add_column("Name")
    table.add_column("Elements")
    for sid in registry.list_schemas():
        s = registry.get(sid)
        table.add_row(sid, s.name, str(len(s.elements)))
    console.print(table)


@schema.command("show")
@click.argument("schema_id")
def schema_show(schema_id):
    """Show all elements in a schema with their dependency types."""
    from core.schema import SchemaRegistry
    registry = SchemaRegistry()
    s = registry.get(schema_id)
    table = Table(title=f"Schema: {s.name}")
    table.add_column("Element ID", style="cyan")
    table.add_column("Label")
    table.add_column("Depends On")
    table.add_column("Dep Type")
    table.add_column("Required")
    for el in registry.get_authoring_order(schema_id):
        table.add_row(
            el.id, el.label,
            ", ".join(el.depends_on) or "—",
            el.dependency_type.value,
            "✓" if el.required else ""
        )
    console.print(table)


@schema.command("validate")
@click.argument("schema_id")
def schema_validate(schema_id):
    """Validate a schema for cycles and broken dependencies."""
    from core.schema import SchemaRegistry
    registry = SchemaRegistry()
    errors = registry.validate_schema(registry.get(schema_id))
    if errors:
        for e in errors:
            console.print(f"[red]ERROR:[/red] {e}")
    else:
        console.print(f"[green]Schema '{schema_id}' is valid.[/green]")


@cli.group()
def twin():
    """Digital twin commands"""
    pass


@twin.command("show")
@click.argument("twin_id")
def twin_show(twin_id):
    """Show all elements in a twin with status."""
    from core.twin import DigitalTwin
    t = DigitalTwin.load(twin_id)
    table = Table(title=f"Twin: {t.trial_name}")
    table.add_column("Element ID", style="cyan")
    table.add_column("Value")
    table.add_column("Status")
    table.add_column("Source")
    for eid, el in t.get_all().items():
        val = str(el.value)[:60] if el.value is not None else "[dim]empty[/dim]"
        table.add_row(eid, val, el.status.value, el.source or "")
    console.print(table)


@twin.command("set")
@click.argument("twin_id")
@click.argument("element_id")
@click.argument("value")
def twin_set(twin_id, element_id, value):
    """Set an element value in the twin and run propagation."""
    from core.twin import DigitalTwin
    from core.schema import SchemaRegistry
    from core.dependency import DependencyGraph

    t = DigitalTwin.load(twin_id)
    registry = SchemaRegistry()
    schema = registry.get(t.schema_id)
    dep_graph = DependencyGraph(schema)

    t.set(element_id, value)
    result = dep_graph.propagate(element_id, t)
    t.save()

    console.print(f"[green]Set {element_id} = {value}[/green]")
    if result.affected_elements:
        console.print(f"Affected downstream elements: {', '.join(result.affected_elements)}")
    if result.violations:
        for v in result.violations:
            console.print(f"[yellow]VIOLATION ({v.dependency_type.value}):[/yellow] {v.message}")
    if result.inferred_updates:
        for eid, val in result.inferred_updates.items():
            console.print(f"[blue]INFERRED:[/blue] {eid} → {val}")
            t.set_inferred(eid, val, element_id)
        t.save()


@twin.command("diff")
@click.argument("twin_id_a")
@click.argument("twin_id_b")
def twin_diff(twin_id_a, twin_id_b):
    """Diff two twins and show differing elements."""
    from core.twin import DigitalTwin
    a = DigitalTwin.load(twin_id_a)
    b = DigitalTwin.load(twin_id_b)
    diffs = a.diff(b)
    if not diffs:
        console.print("[green]No differences found.[/green]")
        return
    table = Table(title=f"Diff: {twin_id_a} vs {twin_id_b}")
    table.add_column("Element ID", style="cyan")
    table.add_column(twin_id_a)
    table.add_column(twin_id_b)
    for d in diffs:
        table.add_row(d["element_id"], str(d["value_a"]), str(d["value_b"]))
    console.print(table)


@cli.group()
def dep():
    """Dependency graph commands"""
    pass


@dep.command("graph")
@click.argument("schema_id")
def dep_graph_cmd(schema_id):
    """Show the full dependency graph for a schema."""
    from core.schema import SchemaRegistry
    registry = SchemaRegistry()
    schema = registry.get(schema_id)
    table = Table(title=f"Dependency Graph: {schema.name}")
    table.add_column("Element", style="cyan")
    table.add_column("Depends On")
    table.add_column("Type")
    for el in registry.get_authoring_order(schema_id):
        table.add_row(
            el.id,
            ", ".join(el.depends_on) or "—",
            el.dependency_type.value
        )
    console.print(table)


@dep.command("propagate")
@click.argument("twin_id")
@click.argument("element_id")
def dep_propagate(twin_id, element_id):
    """Show what would be affected if element_id changed."""
    from core.twin import DigitalTwin
    from core.schema import SchemaRegistry
    from core.dependency import DependencyGraph

    t = DigitalTwin.load(twin_id)
    registry = SchemaRegistry()
    schema = registry.get(t.schema_id)
    dep_graph = DependencyGraph(schema)

    downstream = dep_graph.get_downstream(element_id)
    console.print(f"Downstream elements of '[cyan]{element_id}[/cyan]':")
    for eid in downstream:
        el = t.get(eid)
        status = el.status.value if el else "empty"
        console.print(f"  [cyan]{eid}[/cyan] (current status: {status})")


@dep.command("check")
@click.argument("twin_id_a")
@click.argument("twin_id_b")
def dep_check(twin_id_a, twin_id_b):
    """Cross-document consistency check between two twins."""
    from core.twin import DigitalTwin
    from core.schema import SchemaRegistry
    from core.dependency import DependencyGraph

    a = DigitalTwin.load(twin_id_a)
    b = DigitalTwin.load(twin_id_b)
    registry = SchemaRegistry()
    schema = registry.get(a.schema_id)
    dep_graph = DependencyGraph(schema)

    violations = dep_graph.check_consistency(a, b)
    if not violations:
        console.print("[green]No cross-document inconsistencies found.[/green]")
        return
    for v in violations:
        console.print(f"[yellow]INCONSISTENCY ({v.dependency_type.value}):[/yellow] {v.message}")


@cli.group()
def generate():
    """Prose generation commands"""
    pass


@generate.command("section")
@click.argument("twin_id")
@click.argument("section_id")
@click.option("--real-llm", is_flag=True, default=False)
def gen_section(twin_id, section_id, real_llm):
    """Generate prose for a single document section from the twin."""
    from core.twin import DigitalTwin
    from core.schema import SchemaRegistry
    from generation.generator import ProseGenerator
    from generation.qc_agent import QCAgent

    t = DigitalTwin.load(twin_id)
    registry = SchemaRegistry()
    schema = registry.get(t.schema_id)

    section = next((s for s in schema.sections if s.id == section_id), None)
    if not section:
        console.print(f"[red]Section '{section_id}' not found in schema '{schema.id}'[/red]")
        return

    source_data = t.get_section_data(section.source_elements)
    generator = ProseGenerator(use_real_llm=real_llm)
    result = generator.generate(section_id, section.title, source_data)

    console.print(f"\n[bold]{section.title}[/bold]")
    console.print(f"[dim]Confidence: {result.confidence:.2f} — {result.confidence_rationale}[/dim]")
    console.print(f"\n{result.prose}\n")

    qc = QCAgent(use_real_llm=real_llm)
    qc_result = qc.check(result, source_data)
    console.print(f"QC: [{'green' if qc_result.passed else 'red'}]{qc_result.recommendation}[/]")
    for finding in qc_result.findings:
        console.print(f"  [{finding.severity}] {finding.category}: {finding.description}")


@generate.command("document")
@click.argument("twin_id")
@click.option("--real-llm", is_flag=True, default=False)
def gen_document(twin_id, real_llm):
    """Generate prose for all sections of the twin's schema."""
    from core.twin import DigitalTwin
    from core.schema import SchemaRegistry
    from generation.generator import ProseGenerator
    from generation.qc_agent import QCAgent

    t = DigitalTwin.load(twin_id)
    registry = SchemaRegistry()
    schema = registry.get(t.schema_id)
    generator = ProseGenerator(use_real_llm=real_llm)
    qc = QCAgent(use_real_llm=real_llm)

    for section in schema.sections:
        source_data = t.get_section_data(section.source_elements)
        result = generator.generate(section.id, section.title, source_data)
        qc_result = qc.check(result, source_data)

        console.print(f"\n[bold cyan]{'='*60}[/bold cyan]")
        console.print(f"[bold]{section.title}[/bold]  "
                      f"[dim]confidence: {result.confidence:.2f}  "
                      f"QC: {qc_result.recommendation}[/dim]")
        console.print(f"\n{result.prose}")


@cli.group()
def evaluate():
    """Evaluation and testbed commands"""
    pass


@evaluate.command("accuracy")
@click.option("--real-llm", is_flag=True, default=False)
def eval_accuracy(real_llm):
    """Run all ground truth pairs through the generator and report accuracy."""
    from llm.testbed import LLMTestBed
    testbed = LLMTestBed(use_real_llm=real_llm)
    results = testbed.run_accuracy_eval()
    df = testbed.to_dataframe(results)
    console.print(df[["pair_id", "section_id", "auto_score", "confidence"]].to_string())
    avg = df["auto_score"].mean()
    console.print(f"\nAverage auto_score: [bold]{avg:.3f}[/bold]")
    cal = testbed.run_calibration_eval(results)
    console.print(f"Calibration delta: {cal['calibration_delta']:.3f} "
                  f"({'PASSED' if cal['calibration_passed'] else 'FAILED'})")


@evaluate.command("calibration")
@click.option("--real-llm", is_flag=True, default=False)
def eval_calibration(real_llm):
    """Report calibration: do high-confidence outputs score better?"""
    from llm.testbed import LLMTestBed
    testbed = LLMTestBed(use_real_llm=real_llm)
    results = testbed.run_accuracy_eval()
    cal = testbed.run_calibration_eval(results)
    console.print(f"High confidence (>=0.7): {cal['high_confidence_count']} pairs, "
                  f"avg score {cal['high_confidence_avg_score']:.3f}")
    console.print(f"Low confidence (<0.7):  {cal['low_confidence_count']} pairs, "
                  f"avg score {(cal['low_confidence_avg_score'] or 0):.3f}")
    console.print(f"Calibration delta: [bold]{cal['calibration_delta']:.3f}[/bold] "
                  f"→ [{'green' if cal['calibration_passed'] else 'red'}]"
                  f"{'PASSED' if cal['calibration_passed'] else 'FAILED'}[/]")


@evaluate.command("consistency")
@click.argument("twin_id_a")
@click.argument("twin_id_b")
def eval_consistency(twin_id_a, twin_id_b):
    """Cross-document consistency check between two twins."""
    from core.twin import DigitalTwin
    from core.schema import SchemaRegistry
    from core.dependency import DependencyGraph

    a = DigitalTwin.load(twin_id_a)
    b = DigitalTwin.load(twin_id_b)
    registry = SchemaRegistry()
    schema = registry.get(a.schema_id)
    dep_graph = DependencyGraph(schema)
    violations = dep_graph.check_consistency(a, b)

    if not violations:
        console.print("[green]No inconsistencies detected.[/green]")
    else:
        console.print(f"[red]{len(violations)} inconsistency/ies found:[/red]")
        for v in violations:
            console.print(f"  [yellow]{v.dependency_type.value.upper()}[/yellow]: {v.message}")


if __name__ == "__main__":
    cli()
