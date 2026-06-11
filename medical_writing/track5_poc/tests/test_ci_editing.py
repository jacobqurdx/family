import json
import shutil
from pathlib import Path

import config
from labeling.ci_twin import CITwinManager
from labeling.labeling_models import ApprovedClaim
from labeling.ci_analysis import achievability_table, reference_sections
from labeling.message_map_generator import MessageMapGenerator
from core.twin import DigitalTwin

ROOT = Path(__file__).parent.parent
SRC = ROOT / "data" / "ci_twins" / "ci_glp1_obesity_fda.json"


def _tmp_mgr(tmp_path):
    dst = tmp_path / "ci_twins"
    dst.mkdir()
    shutil.copy(SRC, dst / "ci_glp1_obesity_fda.json")
    return CITwinManager(ci_dir=str(dst)), dst


def test_save_bumps_version_and_rebuilds_index(tmp_path):
    mgr, dst = _tmp_mgr(tmp_path)
    twin = mgr.load("ci_glp1_obesity_fda")
    start_version = twin.version
    n = len(twin.approved_claims)
    twin.approved_claims.append(ApprovedClaim(
        claim_id="ap_999", drug_name="testdrug", indication="obesity",
        label_section="Indications and Usage", claim_text="Test claim.",
        evidence_standard="test",
    ))
    mgr.save(twin)
    reloaded = mgr.load("ci_glp1_obesity_fda")
    assert len(reloaded.approved_claims) == n + 1
    assert reloaded.version != start_version            # version bumped
    assert "ap_999" in reloaded.claims_by_section["Indications and Usage"]  # index rebuilt


def test_delete_claim_persists(tmp_path):
    mgr, dst = _tmp_mgr(tmp_path)
    twin = mgr.load("ci_glp1_obesity_fda")
    twin.approved_claims = [c for c in twin.approved_claims if c.claim_id != "ap_001"]
    mgr.save(twin)
    reloaded = mgr.load("ci_glp1_obesity_fda")
    assert all(c.claim_id != "ap_001" for c in reloaded.approved_claims)


def test_signal_override_applied():
    ci = CITwinManager().load("ci_glp1_obesity_fda")
    base = {r["section"]: r for r in achievability_table(ci)}
    assert base["Indications and Usage"]["signal"] == "HIGH"
    over = {r["section"]: r for r in achievability_table(
        ci, signal_overrides={"Indications and Usage": "GAP"})}
    assert over["Indications and Usage"]["signal"] == "GAP"
    assert over["Indications and Usage"]["overridden"] is True


def test_action_override_flows_to_reference_sections():
    config.SIMULATION_MODE = "high_quality"
    ci = CITwinManager().load("ci_glp1_obesity_fda")
    mm = MessageMapGenerator().generate(ci, DigitalTwin.load("molecule_aleniglipron"))
    rows = reference_sections(ci, "orforglipron (Foundayo)", mm,
                              action_overrides={"Indications and Usage": "skip"})
    ind = next(r for r in rows if r["section"] == "Indications and Usage")
    assert ind["action"] == "skip"
    assert ind["color"] == "red"
