import datetime

from governance.permissions import PermissionEngine, Permission
from governance.versioning import VersionManager
from governance.audit import AuditTrail
from generation.spec_models import ContentSpec
from review.finding_models import ReviewDecision


def _spec():
    return ContentSpec(
        spec_id="spec_test", document_type="eop2_briefing",
        content_twin_id="molecule_aleniglipron",
        structure_twin_id="structure_eop2_fda", generated_by_role="regulatory_affairs",
    )


def test_regulatory_affairs_cannot_submission_lock():
    engine = PermissionEngine()
    # submission lock requires ADMIN
    assert engine.can("regulatory_affairs", "document_ra_sections", Permission.ADMIN) is False
    # but RA can apply a (review/version) lock
    assert engine.can("regulatory_affairs", "document_ra_sections", Permission.LOCK) is True


def test_admin_can_lock_and_release():
    engine = PermissionEngine()
    assert engine.can("admin", "document_all_sections", Permission.ADMIN) is True
    vm = VersionManager()
    spec = _spec()
    vm.submission_lock(spec, "admin")
    assert spec.locked is True and spec.version == "submission_lock"
    vm.release(spec)
    assert spec.locked is False


def test_version_lock_sets_version_string():
    vm = VersionManager()
    spec = _spec()
    vm.version_lock(spec, "regulatory_affairs", timestamp="20260609_1200")
    assert spec.version == "v20260609_1200"
    assert spec.locked is True
    assert spec.locked_by == "regulatory_affairs"


def test_clinical_science_cannot_version_lock():
    engine = PermissionEngine()
    assert engine.can("clinical_science", "document_efficacy_sections", Permission.LOCK) is False


def test_audit_trail_records_decisions_with_role_and_timestamp():
    trail = AuditTrail()
    decisions = [ReviewDecision(
        decision_id="d1", section_id="background_rationale",
        reviewer_role="regulatory_affairs", decision="correct",
        from_value="a", to_value="b", decided_at=datetime.datetime.utcnow(),
    )]
    trail.record_decisions(decisions)
    assert len(trail) == 1
    entry = trail.entries()[0]
    assert entry["role"] == "regulatory_affairs"
    assert entry["timestamp"]
    assert entry["target"] == "background_rationale"
