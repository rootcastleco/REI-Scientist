# REI Scientist v0.1 - measured local verification

**Date:** 2026-11-08. **Platform:** local Linux / Python 3.13.5. Evidence is in `demo/` and source tests. These are local test measurements, not a third-party certification.

## Checked implementation paths

- Unit / negative / integration tests: **36/36 passed** (`PYTHONPATH=src python -m unittest discover -s tests -v`).
- Python bytecode compilation: **PASS** (`python -m compileall -q src tests`).
- Wheel build: **PASS** (`python -m pip wheel --no-build-isolation --no-deps . -w /mnt/data`).
- Install from generated wheel into isolated virtual environment: **PASS**; `rei-scientist --version` returns `0.1.0`.
- Sphere pilot: **PASS** protocol verdict, 4,440 objective evaluations; independent replay **PASS**.
- Rastrigin pilot: **PASS** protocol verdict, 7,740 objective evaluations; independent replay **PASS**.
- Corrupted report/result/dashboard artifact tests: **PASS** detection.
- Opt-in network and remote LLM integration: **NOT VERIFIED** in a live provider environment; only local mocks and guards were tested.
- Docker image build/run: **NOT VERIFIED** in this runtime.
- Cross-version numeric replay on Python 3.11 and 3.12: **NOT VERIFIED** locally; CI configurations are included.
- Security penetration test or independent external validation: **NOT VERIFIED**.

## Repeated local benchmark

A 30-run microbenchmark of the full Sphere `run_search` path (without persistence, HTTP, LLM or paper generation) produced:

| Metric | Measured elapsed time |
|---|---:|
| Runs | 30 |
| p50 | 30.58 ms |
| p95 | 31.80 ms |
| p99 | 32.04 ms |

These measurements apply only to the named synthetic problem and the execution environment above. They do not represent production throughput, model response latency, industrial workload latency, GPU utilization or cloud operating cost.

## Example Sphere experiment metrics

| Quantity | Value |
|---|---:|
| Baseline mean (5 held-out seeds) | 0.44453352 |
| Selected candidate mean (5 held-out seeds) | 0.02317467 |
| Mean relative objective reduction | 94.787% |
| Paired wins | 4 / 5 |
| Exploratory 95% paired bootstrap CI of absolute mean improvement | [0.206625539, 0.609954054] |

The synthetic experiment is not evidence of scientific novelty or performance on REI Track/Magnus Balance. Review `demo/sphere-001/manifest.json` and rerun experiments before relying on any numbers.
