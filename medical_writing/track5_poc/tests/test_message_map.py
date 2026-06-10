from labeling.labeling_models import (
    MessageMap, MessageMapClaim, Achievability,
)


def _claim(cid, achiev, gap=False):
    return MessageMapClaim(
        claim_id=cid, label_section="Indications and Usage",
        proposed_claim_text="text", supporting_element_id="indication",
        supporting_value="obesity", achievability=achiev, is_gap=gap,
    )


def test_message_map_claim_validates():
    c = _claim("c1", Achievability.HIGH)
    assert c.claim_id == "c1"
    assert c.achievability == Achievability.HIGH
    assert c.is_gap is False


def test_recount_tallies_achievability():
    m = MessageMap(
        map_id="m1", program_name="Aleniglipron", indication="obesity",
        document_type="ccds", regulatory_body="FDA",
        ci_twin_id="ci_glp1_obesity_fda", content_twin_id="molecule_aleniglipron",
        claims=[
            _claim("c1", Achievability.HIGH),
            _claim("c2", Achievability.HIGH),
            _claim("c3", Achievability.MEDIUM),
            _claim("c4", Achievability.LOW, gap=True),
        ],
    )
    m.recount()
    assert m.high_achievability_count == 2
    assert m.medium_achievability_count == 1
    assert m.low_achievability_count == 1


def test_gaps_detected_identifies_gap_claims():
    m = MessageMap(
        map_id="m2", program_name="Aleniglipron", indication="obesity",
        document_type="ccds", regulatory_body="FDA",
        ci_twin_id="ci_glp1_obesity_fda", content_twin_id="molecule_aleniglipron",
        claims=[_claim("c1", Achievability.HIGH), _claim("c2", Achievability.HIGH, gap=True)],
    )
    m.recount()
    assert m.gaps_detected == ["c2"]
