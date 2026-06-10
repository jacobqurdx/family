import config
from labeling.ci_twin import CITwinManager
from labeling.message_map_generator import MessageMapGenerator
from labeling.labeling_models import Achievability
from core.twin import DigitalTwin

CCDS_SECTIONS = {"Indications and Usage", "Clinical Studies",
                 "Warnings and Precautions", "Adverse Reactions"}


def _generate(mode):
    config.SIMULATION_MODE = mode
    ci = CITwinManager().load("ci_glp1_obesity_fda")
    content = DigitalTwin.load("molecule_aleniglipron")
    return MessageMapGenerator().generate(ci, content)


def test_high_quality_five_claims_all_sections():
    m = _generate("high_quality")
    assert len(m.claims) == 5
    sections = {c.label_section for c in m.claims}
    assert sections == CCDS_SECTIONS


def test_high_quality_achievability_and_precedent():
    m = _generate("high_quality")
    highs = [c for c in m.claims if c.achievability == Achievability.HIGH]
    assert len(highs) >= 3
    assert all(c.regulatory_precedent_ids for c in highs)
    assert all(c.precedent_summary for c in m.claims)


def test_high_quality_has_gaps():
    m = _generate("high_quality")
    gaps = [c for c in m.claims if c.is_gap]
    assert len(gaps) >= 2


def test_low_quality_degraded():
    m = _generate("low_quality")
    assert all(c.achievability == Achievability.MEDIUM for c in m.claims)
    assert all(c.regulatory_precedent_ids == [] for c in m.claims)
    assert m.high_achievability_count == 0
