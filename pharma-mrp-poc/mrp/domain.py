from __future__ import annotations
from dataclasses import dataclass, field
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
