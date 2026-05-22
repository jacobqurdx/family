"""
eval/metrics.py
===============
Metric helpers used by all evaluators.  Intentionally dependency-light;
sklearn is only imported for the confusion matrix string helper.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------

@dataclass
class BinaryMetrics:
    precision: float
    recall: float
    f1: float
    accuracy: float
    n_total: int
    n_positive_true: int
    tp: int
    fp: int
    fn: int
    tn: int

    def as_dict(self, prefix: str = "") -> dict[str, float]:
        return {
            f"{prefix}precision": self.precision,
            f"{prefix}recall":    self.recall,
            f"{prefix}f1":        self.f1,
            f"{prefix}accuracy":  self.accuracy,
            f"{prefix}n_total":   float(self.n_total),
        }


@dataclass
class MulticlassMetrics:
    macro_precision: float
    macro_recall: float
    macro_f1: float
    accuracy: float
    n_total: int
    n_correct: int
    per_class: dict[str, dict[str, float]] = field(default_factory=dict)
    confusion: list[list[int]] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)

    def as_dict(self, prefix: str = "") -> dict[str, float]:
        out: dict[str, float] = {
            f"{prefix}macro_precision": self.macro_precision,
            f"{prefix}macro_recall":    self.macro_recall,
            f"{prefix}macro_f1":        self.macro_f1,
            f"{prefix}accuracy":        self.accuracy,
            f"{prefix}n_total":         float(self.n_total),
            f"{prefix}n_correct":       float(self.n_correct),
        }
        for cls, m in self.per_class.items():
            for k, v in m.items():
                out[f"{prefix}{cls}/{k}"] = v
        return out


@dataclass
class RegressionMetrics:
    mae: float
    rmse: float
    mean_pct_error: float   # signed mean % error
    n_total: int
    n_null_pred: int        # predictions that returned None when truth was non-null

    def as_dict(self, prefix: str = "") -> dict[str, float]:
        return {
            f"{prefix}mae":            self.mae,
            f"{prefix}rmse":           self.rmse,
            f"{prefix}mean_pct_error": self.mean_pct_error,
            f"{prefix}n_total":        float(self.n_total),
            f"{prefix}n_null_pred":    float(self.n_null_pred),
        }


# ---------------------------------------------------------------------------
# Computation
# ---------------------------------------------------------------------------

def binary_metrics(
    y_true: list[bool],
    y_pred: list[bool],
) -> BinaryMetrics:
    assert len(y_true) == len(y_pred), "Mismatched lengths"
    tp = sum(1 for t, p in zip(y_true, y_pred) if t and p)
    fp = sum(1 for t, p in zip(y_true, y_pred) if not t and p)
    fn = sum(1 for t, p in zip(y_true, y_pred) if t and not p)
    tn = sum(1 for t, p in zip(y_true, y_pred) if not t and not p)
    n  = len(y_true)
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1        = (2 * precision * recall / (precision + recall)
                 if (precision + recall) > 0 else 0.0)
    accuracy  = (tp + tn) / n if n > 0 else 0.0
    return BinaryMetrics(
        precision=precision, recall=recall, f1=f1, accuracy=accuracy,
        n_total=n, n_positive_true=sum(y_true),
        tp=tp, fp=fp, fn=fn, tn=tn,
    )


def multiclass_metrics(
    y_true: list[str],
    y_pred: list[str],
    labels: list[str],
) -> MulticlassMetrics:
    assert len(y_true) == len(y_pred), "Mismatched lengths"
    n = len(y_true)
    n_correct = sum(1 for t, p in zip(y_true, y_pred) if t == p)
    accuracy  = n_correct / n if n > 0 else 0.0

    # Per-class TP/FP/FN
    per_class: dict[str, dict[str, float]] = {}
    for cls in labels:
        tp = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p == cls)
        fp = sum(1 for t, p in zip(y_true, y_pred) if t != cls and p == cls)
        fn = sum(1 for t, p in zip(y_true, y_pred) if t == cls and p != cls)
        p_  = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        r_  = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1_ = 2 * p_ * r_ / (p_ + r_) if (p_ + r_) > 0 else 0.0
        per_class[cls] = {"precision": p_, "recall": r_, "f1": f1_,
                          "support": sum(1 for t in y_true if t == cls)}

    active = [cls for cls in labels if per_class[cls]["support"] > 0]
    macro_p  = sum(per_class[c]["precision"] for c in active) / len(active) if active else 0.0
    macro_r  = sum(per_class[c]["recall"]    for c in active) / len(active) if active else 0.0
    macro_f1 = sum(per_class[c]["f1"]        for c in active) / len(active) if active else 0.0

    # Confusion matrix (rows=true, cols=pred)
    idx = {c: i for i, c in enumerate(labels)}
    cm  = [[0] * len(labels) for _ in labels]
    for t, p in zip(y_true, y_pred):
        if t in idx and p in idx:
            cm[idx[t]][idx[p]] += 1

    return MulticlassMetrics(
        macro_precision=macro_p,
        macro_recall=macro_r,
        macro_f1=macro_f1,
        accuracy=accuracy,
        n_total=n,
        n_correct=n_correct,
        per_class=per_class,
        confusion=cm,
        labels=labels,
    )


def regression_metrics(
    y_true: list[float],
    y_pred: list[float | None],
) -> RegressionMetrics:
    """
    Compute MAE / RMSE / mean % error for numeric impact predictions.
    Pairs where y_pred is None are counted as null_pred but excluded from
    MAE/RMSE to avoid contaminating numeric metrics.
    """
    n_null = sum(1 for p in y_pred if p is None)
    pairs  = [(t, p) for t, p in zip(y_true, y_pred) if p is not None]

    if not pairs:
        return RegressionMetrics(
            mae=0.0, rmse=0.0, mean_pct_error=0.0,
            n_total=len(y_true), n_null_pred=n_null,
        )

    errors   = [abs(t - p) for t, p in pairs]
    sq_errs  = [(t - p) ** 2 for t, p in pairs]
    pct_errs = [(p - t) / t * 100 if t != 0 else 0.0 for t, p in pairs]

    return RegressionMetrics(
        mae=sum(errors) / len(errors),
        rmse=math.sqrt(sum(sq_errs) / len(sq_errs)),
        mean_pct_error=sum(pct_errs) / len(pct_errs),
        n_total=len(y_true),
        n_null_pred=n_null,
    )


# ---------------------------------------------------------------------------
# Pretty printing helpers
# ---------------------------------------------------------------------------

def confusion_matrix_str(cm: list[list[int]], labels: list[str]) -> str:
    """Return an ASCII confusion matrix for artifact logging."""
    col_w = max(len(l) for l in labels) + 2
    header = " " * col_w + "".join(f"{l:>{col_w}}" for l in labels) + "  ← predicted"
    rows = [header]
    for i, row in enumerate(cm):
        rows.append(f"{labels[i]:>{col_w}}" + "".join(f"{v:>{col_w}}" for v in row))
    rows.append("↑ true")
    return "\n".join(rows)


def format_metrics_table(metrics: dict[str, Any]) -> str:
    """Format a flat metrics dict as a markdown table."""
    rows = ["| Metric | Value |", "|---|---|"]
    for k, v in sorted(metrics.items()):
        val = f"{v:.4f}" if isinstance(v, float) else str(v)
        rows.append(f"| {k} | {val} |")
    return "\n".join(rows)
