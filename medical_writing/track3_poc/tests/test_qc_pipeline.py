import config
from twins.registry import TwinRegistry
from generation.content_spec_generator import ContentSpecGenerator
from regulatory.framework_twin import FrameworkTwinManager
from qc.pipeline import QCPipeline

CHECKLIST = f"{config.CHECKLISTS_DIR}/eop2_checklist.json"


def _pipeline():
    fw = FrameworkTwinManager().load("framework_fda_obesity")
    return QCPipeline(fw, CHECKLIST)


def _spec(mode):
    config.SIMULATION_MODE = mode
    pair = TwinRegistry().resolve("structure_eop2_fda")
    return ContentSpecGenerator().generate(pair)


def test_high_quality_passes_with_only_minor_findings():
    spec, findings = _pipeline().run(_spec("high_quality"))
    assert spec.qc_passed is True
    severities = {f.severity for f in findings}
    assert "blocking" not in severities
    assert "major" not in severities
    # metacognitive minor flags present
    assert any(f.pass_number == 4 for f in findings)


def test_checklist_detects_deliberately_missing_section():
    spec = _spec("high_quality")
    # deliberately drop the regulatory_questions section
    spec.sections = [s for s in spec.sections if s.section_id != "regulatory_questions"]
    spec, findings = _pipeline().run(spec)
    chk = [f for f in findings if f.pass_number == 3
           and f.section_id == "regulatory_questions"]
    assert chk and chk[0].severity == "blocking"
    assert spec.qc_passed is False


def test_low_quality_produces_blocking_historical_finding():
    spec, findings = _pipeline().run(_spec("low_quality"))
    hist = [f for f in findings if f.pass_number == 2 and f.severity == "blocking"]
    assert hist and hist[0].category == "prior_crl_concern"
    assert spec.qc_passed is False


def test_consistency_pass_fires_in_low_quality():
    spec, findings = _pipeline().run(_spec("low_quality"))
    con = [f for f in findings if f.pass_number == 1
           and f.category == "internal_inconsistency"]
    assert len(con) >= 1
