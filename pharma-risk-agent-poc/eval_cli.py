#!/usr/bin/env python3.11
"""
eval_cli.py — Eval pipeline entry point
=========================================
Runs the 5 assessment skills against SME-labeled signals and logs to MLflow.

Usage examples:

  # Stub mode — fast, uses stub_responses/, no API calls
  python3.11 eval_cli.py run --stub

  # Live mode — calls Claude API for each skill
  python3.11 eval_cli.py run --model claude-3-5-haiku-20241022

  # Only evaluate specific skills
  python3.11 eval_cli.py run --stub --skills relevance,severity

  # Custom label file and remote MLflow server
  python3.11 eval_cli.py run --labels path/to/export.jsonl \\
    --mlflow-uri http://localhost:5000

  # Launch MLflow UI (separate terminal)
  python3.11 eval_cli.py ui
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

# ---------------------------------------------------------------------------
# Defaults
# ---------------------------------------------------------------------------

DEFAULT_LABELS       = Path(__file__).parent / "labeled_data" / "export.jsonl"
DEFAULT_SENSITIVITY  = Path(__file__).parent / "examples" / "sensitivity_report_wuxi.json"
DEFAULT_MLFLOW_DIR   = Path(__file__).parent / "mlruns"
DEFAULT_MODEL        = "claude-3-5-haiku-20241022"
DEFAULT_MLFLOW_PORT  = 5001


# ---------------------------------------------------------------------------
# CLI group
# ---------------------------------------------------------------------------

@click.group()
def cli():
    """Pharma Risk Agent — evaluation pipeline."""


# ---------------------------------------------------------------------------
# run
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--labels",      default=str(DEFAULT_LABELS),
              show_default=True, help="Path to labeled_data/export.jsonl")
@click.option("--sensitivity", default=str(DEFAULT_SENSITIVITY),
              show_default=True, help="Path to sensitivity report JSON")
@click.option("--skills",      default=",".join(["relevance","novelty","severity","impact","metacognition"]),
              show_default=True, help="Comma-separated list of skills to eval")
@click.option("--model",       default=DEFAULT_MODEL,
              show_default=True, help="Model name (used for tagging; irrelevant in stub mode)")
@click.option("--stub",        is_flag=True, default=False,
              help="Use stub LLM responses (no API calls)")
@click.option("--mlflow-uri",  default=None,
              help="MLflow tracking URI. Defaults to local ./mlruns")
@click.option("--run-name",    default=None,
              help="Override the MLflow run name")
@click.option("--cache-dir",   default=None,
              help="LLM response cache directory")
@click.option("--include-partial/--complete-only", default=True,
              help="Include partial labels or require complete status")
def run(labels, sensitivity, skills, model, stub, mlflow_uri, run_name, cache_dir,
        include_partial):
    """Run the eval pipeline and log results to MLflow."""

    from eval.dataset import load_dataset, filter_samples
    from eval.runner import run_eval
    from eval.evaluators import ALL_SKILLS

    # ---- Load dataset --------------------------------------------------------
    labels_path = Path(labels)
    if not labels_path.exists():
        click.echo(f"⚠  Labels file not found: {labels_path}", err=True)
        click.echo("   Run the labeling app first: streamlit run label_app.py", err=True)
        click.echo("   (Continuing with 0 samples — this is a dry-run.)", err=True)
        samples = []
    else:
        samples = load_dataset(labels_path)
        if not include_partial:
            samples = [s for s in samples if s.status == "complete"]
        click.echo(f"✓  Loaded {len(samples)} samples from {labels_path}")

    # ---- Parse skills --------------------------------------------------------
    skill_list = [s.strip() for s in skills.split(",") if s.strip()]
    invalid = [s for s in skill_list if s not in ALL_SKILLS]
    if invalid:
        click.echo(f"Unknown skills: {invalid}. Valid: {ALL_SKILLS}", err=True)
        sys.exit(1)

    # ---- Build LLM client ----------------------------------------------------
    sys.path.insert(0, str(Path(__file__).parent))
    from agent.llm import LLMClient

    sensitivity_path = Path(sensitivity)
    if not sensitivity_path.exists():
        click.echo(f"Sensitivity report not found: {sensitivity_path}", err=True)
        sys.exit(1)
    sensitivity_data = json.loads(sensitivity_path.read_text())

    client = LLMClient(
        stub=stub,
        model=model,
    )

    # ---- Build context -------------------------------------------------------
    from agent.rule_engine import load_risk_profile_yaml
    from agent.domain import SensitivityContext

    profile_path = Path(__file__).parent / "examples" / "risk_profile.yaml"
    context = _build_context(sensitivity_data, profile_path)

    # ---- Run -----------------------------------------------------------------
    click.echo(f"\n{'='*55}")
    click.echo(f"  Model  : {model}  {'(STUB)' if stub else '(LIVE)'}")
    click.echo(f"  Skills : {skill_list}")
    click.echo(f"  Samples: {len(samples)}")
    click.echo(f"{'='*55}\n")

    results = run_eval(
        samples=samples,
        client=client,
        context=context,
        skills=skill_list,
        run_name=run_name,
        model_name=model,
        stub=stub,
        cache_dir=Path(cache_dir) if cache_dir else None,
        mlflow_tracking_uri=mlflow_uri,
    )

    # ---- Print summary -------------------------------------------------------
    click.echo(f"\n{'='*55}")
    click.echo("  RESULTS")
    click.echo(f"{'='*55}")
    for skill, result in results.items():
        click.echo(result.summary_str())
        click.echo()

    click.echo(
        f"MLflow UI: python3.11 eval_cli.py ui  "
        f"(or mlflow ui --port {DEFAULT_MLFLOW_PORT})"
    )


# ---------------------------------------------------------------------------
# ui — convenience wrapper around `mlflow ui`
# ---------------------------------------------------------------------------

@cli.command()
@click.option("--port", default=DEFAULT_MLFLOW_PORT, show_default=True)
@click.option("--host", default="127.0.0.1", show_default=True)
def ui(port, host):
    """Launch the MLflow tracking UI."""
    import subprocess
    click.echo(f"Opening MLflow UI at http://{host}:{port}")
    subprocess.run(["mlflow", "ui", "--host", host, "--port", str(port)], check=False)


# ---------------------------------------------------------------------------
# compare — quick CLI diff between two MLflow runs
# ---------------------------------------------------------------------------

@cli.command()
@click.argument("run_id_a")
@click.argument("run_id_b")
@click.option("--skill", default=None, help="Filter to one skill")
def compare(run_id_a, run_id_b, skill):
    """Print a metric diff between two MLflow run IDs."""
    import mlflow
    client = mlflow.tracking.MlflowClient()

    def get_metrics(run_id):
        run = client.get_run(run_id)
        return run.data.metrics, run.data.params

    m_a, p_a = get_metrics(run_id_a)
    m_b, p_b = get_metrics(run_id_b)

    all_keys = sorted(set(m_a) | set(m_b))
    if skill:
        all_keys = [k for k in all_keys if k.startswith(skill + "/")]

    click.echo(f"\n{'Metric':<45} {'Run A':>10} {'Run B':>10} {'Δ':>10}")
    click.echo("-" * 80)
    for k in all_keys:
        a = m_a.get(k, float("nan"))
        b = m_b.get(k, float("nan"))
        delta = b - a
        sign  = "+" if delta > 0 else ""
        click.echo(f"{k:<45} {a:>10.4f} {b:>10.4f} {sign}{delta:>9.4f}")

    click.echo(f"\nModel A: {p_a.get('model','?')} (stub={p_a.get('stub','?')})")
    click.echo(f"Model B: {p_b.get('model','?')} (stub={p_b.get('stub','?')})")


# ---------------------------------------------------------------------------
# list-runs
# ---------------------------------------------------------------------------

@cli.command("list-runs")
@click.option("--n", default=10, show_default=True, help="Number of runs to show")
def list_runs(n):
    """List recent eval runs from MLflow."""
    import mlflow
    client = mlflow.tracking.MlflowClient()
    try:
        exp = client.get_experiment_by_name("pharma-risk-agent-eval")
        if exp is None:
            click.echo("No eval experiment found yet. Run 'eval_cli.py run' first.")
            return
        runs = client.search_runs(
            experiment_ids=[exp.experiment_id],
            order_by=["start_time DESC"],
            max_results=n,
        )
    except Exception as e:
        click.echo(f"MLflow error: {e}", err=True)
        return

    click.echo(f"\n{'Run ID':<10} {'Name':<38} {'Model':<28} {'Sev F1':>8} {'Rel F1':>8}")
    click.echo("-" * 100)
    for r in runs:
        run_id = r.info.run_id[:8]
        name   = (r.info.run_name or "")[:36]
        model  = r.data.params.get("model", "?")[:26]
        sev_f1 = r.data.metrics.get("severity/macro_f1", float("nan"))
        rel_f1 = r.data.metrics.get("relevance/f1", float("nan"))
        click.echo(f"{run_id:<10} {name:<38} {model:<28} {sev_f1:>8.3f} {rel_f1:>8.3f}")


# ---------------------------------------------------------------------------
# Context builder helper
# ---------------------------------------------------------------------------

def _build_context(sensitivity_data: dict, profile_path: Path):
    """Build a SensitivityContext from sensitivity JSON + risk profile YAML."""
    from agent.domain import (
        SensitivityContext, SignalPriorityWeight, RiskProfile,
    )
    from agent.rule_engine import load_risk_profile_yaml

    profile: RiskProfile | None = None
    if profile_path.exists():
        try:
            profile = load_risk_profile_yaml(str(profile_path))
        except Exception:
            pass

    # Build SignalPriorityWeights from sensitivity data parameters
    weights: list[SignalPriorityWeight] = []
    params = sensitivity_data.get("parameters", [])
    for i, p in enumerate(params):
        weights.append(
            SignalPriorityWeight(
                rank=i + 1,
                parameter_name=p.get("name", f"param_{i}"),
                parameter_type=p.get("type", "unknown"),
                cdmo_node_name=p.get("cdmo_node_name"),
                country_of_origin=p.get("country_of_origin"),
                sensitivity_cost_per_unit=float(p.get("sensitivity_cost_per_unit", 0)),
                is_single_source=bool(p.get("is_single_source", False)),
                risk_flags=p.get("risk_flags", []),
                timeline_impact_weeks=int(p.get("timeline_impact_weeks", 0)),
            )
        )

    tariff_sweep = sensitivity_data.get("tariff_sweep", [])
    cdmo_removal = sensitivity_data.get("cdmo_removal_scenarios", [])

    exposure = sensitivity_data.get("exposure_summary", {})
    return SensitivityContext(
        report_id=sensitivity_data.get("report_id", "eval"),
        scenario_id=sensitivity_data.get("scenario_id", "eval"),
        process_name=sensitivity_data.get("process_name", "Unknown"),
        base_cost_per_kg_api=float(sensitivity_data.get("base_cost_per_kg_api", 0)),
        currency=sensitivity_data.get("currency", "USD"),
        china_origin_cost_pct=float(exposure.get("china_origin_cost_pct", 0)),
        indirect_china_cost_pct=float(exposure.get("indirect_china_cost_pct", 0)),
        single_source_cost_pct=float(exposure.get("single_source_cost_pct", 0)),
        cdmo_exposed_cost_pct=float(exposure.get("cdmo_exposed_cost_pct", 0)),
        signal_priority_weights=weights,
        tariff_sweep=tariff_sweep,
        cdmo_removal_scenarios=cdmo_removal,
    )


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    cli()
