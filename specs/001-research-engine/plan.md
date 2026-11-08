# Implementation plan and architecture (2026-11-08)

## Constitution

This is a greenfield, independent application. Rules: no arbitrary model-generated code execution, deny-by-default network, separate trusted solver from untrusted study/config, reproducible numerical budgets, independent objective check, no unsupported scientific claims, no integration into existing product cores, reversible deployment.

## Component boundaries

```text
untrusted study JSON ---> models.StudySpec validation ---> search.run_search
                                   |                       |
optional LLM/Crossref ---> network allowlist          algorithms.run_seed
                                   |                       |
                        schema-checked proposals       objectives.evaluate
                                                           |
                                         verification.reference_objective
                                                           |
                                               report + artifacts + replay
```

Registered solvers run in the current process but only take numeric input from validated JSON and never execute an untrusted string. To introduce untrusted executable experiments, a future **separate OS/container sandbox** is mandatory. Do not interpret the current numeric safety checks as a sandbox.

## Data and state

- StudySpec: immutable versioned protocol, dimension/bounds/budgets, methods, disjoint seed groups, threshold.
- Proposal: method, parameter tuple, deterministic content hash, tree parent, depth.
- SeedResult: best position and objective, evaluation count, trace SHA-256, elapsed time.
- SearchOutcome: development leaderboard/runs plus selected candidate and two holdout groups.
- Artifacts: `study.json`, `results.json`, `manifest.json`, `report.md`, `events.jsonl`, `dashboard.html`, created in a new output folder.

Transitions: INIT -> VALIDATED -> (OPTIONAL_NET) -> SEARCH_DEV -> SELECT -> HOLDOUT_ONCE -> VERIFY -> REPORT -> REPLAY. On malformed input or failure, the CLI returns nonzero; existing study files cannot be overwritten. A failure during a local run before persistence produces no fabricated report. Mid-persistence filesystem errors may leave a partial directory; operators must discard it, not regard it as a valid experiment.

## Algorithm and safety reasoning

Use registered analytic benchmarks to avoid hidden data leakage and provide a mathematically independent reference. Use a priority queue for best-first tree exploration, capped by candidate and depth budgets. Seeds within a stage are deterministic via `random.Random`; bootstrap resampling uses a separate fixed seed. A model assistant can only generate validated numeric proposals within method bounds, never a Python program or shell command.

Verification recalculates objective values and checks constraints, seed identities, number of evaluations, and isolated test partitions. Evidence hashes support reproducibility audits; they are not signatures and do not provide nonrepudiation.

## External calls and security controls

Network module allowlists explicit HTTPS hosts, disallows redirects and proxies, limits payload and response sizes, and sets fixed timeouts. LLM key is read only from environment variables. No external request occurs in the offline path. For truly bounded execution time and resource use, deploy a non-root container with `--network none`, memory/CPU/PID caps and read-only filesystem. Future worker orchestration requires cancellation, cgroups and metered API budgets.

## Observability and budgets

Record evaluated configurations, source fingerprint, per-run timing, evaluation counts and verdict. CLI prints status; metadata is reproducible, except time fields. Hard evaluation ceiling: <= (candidate_budget + 1) * len(dev_seeds) * evaluation_budget + 2 * len(test_seeds) * evaluation_budget. At default settings: (8 + 1)*3*120 + 2*5*120 = 4440 evaluations.

Target: example run under 10 seconds on a typical development CPU; this is an **acceptance target** until measured, not an observed performance claim. No reliability or latency guarantees for network mode.

## Rollout, migration and rollback

New independent package; no schema/data migration of existing Rootcastle products. Integrations must use reviewed adapters and feature flags. Roll back by stopping the CLI/container and returning to current manual experiment workflows. Do not add write-access to Rootcastle production data, repositories or machinery in v0.1. Experimental results can be discarded without affecting running products.

## Alternatives considered

1. Fork Sakana AI Scientist v2: rejected for initial build due to distinct source license, autonomous code execution exposure, and wide dependency surface.
2. LLM-written arbitrary Python runner: rejected without an enforceable OS isolation boundary.
3. Simple fixed experiment loop: rejected because it lacks bounded proposal search and evidence separation.
4. **Chosen:** original Python standard-library implementation; constrained search with explicit verification and optional narrow LLM adapter.
