"""
CLI commands for document ingestion.
"""
from __future__ import annotations
import click
from rich.console import Console
from rich.table import Table

console = Console()


@click.group("ingest")
def ingest_group():
    """Document ingestion commands."""
    pass


@ingest_group.command("start")
@click.argument("document_path")
@click.option("--twin-id", default="synth_phase2_trial", help="Digital twin ID")
@click.option("--schema-id", default="protocol", help="Schema ID")
@click.option("--writer-id", default="writer_1", help="Writer identifier")
@click.option("--stub", is_flag=True, default=False, help="Use stub extraction (no API key needed)")
def ingest_start(document_path: str, twin_id: str, schema_id: str, writer_id: str, stub: bool):
    """Start a new ingestion session for DOCUMENT_PATH."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    from ingestion.ingestion_session import IngestionSessionManager
    from ingestion.layer_runner import LayerRunner
    from ingestion.document_parser import DocumentParser

    mgr = IngestionSessionManager()
    session = mgr.create(document_path, twin_id, schema_id, writer_id)
    console.print(f"[green]Created ingestion session: {session.session_id}[/green]")
    console.print(f"  Document: {session.document_filename}")
    console.print(f"  Twin: {session.twin_id}")
    console.print(f"  Stub mode: {stub}")
    mgr.save(session)


@ingest_group.command("run-layer")
@click.argument("session_id")
@click.option("--stub", is_flag=True, default=True, help="Use stub extraction")
def ingest_run_layer(session_id: str, stub: bool):
    """Run extraction for the current layer of SESSION_ID."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    from ingestion.ingestion_session import IngestionSessionManager
    from ingestion.layer_runner import LayerRunner

    mgr = IngestionSessionManager()
    session = mgr.load(session_id)

    if session.status == "complete":
        console.print("[yellow]Session already complete.[/yellow]")
        return

    runner = LayerRunner(use_stub=stub)
    result = runner.run_extraction(session, None)
    runner.auto_verify_layer(session, session.current_layer, result)
    runner.advance_layer(session)
    mgr.save(session)

    console.print(f"[green]Layer {result.layer_index} ({result.layer_name}) extracted.[/green]")
    console.print(f"  Nodes extracted: {len(result.extracted_nodes)}")
    console.print(f"  Current layer: {session.current_layer}/{session.total_layers}")
    console.print(f"  Status: {session.status}")


@ingest_group.command("list")
def ingest_list():
    """List all ingestion sessions."""
    import os
    import sys
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

    from ingestion.ingestion_session import IngestionSessionManager

    mgr = IngestionSessionManager()
    sessions = mgr.list_sessions()

    if not sessions:
        console.print("[yellow]No ingestion sessions found.[/yellow]")
        return

    table = Table(title="Ingestion Sessions")
    table.add_column("Session ID")
    table.add_column("Document")
    table.add_column("Status")
    table.add_column("Layer")
    table.add_column("Confirmed")

    for s in sessions:
        table.add_row(
            s.session_id,
            s.document_filename,
            s.status,
            f"{s.current_layer}/{s.total_layers}",
            str(s.total_nodes_confirmed),
        )
    console.print(table)
