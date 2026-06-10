import config
from llm.stubs.guidance_extractor_stub import GuidanceExtractorStub
from regulatory.guidance_ingestor import GuidanceIngestor


def test_high_quality_returns_at_least_five_with_confidence():
    config.SIMULATION_MODE = "high_quality"
    reqs = GuidanceExtractorStub().extract_requirements("text", "eop2_briefing")
    assert len(reqs) >= 5
    assert all(r.confidence >= 0.80 for r in reqs)
    assert all(r.source_quote for r in reqs)


def test_low_quality_degrades_confidence_and_citations():
    config.SIMULATION_MODE = "low_quality"
    reqs = GuidanceExtractorStub().extract_requirements("text", "eop2_briefing")
    assert len(reqs) >= 5
    assert all(r.confidence <= 0.50 for r in reqs)
    assert all(r.source_quote == "" for r in reqs)


def test_ingestor_reads_guidance_file():
    config.SIMULATION_MODE = "high_quality"
    path = f"{config.GUIDANCE_DOCS_DIR}/fda_obesity_guidance.txt"
    reqs = GuidanceIngestor().ingest(path, "eop2_briefing")
    assert len(reqs) >= 5


def test_ingestor_handles_missing_file_gracefully():
    config.SIMULATION_MODE = "high_quality"
    reqs = GuidanceIngestor().ingest("does/not/exist.pdf", "eop2_briefing")
    # extraction stub is deterministic regardless of (empty) text
    assert len(reqs) >= 5
