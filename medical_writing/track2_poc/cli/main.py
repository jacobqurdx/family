"""
Main CLI entry point for Track 2 POC.
"""
from __future__ import annotations
import sys
from pathlib import Path

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent.parent))

import click
from cli.commands.ingest import ingest_group
from cli.commands.session import session_group
from cli.commands.workflow import workflow_group
from cli.commands.evaluate import evaluate_group


@click.group()
def cli():
    """AI Clinical Document Intelligence System — Track 2."""
    pass


cli.add_command(ingest_group)
cli.add_command(session_group)
cli.add_command(workflow_group)
cli.add_command(evaluate_group)


if __name__ == "__main__":
    cli()
