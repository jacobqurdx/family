import config
from labeling.ci_twin import CITwinManager
from labeling.ci_analysis import (
    achievability_table, strategic_insight, comparator_detail,
    list_comparators, reference_sections, CCDS_SECTIONS_5,
)
from labeling.message_map_generator import MessageMapGenerator
from core.twin import DigitalTwin


def _ci():
    return CITwinManager().load("ci_glp1_obesity_fda")


def test_foundayo_present_as_comparator():
    comps = list_comparators(_ci())
    assert any("foundayo" in c.lower() for c in comps)
    # Foundayo surfaced first (reference default)
    assert "foundayo" in comps[0].lower()


def test_achievability_table_five_sections_with_signals():
    table = achievability_table(_ci())
    assert len(table) == 5
    assert [r["section"] for r in table] == CCDS_SECTIONS_5
    assert all(r["signal"] in ("HIGH", "MED", "GAP") for r in table)
    # Indications is HIGH, Dosage is a GAP (route divergence)
    by_section = {r["section"]: r for r in table}
    assert by_section["Indications and Usage"]["signal"] == "HIGH"
    assert by_section["Dosage and Administration"]["signal"] == "GAP"


def test_strategic_insight_non_empty():
    insight = strategic_insight(_ci(), "aleniglipron", "orforglipron (Foundayo)")
    assert isinstance(insight, str) and len(insight) > 40
    assert "boxed warning" in insight.lower()


def test_comparator_detail_for_foundayo():
    detail = comparator_detail(_ci(), "orforglipron (Foundayo)")
    sections = {d["section"] for d in detail}
    assert "Dosage and Administration" in sections
    # the dosage row carries a skip action (divergence)
    dosage = next(d for d in detail if d["section"] == "Dosage and Administration")
    assert dosage["action"] == "skip"
    assert dosage["color"] == "red"


def test_reference_sections_align_with_message_map():
    config.SIMULATION_MODE = "high_quality"
    ci = _ci()
    mm = MessageMapGenerator().generate(ci, DigitalTwin.load("molecule_aleniglipron"))
    rows = reference_sections(ci, "orforglipron (Foundayo)", mm)
    assert len(rows) == 5
    by_section = {r["section"]: r for r in rows}
    # Adopt section has a proposed claim; skip section does not
    assert by_section["Indications and Usage"]["action"] == "adopt"
    assert by_section["Indications and Usage"]["proposed_text"]
    assert by_section["Dosage and Administration"]["action"] == "skip"
    assert by_section["Dosage and Administration"]["proposed_text"] == ""
    # every row carries a colour for highlight rendering
    assert all(r["color"] in ("purple", "amber", "red", "blue") for r in rows)
