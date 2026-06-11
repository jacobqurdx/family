import pytest

import config
from labeling.ci_twin import CITwinManager
from labeling.message_map_generator import MessageMapGenerator
from labeling.label_draft_generator import LabelDraftGenerator
from core.twin import DigitalTwin

CCDS_SECTION_IDS = {"indications_usage", "clinical_studies",
                    "warnings_precautions", "adverse_reactions"}


def _locked_map(mode):
    config.SIMULATION_MODE = mode
    ci = CITwinManager().load("ci_glp1_obesity_fda")
    content = DigitalTwin.load("molecule_aleniglipron")
    m = MessageMapGenerator().generate(ci, content)
    m.locked = True
    return m


def test_high_quality_draft_four_sections():
    config.SIMULATION_MODE = "high_quality"
    draft = LabelDraftGenerator().generate(_locked_map("high_quality"))
    assert len(draft.sections) == 4
    assert {s.section_id for s in draft.sections} == CCDS_SECTION_IDS


def test_high_quality_indications_has_bmi_threshold():
    config.SIMULATION_MODE = "high_quality"
    draft = LabelDraftGenerator().generate(_locked_map("high_quality"))
    indications = next(s for s in draft.sections if s.section_id == "indications_usage")
    assert "30 kg/m" in indications.prose
    assert "27 kg/m" in indications.prose


def test_high_quality_warnings_has_thyroid_language():
    config.SIMULATION_MODE = "high_quality"
    draft = LabelDraftGenerator().generate(_locked_map("high_quality"))
    warnings = next(s for s in draft.sections if s.section_id == "warnings_precautions")
    assert "thyroid c-cell" in warnings.prose.lower()
    assert "medullary thyroid carcinoma" in warnings.prose.lower()


def test_high_quality_overall_confidence():
    config.SIMULATION_MODE = "high_quality"
    draft = LabelDraftGenerator().generate(_locked_map("high_quality"))
    assert draft.overall_confidence >= 0.75


def test_low_quality_has_missing_placeholders():
    config.SIMULATION_MODE = "low_quality"
    draft = LabelDraftGenerator().generate(_locked_map("low_quality"))
    assert draft.overall_confidence <= 0.45
    missing = [s for s in draft.sections if "[MISSING" in s.prose]
    assert len(missing) >= 2


def test_low_quality_warnings_missing_boxed_warning():
    config.SIMULATION_MODE = "low_quality"
    draft = LabelDraftGenerator().generate(_locked_map("low_quality"))
    warnings = next(s for s in draft.sections if s.section_id == "warnings_precautions")
    assert "[MISSING" in warnings.prose
    # the verbatim mandatory phrase is absent
    assert "medullary thyroid carcinoma" not in warnings.prose.lower()


def test_unlocked_map_raises():
    config.SIMULATION_MODE = "high_quality"
    ci = CITwinManager().load("ci_glp1_obesity_fda")
    content = DigitalTwin.load("molecule_aleniglipron")
    m = MessageMapGenerator().generate(ci, content)  # not locked
    with pytest.raises(ValueError):
        LabelDraftGenerator().generate(m)
