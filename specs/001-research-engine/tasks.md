# Traceable implementation tasks

- [x] T001 [US1, FR-001, FR-010] Create strict schema in `models.py`, reject malformed studies; verify invalid-input tests.
- [x] T002 [US1, FR-002] Add registered benchmark algorithms and objective evaluation limits in `algorithms.py`; verify exact count and seed reproducibility tests.
- [x] T003 [US1, FR-003] Add a bounded best-first configuration search in `search.py`; verify candidate budget/parent relationships.
- [x] T004 [US2, FR-004, FR-005] Add independent reference objectives and held-out paired comparison in `verification.py`; verify objective mismatch and seed-split tests.
- [x] T005 [US3, FR-006, FR-009] Add immutable artifacts, hashes, report and full replay in `artifacts.py`, `report.py`, `replay.py`; verify tamper tests.
- [x] T006 [US4, FR-007] Add opt-in LLM proposal/ideation client and HTTPS guard in `llm.py`, `network.py`; verify schema and malicious endpoint tests.
- [x] T007 [US5, FR-008] Add opt-in Crossref metadata lookup in `literature.py` with explicit content limitations; verify response parsing tests.
- [x] T008 [US1-5] Implement CLI, examples, documentation, non-root Docker build and offline CI smoke test.
- [ ] T009 [US1-5] Conduct external production security assessment, actual LLM/Crossref integration tests and a representative workload performance study (**NOT VERIFIED**, beyond offline release gate).
