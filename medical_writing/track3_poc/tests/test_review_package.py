import config
import datetime
from twins.registry import TwinRegistry
from generation.content_spec_generator import ContentSpecGenerator
from review.review_package import ReviewPackageBuilder
from review.finding_models import ReviewDecision
from review.feedback_handler import FeedbackHandler
from llm.stubs.role_router_stub import RoleRouterStub
from twins.content.manager import ContentTwinManager


def _spec():
    config.SIMULATION_MODE = "high_quality"
    pair = TwinRegistry().resolve("structure_eop2_fda")
    return ContentSpecGenerator().generate(pair)


def test_primary_sections_match_role_map():
    spec = _spec()
    pkg = ReviewPackageBuilder().build(spec, [], "regulatory_affairs")
    assert pkg.reviewer_role == "regulatory_affairs"
    assert pkg.primary_sections == RoleRouterStub().get_primary_sections("regulatory_affairs")


def test_back_propagate_decision_updates_content_twin(tmp_twins):
    spec = _spec()
    decisions = [ReviewDecision(
        decision_id="dec_1", section_id="cardiovascular_safety",
        reviewer_role="regulatory_affairs", decision="correct",
        from_value="old", to_value="MACE adjudication committee established.",
        back_propagate=True, decided_at=datetime.datetime.utcnow(),
    )]
    summary = FeedbackHandler().apply(spec.content_twin_id, decisions)
    assert "cardiovascular_safety" in summary["back_propagated"]
    twin = ContentTwinManager().load(spec.content_twin_id)
    assert twin.get_value("cardiovascular_safety") == "MACE adjudication committee established."


def test_suggest_decision_created_for_suggest_only_role():
    # clinical_science can only SUGGEST on content twin; verify a suggest decision
    # round-trips through the feedback handler counts.
    decisions = [ReviewDecision(
        decision_id="dec_2", section_id="phase2_results_summary",
        reviewer_role="clinical_science", decision="suggest",
        from_value="x", to_value="please clarify endpoint magnitude",
        back_propagate=False, decided_at=datetime.datetime.utcnow(),
    )]
    summary = FeedbackHandler().apply("molecule_aleniglipron", decisions)
    assert summary["suggested"] == 1
    assert summary["back_propagated"] == []
