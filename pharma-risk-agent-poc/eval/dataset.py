"""
eval/dataset.py
===============
Load SME-labeled signal records produced by label_app.py and expose them as
typed EvalSample objects ready for the evaluators.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import hashlib

from agent.domain import Signal, SignalSourceType


@dataclass
class EvalSample:
    """One SME-labeled signal, with convenience accessors per skill label."""

    signal_id: str
    signal: Signal
    labeler: str
    labeled_at: str
    status: str
    notes: str
    labels: dict = field(default_factory=dict)

    # ------------------------------------------------------------------ #
    # Convenience label accessors (return None if that step wasn't labeled)
    # ------------------------------------------------------------------ #

    @property
    def relevance_label(self) -> dict | None:
        return self.labels.get("relevance")

    @property
    def novelty_label(self) -> dict | None:
        return self.labels.get("novelty")

    @property
    def severity_label(self) -> dict | None:
        return self.labels.get("severity")

    @property
    def impact_label(self) -> dict | None:
        return self.labels.get("impact")

    @property
    def metacognition_label(self) -> dict | None:
        return self.labels.get("metacognition")

    # ------------------------------------------------------------------ #
    # Gate helpers — mirror the assessor's short-circuit logic
    # ------------------------------------------------------------------ #

    @property
    def is_relevant(self) -> bool | None:
        r = self.relevance_label
        return bool(r["is_relevant"]) if r else None

    @property
    def is_novel(self) -> bool | None:
        n = self.novelty_label
        if n is None:
            return None
        return bool(n["is_novel"])

    @property
    def ground_truth_severity(self) -> str | None:
        s = self.severity_label
        return s["severity"] if s else None

    @property
    def ground_truth_cost_impact(self) -> float | None:
        imp = self.impact_label
        if imp is None:
            return None
        if imp.get("qualitative_only"):
            return None
        v = imp.get("estimated_cost_impact_per_kg")
        return float(v) if v else None

    @property
    def ground_truth_qualitative_only(self) -> bool | None:
        imp = self.impact_label
        return bool(imp.get("qualitative_only")) if imp else None


def load_dataset(path: Path) -> list[EvalSample]:
    """
    Load the JSONL export from label_app.py.  Returns all records regardless
    of status; callers filter by status or label completeness as needed.
    """
    if not path.exists():
        return []

    samples: list[EvalSample] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue

        sig_dict = rec.get("signal", {})
        raw_content = sig_dict.get("raw_content", sig_dict.get("content", ""))
        signal = Signal(
            id=sig_dict.get("id", rec.get("signal_id", "unknown")),
            source_type=SignalSourceType.FILE,
            source_name=sig_dict.get("source_name", ""),
            source_url=sig_dict.get("source_url"),
            collected_at=sig_dict.get("collected_at", "1970-01-01T00:00:00+00:00"),
            raw_content=raw_content,
            raw_content_hash=hashlib.md5(raw_content.encode()).hexdigest(),
        )
        samples.append(
            EvalSample(
                signal_id=rec.get("signal_id", signal.id),
                signal=signal,
                labeler=rec.get("labeler", ""),
                labeled_at=rec.get("labeled_at", ""),
                status=rec.get("status", "unknown"),
                notes=rec.get("notes", ""),
                labels=rec.get("labels", {}),
            )
        )
    return samples


def filter_samples(
    samples: list[EvalSample],
    skill: str,
    include_statuses: tuple[str, ...] = ("complete", "partial"),
) -> list[EvalSample]:
    """
    Return samples that have a non-null label for *skill* and whose overall
    status is in *include_statuses*.
    """
    out = []
    for s in samples:
        if s.status not in include_statuses:
            continue
        label = s.labels.get(skill)
        if label is not None:
            out.append(s)
    return out
