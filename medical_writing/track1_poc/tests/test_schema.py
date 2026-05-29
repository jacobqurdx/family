import pytest
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.schema import SchemaRegistry
from core.models import SchemaElement, DependencyType


@pytest.fixture
def registry():
    return SchemaRegistry()


def test_load_all_schemas(registry):
    schema_ids = registry.list_schemas()
    assert len(schema_ids) >= 3
    assert "protocol" in schema_ids
    assert "icf" in schema_ids
    assert "investigator_brochure" in schema_ids


def test_validate_no_errors(registry):
    for sid in registry.list_schemas():
        errors = registry.validate_schema(registry.get(sid))
        assert errors == [], f"Schema '{sid}' has errors: {errors}"


def test_topological_order_leaves_first(registry):
    ordered = registry.get_authoring_order("protocol")
    ids = [el.id for el in ordered]

    for el in ordered:
        for dep in el.depends_on:
            assert ids.index(dep) < ids.index(el.id), (
                f"Dependency '{dep}' appears after '{el.id}' in authoring order"
            )


def test_leaf_elements_have_no_dependencies(registry):
    leaves = registry.get_leaf_elements("protocol")
    for el in leaves:
        assert el.depends_on == []


def test_get_element(registry):
    el = registry.get_element("protocol", "primary_endpoint")
    assert el.id == "primary_endpoint"
    assert el.data_type == "string"


def test_get_element_not_found(registry):
    with pytest.raises(KeyError):
        registry.get_element("protocol", "nonexistent_element")


def test_schema_extension_adds_element(registry, tmp_path, monkeypatch):
    import config
    import shutil

    # Point schemas dir to a temp copy so we don't modify real data
    tmp_schemas = tmp_path / "schemas"
    shutil.copytree(Path(config.SCHEMAS_DIR), tmp_schemas)
    monkeypatch.setattr(config, "SCHEMAS_DIR", str(tmp_schemas))

    reg2 = SchemaRegistry()
    new_el = SchemaElement(
        id="followup_duration_weeks",
        label="Follow-up Duration (weeks)",
        description="Length of the safety follow-up in weeks",
        data_type="number",
        required=False,
        depends_on=["study_duration_weeks"],
        dependency_type=DependencyType.INFORMATIONAL,
    )
    reg2.add_element("protocol", new_el)

    # Re-load and verify persistence
    reg3 = SchemaRegistry()
    ids = [el.id for el in reg3.get("protocol").elements]
    assert "followup_duration_weeks" in ids


def test_cycle_detection(registry):
    from core.models import DocumentSchema, DocumentSection
    cyclic_schema = DocumentSchema(
        id="cyclic_test",
        name="Cyclic Test",
        version="0.1",
        description="Schema with a cycle",
        elements=[
            SchemaElement(id="a", label="A", description="A", data_type="string",
                          depends_on=["b"], dependency_type=DependencyType.REQUIRED),
            SchemaElement(id="b", label="B", description="B", data_type="string",
                          depends_on=["a"], dependency_type=DependencyType.REQUIRED),
        ],
        sections=[]
    )
    errors = registry.validate_schema(cyclic_schema)
    assert any("cycle" in e.lower() for e in errors)
