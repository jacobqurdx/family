"""
SchemaRegistry: loads document schemas from JSON files, validates them,
and provides dependency ordering for guided authoring.

Schemas are organised in subdirectories matching the twin tier hierarchy:
  data/schemas/company/   — company-tier schemas
  data/schemas/molecule/  — molecule-tier schemas (protocol, IND)
  data/schemas/trial/     — trial-tier schemas (IB, ICF, CSR)

For backward compatibility, schemas in the root schemas directory are
also loaded (no tier subdirectory required).
"""
from pathlib import Path
import json
import networkx as nx
from core.models import (
    DocumentSchema, SchemaElement, DependencyType,
    TwinTier, IncrementalPopulationPlan,
)
import config


class SchemaRegistry:
    def __init__(self):
        self._schemas: dict[str, DocumentSchema] = {}
        self._load_all()

    def _load_all(self):
        schema_dir = Path(config.SCHEMAS_DIR)
        # Load from all subdirectories (tier-organised) and root (legacy)
        for f in schema_dir.rglob("*.json"):
            try:
                raw = json.loads(f.read_text())
                schema = DocumentSchema(**raw)
                self._schemas[schema.id] = schema
            except Exception:
                pass  # skip malformed files

    def list_schemas(self) -> list[str]:
        return list(self._schemas.keys())

    def list_by_tier(self, tier: TwinTier) -> list[str]:
        """Returns schema IDs belonging to the specified twin tier."""
        return [sid for sid, s in self._schemas.items() if s.tier == tier]

    def get(self, schema_id: str) -> DocumentSchema:
        if schema_id not in self._schemas:
            raise KeyError(f"Schema '{schema_id}' not found")
        return self._schemas[schema_id]

    def get_element(self, schema_id: str, element_id: str) -> SchemaElement:
        schema = self.get(schema_id)
        for el in schema.elements:
            if el.id == element_id:
                return el
        raise KeyError(f"Element '{element_id}' not found in schema '{schema_id}'")

    def get_authoring_order(self, schema_id: str) -> list[SchemaElement]:
        """
        Returns elements in topological order — foundational elements
        (no dependencies) first. This is the guided authoring sequence.
        """
        schema = self.get(schema_id)
        G = nx.DiGraph()
        for el in schema.elements:
            G.add_node(el.id)
        for el in schema.elements:
            for dep in el.depends_on:
                G.add_edge(dep, el.id)
        ordered_ids = list(nx.topological_sort(G))
        element_map = {el.id: el for el in schema.elements}
        return [element_map[eid] for eid in ordered_ids if eid in element_map]

    def get_leaf_elements(self, schema_id: str) -> list[SchemaElement]:
        """Elements with no upstream dependencies — authoring starting points."""
        schema = self.get(schema_id)
        return [el for el in schema.elements if not el.depends_on]

    def validate_schema(self, schema: DocumentSchema) -> list[str]:
        """Returns list of validation errors. Empty list = valid."""
        errors = []
        element_ids = {el.id for el in schema.elements}
        for el in schema.elements:
            for dep in el.depends_on:
                if dep not in element_ids:
                    errors.append(f"Element '{el.id}' depends on unknown element '{dep}'")
        G = nx.DiGraph()
        for el in schema.elements:
            for dep in el.depends_on:
                G.add_edge(dep, el.id)
        if not nx.is_directed_acyclic_graph(G):
            errors.append("Schema dependency graph contains a cycle")
        return errors

    def get_population_plan(
        self, schema_id: str, twin_id: str, twin
    ) -> IncrementalPopulationPlan:
        """
        Returns an IncrementalPopulationPlan for the given schema and twin.
        Identifies which required elements are already populated, need collection,
        or can be inherited from a parent twin.
        """
        schema = self.get(schema_id)
        required = [el.id for el in schema.elements if el.required]
        already_populated = [eid for eid in required if twin.get_value(eid) is not None]
        inherited = [
            eid for eid in required
            if twin.get(eid) and twin.get(eid).source
            and twin.get(eid).source.startswith("inherited:")
        ]
        needs_collection = [eid for eid in required if eid not in already_populated]
        return IncrementalPopulationPlan(
            document_type=schema_id,
            twin_id=twin_id,
            required_elements=required,
            already_populated=already_populated,
            needs_collection=needs_collection,
            inherited_from_parent=inherited,
        )

    def add_element(self, schema_id: str, element: SchemaElement):
        """Extends a schema with a new element. Persists to disk."""
        schema = self.get(schema_id)
        schema.elements.append(element)
        self._persist(schema_id)

    def _persist(self, schema_id: str):
        schema = self.get(schema_id)
        # Write to tier subdirectory if tier is set, else root
        tier_dir = Path(config.SCHEMAS_DIR) / schema.tier.value
        tier_dir.mkdir(parents=True, exist_ok=True)
        path = tier_dir / f"{schema_id}.json"
        path.write_text(schema.model_dump_json(indent=2))
