import config
from twins.registry import TwinRegistry
from generation.content_spec_generator import ContentSpecGenerator

EOP2_SECTIONS = {
    "background_rationale", "phase2_results_summary", "proposed_phase3_design",
    "cardiovascular_safety", "regulatory_questions",
}


def _gen():
    pair = TwinRegistry().resolve("structure_eop2_fda")
    return ContentSpecGenerator().generate(pair)


def test_high_quality_has_all_five_sections():
    config.SIMULATION_MODE = "high_quality"
    spec = _gen()
    assert {s.section_id for s in spec.sections} == EOP2_SECTIONS


def test_gaps_detected_contains_expected_missing():
    config.SIMULATION_MODE = "high_quality"
    spec = _gen()
    assert "cv_safety_data" in spec.gaps_detected
    assert "phase3_sample_size" in spec.gaps_detected
    assert len(spec.gaps_detected) >= 2


def test_non_gap_claims_have_high_confidence():
    config.SIMULATION_MODE = "high_quality"
    spec = _gen()
    non_gap = [c for s in spec.sections for c in s.claims if not c.is_gap]
    assert non_gap
    assert all(c.confidence >= 0.70 for c in non_gap)


def test_low_quality_degrades_all_sections():
    config.SIMULATION_MODE = "low_quality"
    spec = _gen()
    assert all(s.overall_confidence <= 0.50 for s in spec.sections)
    assert all(s.needs_human_review for s in spec.sections)
