"""
SchemaRegistry: loads document schemas from JSON files, validates them,
and provides dependency ordering for guided authoring.
"""
from pathlib import Path
import json
import networkx as nx
from core.models import DocumentSchema, SchemaElement, DependencyType
import config


class SchemaRegistry:
    def __init__(self):
        self._schemas: dict[str, DocumentSchema] = {}
        self._load_all()

    def _load_all(self):
        schema_dir = Path(config.SCHEMAS_DIR)
        for f in schema_dir.glob("*.json"):
            raw = json.loads(f.read_text())
            schema = DocumentSchema(**raw)
            self._schemas[schema.id] = schema

    def list_schemas(self) -> list[str]:
        return list(self._schemas.keys())

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
        Returns elements in topological order — foundational elements first,
        then elements that depend on them. This is the guided authoring sequence.
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
        """Elements with no upstream dependencies — the starting points for authoring."""
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

    def add_element(self, schema_id: str, element: SchemaElement):
        """Extends a schema with a new element. Persists to disk."""
        schema = self.get(schema_id)
        schema.elements.append(element)
        self._persist(schema_id)

    def _persist(self, schema_id: str):
        schema = self.get(schema_id)
        path = Path(config.SCHEMAS_DIR) / f"{schema_id}.json"
        path.write_text(schema.model_dump_json(indent=2))
