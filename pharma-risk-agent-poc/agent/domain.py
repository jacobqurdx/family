from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


class SignalSourceType(str, Enum):
    FILE = "file"
    WEB_SEARCH = "web_search"
    MANUAL = "manual"


class SeverityTier(str, Enum):
    ROUTINE = "routine"
    ELEVATED = "elevated"
    HIGH = "high"
    CRITICAL = "critical"


class RiskVectorType(str, Enum):
    TARIFF_ESCALATION = "tariff_escalation"
    CDMO_REMOVAL = "cdmo_removal"
    YIELD_DISRUPTION = "yield_disruption"
    LEAD_TIME_EXTENSION = "lead_time_extension"
    UNKNOWN = "unknown"


class ActionType(str, Enum):
    ADD_TO_DIGEST = "add_to_digest"
    SEND_ALERT = "send_alert"
    TRIGGER_TARIFF_SWEEP = "trigger_tariff_sweep"
    TRIGGER_CDMO_REMOVAL = "trigger_cdmo_removal"
    TRIGGER_SENSITIVITY_RERUN = "trigger_sensitivity_rerun"
    DRAFT_INVESTIGATION_REPORT = "draft_investigation_report"
    DRAFT_MANAGEMENT_BRIEFING = "draft_management_briefing"


@dataclass
class SignalPriorityWeight:
    rank: int
    parameter_name: str
    parameter_type: str
    sensitivity_cost_per_unit: float
    country_of_origin: str | None
    cdmo_node_name: str | None
    cdmo_node_id: str | None
    is_single_source: bool
    is_indirect_china: bool
    timeline_impact_weeks: float | None
    risk_flags: list[str]
    tariff_impact_at_55pct: float | None
    target_id: str | None


@dataclass
class SensitivityContext:
    report_id: str
    scenario_id: str
    process_name: str
    base_cost_per_kg_api: float
    currency: str
    china_origin_cost_pct: float
    indirect_china_cost_pct: float
    single_source_cost_pct: float
    cdmo_exposed_cost_pct: float
    signal_priority_weights: list[SignalPriorityWeight]
    tariff_sweep: list[dict]
    cdmo_removal_scenarios: list[dict]


@dataclass
class Signal:
    id: str
    source_type: SignalSourceType
    source_name: str
    source_url: str | None
    collected_at: str
    raw_content: str
    raw_content_hash: str


@dataclass
class RelevanceResult:
    is_relevant: bool
    relevant_parameters: list[str]
    relevance_reasoning: str
    prompt_version: str


@dataclass
class NoveltyResult:
    is_novel: bool
    novelty_reasoning: str
    updated_parameter_states: list[dict]
    prompt_version: str


@dataclass
class SeverityResult:
    severity: SeverityTier
    severity_reasoning: str
    risk_vector_type: RiskVectorType
    affected_geography: str | None
    affected_cdmo_node_name: str | None
    prompt_version: str


@dataclass
class ImpactResult:
    estimated_cost_impact_per_kg: float | None
    estimated_cost_impact_reasoning: str
    estimated_timeline_impact_weeks: float | None
    estimated_timeline_reasoning: str
    confidence: str
    caveats: list[str]
    prompt_version: str


@dataclass
class MetacognitionResult:
    grade: str  # "CERTAIN" or "UNCERTAIN"
    confidence: float  # 0.0 - 1.0
    uncertainty_flags: list[str]
    reasoning: str
    step: str  # "severity" or "impact"
    adjudicated: bool = False
    adjudicated_by: str | None = None
    prompt_version: str = "unknown"


@dataclass
class AssessedSignal:
    signal: Signal
    relevance: RelevanceResult
    novelty: NoveltyResult | None
    severity: SeverityResult | None
    impact: ImpactResult | None
    recommended_actions: list[ActionType]
    assessment_failed: bool = False
    failure_reason: str | None = None
    severity_metacognition: MetacognitionResult | None = None
    impact_metacognition: MetacognitionResult | None = None
    assessment_engine: str = "llm"  # "llm" | "rule_engine"


# ─── Risk Profile domain objects (v1.2) ──────────────────────────────────────

@dataclass
class InternalThresholds:
    planned_value: float
    unit: str
    elevated_threshold: float
    high_threshold: float
    critical_threshold: float
    threshold_type: str = "ratio"  # "ratio" | "absolute"


@dataclass
class RiskProfileParameter:
    id: str
    name: str
    category: str  # "tariff_escalation"|"cdmo_removal"|"operational"|"material_price"|"capacity_constraint"
    risk_tier: str  # "HIGH" | "MEDIUM" | "LOW"
    applies_to_scenarios: list[str]
    description: str | None = None
    internal_thresholds: InternalThresholds | None = None
    sources_to_monitor: list[str] = field(default_factory=list)
    notes: str | None = None


@dataclass
class RiskProfileScenario:
    id: str
    name: str
    is_primary: bool = False
    mrp_scenario_id: str | None = None
    notes: str | None = None


@dataclass
class DefaultThresholds:
    yield_parameters: dict[str, float]
    rate_parameters: dict[str, float]
    price_parameters: dict[str, float] = field(default_factory=dict)


@dataclass
class RiskProfile:
    name: str
    version: str
    scenarios: list[RiskProfileScenario]
    parameters: list[RiskProfileParameter]
    default_thresholds: DefaultThresholds | None = None

    def get_parameter(self, param_id: str) -> RiskProfileParameter | None:
        return next((p for p in self.parameters if p.id == param_id), None)

    def primary_scenario(self) -> RiskProfileScenario | None:
        return next((s for s in self.scenarios if s.is_primary), None)

    def thresholds_for(self, parameter: RiskProfileParameter) -> InternalThresholds | None:
        if parameter.internal_thresholds:
            return parameter.internal_thresholds
        if self.default_thresholds and parameter.category == "operational":
            dt = self.default_thresholds.yield_parameters
            return InternalThresholds(
                planned_value=0.0,
                unit="ratio",
                elevated_threshold=dt.get("elevated_threshold", 0.85),
                high_threshold=dt.get("high_threshold", 0.75),
                critical_threshold=dt.get("critical_threshold", 0.65),
                threshold_type=dt.get("threshold_type", "ratio"),
            )
        return None


# ─── Internal signal domain objects (v1.2) ───────────────────────────────────

@dataclass
class InternalSignal:
    """Structured signal from MES, QMS, ERP, or capacity tracker. Rule-engine assessed."""
    id: str
    signal_type: str
    # Supported signal_type values:
    #   "step_yield"           — actual/planned yield ratio for a process step
    #   "batch_failure_rate"   — % of batches failing quality release
    #   "po_delivery_exception"— PO delivery delay in weeks
    #   "sdd_global_fraction"  — our % of global SDD capacity
    #   "sdd_facility_util"    — our % of a named SDD facility capacity
    source_system: str  # "mes" | "qms" | "erp" | "capacity_tracker"
    parameter_id: str
    scenario_id: str
    actual_value: float
    planned_value: float
    unit: str
    measurement_timestamp: str
    context: dict = field(default_factory=dict)


# ─── Multi-scenario comparator (v1.2) ────────────────────────────────────────

@dataclass
class ScenarioImpact:
    scenario_id: str
    scenario_name: str
    is_primary: bool
    qualitative_impact: str  # "HIGH" | "MEDIUM" | "LOW" | "UNKNOWN"
    cost_delta_per_kg: float | None
    timeline_impact_weeks: float | None
    data_source: str  # "mrp" | "rule_engine" | "estimated"
    notes: str | None = None


@dataclass
class SignalState:
    parameter_name: str
    last_updated_at: str
    last_signal_source: str | None
    current_state_summary: str
    baseline_value: float | None
    baseline_value_unit: str | None
    last_known_change_direction: str | None
    risk_level: str
    source_url: str | None


@dataclass
class ActionResult:
    action_type: ActionType
    success: bool
    output_file: Path | None
    summary: str
    error: str | None = None


@dataclass
class RunResult:
    mode: str
    started_at: str
    completed_at: str
    signals_collected: int
    signals_relevant: int
    signals_novel: int
    signals_by_severity: dict[str, int]
    actions_taken: list[ActionResult]
    output_dir: Path


@dataclass
class CorpusLabel:
    signal_id: str
    expected_is_relevant: bool
    expected_is_novel: bool
    expected_severity: SeverityTier | None
    expected_risk_vector: RiskVectorType | None
    notes: str | None = None


@dataclass
class EvalMetrics:
    precision: float
    recall: float
    f1: float
    n_total: int
    n_correct: int
    confusion: dict


@dataclass
class EvalReport:
    prompt_versions: dict[str, str]
    relevance_metrics: EvalMetrics
    novelty_metrics: EvalMetrics
    severity_metrics: EvalMetrics
    severity_per_class: dict[str, EvalMetrics]
    worst_cases: list[dict]
    total_llm_calls: int
    total_cost_estimate_usd: float
    elapsed_sec: float
