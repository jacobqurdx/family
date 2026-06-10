"""
VersionManager: simulated document and twin versioning / locking for the POC.

Three document lock levels:
  - review_lock      frozen for async review; suggestions only
  - version_lock     named immutable version + content-twin snapshot
  - submission_lock  compiled into eCTD; no change without formal amendment

Lock state is stored as fields on the spec/twin record. The UI enforces lock
state; no cryptographic signing or formal audit log (deferred to production).
"""
import datetime


class VersionManager:
    def review_lock(self, spec, locked_by: str):
        spec.locked = True
        spec.locked_at = datetime.datetime.utcnow()
        spec.locked_by = locked_by
        spec.version = "review_lock_v1"
        return spec

    def version_lock(self, spec, locked_by: str, timestamp: str = None):
        """Apply a named immutable version. timestamp injectable for determinism."""
        stamp = timestamp or datetime.datetime.utcnow().strftime("%Y%m%d_%H%M")
        spec.version = f"v{stamp}"
        spec.locked = True
        spec.locked_at = datetime.datetime.utcnow()
        spec.locked_by = locked_by
        return spec

    def submission_lock(self, spec, locked_by: str):
        spec.locked = True
        spec.locked_at = datetime.datetime.utcnow()
        spec.locked_by = locked_by
        spec.version = "submission_lock"
        return spec

    def release(self, spec):
        spec.locked = False
        return spec

    def snapshot(self, content_twin) -> dict:
        """
        Produce an immutable, document-bound snapshot of the content-twin state
        that fed a version-locked document. Audit trail reconstructible.
        """
        return {
            "twin_id": content_twin.twin_id,
            "elements": {
                eid: el.value for eid, el in content_twin.get_all().items()
            },
        }
