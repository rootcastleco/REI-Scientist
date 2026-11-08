# REI Scientist research report: sphere-optimizer-pilot

## Integrity and disclosure

**Research status: PASS**. This is an automated exploratory engineering experiment, **not a peer-reviewed scientific publication**.
Any model-assisted configurations must be disclosed; LLM proposals used: **NO**.

## Research question

On a bounded two-dimensional Sphere benchmark, can an adaptive local search configuration reduce final objective value compared with random sampling?

**Predeclared hypothesis:** Under equal function evaluation budgets and unseen holdout seeds, best-first-tuned local search yields at least 5 percent lower mean final objective than random search.

## Protocol

- Benchmark: `sphere`, dimension: 2, bounds: (-5.0, 5.0)
- Objective: **minimize** analytic benchmark; independently recomputed at the reported solution
- Baseline: `random_search`; development seeds: [11, 23, 37]
- Holdout seeds, never used for configuration selection: [101, 103, 107, 109, 113]
- Evaluation budget: **120 per method per seed**, candidates explored: 8 / 8
- Predeclared target: **5.00%** relative improvement, positive bootstrap lower bound
- Source note: Analytic objective; no empirical sensor data; independent reproducibility study

## Development search (not confirmatory evidence)

| Configuration | Development mean objective | Parent |
|---|---:|---|
| `simulated_annealing` {'cooling': 0.97, 'step_fraction': 0.06, 'temperature': 4.0} | 0.0050613807 | `a5c721bf41ea` |
| `simulated_annealing` {'cooling': 0.97, 'step_fraction': 0.03, 'temperature': 2.0} | 0.0066908376 | `a5c721bf41ea` |
| `simulated_annealing` {'cooling': 0.97, 'step_fraction': 0.06, 'temperature': 1.0} | 0.008444487 | `a5c721bf41ea` |
| `simulated_annealing` {'cooling': 0.9409, 'step_fraction': 0.06, 'temperature': 2.0} | 0.0088045691 | `a5c721bf41ea` |
| `simulated_annealing` {'cooling': 0.97, 'step_fraction': 0.06, 'temperature': 2.0} | 0.017740499 | `d4f2cba8318f` |
| `simulated_annealing` {'cooling': 0.97, 'step_fraction': 0.12, 'temperature': 2.0} | 0.03432846 | `root` |
| `simulated_annealing` {'cooling': 0.97, 'step_fraction': 0.09, 'temperature': 2.0} | 0.036786175 | `a5c721bf41ea` |
| `hill_climb` {'step_fraction': 0.12} | 0.054988953 | `root` |
| `random_search` {} | 0.36082988 | `root` |

**Selected configuration:** `simulated_annealing` `{'cooling': 0.97, 'step_fraction': 0.06, 'temperature': 4.0}`.
Selection uses only development seeds. Holdout results are evaluated once after selection.

## Independent holdout evaluation

- Baseline mean: **0.44453352**
- Candidate mean: **0.02317467**
- Absolute mean improvement: **0.42135885**
- Relative mean improvement: **94.787%**
- Paired wins: **4/5**
- Exploratory paired bootstrap 95% CI of mean improvement: **[0.20662553907273282, 0.6099540538359]**

**Decision: PASS**. Reasons: Target met and paired-bootstrap lower bound > 0; exploratory result only.

## Independent verification

- Feasibility bounds and dimensionality checked for every recorded solution.
- Objective values recomputed using a separate reference implementation.
- Every recorded run checked against the prescribed evaluation count.
- Exact stochastic traces are fingerprinted with SHA-256 for reproducibility investigation.

## Provenance and reproducibility

- Study SHA-256: `20df0ab27eb531a60095a7f9618b3c23837dbdbb4fc1c813e573d7324c633792`
- Results SHA-256: `09f74ee38ac8870b5b2a2118111a31dd96a17914d2d2edc61b61e8be8fcb3289`
- Source snapshot SHA-256: `5dcb1362e3174e3eba0bb6cab3c9d700d669c03efa6caf08fde8fcfc538d43da`
- Python: `3.13.5`
- Total objective evaluations: 4440
- Data: Analytic, deterministic synthetic benchmarks; no customer data
- Re-run the source study JSON and compare results, ignoring elapsed time and generated timestamps.

## Related work

- No literature retrieval was executed. Related-work coverage: NOT VERIFIED.

## Limitations, risks and release gate

- Synthetic analytic benchmarks do not establish performance on real machinery, GNSS, medical, or industrial data.
- The percentile bootstrap is exploratory and cannot establish a formal generalization guarantee with a small holdout set.
- The hyperparameter search can overfit development seeds; holdout seeds are isolated but benchmark selection was not blinded.
- Some algorithms and benchmarks have different landscapes; results cannot be generalized to other objective functions.
- Literature metadata alone does not verify scientific claims. References must be checked against original papers before publication.
- Manuscript submission requires independent human review, full methods disclosure and external replication.

## Next experiment

Add a separately versioned real or synthetic domain-specific benchmark through a reviewed, approved adapter. Do not grant model-written code access to the host environment.
