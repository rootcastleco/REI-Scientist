# Requirement-to-evidence trace

| Requirement | Implementation | Acceptance evidence | Scope status |
|---|---|---|---|
| FR-001, FR-010 | `models.py` | tests/test_models.py | Implemented |
| FR-002 | `algorithms.py`, `objectives.py` | tests/test_algorithms.py | Implemented |
| FR-003 | `search.py` | tests/test_search.py | Implemented |
| FR-004, FR-005 | `verification.py`, `search.py` | tests/test_verification.py + tests/test_search.py | Implemented |
| FR-006 | `artifacts.py`, `replay.py` | tests/test_artifacts.py | Implemented |
| FR-007 | `network.py`, `llm.py` | tests/test_network.py | Implemented; live provider NOT VERIFIED |
| FR-008 | `literature.py` | tests/test_network.py | Implemented; live provider NOT VERIFIED |
| FR-009 | `report.py` | tests/test_artifacts.py + offline smoke | Implemented |

Read `docs/verification-results.md` for actual local test outputs; do not confuse implementation status with proof that external services work.
