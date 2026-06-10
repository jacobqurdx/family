import config
from twins.registry import TwinRegistry
from generation.content_spec_generator import ContentSpecGenerator
from generation.gap_handler import GapHandler
from twins.content.manager import ContentTwinManager


def test_gap_fill_removes_gap_and_back_propagates(tmp_twins):
    config.SIMULATION_MODE = "high_quality"
    pair = TwinRegistry().resolve("structure_eop2_fda")
    spec = ContentSpecGenerator().generate(pair)
    assert "cv_safety_data" in spec.gaps_detected

    handler = GapHandler()
    handler.fill_gap(spec, "cv_safety_data",
                     "No clinically meaningful CV signal in ACCESS II.",
                     filled_by="regulatory_affairs", back_propagate=True)

    # gap removed + recorded
    assert "cv_safety_data" not in spec.gaps_detected
    assert "cv_safety_data" in spec.gaps_filled

    # claim updated
    cv_claims = [c for s in spec.sections for c in s.claims
                 if c.supporting_element_id == "cv_safety_data"]
    assert cv_claims and all(not c.is_gap for c in cv_claims)
    assert all(c.gap_filled_by == "regulatory_affairs" for c in cv_claims)

    # back-propagated to content twin with provenance
    twin = ContentTwinManager().load(pair.content_twin_id)
    el = twin.get("cv_safety_data")
    assert el is not None and el.source == "jit_gap_fill"


def test_filled_value_no_longer_a_gap_on_regeneration(tmp_twins):
    config.SIMULATION_MODE = "high_quality"
    pair = TwinRegistry().resolve("structure_eop2_fda")
    spec = ContentSpecGenerator().generate(pair)
    GapHandler().fill_gap(spec, "cv_safety_data", "value", back_propagate=True)

    # regenerate against the now-updated content twin
    spec2 = ContentSpecGenerator().generate(pair)
    assert "cv_safety_data" not in spec2.gaps_detected
