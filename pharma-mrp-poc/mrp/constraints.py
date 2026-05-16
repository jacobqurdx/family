from dataclasses import dataclass
from typing import Callable
from mrp.domain import BoMResult

@dataclass(frozen=True)
class ConstraintDefinition:
    name: str
    description: str
    unit: str
    extractor_bom: Callable[[BoMResult], float]
    hard_lower: float | None
    hard_upper: float | None

CONSTRAINT_REGISTRY: dict[str, ConstraintDefinition] = {
    "cost_per_kg_api": ConstraintDefinition(
        name="cost_per_kg_api",
        description="Total cost / kg API",
        unit="USD/kg",
        extractor_bom=lambda b: b.cost_per_kg_api,
        hard_lower=0.0, hard_upper=None,
    ),
    "total_cost": ConstraintDefinition(
        name="total_cost",
        description="Total campaign cost",
        unit="USD",
        extractor_bom=lambda b: b.total_cost,
        hard_lower=0.0, hard_upper=None,
    ),
    "overall_route_yield_pct": ConstraintDefinition(
        name="overall_route_yield_pct",
        description="Product of all step yields",
        unit="%",
        extractor_bom=lambda b: b.overall_route_yield_pct,
        hard_lower=0.0, hard_upper=100.0,
    ),
    "total_material_cost": ConstraintDefinition(
        name="total_material_cost",
        description="Total material cost",
        unit="USD",
        extractor_bom=lambda b: b.total_material_cost,
        hard_lower=0.0, hard_upper=None,
    ),
}

class ConstraintRegistryError(ValueError):
    pass

class InfeasibleConstraintError(ValueError):
    pass

def validate_constraint(metric: str, operator: str, value: float) -> None:
    if metric not in CONSTRAINT_REGISTRY:
        raise ConstraintRegistryError(
            f"Unknown metric '{metric}'. Registered: {list(CONSTRAINT_REGISTRY)}"
        )
    if operator not in ("<=", ">=", "=="):
        raise ConstraintRegistryError(f"Operator must be '<=', '>=', or '=='; got '{operator}'")
    defn = CONSTRAINT_REGISTRY[metric]
    if operator in (">=", "==") and defn.hard_upper is not None and value > defn.hard_upper:
        raise InfeasibleConstraintError(
            f"'{metric}' cannot be >= {value}; physical maximum is {defn.hard_upper}"
        )
    if operator in ("<=", "==") and defn.hard_lower is not None and value < defn.hard_lower:
        raise InfeasibleConstraintError(
            f"'{metric}' cannot be <= {value}; physical minimum is {defn.hard_lower}"
        )
