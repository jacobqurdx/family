from core.twin import DigitalTwin
from core.models import TwinTier, ElementStatus
from twins.content.manager import ContentTwinManager
from twins.content.gap_detector import GapDetector
from twins.structure.manager import StructureTwinManager


def test_load_molecule_content_twin():
    t = DigitalTwin.load("molecule_aleniglipron")
    assert t.tier == TwinTier.MOLECULE
    assert t.get_value("drug_name") == "aleniglipron"
    assert "obesity" in str(t.get_value("indication")).lower()


def test_inherit_from_parent_pulls_program_facts():
    parent = DigitalTwin.load("molecule_aleniglipron")
    child = DigitalTwin.new("tmp_child", schema_id="protocol", tier=TwinTier.TRIAL,
                            parent_twin_id="molecule_aleniglipron")
    child.inherit_from_parent(parent)
    assert child.get_value("drug_name") == "aleniglipron"
    assert child.get_value("indication") is not None
    el = child.get("drug_name")
    assert el.source.startswith("inherited:")


def test_gap_detection_for_eop2_structure():
    content = DigitalTwin.load("molecule_aleniglipron")
    structure = StructureTwinManager().load("structure_eop2_fda")
    gaps = GapDetector().detect(content, structure)
    # molecule twin only has drug_name + indication; everything else is a gap
    assert "cv_safety_data" in gaps
    assert "phase3_sample_size" in gaps
    assert "drug_name" not in gaps
    assert len(gaps) >= 2


def test_back_propagation_writes_with_provenance(tmp_twins):
    mgr = ContentTwinManager()
    twin = mgr.back_propagate("molecule_aleniglipron", "cv_safety_data",
                              "No MACE imbalance observed in ACCESS II.",
                              source="jit_gap_fill", modified_by="regulatory_affairs")
    el = twin.get("cv_safety_data")
    assert el.value.startswith("No MACE")
    assert el.source == "jit_gap_fill"
    assert el.status == ElementStatus.VERIFIED
    assert el.modified_by == "regulatory_affairs"
    # persisted
    reloaded = ContentTwinManager().load("molecule_aleniglipron")
    assert reloaded.get_value("cv_safety_data").startswith("No MACE")
