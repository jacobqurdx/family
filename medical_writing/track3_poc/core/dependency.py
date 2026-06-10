"""
DependencyGraph: propagates changes through the schema dependency graph.
When an element is updated, identifies all downstream elements that may
be affected, checks for violations, and computes inferred values.
"""
import networkx as nx
from core.models import (
    DocumentSchema, DependencyType, DependencyViolation,
    PropagationResult, ElementStatus
)
from core.twin import DigitalTwin


class DependencyGraph:
    def __init__(self, schema: DocumentSchema):
        self._schema = schema
        self._G = nx.DiGraph()
        self._element_map = {el.id: el for el in schema.elements}
        for el in schema.elements:
            self._G.add_node(el.id)
            for dep in el.depends_on:
                self._G.add_edge(dep, el.id)

    def get_downstream(self, element_id: str) -> list[str]:
        """All elements that (directly or transitively) depend on element_id."""
        return list(nx.descendants(self._G, element_id))

    def get_upstream(self, element_id: str) -> list[str]:
        """All elements that element_id (directly or transitively) depends on."""
        return list(nx.ancestors(self._G, element_id))

    def propagate(self, changed_element_id: str, twin: DigitalTwin) -> PropagationResult:
        """
        Called when an element value changes in the twin.
        Returns all affected downstream elements, violations, and inferred updates.
        """
        downstream = self.get_downstream(changed_element_id)
        violations = []
        inferred_updates = {}

        changed_value = twin.get_value(changed_element_id)

        for eid in downstream:
            el = self._element_map.get(eid)
            if not el:
                continue

            current_value = twin.get_value(eid)

            if changed_element_id in el.depends_on:
                dep_type = el.dependency_type

                if dep_type == DependencyType.ENFORCED and current_value is not None:
                    violations.append(DependencyViolation(
                        element_id=eid,
                        upstream_element_id=changed_element_id,
                        dependency_type=dep_type,
                        expected_value=changed_value,
                        actual_value=current_value,
                        message=(
                            f"ENFORCED dependency violated: '{eid}' has value '{current_value}' "
                            f"but upstream '{changed_element_id}' changed to '{changed_value}'. "
                            f"Admin override required."
                        )
                    ))

                elif dep_type == DependencyType.REQUIRED and current_value is not None:
                    violations.append(DependencyViolation(
                        element_id=eid,
                        upstream_element_id=changed_element_id,
                        dependency_type=dep_type,
                        expected_value=changed_value,
                        actual_value=current_value,
                        message=(
                            f"REQUIRED dependency: '{eid}' may need updating after "
                            f"'{changed_element_id}' changed. Acknowledgment required."
                        )
                    ))

            if current_value is None and el.inference_rule:
                inferred = self._infer(eid, twin)
                if inferred is not None:
                    inferred_updates[eid] = inferred

        return PropagationResult(
            changed_element_id=changed_element_id,
            affected_elements=downstream,
            violations=violations,
            inferred_updates=inferred_updates
        )

    def _infer(self, element_id: str, twin: DigitalTwin):
        """
        Applies inference rules to compute a value for element_id from upstream data.
        """
        el = self._element_map.get(element_id)
        if not el or not el.inference_rule:
            return None

        inference_rules = {
            "statistical_analysis_primary": self._infer_stat_analysis_primary,
            "risk_benefit_framing": self._infer_risk_benefit_framing,
            "primary_endpoint_narrative": self._infer_endpoint_narrative,
        }

        rule_fn = inference_rules.get(element_id)
        if rule_fn:
            return rule_fn(twin)
        return None

    def _infer_stat_analysis_primary(self, twin: DigitalTwin):
        endpoint = twin.get_value("primary_endpoint")
        analysis = twin.get_value("primary_analysis_type")
        if endpoint and analysis:
            return f"{analysis} of {endpoint}"
        return None

    def _infer_risk_benefit_framing(self, twin: DigitalTwin):
        indication = twin.get_value("indication")
        endpoint = twin.get_value("primary_endpoint")
        if indication and endpoint:
            return f"Risk-benefit assessment in {indication} using {endpoint} as primary measure"
        return None

    def _infer_endpoint_narrative(self, twin: DigitalTwin):
        endpoint = twin.get_value("primary_endpoint")
        timepoint = twin.get_value("primary_endpoint_timepoint")
        if endpoint and timepoint:
            return f"Change from baseline in {endpoint} at {timepoint}"
        return None

    def check_consistency(self, twin_a: DigitalTwin, twin_b: DigitalTwin) -> list[DependencyViolation]:
        """
        Cross-document consistency check.
        Finds elements that exist in both twins (same schema) with differing values
        where the dependency type is ENFORCED or REQUIRED.
        """
        violations = []
        diffs = twin_a.diff(twin_b)
        for diff in diffs:
            eid = diff["element_id"]
            el = self._element_map.get(eid)
            if not el:
                continue
            if el.dependency_type in (DependencyType.ENFORCED, DependencyType.REQUIRED):
                violations.append(DependencyViolation(
                    element_id=eid,
                    upstream_element_id="cross_document",
                    dependency_type=el.dependency_type,
                    expected_value=diff["value_a"],
                    actual_value=diff["value_b"],
                    message=(
                        f"Cross-document inconsistency in '{eid}': "
                        f"{twin_a.trial_name}='{diff['value_a']}' vs "
                        f"{twin_b.trial_name}='{diff['value_b']}'"
                    )
                ))
        return violations
