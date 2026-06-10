from twins.structure.manager import StructureTwinManager

REQUIRED_SECTIONS = {
    "background_rationale", "phase2_results_summary", "proposed_phase3_design",
    "cardiovascular_safety", "regulatory_questions",
}


def test_eop2_structure_loads_with_five_sections():
    t = StructureTwinManager().load("structure_eop2_fda")
    assert t.regulatory_body == "FDA"
    assert len(t.sections) == 5
    assert {s.section_id for s in t.sections} == REQUIRED_SECTIONS


def test_required_sections_flagged():
    t = StructureTwinManager().load("structure_eop2_fda")
    assert all(s.required for s in t.sections)


def test_section_ordering_is_sequential():
    t = StructureTwinManager().load("structure_eop2_fda")
    orders = sorted(s.ordering for s in t.sections)
    assert orders == [1, 2, 3, 4, 5]


def test_source_elements_present_and_well_formed():
    t = StructureTwinManager().load("structure_eop2_fda")
    for s in t.sections:
        assert s.source_elements, f"{s.section_id} has no source elements"
        assert all(isinstance(e, str) and e for e in s.source_elements)
        assert s.role_primary  # every section has an owning role


def test_structure_validate_passes():
    mgr = StructureTwinManager()
    assert mgr.validate(mgr.load("structure_eop2_fda")) == []
