# REI Scientist v0.1: Research engine specification

## Problem, actors and scope

An engineering researcher needs an auditable workflow to compare registered numerical methods without presenting automatically generated conjecture as scientific evidence. The primary operator supplies a preregistered hypothesis and resource limits. The system executes repeatable synthetic evaluations, keeps the holdout isolated, and marks claims PASS, FAIL or NOT VERIFIED.

v0.1 scope: numerical optimization on four analytic benchmarks, fixed method registry, bounded best-first parameter search, explicit development/holdout split, source-provenance artifacts, replay, opt-in model/citation metadata. Exclusions: arbitrary executable code generation, unrestricted web research, real machinery control, medical diagnosis, journal submission, guaranteed novelty, and general automatic scientific discovery.

## Priority scenarios

**US1 (P0):** Given a valid versioned study, when an offline run completes, the operator receives a generated report and exact machine-readable records for every trial. When invalid input is provided, no run proceeds.

**US2 (P0):** Given a candidate selected only from development seeds, when the holdout evaluation runs, the same holdout seeds are used for the baseline and candidate exactly once each; the verdict derives only from holdout results.

**US3 (P0):** Given a result artifact, when the operator requests verification, experiment traces and objective values reproduce exactly under the same source code; tampering causes a nonzero status.

**US4 (P1):** Given explicit opt-in and a configured model endpoint, model output may supply only registered algorithm choices and finite parameters, never executable code.

**US5 (P1):** Given explicit literature opt-in, the system may fetch bibliographic metadata but never claim to have read or validated the full text.

## Functional requirements

- **FR-001** Validate an exact, versioned study contract, finite bounds, safe study ID, legal methods and separated development/holdout seed sets.
- **FR-002** Execute only reviewed, registered benchmark/algorithm combinations, with exact per-run objective-evaluation ceilings (20-5000).
- **FR-003** Perform deterministic bounded best-first candidate exploration, recording parent-child relationships and development scores (at most 50 candidates, depth 0-5).
- **FR-004** Select configuration using development data only; evaluate held-out baseline and selected candidate on the same independent seeds and never tune after holdout disclosure.
- **FR-005** Independently recompute objectives and validate finite solutions, declared constraints and evaluation counts; classify claims using predeclared target and an exploratory paired CI.
- **FR-006** Persist full experiment records, provenance manifest, SHA-256 digests, report, offline HTML dashboard and deterministic replay; reject pre-existing output paths.
- **FR-007** No network or LLM calls unless explicitly requested by the operator; accept only schema-checked numerical model proposals.
- **FR-008** If requested, retrieve bounded Crossref metadata labelled NOT VERIFIED for full-text scientific claims; network errors must fail closed.
- **FR-009** Reports must disclose model participation, limitations, false-positive risks, status and independent verification coverage.
- **FR-010** Reject unsupported unknown benchmark names/methods, unreasonable budgets, non-finite values and duplicate/overlapping seeds before work begins.

## Acceptance criteria

- **AC-001:** An offline example runs to completion with exactly declared per-seed evaluation counts; no external services required.
- **AC-002:** Invalid study with overlapping dev/test seeds, unsupported algorithm, or NaN fails with a clear error.
- **AC-003:** Holdout seed set is never used by search; selecting the best development configuration does not change its membership or results.
- **AC-004:** Independent objective checks reject corrupted reported scores.
- **AC-005:** `rei-scientist verify RUN_DIR` replays all runs and detects changed result artifacts.
- **AC-006:** Unconfigured network providers cannot run with silent default credentials or unknown hosts; no arbitrary model-written code is evaluated.
- **AC-007:** Reports label limited evidence honestly and include experiment provenance and reproducibility instructions.
- **AC-008:** The entire test suite runs under standard Python without third-party runtime packages.

## Failure/abuse behavior

Network operations fail closed. Data contamination, non-finite or out-of-bounds objective results, mismatched budgets, malformed LLM proposals, missing credentials, and prior output directory all halt the relevant operation with a nonzero exit status. An unsupported domain must not be silently mapped to an unrelated analytic objective.

## Assumptions, external validity and unresolved decisions

- **A-001:** An analytic numerical benchmark is a suitable first integration smoke test, **not** proof of applicability to REI Track or Magnus Balance.
- **A-002:** Default minimum claim evidence is five holdout seeds and an exploratory paired bootstrap lower bound above zero. Formal statistical testing is future work.
- **A-003:** Output is local and editable; digests without signing do not prove integrity against a privileged attacker.
- **NOT VERIFIED:** External LLM endpoint compatibility, Crossref availability, GPU capability, actual domain datasets, independent peer review, and scientific novelty.
