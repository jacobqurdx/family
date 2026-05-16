import pytest
from mrp.domain import (
    ProcessGraph, Step, Edge, Material, StepMaterial,
    MaterialType, CanonicalUnit, StepMaterialRole,
)
from mrp.units import parse_molar_mass, ureg


def _make_material(name: str, mw: float = 100.0) -> Material:
    return Material(
        name=name,
        material_type=MaterialType.STARTING_MATERIAL,
        canonical_unit=CanonicalUnit.KG,
        molecular_weight=parse_molar_mass(mw),
    )

def _make_step(step_id: str, name: str, yield_pct: float = 90.0) -> Step:
    mat = _make_material(f"Mat-{step_id}")
    sm = StepMaterial(material=mat, role=StepMaterialRole.LIMITING_REAGENT, equivalents=1.0)
    return Step(
        id=step_id,
        name=name,
        step_yield_pct=yield_pct,
        output_name=f"Product-{step_id}",
        materials=[sm],
    )

def _linear_3step_graph() -> ProcessGraph:
    steps = {
        "step_1": _make_step("step_1", "Step 1"),
        "step_2": _make_step("step_2", "Step 2"),
        "step_3": _make_step("step_3", "Step 3"),
    }
    edges = [
        Edge(from_step_id=None,     to_step_id="step_1"),
        Edge(from_step_id="step_1", to_step_id="step_2", intermediate_name="Product-step_1"),
        Edge(from_step_id="step_2", to_step_id="step_3", intermediate_name="Product-step_2"),
        Edge(from_step_id="step_3", to_step_id=None, is_terminal=True, intermediate_name="Product-step_3"),
    ]
    return ProcessGraph(name="Linear3", target_api_name="API", steps=steps, edges=edges)

def _convergent_graph() -> ProcessGraph:
    frag_a = _make_step("frag_a", "Fragment A")
    frag_b = _make_step("frag_b", "Fragment B")

    # Coupling step has two limiting reagents — adjust for test purposes:
    # use one limiting and one reagent
    mat_a = _make_material("Fragment A Product")
    mat_b = _make_material("Fragment B Product")
    sm_a = StepMaterial(material=mat_a, role=StepMaterialRole.LIMITING_REAGENT, equivalents=1.0)
    sm_b = StepMaterial(material=mat_b, role=StepMaterialRole.REAGENT, equivalents=1.0)
    coupling = Step(
        id="coupling",
        name="Coupling",
        step_yield_pct=80.0,
        output_name="API",
        materials=[sm_a, sm_b],
    )
    steps = {"frag_a": frag_a, "frag_b": frag_b, "coupling": coupling}
    edges = [
        Edge(from_step_id=None,     to_step_id="frag_a"),
        Edge(from_step_id=None,     to_step_id="frag_b"),
        Edge(from_step_id="frag_a", to_step_id="coupling", intermediate_name="Fragment A Product"),
        Edge(from_step_id="frag_b", to_step_id="coupling", intermediate_name="Fragment B Product"),
        Edge(from_step_id="coupling", to_step_id=None, is_terminal=True, intermediate_name="API"),
    ]
    return ProcessGraph(name="Convergent", target_api_name="API", steps=steps, edges=edges)


def test_linear_topological_order():
    graph = _linear_3step_graph()
    order = graph.topological_order()
    assert order == ["step_1", "step_2", "step_3"]

def test_convergent_upstream_steps():
    graph = _convergent_graph()
    ups = graph.upstream_steps("coupling")
    assert set(ups) == {"frag_a", "frag_b"}

def test_is_convergent_true():
    assert _convergent_graph().is_convergent() is True

def test_is_convergent_false():
    assert _linear_3step_graph().is_convergent() is False

def test_cyclic_graph_raises():
    steps = {
        "a": _make_step("a", "A"),
        "b": _make_step("b", "B"),
    }
    edges = [
        Edge(from_step_id=None, to_step_id="a"),
        Edge(from_step_id="a", to_step_id="b", intermediate_name="Pa"),
        Edge(from_step_id="b", to_step_id="a", intermediate_name="Pb"),  # cycle
        Edge(from_step_id="b", to_step_id=None, is_terminal=True),
    ]
    graph = ProcessGraph(name="Cyclic", target_api_name="API", steps=steps, edges=edges)
    with pytest.raises(ValueError, match="cycle"):
        graph.topological_order()

def test_missing_terminal_edge_fails_validation():
    steps = {"step_1": _make_step("step_1", "Step 1")}
    edges = [Edge(from_step_id=None, to_step_id="step_1")]
    graph = ProcessGraph(name="NoTerminal", target_api_name="API", steps=steps, edges=edges)
    errors = graph.validate()
    assert any("terminal" in e.lower() for e in errors)

def test_step_with_zero_limiting_reagents_fails_validation():
    mat = _make_material("mat")
    sm = StepMaterial(material=mat, role=StepMaterialRole.REAGENT, equivalents=1.0)
    step = Step(id="s1", name="S1", step_yield_pct=90.0, output_name="out", materials=[sm])
    steps = {"s1": step}
    edges = [
        Edge(from_step_id=None, to_step_id="s1"),
        Edge(from_step_id="s1", to_step_id=None, is_terminal=True),
    ]
    graph = ProcessGraph(name="NoLim", target_api_name="API", steps=steps, edges=edges)
    errors = graph.validate()
    assert any("LIMITING_REAGENT" in e for e in errors)

def test_step_with_two_limiting_reagents_fails_validation():
    mat1 = _make_material("mat1")
    mat2 = _make_material("mat2")
    sm1 = StepMaterial(material=mat1, role=StepMaterialRole.LIMITING_REAGENT, equivalents=1.0)
    sm2 = StepMaterial(material=mat2, role=StepMaterialRole.LIMITING_REAGENT, equivalents=1.0)
    step = Step(id="s1", name="S1", step_yield_pct=90.0, output_name="out", materials=[sm1, sm2])
    steps = {"s1": step}
    edges = [
        Edge(from_step_id=None, to_step_id="s1"),
        Edge(from_step_id="s1", to_step_id=None, is_terminal=True),
    ]
    graph = ProcessGraph(name="TwoLim", target_api_name="API", steps=steps, edges=edges)
    errors = graph.validate()
    assert any("LIMITING_REAGENT" in e for e in errors)

def test_missing_mw_on_equivalents_material_fails_validation():
    mat_lim = _make_material("lim", mw=100.0)
    mat_no_mw = Material(
        name="no-mw",
        material_type=MaterialType.REAGENT,
        canonical_unit=CanonicalUnit.KG,
        molecular_weight=None,
    )
    sm_lim = StepMaterial(material=mat_lim, role=StepMaterialRole.LIMITING_REAGENT, equivalents=1.0)
    sm_no  = StepMaterial(material=mat_no_mw, role=StepMaterialRole.REAGENT, equivalents=1.1)
    step = Step(id="s1", name="S1", step_yield_pct=90.0, output_name="out", materials=[sm_lim, sm_no])
    steps = {"s1": step}
    edges = [
        Edge(from_step_id=None, to_step_id="s1"),
        Edge(from_step_id="s1", to_step_id=None, is_terminal=True),
    ]
    graph = ProcessGraph(name="NoMW", target_api_name="API", steps=steps, edges=edges)
    errors = graph.validate()
    assert any("molecular_weight" in e for e in errors)

def test_valid_linear_graph_passes_validation():
    errors = _linear_3step_graph().validate()
    assert errors == []
