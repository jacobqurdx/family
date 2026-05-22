"""
eval/runner.py
==============
Orchestrates multi-skill evaluation runs and logs everything to MLflow.

MLflow hierarchy:
  Experiment : "pharma-risk-agent-eval"
    Run      : one per eval invocation (model × prompt_version snapshot)
      Params : model, stub, each skill's prompt_version
      Metrics: per-skill flat metrics (e.g. relevance/f1, severity/macro_f1)
      Tags   : run_name, skills_evaluated, dataset_path
      Artifacts:
        eval_summary.md          — human-readable table of all metrics
        predictions/{skill}.json — per-sample prediction log
        confusion/{skill}.txt    — confusion matrix (severity only)
        worst_cases/{skill}.json — top-5 misclassifications / largest errors
"""
from __future__ import annotations

import json
import os
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import mlflow

from eval.dataset import EvalSample
from eval.evaluators import EvalResult, get_evaluator, ALL_SKILLS
from eval.metrics import format_metrics_table


EXPERIMENT_NAME = "pharma-risk-agent-eval"


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_eval(
    samples: list[EvalSample],
    client: Any,
    context: Any,
    skills: list[str] | None = None,
    run_name: str | None = None,
    model_name: str = "unknown",
    stub: bool = False,
    cache_dir: Path | None = None,
    mlflow_tracking_uri: str | None = None,
    extra_tags: dict | None = None,
) -> dict[str, EvalResult]:
    """
    Run evaluation for *skills* against *samples* and log to MLflow.

    Returns a dict of {skill: EvalResult}.
    """
    skills = skills or ALL_SKILLS
    extra_tags = extra_tags or {}

    # ---- MLflow setup --------------------------------------------------------
    if mlflow_tracking_uri:
        mlflow.set_tracking_uri(mlflow_tracking_uri)
    mlflow.set_experiment(EXPERIMENT_NAME)

    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_name = run_name or f"{ts}_{model_name}_{'stub' if stub else 'live'}"

    results: dict[str, EvalResult] = {}

    with mlflow.start_run(run_name=run_name) as run:
        # ---- Tags --------------------------------------------------------
        mlflow.set_tags({
            "model":            model_name,
            "stub":             str(stub),
            "skills":           ",".join(skills),
            "n_samples_total":  str(len(samples)),
            **extra_tags,
        })

        # ---- Per-skill eval ----------------------------------------------
        for skill in skills:
            evaluator = get_evaluator(skill)
            print(f"  [{skill}] evaluating {len(samples)} samples …", flush=True)
            result = evaluator.run(samples, client, context, cache_dir=cache_dir)
            results[skill] = result
            print(f"  [{skill}] done — {result.n_samples} eligible, "
                  f"{result.elapsed_sec:.1f}s", flush=True)

            # Log params
            mlflow.log_param(f"{skill}/prompt_version", result.prompt_version)
            mlflow.log_param(f"{skill}/n_samples", result.n_samples)

            # Log scalar metrics (skip non-numeric like confusion_matrix string)
            for k, v in result.metrics.items():
                if isinstance(v, (int, float)):
                    mlflow.log_metric(f"{skill}/{k}", float(v))

        # ---- Global params -----------------------------------------------
        mlflow.log_param("model", model_name)
        mlflow.log_param("stub", stub)
        mlflow.log_param("n_samples_total", len(samples))

        # ---- Artifacts ---------------------------------------------------
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)

            # eval_summary.md
            summary_path = tmp / "eval_summary.md"
            summary_path.write_text(_build_summary_md(results, model_name, stub, run.info.run_id))
            mlflow.log_artifact(str(summary_path))

            # per-skill artifacts
            for skill, result in results.items():
                skill_dir = tmp / skill
                skill_dir.mkdir()

                # predictions log
                pred_path = skill_dir / "predictions.json"
                pred_path.write_text(json.dumps(result.predictions, indent=2, default=str))
                mlflow.log_artifact(str(pred_path), artifact_path=f"predictions")

                # worst cases
                if result.worst_cases:
                    wc_path = skill_dir / "worst_cases.json"
                    wc_path.write_text(json.dumps(result.worst_cases, indent=2, default=str))
                    mlflow.log_artifact(str(wc_path), artifact_path=f"worst_cases")

                # confusion matrix (severity)
                if result._multiclass and result._multiclass.confusion:
                    from eval.metrics import confusion_matrix_str
                    cm_path = skill_dir / "confusion_matrix.txt"
                    cm_path.write_text(
                        confusion_matrix_str(
                            result._multiclass.confusion,
                            result._multiclass.labels,
                        )
                    )
                    mlflow.log_artifact(str(cm_path), artifact_path=f"confusion")

                # confusion matrix plot (severity)
                if result._multiclass and result._multiclass.confusion:
                    try:
                        plot_path = skill_dir / "confusion_matrix.png"
                        _plot_confusion(
                            result._multiclass.confusion,
                            result._multiclass.labels,
                            str(plot_path),
                        )
                        mlflow.log_artifact(str(plot_path), artifact_path=f"confusion")
                    except Exception:
                        pass  # matplotlib optional

        print(f"\n  MLflow run: {run.info.run_id}")
        print(f"  Tracking UI: {mlflow.get_tracking_uri()}/#/experiments/"
              f"{run.info.experiment_id}/runs/{run.info.run_id}")

    return results


# ---------------------------------------------------------------------------
# Summary markdown builder
# ---------------------------------------------------------------------------

def _build_summary_md(
    results: dict[str, EvalResult],
    model_name: str,
    stub: bool,
    run_id: str,
) -> str:
    lines = [
        "# Eval Pipeline Summary",
        "",
        f"**Model:** `{model_name}`  |  **Stub:** `{stub}`  |  **Run:** `{run_id}`",
        "",
    ]
    for skill, r in results.items():
        lines += [
            f"## {skill.title()} ({r.n_samples} samples, {r.elapsed_sec:.1f}s)",
            f"Prompt version: `{r.prompt_version}`",
            "",
        ]
        # scalar metrics table
        scalar_metrics = {k: v for k, v in r.metrics.items() if isinstance(v, (int, float))}
        if scalar_metrics:
            lines.append(format_metrics_table(scalar_metrics))
            lines.append("")

        # confusion matrix if present
        cm_str = r.metrics.get("confusion_matrix")
        if cm_str:
            lines += ["**Confusion matrix** (rows=true, cols=predicted):", "", "```", cm_str, "```", ""]

        # worst cases
        if r.worst_cases:
            lines += ["**Worst cases:**", ""]
            for wc in r.worst_cases[:3]:
                lines.append(
                    f"- `{wc.get('signal_id','?')}` "
                    f"expected=`{wc.get('expected','?')}` "
                    f"predicted=`{wc.get('predicted','?')}`"
                )
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Plot helper
# ---------------------------------------------------------------------------

def _plot_confusion(cm: list[list[int]], labels: list[str], path: str) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np

    arr = np.array(cm, dtype=float)
    row_sums = arr.sum(axis=1, keepdims=True)
    norm = np.divide(arr, row_sums, out=np.zeros_like(arr), where=row_sums != 0)

    fig, ax = plt.subplots(figsize=(5, 4))
    im = ax.imshow(norm, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(labels)))
    ax.set_yticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=30, ha="right", fontsize=9)
    ax.set_yticklabels(labels, fontsize=9)
    ax.set_xlabel("Predicted")
    ax.set_ylabel("True")
    ax.set_title("Severity Confusion Matrix (row-normalised)")

    for i in range(len(labels)):
        for j in range(len(labels)):
            count = int(arr[i, j])
            color = "white" if norm[i, j] > 0.5 else "black"
            ax.text(j, i, f"{count}", ha="center", va="center",
                    color=color, fontsize=10, fontweight="bold")

    plt.colorbar(im, ax=ax, fraction=0.046, pad=0.04)
    plt.tight_layout()
    plt.savefig(path, dpi=120, bbox_inches="tight")
    plt.close(fig)
