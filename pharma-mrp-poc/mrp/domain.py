from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from pint import Quantity


class MaterialType(str, Enum):
    STARTING_MATERIAL = "starting_material"
    REAGENT = "reagent"
    CATALYST = "catalyst"
    SOLVENT = "solvent"
    CONSUMABLE = "consumable"
    AUXILIARY = "auxiliary"

class StepMaterialRole(str, Enum):
    LIMITING_REAGENT = "limiting_reagent"
    REAGENT = "reagent"
    CATALYST = "catalyst"
    SOLVENT = "solvent"
    WASH_SOLVENT = "wash_solvent"

class CanonicalUnit(str, Enum):
    KG = "kg"
    LITRE = "L"
    EACH = "each"

class SweepMode(str, Enum):
    CARTESIAN = "cartesian"
    ONE_AT_A_TIME = "one_at_a_time"
    NAMED_LIST = "named_list"

class DistributionType(str, Enum):
    NORMAL = "normal"
    LOGNORMAL = "lognormal"
    UNIFORM = "uniform"
    TRIANGULAR = "triangular"
    PERT = "pert"
    BETA = "beta"
    FIXED = "fixed"

class ParameterType(str, Enum):
    STEP_YIELD = "step_yield"
    MATERIAL_PRICE = "material_price"
    BATCH_SIZE = "batch_size"
    NUM_BATCHES = "num_batches"
    MATERIAL_EQUIVALENTS = "material_equivalents"
    MATERIAL_EXCESS = "material_excess"


@dataclass
class Material:
    name: str
    material_type: MaterialType
    canonical_unit: CanonicalUnit
    cas_number: str | None = None
    molecular_weight: Quantity | None = None

@dataclass
class StepMaterial:
    material: Material
    role: StepMaterialRole
    excess_pct: float = 0.0
    equivalents: float | None = None
    volume_ratio: Quantity | None = None
    catalyst_mol_pct: float | None = None

    def __post_init__(self):
        set_count = sum([
            self.equivalents is not None,
            self.volume_ratio is not None,
            self.catalyst_mol_pct is not None,
        ])
        if set_count != 1:
            raise ValueError(
                f"Material '{self.material.name}': exactly one of equivalents, "
                f"volume_ratio, or catalyst_mol_pct must be set; got {set_count}"
            )

@dataclass
class EquipmentCost:
    name: str
    cost_per_batch: float
    currency: str = "USD"

@dataclass
class LaborCost:
    role: str
    hours_per_batch: float
    rate_per_hour: float
    currency: str = "USD"

@dataclass
class UtilityCost:
    utility_type: str
    quantity_per_batch: float
    unit: str
    cost_per_unit: float
    currency: str = "USD"

@dataclass
class Step:
    id: str
    name: str
    step_yield_pct: float
    output_name: str
    output_mw: Quantity | None = None
    theoretical_yield_pct: float = 100.0
    gmp_step: bool = False
    reaction_type: str | None = None
    materials: list[StepMaterial] = field(default_factory=list)
    equipment_costs: list[EquipmentCost] = field(default_factory=list)
    labor_costs: list[LaborCost] = field(default_factory=list)
    utility_costs: list[UtilityCost] = field(default_factory=list)

    def limiting_material(self) -> StepMaterial:
        lims = [m for m in self.materials if m.role == StepMaterialRole.LIMITING_REAGENT]
        if len(lims) != 1:
            raise ValueError(
                f"Step '{self.name}': exactly one LIMITING_REAGENT required; found {len(lims)}"
            )
        return lims[0]

@dataclass
class Edge:
    from_step_id: str | None
    to_step_id: str | None
    intermediate_name: str = ""
    is_terminal: bool = False

@dataclass
class ProcessGraph:
    name: str
    target_api_name: str
    steps: dict[str, Step]
    edges: list[Edge]
    target_api_cas: str | None = None
    description: str | None = None

    def topological_order(self) -> list[str]:
        from collections import deque
        in_degree: dict[str, int] = {sid: 0 for sid in self.steps}
        adjacency: dict[str, list[str]] = {sid: [] for sid in self.steps}

        for edge in self.edges:
            if edge.from_step_id is not None and edge.to_step_id is not None:
                adjacency[edge.from_step_id].append(edge.to_step_id)
                in_degree[edge.to_step_id] += 1

        queue = deque(sid for sid, deg in in_degree.items() if deg == 0)
        order: list[str] = []
        while queue:
            node = queue.popleft()
            order.append(node)
            for neighbour in adjacency[node]:
                in_degree[neighbour] -= 1
                if in_degree[neighbour] == 0:
                    queue.append(neighbour)

        if len(order) != len(self.steps):
            raise ValueError("Process graph contains a cycle — not a valid DAG")
        return order

    def upstream_steps(self, step_id: str) -> list[str]:
        return [
            e.from_step_id for e in self.edges
            if e.to_step_id == step_id and e.from_step_id is not None
        ]

    def is_convergent(self) -> bool:
        return any(len(self.upstream_steps(sid)) > 1 for sid in self.steps)

    def validate(self) -> list[str]:
        errors: list[str] = []
        try:
            order = self.topological_order()
        except ValueError as e:
            errors.append(str(e))
            return errors

        terminals = [e for e in self.edges if e.is_terminal]
        if len(terminals) != 1:
            errors.append(f"Process must have exactly 1 terminal edge; found {len(terminals)}")

        for sid in self.steps:
            step = self.steps[sid]
            if self.upstream_steps(sid) == [] and not any(
                e.from_step_id is None and e.to_step_id == sid for e in self.edges
            ):
                errors.append(f"Step '{sid}' has no incoming edges and no entry edge")

            lims = [m for m in step.materials if m.role == StepMaterialRole.LIMITING_REAGENT]
            if len(lims) != 1:
                errors.append(
                    f"Step '{sid}' has {len(lims)} LIMITING_REAGENT materials; exactly 1 required"
                )

            for sm in step.materials:
                if sm.equivalents is not None and sm.material.molecular_weight is None:
                    errors.append(
                        f"Step '{sid}', material '{sm.material.name}': "
                        f"molecular_weight required when equivalents is set"
                    )
                if sm.catalyst_mol_pct is not None and sm.material.molecular_weight is None:
                    errors.append(
                        f"Step '{sid}', material '{sm.material.name}': "
                        f"molecular_weight required when catalyst_mol_pct is set"
                    )

            if not (0.0 < step.step_yield_pct <= 100.0):
                errors.append(
                    f"Step '{sid}': step_yield_pct must be in (0, 100]; got {step.step_yield_pct}"
                )

        return errors


@dataclass
class PriceEntry:
    name: str
    price_per_unit: float
    unit: str
    currency: str = "USD"
    vendor: str | None = None
    lead_time_days: int | None = None
    min_order_qty: float | None = None

@dataclass
class PriceList:
    name: str
    currency: str
    material_prices: dict[str, PriceEntry]
    labor_rates: dict[str, float]
    utility_rates: dict[str, float]

    def get_material_price(self, name: str) -> PriceEntry | None:
        return self.material_prices.get(name.lower())

@dataclass
class ProcessConfig:
    batch_size: Quantity
    num_batches: int


@dataclass
class SweepParameter:
    param_type: ParameterType
    target_id: str
    label: str
    values: list[float]
    baseline: float
    unit: str

@dataclass
class SweepDefinition:
    name: str
    mode: SweepMode
    parameters: list[SweepParameter]
    base_config: ProcessConfig

@dataclass
class DistributionSpec:
    param_type: ParameterType
    target_id: str
    label: str
    distribution: DistributionType
    unit: str
    params: dict[str, float]
    clip_low: float | None = None
    clip_high: float | None = None

@dataclass
class CorrelationPair:
    label_a: str
    label_b: str
    pearson_r: float

@dataclass
class MCDefinition:
    name: str
    n_iterations: int
    distributions: list[DistributionSpec]
    base_config: ProcessConfig
    correlations: list[CorrelationPair] = field(default_factory=list)
    random_seed: int | None = None


@dataclass
class MaterialLine:
    step_id: str
    step_name: str
    material_name: str
    role: str
    quantity: Quantity
    unit_cost: float
    total_cost: float
    currency: str
    gmp_step: bool

@dataclass
class StepCostSummary:
    step_id: str
    step_name: str
    step_yield_pct: float
    required_output: Quantity
    required_input: Quantity
    material_cost: float
    equipment_cost: float
    labor_cost: float
    utility_cost: float
    total_cost: float
    gmp_step: bool

@dataclass
class BoMResult:
    process_name: str
    config: ProcessConfig
    price_list_name: str
    overall_route_yield_pct: float
    step_summaries: list[StepCostSummary]
    material_lines: list[MaterialLine]
    total_material_cost: float
    total_equipment_cost: float
    total_labor_cost: float
    total_utility_cost: float
    total_cost: float
    cost_per_kg_api: float
    currency: str

@dataclass
class ScenarioResult:
    scenario_label: str
    parameter_values: dict[str, float]
    cost_per_kg_api: float
    total_cost: float
    total_material_cost: float
    total_equipment_cost: float
    total_labor_cost: float
    total_utility_cost: float
    overall_route_yield_pct: float
    status: str
    error: str | None = None

@dataclass
class MCResult:
    iteration: int
    sampled_inputs: dict[str, float]
    cost_per_kg_api: float
    total_cost: float
    total_material_cost: float
    total_equipment_cost: float
    total_labor_cost: float
    total_utility_cost: float
    overall_route_yield_pct: float
    status: str
    error: str | None = None


# ---------------------------------------------------------------------------
# CapEx & Plant Network domain objects (v1.2)
# ---------------------------------------------------------------------------

class DepreciationMethod(str, Enum):
    STRAIGHT_LINE = "straight_line"
    DECLINING_BALANCE = "declining_balance"
    DOUBLE_DECLINING = "double_declining"
    UNITS_OF_PRODUCTION = "units_of_production"

class MaintenanceType(str, Enum):
    FIXED_ANNUAL = "fixed_annual"
    PCT_OF_CAPEX = "pct_of_capex"
    PER_BATCH = "per_batch"


@dataclass
class MaintenanceSchedule:
    maintenance_type: MaintenanceType
    value: float
    currency: str = "USD"
    description: str = ""


@dataclass
class StepAssetAssignment:
    step_id: str
    allocation_pct: float = 100.0


@dataclass
class PlantAsset:
    id: str
    plant_id: str
    name: str
    asset_class: str
    capex_cost: float
    useful_life_years: float
    salvage_value: float
    depreciation_method: DepreciationMethod
    gmp_qualified: bool = False
    purchase_date: date | None = None
    declining_balance_rate: float | None = None
    total_expected_batches: int | None = None
    step_assignments: list[StepAssetAssignment] = field(default_factory=list)
    maintenance_schedules: list[MaintenanceSchedule] = field(default_factory=list)


@dataclass
class CapacityUtilisationBand:
    label: str
    utilisation_lower_pct: float
    utilisation_upper_pct: float
    labor_cost_multiplier: float = 1.0
    utility_cost_multiplier: float = 1.0


@dataclass
class Plant:
    id: str
    name: str
    currency: str
    annual_capacity_kg_api: float
    gmp_facility: bool = False
    location: str | None = None
    commissioned_date: date | None = None
    decommission_date: date | None = None
    assets: list[PlantAsset] = field(default_factory=list)
    utilisation_bands: list[CapacityUtilisationBand] = field(default_factory=list)

    def total_capex(self) -> float:
        return sum(a.capex_cost for a in self.assets)

    def effective_annual_capacity_kg(self) -> float:
        return self.annual_capacity_kg_api

    def variable_cost_multipliers(self, utilisation_pct: float) -> tuple[float, float]:
        bands = sorted(self.utilisation_bands, key=lambda b: b.utilisation_lower_pct)
        for band in bands:
            if band.utilisation_lower_pct <= utilisation_pct < band.utilisation_upper_pct:
                return band.labor_cost_multiplier, band.utility_cost_multiplier
        if bands:
            return bands[-1].labor_cost_multiplier, bands[-1].utility_cost_multiplier
        return 1.0, 1.0


@dataclass
class NetworkPlantMembership:
    plant_id: str
    volume_allocation_kg: float
    start_year: int | None = None
    end_year: int | None = None


@dataclass
class VolumeTarget:
    year: int
    volume_kg_api: float


@dataclass
class PlantNetwork:
    id: str
    name: str
    currency: str
    plants: list[NetworkPlantMembership] = field(default_factory=list)
    volume_targets: list[VolumeTarget] = field(default_factory=list)
    description: str = ""


@dataclass
class DepreciationYear:
    year_index: int
    opening_book_value: float
    annual_charge: float
    closing_book_value: float
    method: str


@dataclass
class BoMResultWithCapEx:
    bom: BoMResult
    plant_name: str
    analysis_year: int
    batches_produced: int
    utilisation_pct: float
    active_band_label: str
    adjusted_labor_cost: float
    adjusted_utility_cost: float
    total_depreciation_cost: float
    total_maintenance_cost: float
    total_variable_cost: float
    total_fixed_cost: float
    total_cogs: float
    cogs_per_kg_api: float
    fixed_cost_per_kg_api: float
    variable_cost_per_kg_api: float
    breakeven_kg_api: float | None
    currency: str


@dataclass
class PlantYearResult:
    plant_id: str
    plant_name: str
    year: int
    allocated_volume_kg: float
    utilisation_pct: float
    total_depreciation: float
    total_maintenance: float
    total_variable_cost: float
    total_fixed_cost: float
    total_cogs: float
    cogs_per_kg_api: float


@dataclass
class NetworkYearSummary:
    year: int
    total_volume_kg: float
    total_cogs: float
    network_cogs_per_kg_api: float
    total_variable_cost: float = 0.0
    total_fixed_cost: float = 0.0
    volume_gap_kg: float = 0.0
    plant_results: list[PlantYearResult] = field(default_factory=list)


@dataclass
class NetworkAnalysisResult:
    network_name: str
    currency: str
    year_summaries: list[NetworkYearSummary] = field(default_factory=list)
    total_network_capex: float = 0.0


@dataclass
class MinimumNetworkResult:
    required_capacity_kg: float
    best_plant_ids: list[str]
    best_plant_names: list[str]
    total_capex: float
    total_capacity_kg: float
    n_evaluated: int
    meets_target: bool = True


@dataclass
class NetworkBreakevenResult:
    plant_id: str
    plant_name: str
    fixed_cost_annual: float
    variable_cost_per_kg: float
    breakeven_kg_api: float | None
    currency: str


# ─── Supply chain risk domain objects (NEW — v1.3) ────────────────────────────

class RiskVectorType(str, Enum):
    TARIFF_ESCALATION = "tariff_escalation"
    CDMO_REMOVAL = "cdmo_removal"
    YIELD_DISRUPTION = "yield_disruption"
    LEAD_TIME_EXTENSION = "lead_time_extension"

class StepCriticality(str, Enum):
    STANDARD = "standard"
    CRITICAL = "critical"
    SOLE_SOURCE_STEP = "sole_source_step"

@dataclass
class CDMONode:
    id: str
    name: str
    country: str
    city: str | None = None
    biosecure_act_listed: bool = False
    pentagon_1260h_listed: bool = False
    regulatory_watch_flags: list[str] = field(default_factory=list)
    notes: str | None = None

@dataclass
class RiskVector:
    id: str
    name: str
    risk_vector_type: RiskVectorType
    tariff_rate_pct: float | None = None
    geography: str | None = None
    include_indirect: bool = False
    cdmo_node_id: str | None = None
    emergency_premium_pct: float = 50.0
    target_step_name: str | None = None
    target_material_name: str | None = None
    yield_reduction_pct: float | None = None
    lead_time_extension_weeks: float | None = None

@dataclass
class MaterialRiskMetadata:
    material_name: str
    country_of_origin: str | None = None
    cdmo_node_id: str | None = None
    single_source: bool = False
    alternative_supplier_lead_time_weeks: int | None = None
    indirect_china_exposure: bool = False
    indirect_china_exposure_notes: str | None = None
    tariff_hs_code: str | None = None

@dataclass
class StepRiskMetadata:
    step_name: str
    cdmo_node_id: str | None = None
    step_criticality: StepCriticality = StepCriticality.STANDARD

@dataclass
class RiskProfile:
    name: str
    cdmo_nodes: dict[str, CDMONode]
    material_risk: dict[str, MaterialRiskMetadata]
    step_risk: dict[str, StepRiskMetadata]
    risk_vectors: list[RiskVector]
    tariff_sweep_rates: list[float] = field(default_factory=list)
    tariff_sweep_geography: str | None = None
    tariff_sweep_include_indirect: bool = False

@dataclass
class SensitivityLine:
    rank: int
    parameter_name: str
    parameter_type: str
    sensitivity_cost_per_unit: float
    sensitivity_unit: str
    country_of_origin: str | None
    cdmo_node_name: str | None
    is_single_source: bool
    is_indirect_china: bool
    timeline_impact_weeks: float | None
    tariff_impact_at_rate: float | None
    risk_flags: list[str]
    notes: str | None = None

@dataclass
class TariffOverlayResult:
    tariff_rate_pct: float
    geography: str
    include_indirect: bool
    base_cost_per_kg_api: float
    tariff_cost_total: float
    adjusted_cost_per_kg_api: float
    cost_per_kg_delta: float
    exposed_material_lines: list[dict]

@dataclass
class CDMORemovalResult:
    cdmo_node_name: str
    biosecure_act_listed: bool
    affected_step_names: list[str]
    affected_material_names: list[str]
    base_cost_per_kg_api: float
    emergency_cost_per_kg_api: float
    cost_per_kg_delta: float
    timeline_critical_path_weeks: float | None
    timeline_unknown_materials: list[str]
    requalification_notes: str | None

@dataclass
class SensitivityReport:
    scenario_name: str
    process_name: str
    generated_at: str
    base_cost_per_kg_api: float
    currency: str
    china_origin_cost_pct: float
    indirect_china_cost_pct: float
    single_source_cost_pct: float
    cdmo_exposed_cost_pct: float
    sensitivity_lines: list[SensitivityLine]
    tariff_sweep_results: list[TariffOverlayResult]
    cdmo_removal_results: list[CDMORemovalResult]
    generation_time_sec: float
