from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from agent.domain import SignalState, SensitivityContext, AssessedSignal


class SignalStateStore:
    """JSON file-backed signal state store. Thread-safe for single-threaded CLI use."""

    def __init__(self, state_file: Path):
        self.state_file = state_file
        self._states: dict[str, SignalState] = {}
        if state_file.exists():
            self._load()

    def _load(self) -> None:
        data = json.loads(self.state_file.read_text())
        for name, s in data.items():
            self._states[name] = SignalState(**s)

    def save(self) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(
            json.dumps(
                {name: vars(s) for name, s in self._states.items()},
                indent=2,
            )
        )

    def get(self, parameter_name: str) -> SignalState | None:
        return self._states.get(parameter_name)

    def all(self) -> dict[str, SignalState]:
        return dict(self._states)

    def initialise_from_sensitivity_context(self, context: SensitivityContext) -> None:
        """Seed state from the MRP sensitivity report on first run."""
        for w in context.signal_priority_weights:
            if w.parameter_name not in self._states:
                parts = ["No disruption signals collected yet."]
                parts.append(f"Parameter sensitivity rank: #{w.rank}.")
                if w.country_of_origin:
                    parts.append(f"Origin: {w.country_of_origin}.")
                if w.cdmo_node_name:
                    flag = " (BioSecure Act listed)" if "biosecure_act_cdmo" in w.risk_flags else "."
                    parts.append(f"Produced at CDMO: {w.cdmo_node_name}{flag}")
                if w.is_single_source:
                    parts.append("Single-source material — no qualified alternative currently.")
                if w.timeline_impact_weeks:
                    parts.append(
                        f"Alternative qualification lead time: {w.timeline_impact_weeks:.0f} weeks."
                    )
                if w.tariff_impact_at_55pct:
                    parts.append(
                        f"At current 55% CN tariff: +${w.tariff_impact_at_55pct:.2f}/kg impact."
                    )
                self._states[w.parameter_name] = SignalState(
                    parameter_name=w.parameter_name,
                    last_updated_at=_utcnow(),
                    last_signal_source=None,
                    current_state_summary=" ".join(parts),
                    baseline_value=None,
                    baseline_value_unit=None,
                    last_known_change_direction="stable",
                    risk_level="normal" if w.rank > 5 else "elevated",
                    source_url=None,
                )
        self.save()

    def apply_novelty_updates(
        self,
        assessed: AssessedSignal,
        parameter_name: str,
    ) -> None:
        if assessed.novelty is None:
            return
        for update in assessed.novelty.updated_parameter_states:
            name = update.get("parameter_name")
            if name and name == parameter_name:
                existing = self._states.get(name)
                if existing:
                    existing.current_state_summary = update.get(
                        "new_state_summary", existing.current_state_summary
                    )
                    if update.get("new_baseline_value") is not None:
                        existing.baseline_value = update["new_baseline_value"]
                        existing.baseline_value_unit = update.get("new_baseline_value_unit")
                    existing.last_known_change_direction = update.get("change_direction")
                    existing.last_updated_at = _utcnow()
                    existing.last_signal_source = assessed.signal.source_url
        self.save()


def _utcnow() -> str:
    return datetime.now(timezone.utc).isoformat()
