import pytest
from pathlib import Path

from agent.eval import run_evaluation, _metrics_from_counts

EXAMPLES_DIR = Path(__file__).parent.parent / "examples"
CORPUS_DIR = Path(__file__).parent.parent / "corpus"


def test_metrics_from_counts_perfect():
    m = _metrics_from_counts(tp=10, fp=0, tn=10, fn=0)
    assert m.precision == 1.0
    assert m.recall == 1.0
    assert m.f1 == 1.0


def test_metrics_from_counts_zero_division():
    m = _metrics_from_counts(tp=0, fp=0, tn=0, fn=5)
    assert m.precision == 0.0
    assert m.recall == 0.0
    assert m.f1 == 0.0


def test_run_evaluation_stub(stub_client, tmp_path):
    report = run_evaluation(
        corpus_dir=CORPUS_DIR / "signals",
        labels_file=CORPUS_DIR / "labels.yaml",
        sensitivity_json=EXAMPLES_DIR / "sensitivity_report_wuxi.json",
        client=stub_client,
        cache_dir=tmp_path / "cache",
        out_dir=tmp_path / "out",
    )
    assert report.relevance_metrics.f1 > 0
    assert report.total_llm_calls > 0
    assert isinstance(report.elapsed_sec, float)
    assert report.elapsed_sec >= 0
