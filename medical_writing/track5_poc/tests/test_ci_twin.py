from labeling.ci_twin import CITwinManager


def _twin():
    return CITwinManager().load("ci_glp1_obesity_fda")


def test_ci_twin_loads_with_claims():
    twin = _twin()
    assert twin.regulatory_body == "FDA"
    assert len(twin.approved_claims) >= 6


def test_all_claims_have_required_fields():
    twin = _twin()
    for c in twin.approved_claims:
        assert c.source_label, f"{c.claim_id} missing source_label"
        assert c.claim_text, f"{c.claim_id} missing claim_text"
        assert c.label_section, f"{c.claim_id} missing label_section"


def test_claims_by_section_index_populated():
    twin = _twin()
    assert twin.claims_by_section
    assert "Indications and Usage" in twin.claims_by_section


def test_get_claims_for_section_filters():
    mgr = CITwinManager()
    twin = mgr.load("ci_glp1_obesity_fda")
    claims = mgr.get_claims_for_section(twin, "Warnings and Precautions")
    assert claims
    assert all(c.label_section == "Warnings and Precautions" for c in claims)


def test_generate_precedent_summary_nonempty():
    mgr = CITwinManager()
    twin = mgr.load("ci_glp1_obesity_fda")
    summary = mgr.generate_precedent_summary(twin, ["ap_001", "ap_002"])
    assert isinstance(summary, str) and len(summary) > 0
    assert "semaglutide" in summary.lower() or "Wegovy" in summary
