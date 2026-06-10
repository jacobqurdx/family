from regulatory.framework_twin import FrameworkTwinManager

VALID_TYPES = {"structure", "content", "format", "process"}


def test_framework_twin_loads():
    t = FrameworkTwinManager().load("framework_fda_obesity")
    assert t.regulatory_body == "FDA"
    assert len(t.requirements) >= 5


def test_all_requirements_have_citations():
    t = FrameworkTwinManager().load("framework_fda_obesity")
    for r in t.requirements:
        assert r.source_quote, f"{r.requirement_id} missing source_quote"
        assert r.guidance_section, f"{r.requirement_id} missing guidance_section"


def test_requirement_types_valid():
    t = FrameworkTwinManager().load("framework_fda_obesity")
    for r in t.requirements:
        assert r.requirement_type in VALID_TYPES


def test_agency_concerns_and_prior_positions_populated():
    t = FrameworkTwinManager().load("framework_fda_obesity")
    assert len(t.agency_concerns) >= 1
    assert len(t.prior_positions) >= 1


def test_requirements_for_document_type():
    mgr = FrameworkTwinManager()
    eop2 = mgr.requirements_for("framework_fda_obesity", "eop2_briefing")
    assert len(eop2) >= 1
    assert all("eop2_briefing" in r.applies_to_document_types for r in eop2)
