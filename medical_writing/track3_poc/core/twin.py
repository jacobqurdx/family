"""
DigitalTwin: the authoritative structured representation of a program or trial.

Three-tier hierarchy:
  Company twin  ←  Molecule twin  ←  Trial twin
  (Structure Th.)  (aleniglipron)     (ACCESS II)

Inheritance: a trial twin pulls verified elements from its molecule twin;
the molecule twin may pull from the company twin. Inherited values are
available for generation without re-entry.
"""
from pathlib import Path
import json
import datetime
from core.models import DigitalTwinRecord, TwinElement, ElementStatus, TwinTier
import config


class DigitalTwin:
    def __init__(self, record: DigitalTwinRecord):
        self._record = record

    @classmethod
    def load(cls, twin_id: str) -> "DigitalTwin":
        path = Path(config.TWINS_DIR) / f"{twin_id}.json"
        raw = json.loads(path.read_text())
        return cls(DigitalTwinRecord(**raw))

    @classmethod
    def new(
        cls, twin_id: str, schema_id: str, program_name: str = "",
        tier: TwinTier = TwinTier.TRIAL,
        trial_name: str = None,
        parent_twin_id: str = None,
    ) -> "DigitalTwin":
        record = DigitalTwinRecord(
            twin_id=twin_id,
            schema_id=schema_id,
            tier=tier,
            program_name=program_name,
            trial_name=trial_name,
            parent_twin_id=parent_twin_id,
        )
        return cls(record)

    def save(self):
        path = Path(config.TWINS_DIR) / f"{self._record.twin_id}.json"
        path.write_text(self._record.model_dump_json(indent=2))

    # ── Properties ────────────────────────────────────────────────────────────

    @property
    def schema_id(self) -> str:
        return self._record.schema_id

    @property
    def tier(self) -> TwinTier:
        return self._record.tier

    @property
    def program_name(self) -> str:
        return self._record.program_name

    @property
    def trial_name(self) -> str:
        return self._record.trial_name or self._record.program_name

    @property
    def parent_twin_id(self) -> str:
        return self._record.parent_twin_id

    @property
    def twin_id(self) -> str:
        return self._record.twin_id

    # ── Element access ────────────────────────────────────────────────────────

    def get(self, element_id: str) -> "TwinElement | None":
        return self._record.elements.get(element_id)

    def get_value(self, element_id: str):
        el = self.get(element_id)
        return el.value if el else None

    def set(self, element_id: str, value, source: str = "user",
            status: ElementStatus = ElementStatus.VERIFIED,
            modified_by: str = "user"):
        el = TwinElement(
            element_id=element_id,
            value=value,
            status=status,
            source=source,
            last_modified=datetime.datetime.utcnow(),
            modified_by=modified_by
        )
        self._record.elements[element_id] = el

    def set_inferred(self, element_id: str, value, source_element: str):
        """Marks an element as inferred — needs human verification."""
        el = TwinElement(
            element_id=element_id,
            value=value,
            status=ElementStatus.INFERRED,
            source=f"inferred_from:{source_element}",
            last_modified=datetime.datetime.utcnow(),
            modified_by="system"
        )
        self._record.elements[element_id] = el

    def set_inherited(self, element_id: str, value, parent_twin_id: str):
        """
        Marks an element as inherited from a parent twin.
        Inherited values are available for generation but sourced from a higher tier.
        """
        el = TwinElement(
            element_id=element_id,
            value=value,
            status=ElementStatus.VERIFIED,
            source=f"inherited:{parent_twin_id}",
            last_modified=datetime.datetime.utcnow(),
            modified_by="system"
        )
        self._record.elements[element_id] = el

    def override(self, element_id: str, value, justification: str, modified_by: str):
        el = TwinElement(
            element_id=element_id,
            value=value,
            status=ElementStatus.OVERRIDDEN,
            source="user_override",
            override_justification=justification,
            last_modified=datetime.datetime.utcnow(),
            modified_by=modified_by
        )
        self._record.elements[element_id] = el

    # ── Hierarchy operations ──────────────────────────────────────────────────

    def inherit_from_parent(self, parent: "DigitalTwin", element_ids: list = None):
        """
        Pull verified elements from a parent twin into this twin as inherited values.
        If element_ids is None, inherits all verified elements from the parent.
        Does not overwrite elements already set in this twin.
        """
        for eid, el in parent.get_all().items():
            if element_ids and eid not in element_ids:
                continue
            if self.get_value(eid) is not None:
                continue  # don't overwrite existing values
            if el.status == ElementStatus.VERIFIED and el.value is not None:
                self.set_inherited(eid, el.value, parent.twin_id)

    # ── Query ─────────────────────────────────────────────────────────────────

    def get_all(self) -> dict:
        return dict(self._record.elements)

    def get_section_data(self, source_elements: list) -> dict:
        """Returns snapshot of element values needed for a prose section."""
        return {eid: self.get_value(eid) for eid in source_elements}

    def diff(self, other: "DigitalTwin") -> list:
        """
        Compares two twins element-by-element.
        Returns list of {element_id, twin_a_value, twin_b_value} for differing elements.
        """
        diffs = []
        all_ids = set(self._record.elements.keys()) | set(other._record.elements.keys())
        for eid in all_ids:
            v1 = self.get_value(eid)
            v2 = other.get_value(eid)
            if v1 != v2:
                diffs.append({
                    "element_id": eid,
                    "twin_a": self._record.twin_id,
                    "twin_b": other._record.twin_id,
                    "value_a": v1,
                    "value_b": v2
                })
        return diffs

    def completeness(self, required_elements: list) -> dict:
        """Returns completeness stats including inherited element count."""
        total = len(required_elements)
        populated = sum(1 for eid in required_elements if self.get_value(eid) is not None)
        verified = sum(
            1 for eid in required_elements
            if self.get(eid) and self.get(eid).status == ElementStatus.VERIFIED
        )
        inherited = sum(
            1 for eid in required_elements
            if self.get(eid) and self.get(eid).source
            and self.get(eid).source.startswith("inherited:")
        )
        return {
            "total": total,
            "populated": populated,
            "verified": verified,
            "inherited": inherited,
            "completeness_pct": round(populated / total * 100, 1) if total else 0,
            "verification_pct": round(verified / total * 100, 1) if total else 0,
            "inherited_pct": round(inherited / total * 100, 1) if total else 0,
        }
