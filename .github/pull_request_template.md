## Description
<!-- Provide a clear, concise summary of the proposed changes and architectural context. -->

## Invariant Conformance & Checklist
- [ ] **Automated Test Suite**: All tests pass cleanly (`pytest tests/`).
- [ ] **Core Invariants Verified**: Passes all tests in `tests/test_graph_invariants.py` and `tests/test_security_hardening.py`.
- [ ] **Property-Based Grounding**: Passes mutation test suite (`pytest tests/unit/test_grounding_properties.py`).
- [ ] **Confirmed-Edge Invariant**: Verified that proposed relations emit uncertainty warnings and do not silently alter controlling law.
- [ ] **Temporal Validity Gating**: Inquiries evaluate law strictly as of incident date; future amendments do not govern past events.
- [ ] **No Silent Keyword Fallback**: Uncovered topics return explicit `CoverageHole` rather than promoting arbitrary statutes.
- [ ] **Immutable Audit Trail**: Verified `AuditLog` records cannot be updated or deleted.
- [ ] **Pre-Spool Magic-Byte Gate**: Executable binaries and polyglots rejected before disk write.
- [ ] **Legal Hold Gating**: Matters under legal hold blocked from deletion with HTTP 423 Locked.
- [ ] **Air-Gap Compliance**: Zero external cloud network requests or telemetry.
- [ ] **Docs & Invariants Updated**: Updated `docs/INVARIANTS.md` or `CHANGELOG.md` if applicable.

## Related Issues or Specs
<!-- E.g., Closes #123 or implements Spec section X -->
