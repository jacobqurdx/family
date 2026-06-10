"""Pass 1: internal consistency. Re-exports the active implementation.
Promotion: when the functional ConsistencyChecker lands, point this alias at it."""
from llm.stubs.consistency_checker_stub import ConsistencyCheckerStub as ConsistencyChecker

__all__ = ["ConsistencyChecker"]
